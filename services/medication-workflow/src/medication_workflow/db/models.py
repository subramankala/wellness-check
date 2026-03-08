from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from shared_types import DailyMedicationLog, MedicationPlan, PatientRecord


@dataclass(frozen=True)
class PatientRecordRow:
    patient_id: str
    payload: PatientRecord
    updated_at: datetime


@dataclass(frozen=True)
class MedicationPlanRow:
    patient_id: str
    payload: MedicationPlan
    updated_at: datetime


@dataclass(frozen=True)
class DailyLogRow:
    patient_id: str
    day: str
    payload: DailyMedicationLog
    updated_at: datetime


@dataclass(frozen=True)
class RuntimeStateRow:
    state_key: str
    state_value: dict[str, str]
    updated_at: datetime
