from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from medication_workflow.db.migrations import apply_migrations
from medication_workflow.db.models import DailyLogRow, MedicationPlanRow, PatientRecordRow, RuntimeStateRow
from shared_types import DailyMedicationLog, MedicationPlan, PatientRecord


class PostgresMedicationRepository:
    def __init__(self, database_url: str, migrations_dir: Path) -> None:
        self._database_url = database_url
        self._migrations_dir = migrations_dir
        self._initialize()

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._database_url, row_factory=dict_row)

    def _initialize(self) -> None:
        with self._connect() as conn:
            apply_migrations(conn, self._migrations_dir)
            with conn.cursor() as cur:
                cur.execute("SELECT state_key FROM mw_runtime_state WHERE state_key = 'simulated_now'")
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        """
                        INSERT INTO mw_runtime_state (state_key, state_value)
                        VALUES ('simulated_now', %s::jsonb)
                        """,
                        (json.dumps({"simulated_now": datetime.now(UTC).isoformat()}),),
                    )
            conn.commit()

    def upsert_patient(self, patient: PatientRecord) -> PatientRecordRow:
        payload = patient.model_dump(mode="json")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mw_patients (patient_id, payload, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (patient_id) DO UPDATE
                    SET payload = EXCLUDED.payload, updated_at = NOW()
                    RETURNING patient_id, payload, updated_at
                    """,
                    (patient.patient_id, json.dumps(payload)),
                )
                row = cur.fetchone()
            conn.commit()
        assert row is not None
        return PatientRecordRow(
            patient_id=str(row["patient_id"]),
            payload=PatientRecord.model_validate(row["payload"]),
            updated_at=row["updated_at"],
        )

    def get_patient(self, patient_id: str) -> PatientRecordRow | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT patient_id, payload, updated_at FROM mw_patients WHERE patient_id = %s",
                    (patient_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return PatientRecordRow(
            patient_id=str(row["patient_id"]),
            payload=PatientRecord.model_validate(row["payload"]),
            updated_at=row["updated_at"],
        )

    def list_patients(self) -> list[PatientRecordRow]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT patient_id, payload, updated_at FROM mw_patients ORDER BY patient_id")
                rows = cur.fetchall()
        return [
            PatientRecordRow(
                patient_id=str(row["patient_id"]),
                payload=PatientRecord.model_validate(row["payload"]),
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def upsert_plan(self, plan: MedicationPlan) -> MedicationPlanRow:
        payload = plan.model_dump(mode="json")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mw_plans (patient_id, payload, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (patient_id) DO UPDATE
                    SET payload = EXCLUDED.payload, updated_at = NOW()
                    RETURNING patient_id, payload, updated_at
                    """,
                    (plan.patient_id, json.dumps(payload)),
                )
                row = cur.fetchone()
            conn.commit()
        assert row is not None
        return MedicationPlanRow(
            patient_id=str(row["patient_id"]),
            payload=MedicationPlan.model_validate(row["payload"]),
            updated_at=row["updated_at"],
        )

    def get_plan(self, patient_id: str) -> MedicationPlanRow | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT patient_id, payload, updated_at FROM mw_plans WHERE patient_id = %s",
                    (patient_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return MedicationPlanRow(
            patient_id=str(row["patient_id"]),
            payload=MedicationPlan.model_validate(row["payload"]),
            updated_at=row["updated_at"],
        )

    def upsert_log(self, log: DailyMedicationLog) -> DailyLogRow:
        payload = log.model_dump(mode="json")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mw_daily_logs (patient_id, day, payload, updated_at)
                    VALUES (%s, %s, %s::jsonb, NOW())
                    ON CONFLICT (patient_id, day) DO UPDATE
                    SET payload = EXCLUDED.payload, updated_at = NOW()
                    RETURNING patient_id, day, payload, updated_at
                    """,
                    (log.patient_id, log.date, json.dumps(payload)),
                )
                row = cur.fetchone()
            conn.commit()
        assert row is not None
        return DailyLogRow(
            patient_id=str(row["patient_id"]),
            day=str(row["day"]),
            payload=DailyMedicationLog.model_validate(row["payload"]),
            updated_at=row["updated_at"],
        )

    def get_log(self, patient_id: str, day: str) -> DailyLogRow | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT patient_id, day, payload, updated_at FROM mw_daily_logs WHERE patient_id = %s AND day = %s",
                    (patient_id, day),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return DailyLogRow(
            patient_id=str(row["patient_id"]),
            day=str(row["day"]),
            payload=DailyMedicationLog.model_validate(row["payload"]),
            updated_at=row["updated_at"],
        )

    def list_logs_for_patient(self, patient_id: str) -> list[DailyLogRow]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT patient_id, day, payload, updated_at FROM mw_daily_logs WHERE patient_id = %s ORDER BY day",
                    (patient_id,),
                )
                rows = cur.fetchall()
        return [
            DailyLogRow(
                patient_id=str(row["patient_id"]),
                day=str(row["day"]),
                payload=DailyMedicationLog.model_validate(row["payload"]),
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def get_runtime_state(self, state_key: str) -> RuntimeStateRow | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT state_key, state_value, updated_at FROM mw_runtime_state WHERE state_key = %s",
                    (state_key,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return RuntimeStateRow(
            state_key=str(row["state_key"]),
            state_value=dict(row["state_value"]),
            updated_at=row["updated_at"],
        )

    def upsert_runtime_state(self, state_key: str, state_value: dict[str, str]) -> RuntimeStateRow:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mw_runtime_state (state_key, state_value, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (state_key) DO UPDATE
                    SET state_value = EXCLUDED.state_value, updated_at = NOW()
                    RETURNING state_key, state_value, updated_at
                    """,
                    (state_key, json.dumps(state_value)),
                )
                row = cur.fetchone()
            conn.commit()
        assert row is not None
        return RuntimeStateRow(
            state_key=str(row["state_key"]),
            state_value=dict(row["state_value"]),
            updated_at=row["updated_at"],
        )
