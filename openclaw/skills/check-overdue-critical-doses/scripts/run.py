from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any


def _request_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(request) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def run(base_url: str, patient_id: str, cooldown_minutes: int) -> dict[str, Any]:
    today = _request_json(f"{base_url}/medication/{patient_id}/today")
    followup_url = (
        f"{base_url}/medication/{patient_id}/send-overdue-critical-followups?"
        f"{urllib.parse.urlencode({'cooldown_minutes': cooldown_minutes})}"
    )
    followup = _request_json(followup_url, method="POST")
    return {
        "skill": "check-overdue-critical-doses",
        "patient_id": patient_id,
        "local_now": followup["local_now"],
        "overdue_windows": [
            window["window_id"]
            for window in today.get("administration_windows", [])
            if window.get("window_status") == "overdue" and window.get("window_risk_level") == "high"
        ],
        "sent_count": len(followup.get("sent_messages", [])),
        "sent_messages": followup.get("sent_messages", []),
    }


if __name__ == "__main__":
    base_url = os.getenv("MEDICATION_BASE_URL", "http://localhost:8105")
    patient_id = os.getenv("PATIENT_ID", "")
    cooldown_minutes = int(os.getenv("FOLLOWUP_COOLDOWN_MINUTES", "60"))
    if not patient_id:
        raise SystemExit("PATIENT_ID is required")
    print(json.dumps(run(base_url, patient_id, cooldown_minutes), indent=2))
