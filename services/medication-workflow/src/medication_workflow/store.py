from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock

from medication_workflow.db.repository import PostgresMedicationRepository
from shared_types import (
    AuditEvent,
    DailyMedicationLog,
    MedicationPlan,
    PatientRecord,
    ReviewActionType,
    SimulatedTimeState,
)


class MedicationWorkflowStore:
    def __init__(self) -> None:
        self._patients: dict[str, PatientRecord] = {}
        self._plans: dict[str, MedicationPlan] = {}
        self._logs: dict[tuple[str, str], DailyMedicationLog] = {}
        self._simulated_now = datetime.now(UTC)
        self._lock = Lock()

    def put_patient(self, patient: PatientRecord) -> PatientRecord:
        with self._lock:
            self._patients[patient.patient_id] = patient
            return patient

    def get_patient(self, patient_id: str) -> PatientRecord | None:
        with self._lock:
            return self._patients.get(patient_id)

    def list_patients(self) -> list[PatientRecord]:
        with self._lock:
            return list(self._patients.values())

    def put_plan(self, plan: MedicationPlan) -> MedicationPlan:
        with self._lock:
            self._plans[plan.patient_id] = plan
            return plan

    def get_plan(self, patient_id: str) -> MedicationPlan | None:
        with self._lock:
            return self._plans.get(patient_id)

    def get_log(self, patient_id: str, date: str) -> DailyMedicationLog:
        with self._lock:
            key = (patient_id, date)
            if key not in self._logs:
                self._logs[key] = DailyMedicationLog(patient_id=patient_id, date=date)
            return self._logs[key]

    def put_log(self, log: DailyMedicationLog) -> DailyMedicationLog:
        with self._lock:
            self._logs[(log.patient_id, log.date)] = log
            return log

    def list_logs_for_patient(self, patient_id: str) -> list[DailyMedicationLog]:
        with self._lock:
            return [log for (pid, _), log in self._logs.items() if pid == patient_id]

    def now(self) -> datetime:
        with self._lock:
            return self._simulated_now

    def set_simulated_now(self, value: datetime) -> SimulatedTimeState:
        with self._lock:
            self._simulated_now = value.astimezone(UTC)
            return SimulatedTimeState(simulated_now=self._simulated_now.isoformat(), timezone="UTC")

    def advance_simulated_now(self, *, minutes: int, hours: int) -> SimulatedTimeState:
        with self._lock:
            self._simulated_now = self._simulated_now + timedelta(minutes=minutes, hours=hours)
            return SimulatedTimeState(simulated_now=self._simulated_now.isoformat(), timezone="UTC")

    def reset_simulated_to_day_start(self) -> SimulatedTimeState:
        with self._lock:
            self._simulated_now = self._simulated_now.replace(hour=0, minute=0, second=0, microsecond=0)
            return SimulatedTimeState(simulated_now=self._simulated_now.isoformat(), timezone="UTC")

    def get_simulated_state(self) -> SimulatedTimeState:
        with self._lock:
            return SimulatedTimeState(simulated_now=self._simulated_now.isoformat(), timezone="UTC")

    def append_event(
        self,
        patient_id: str,
        date: str,
        event_type: ReviewActionType,
        message: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        log = self.get_log(patient_id, date)
        log.audit_events.append(
            AuditEvent(
                event_id=f"evt_{datetime.now(UTC).timestamp()}_{len(log.audit_events) + 1}",
                event_type=event_type,
                timestamp=datetime.now(UTC).isoformat(),
                actor_id="system",
                actor_name="medication-workflow",
                message=message,
                metadata=metadata or {},
            )
        )


class PostgresMedicationWorkflowStore:
    def __init__(self, database_url: str) -> None:
        migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
        self._repo = PostgresMedicationRepository(database_url=database_url, migrations_dir=migrations_dir)
        self._lock = Lock()

    def put_patient(self, patient: PatientRecord) -> PatientRecord:
        return self._repo.upsert_patient(patient).payload

    def get_patient(self, patient_id: str) -> PatientRecord | None:
        row = self._repo.get_patient(patient_id)
        return row.payload if row is not None else None

    def list_patients(self) -> list[PatientRecord]:
        return [row.payload for row in self._repo.list_patients()]

    def put_plan(self, plan: MedicationPlan) -> MedicationPlan:
        return self._repo.upsert_plan(plan).payload

    def get_plan(self, patient_id: str) -> MedicationPlan | None:
        row = self._repo.get_plan(patient_id)
        return row.payload if row is not None else None

    def get_log(self, patient_id: str, date: str) -> DailyMedicationLog:
        row = self._repo.get_log(patient_id, date)
        if row is not None:
            return row.payload
        created = DailyMedicationLog(patient_id=patient_id, date=date)
        return self._repo.upsert_log(created).payload

    def put_log(self, log: DailyMedicationLog) -> DailyMedicationLog:
        return self._repo.upsert_log(log).payload

    def list_logs_for_patient(self, patient_id: str) -> list[DailyMedicationLog]:
        return [row.payload for row in self._repo.list_logs_for_patient(patient_id)]

    def now(self) -> datetime:
        row = self._repo.get_runtime_state("simulated_now")
        if row is None:
            fallback = datetime.now(UTC)
            self._repo.upsert_runtime_state("simulated_now", {"simulated_now": fallback.isoformat()})
            return fallback
        return datetime.fromisoformat(str(row.state_value["simulated_now"]))

    def set_simulated_now(self, value: datetime) -> SimulatedTimeState:
        simulated = value.astimezone(UTC)
        row = self._repo.upsert_runtime_state("simulated_now", {"simulated_now": simulated.isoformat()})
        return SimulatedTimeState(simulated_now=row.state_value["simulated_now"], timezone="UTC")

    def advance_simulated_now(self, *, minutes: int, hours: int) -> SimulatedTimeState:
        current = self.now()
        return self.set_simulated_now(current + timedelta(minutes=minutes, hours=hours))

    def reset_simulated_to_day_start(self) -> SimulatedTimeState:
        current = self.now()
        return self.set_simulated_now(current.replace(hour=0, minute=0, second=0, microsecond=0))

    def get_simulated_state(self) -> SimulatedTimeState:
        current = self.now()
        return SimulatedTimeState(simulated_now=current.isoformat(), timezone="UTC")

    def append_event(
        self,
        patient_id: str,
        date: str,
        event_type: ReviewActionType,
        message: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        with self._lock:
            log = self.get_log(patient_id, date)
            log.audit_events.append(
                AuditEvent(
                    event_id=f"evt_{datetime.now(UTC).timestamp()}_{len(log.audit_events) + 1}",
                    event_type=event_type,
                    timestamp=datetime.now(UTC).isoformat(),
                    actor_id="system",
                    actor_name="medication-workflow",
                    message=message,
                    metadata=metadata or {},
                )
            )
            self.put_log(log)
