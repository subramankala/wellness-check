from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="careos-mcp")


def _careos_base_url() -> str:
    return os.getenv("CAREOS_BASE_URL", "http://localhost:8105").rstrip("/")


def _mcp_api_key() -> str:
    return os.getenv("CAREOS_MCP_API_KEY", "").strip()


def _allowed_write_roles() -> set[str]:
    raw = os.getenv("CAREOS_MCP_ALLOWED_WRITE_ROLES", "doctor,clinician,caregiver")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | list[Any]:
    body = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, method=method, data=body, headers=headers)
    with urlopen(request) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _normalize_time(value: str) -> str:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", value.strip())
    if not match:
        raise HTTPException(status_code=400, detail=f"invalid scheduled_time '{value}', expected HH:MM")
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise HTTPException(status_code=400, detail=f"invalid scheduled_time '{value}', expected 00:00-23:59")
    return f"{hour:02d}:{minute:02d}"


def _entry_id_slug(name: str, scheduled_time: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"{base}_{scheduled_time.replace(':', '')}"


def _require_write_role(arguments: dict[str, Any]) -> None:
    actor_id = str(arguments.get("actor_id", "")).strip()
    actor_role = str(arguments.get("actor_role", "")).strip().lower()
    reason = str(arguments.get("reason", "")).strip()
    if not actor_id:
        raise HTTPException(status_code=400, detail="actor_id is required for write tools")
    if actor_role not in _allowed_write_roles():
        raise HTTPException(status_code=403, detail=f"actor_role '{actor_role}' not allowed for write tools")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required for write tools")


def _plan_export(patient_id: str) -> dict[str, Any]:
    payload = _request_json(f"{_careos_base_url()}/medication/plan/{patient_id}/export")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="unexpected response from careos plan export")
    return payload


def _import_plan(export_payload: dict[str, Any]) -> dict[str, Any]:
    result = _request_json(
        f"{_careos_base_url()}/medication/plan/import",
        method="POST",
        payload=export_payload,
    )
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="unexpected response from careos plan import")
    return result


@dataclass(frozen=True)
class ToolSpec:
    name: str
    write: bool
    description: str


TOOLS: list[ToolSpec] = [
    ToolSpec("careos_get_today", False, "Get CareOS today view for a patient."),
    ToolSpec("careos_get_timeline", False, "Get timeline for date."),
    ToolSpec("careos_get_notifications", False, "Get caregiver notifications for date."),
    ToolSpec("careos_get_messages", False, "Get message records for date."),
    ToolSpec("careos_get_plan_export", False, "Get full patient+plan export."),
    ToolSpec("careos_import_plan", True, "Replace patient+plan from provided payload."),
    ToolSpec("careos_upsert_medication", True, "Create or update medication in plan."),
    ToolSpec("careos_delete_medication", True, "Delete medication from plan by entry_id or name/time."),
    ToolSpec("careos_upsert_activity", True, "Create or update care activity in plan."),
    ToolSpec("careos_delete_activity", True, "Delete care activity from plan."),
    ToolSpec("careos_timeline_action", True, "Complete/skip/delay timeline item."),
]


class ToolCallRequest(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    ok: bool
    tool: str
    result: dict[str, Any] | list[Any] | None = None
    error: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "careos-mcp", "status": "ok"}


@app.get("/mcp/tools")
def list_tools(x_mcp_api_key: str = Header(default="")) -> dict[str, Any]:
    if _mcp_api_key() and x_mcp_api_key != _mcp_api_key():
        raise HTTPException(status_code=401, detail="invalid mcp api key")
    return {
        "tools": [
            {"name": tool.name, "write": tool.write, "description": tool.description}
            for tool in TOOLS
        ]
    }


def _call_read_tool(tool: str, args: dict[str, Any]) -> dict[str, Any] | list[Any]:
    patient_id = str(args.get("patient_id", "")).strip()
    if not patient_id:
        raise HTTPException(status_code=400, detail="patient_id is required")
    today_str = str(args.get("date", date.today().isoformat()))

    if tool == "careos_get_today":
        return _request_json(f"{_careos_base_url()}/careos/{patient_id}/today")
    if tool == "careos_get_timeline":
        return _request_json(f"{_careos_base_url()}/careos/{patient_id}/timeline?{urlencode({'date': today_str})}")
    if tool == "careos_get_notifications":
        return _request_json(f"{_careos_base_url()}/medication/{patient_id}/notifications?{urlencode({'date': today_str})}")
    if tool == "careos_get_messages":
        return _request_json(f"{_careos_base_url()}/medication/{patient_id}/messages?{urlencode({'date': today_str})}")
    if tool == "careos_get_plan_export":
        return _plan_export(patient_id)
    raise HTTPException(status_code=404, detail=f"unknown tool '{tool}'")


