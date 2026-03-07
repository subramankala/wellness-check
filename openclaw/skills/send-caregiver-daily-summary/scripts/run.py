from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any


def _request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def build_digest(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "patient_id": summary["patient_id"],
        "date": summary["date"],
        "patient_timezone": summary.get("patient_timezone", "UTC"),
        "local_now": summary.get("local_now", ""),
        "progress": {
            "doses_due_so_far": summary.get("doses_due_so_far", 0),
            "doses_completed_so_far": summary.get("doses_completed_so_far", 0),
            "overdue_so_far": summary.get("overdue_so_far", 0),
            "current_progress_rate": summary.get("current_progress_rate"),
            "final_day_adherence_rate": summary.get("final_day_adherence_rate"),
        },
        "alerts_count": len(summary.get("active_alerts", [])),
        "recommended_actions": summary.get("recommended_actions", []),
        "summary_text": summary.get("summary_text", ""),
    }


def run(base_url: str, patient_id: str, summary_date: str, output_path: str | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode({"date": summary_date})
    summary = _request_json(f"{base_url}/medication/{patient_id}/daily-summary?{query}")
    digest = build_digest(summary)

    destination = Path(output_path or f"openclaw/output/caregiver-summary-{patient_id}-{summary_date}.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(digest, indent=2), encoding="utf-8")

    return {
        "skill": "send-caregiver-daily-summary",
        "output_path": str(destination),
        "digest": digest,
    }


if __name__ == "__main__":
    base_url = os.getenv("MEDICATION_BASE_URL", "http://localhost:8105")
    patient_id = os.getenv("PATIENT_ID", "")
    summary_date = os.getenv("SUMMARY_DATE", date.today().isoformat())
    output_path = os.getenv("OUTPUT_PATH")
    if not patient_id:
        raise SystemExit("PATIENT_ID is required")
    print(json.dumps(run(base_url, patient_id, summary_date, output_path), indent=2))
