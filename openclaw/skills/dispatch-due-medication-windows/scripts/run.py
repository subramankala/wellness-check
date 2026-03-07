from __future__ import annotations

import json
import os
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


def run(base_url: str, patient_id: str) -> dict[str, Any]:
    due_now = _request_json(f"{base_url}/medication/{patient_id}/due-now")
    sent = _request_json(f"{base_url}/medication/{patient_id}/send-due-reminders", method="POST")
    return {
        "skill": "dispatch-due-medication-windows",
        "patient_id": patient_id,
        "local_now": sent["local_now"],
        "due_windows_count": len(due_now.get("due_now", [])),
        "sent_count": len(sent.get("sent_messages", [])),
        "sent_messages": sent.get("sent_messages", []),
    }


if __name__ == "__main__":
    base_url = os.getenv("MEDICATION_BASE_URL", "http://localhost:8105")
    patient_id = os.getenv("PATIENT_ID", "")
    if not patient_id:
        raise SystemExit("PATIENT_ID is required")
    print(json.dumps(run(base_url, patient_id), indent=2))