def _upsert_medication(args: dict[str, Any]) -> dict[str, Any]:
    patient_id = str(args.get("patient_id", "")).strip()
    medication_name = str(args.get("medication_name", "")).strip()
    dose_instructions = str(args.get("dose_instructions", "")).strip()
    scheduled_time = _normalize_time(str(args.get("scheduled_time", "")).strip())
    if not patient_id or not medication_name or not dose_instructions:
        raise HTTPException(status_code=400, detail="patient_id, medication_name, dose_instructions required")

    export_payload = _plan_export(patient_id)
    plan = export_payload["plan"]
    medications: list[dict[str, Any]] = list(plan.get("medications", []))
    entry_id = str(args.get("entry_id", "")).strip() or _entry_id_slug(medication_name, scheduled_time)

    meal_constraint = str(args.get("meal_constraint", "none")).strip() or "none"
    priority = str(args.get("priority", "routine")).strip() or "routine"
    criticality_level = str(args.get("criticality_level", priority)).strip() or priority
    monitoring_notes = str(args.get("monitoring_notes", "")).strip()
    side_effect_watch_items = args.get("side_effect_watch_items", [])
    if not isinstance(side_effect_watch_items, list):
        raise HTTPException(status_code=400, detail="side_effect_watch_items must be list")

    new_entry = {
        "entry_id": entry_id,
        "display_name": str(args.get("display_name", medication_name)).strip() or medication_name,
        "generic_name": args.get("generic_name"),
        "medication_name": medication_name,
        "dose_instructions": dose_instructions,
        "scheduled_time": scheduled_time,
        "meal_constraint": meal_constraint,
        "priority": priority,
        "criticality_level": criticality_level,
        "monitoring_notes": monitoring_notes,
        "missed_dose_policy": str(args.get("missed_dose_policy", "log and notify caregiver")).strip(),
        "side_effect_watch_items": side_effect_watch_items,
    }

    replaced = False
    for index, entry in enumerate(medications):
        if entry.get("entry_id") == entry_id:
            medications[index] = new_entry
            replaced = True
            break
    if not replaced:
        medications.append(new_entry)
    plan["medications"] = medications
    export_payload["plan"] = plan
    return _import_plan(export_payload)


def _delete_medication(args: dict[str, Any]) -> dict[str, Any]:
    patient_id = str(args.get("patient_id", "")).strip()
    entry_id = str(args.get("entry_id", "")).strip()
    medication_name = str(args.get("medication_name", "")).strip()
    scheduled_time = str(args.get("scheduled_time", "")).strip()
    if not patient_id:
        raise HTTPException(status_code=400, detail="patient_id is required")
    if not entry_id and not (medication_name and scheduled_time):
        raise HTTPException(status_code=400, detail="entry_id or medication_name+scheduled_time required")

    export_payload = _plan_export(patient_id)
    plan = export_payload["plan"]
    medications: list[dict[str, Any]] = list(plan.get("medications", []))
    if not entry_id:
        scheduled_time = _normalize_time(scheduled_time)
        target = next(
            (
                entry.get("entry_id", "")
                for entry in medications
                if str(entry.get("medication_name", "")).lower() == medication_name.lower()
                and str(entry.get("scheduled_time", "")) == scheduled_time
            ),
            "",
        )
        entry_id = target
    if not entry_id:
        raise HTTPException(status_code=404, detail="medication entry not found")
    filtered = [entry for entry in medications if entry.get("entry_id") != entry_id]
    plan["medications"] = filtered
    export_payload["plan"] = plan
    return _import_plan(export_payload)


