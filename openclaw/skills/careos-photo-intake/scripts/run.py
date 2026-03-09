from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedMedication:
    medication_name: str
    dose_instructions: str
    scheduled_time: str
    meal_constraint: str
    priority: str


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _extract_time(text: str) -> str:
    # Supports "9 PM", "09:30 PM", "21:00".
    text = text.strip()
    ampm = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(AM|PM)\b", text, flags=re.IGNORECASE)
    if ampm:
        hour = int(ampm.group(1))
        minute = int(ampm.group(2) or "00")
        marker = ampm.group(3).upper()
        if marker == "PM" and hour != 12:
            hour += 12
        if marker == "AM" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"
    hhmm = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if hhmm:
        return f"{int(hhmm.group(1)):02d}:{int(hhmm.group(2)):02d}"
    raise ValueError("Could not parse scheduled time from PHOTO_TEXT")


def _extract_meal_rule(text: str) -> str:
    lowered = text.lower()
    if "before food" in lowered or "before meal" in lowered:
        return "before_meal"
    if "after food" in lowered or "after meal" in lowered:
        return "after_meal"
    if "with food" in lowered:
        return "with_food"
    if "empty stomach" in lowered:
        return "empty_stomach"
    return "none"


def _extract_med_name(text: str) -> str:
    cleaned = _normalize_spaces(text)
    # Prefer all-caps token run first.
    uppercase = re.search(r"\b([A-Z][A-Z0-9\-\+ ]{2,})\b", cleaned)
    if uppercase:
        return uppercase.group(1).strip()
    # Fallback: first phrase before dosage/time keywords.
    fallback = re.split(r"\b(\d+\s*(mg|ml|tab|tablet)|at\b|before\b|after\b|with\b)", cleaned, flags=re.IGNORECASE)[0]
    fallback = _normalize_spaces(fallback)
    if not fallback:
        raise ValueError("Could not parse medication name from PHOTO_TEXT")
    return fallback.upper()


def _extract_dose_instruction(text: str, meal_constraint: str) -> str:
    lowered = text.lower()
    dose = re.search(r"\b(\d+(?:\.\d+)?)\s*(mg|ml|tab|tablet)\b", lowered)
    count = re.search(r"\b(\d+\/\d+|\d+)\s*(tablet|tab)\b", lowered)
    if count:
        base = f"{count.group(1)} tablet"
    elif dose:
        base = f"{dose.group(1)} {dose.group(2)}"
    else:
        base = "1 tablet"
    suffix = {
        "before_meal": "before food",
        "after_meal": "after food",
        "with_food": "with food",
        "empty_stomach": "on empty stomach",
        "none": "",
    }[meal_constraint]
    return _normalize_spaces(f"{base} {suffix}")


def parse_photo_text(text: str) -> ParsedMedication:
    meal_constraint = _extract_meal_rule(text)
    scheduled_time = _extract_time(text)
    medication_name = _extract_med_name(text)
    dose_instructions = _extract_dose_instruction(text, meal_constraint)
    priority = "critical" if any(token in medication_name.lower() for token in {"brilinta", "cardivas", "ecosprin"}) else "important"
    return ParsedMedication(
        medication_name=medication_name,
        dose_instructions=dose_instructions,
        scheduled_time=scheduled_time,
        meal_constraint=meal_constraint,
        priority=priority,
    )


def _call_mcp(base_url: str, api_key: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps({"tool": tool, "arguments": arguments}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/mcp/call",
        method="POST",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-mcp-api-key": api_key,
        },
    )
    with urllib.request.urlopen(request) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def run() -> dict[str, Any]:
    base_url = os.getenv("MCP_BASE_URL", "http://localhost:8110")
    api_key = os.getenv("MCP_API_KEY", "")
    patient_id = os.getenv("PATIENT_ID", "")
    action = os.getenv("ACTION", "preview").strip().lower()
    photo_text = os.getenv("PHOTO_TEXT", "")
    actor_id = os.getenv("ACTOR_ID", "openclaw_user")
    actor_role = os.getenv("ACTOR_ROLE", "doctor")
    reason = os.getenv("REASON", "photo_intake_update")

    if not api_key:
        raise SystemExit("MCP_API_KEY is required")
    if not patient_id:
        raise SystemExit("PATIENT_ID is required")

    if action == "get_today":
        return _call_mcp(base_url, api_key, "careos_get_today", {"patient_id": patient_id})

    if action in {"preview", "upsert_medication", "delete_medication"}:
        if not photo_text.strip():
            raise SystemExit("PHOTO_TEXT is required for preview/upsert/delete")
        parsed = parse_photo_text(photo_text)
        parsed_payload = {
            "patient_id": patient_id,
            "medication_name": parsed.medication_name,
            "dose_instructions": parsed.dose_instructions,
            "scheduled_time": parsed.scheduled_time,
            "meal_constraint": parsed.meal_constraint,
            "priority": parsed.priority,
        }
        if action == "preview":
            return {"ok": True, "action": "preview", "parsed": parsed_payload}
        if action == "upsert_medication":
            args = {
                **parsed_payload,
                "actor_id": actor_id,
                "actor_role": actor_role,
                "reason": reason,
                "monitoring_notes": "updated from photo intake",
                "side_effect_watch_items": [],
            }
            return _call_mcp(base_url, api_key, "careos_upsert_medication", args)
        args = {
            "patient_id": patient_id,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "reason": reason,
            "medication_name": parsed.medication_name,
            "scheduled_time": parsed.scheduled_time,
        }
        return _call_mcp(base_url, api_key, "careos_delete_medication", args)

    raise SystemExit(f"Unsupported ACTION '{action}'")


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))