def _upsert_activity(args: dict[str, Any]) -> dict[str, Any]:
    patient_id = str(args.get("patient_id", "")).strip()
    activity_id = str(args.get("activity_id", "")).strip()
    title = str(args.get("title", "")).strip()
    schedule = _normalize_time(str(args.get("schedule", "")).strip())
    if not patient_id or not activity_id or not title:
        raise HTTPException(status_code=400, detail="patient_id, activity_id, title required")

    export_payload = _plan_export(patient_id)
    plan = export_payload["plan"]
    activities: list[dict[str, Any]] = list(plan.get("care_activities", []))
    activity = {
        "activity_id": activity_id,
        "title": title,
        "category": str(args.get("category", "activity")),
        "schedule": schedule,
        "duration_minutes": args.get("duration_minutes"),
        "instruction": str(args.get("instruction", title)),
        "frequency": str(args.get("frequency", "daily")),
        "priority": str(args.get("priority", "routine")),
        "confirmation_required": bool(args.get("confirmation_required", True)),
        "escalation_policy": args.get("escalation_policy"),
    }
    replaced = False
    for index, existing in enumerate(activities):
        if existing.get("activity_id") == activity_id:
            activities[index] = activity
            replaced = True
            break
    if not replaced:
        activities.append(activity)
    plan["care_activities"] = activities
    export_payload["plan"] = plan
    return _import_plan(export_payload)


def _delete_activity(args: dict[str, Any]) -> dict[str, Any]:
    patient_id = str(args.get("patient_id", "")).strip()
    activity_id = str(args.get("activity_id", "")).strip()
    if not patient_id or not activity_id:
        raise HTTPException(status_code=400, detail="patient_id and activity_id are required")
    export_payload = _plan_export(patient_id)
    plan = export_payload["plan"]
    activities: list[dict[str, Any]] = list(plan.get("care_activities", []))
    plan["care_activities"] = [entry for entry in activities if entry.get("activity_id") != activity_id]
    export_payload["plan"] = plan
    return _import_plan(export_payload)


def _timeline_action(args: dict[str, Any]) -> dict[str, Any]:
    patient_id = str(args.get("patient_id", "")).strip()
    item_id = str(args.get("item_id", "")).strip()
    action = str(args.get("action", "")).strip().lower()
    if not patient_id or not item_id or action not in {"complete", "skip", "delay"}:
        raise HTTPException(status_code=400, detail="patient_id, item_id, valid action required")

    reason = str(args.get("reason", "mcp_tool_action")).strip() or "mcp_tool_action"
    base_payload: dict[str, Any] = {
        "reason": reason,
        "actor_id": str(args.get("actor_id", "")),
        "actor_name": str(args.get("actor_name", args.get("actor_role", "mcp"))),
        "allow_high_risk_medication_edit": bool(args.get("allow_high_risk_medication_edit", False)),
    }
    if action == "delay":
        base_payload["minutes"] = int(args.get("minutes", 15))
    endpoint = f"/careos/{patient_id}/timeline/{item_id}/{action}"
    return _request_json(f"{_careos_base_url()}{endpoint}", method="POST", payload=base_payload)


def _call_write_tool(tool: str, args: dict[str, Any]) -> dict[str, Any] | list[Any]:
    _require_write_role(args)
    if tool == "careos_import_plan":
        payload = args.get("payload")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="payload object is required")
        return _import_plan(payload)
    if tool == "careos_upsert_medication":
        return _upsert_medication(args)
    if tool == "careos_delete_medication":
        return _delete_medication(args)
    if tool == "careos_upsert_activity":
        return _upsert_activity(args)
    if tool == "careos_delete_activity":
        return _delete_activity(args)
    if tool == "careos_timeline_action":
        return _timeline_action(args)
    raise HTTPException(status_code=404, detail=f"unknown tool '{tool}'")


@app.post("/mcp/call", response_model=ToolCallResponse)
def call_tool(payload: ToolCallRequest, x_mcp_api_key: str = Header(default="")) -> ToolCallResponse:
    if _mcp_api_key() and x_mcp_api_key != _mcp_api_key():
        raise HTTPException(status_code=401, detail="invalid mcp api key")
    tool = payload.tool
    spec = next((entry for entry in TOOLS if entry.name == tool), None)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"unknown tool '{tool}'")
    if spec.write:
        result = _call_write_tool(tool, payload.arguments)
    else:
        result = _call_read_tool(tool, payload.arguments)
    return ToolCallResponse(ok=True, tool=tool, result=result)

