from __future__ import annotations

import os
from datetime import UTC, datetime

import psycopg
import pytest

from medication_workflow.store import PostgresMedicationWorkflowStore
from shared_types import (
    AuditEvent,
    CareActivity,
    CareActivityCategory,
    CareActivityConfirmation,
    CareActivityConfirmationStatus,
    ChannelType,
    DeliveryStatus,
    DoseConfirmation,
    DoseStatus,
    MealConstraintType,
    MedicationMessageRecord,
    MedicationPlan,
    MedicationScheduleEntry,
    MedicationWorkflowStatus,
    MessageKind,
    PatientRecord,
    RecipientRole,
    ReviewActionType,
)


def _database_url() -> str | None:
    return os.getenv("MEDICATION_WORKFLOW_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")


@pytest.mark.skipif(_database_url() is None, reason="postgres test database url not configured")
def test_postgres_persistence_survives_store_restart() -> None:
    database_url = _database_url()
    assert database_url is not None

    # Clean tables for deterministic restart test.
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE mw_daily_logs, mw_plans, mw_patients, mw_runtime_state RESTART IDENTITY")
            cur.execute(
                "INSERT INTO mw_runtime_state (state_key, state_value) VALUES ('simulated_now', %s::jsonb)",
                ('{"simulated_now":"2026-03-07T00:00:00+00:00"}',),
            )
        conn.commit()

    store_a = PostgresMedicationWorkflowStore(database_url)

    patient = PatientRecord(
        patient_id="persist_patient_1",
        display_name="Persist Test",
        timezone="Asia/Kolkata",
        patient_contact="+919999111111",
        caregiver_name="Caregiver",
        caregiver_contact="+919999111112",
        created_at="2026-03-07T08:00:00+05:30",
        notes="persistence test",
    )
    store_a.put_patient(patient)

    plan = MedicationPlan(
        patient_id=patient.patient_id,
        plan_id="plan_persist_1",
        workflow_status=MedicationWorkflowStatus.ACTIVE,
        timezone="Asia/Kolkata",
        created_at="2026-03-07T08:00:00+05:30",
        medications=[
            MedicationScheduleEntry(
                entry_id="med_1",
                display_name="Med1",
                generic_name="g1",
                medication_name="MED1",
                dose_instructions="1 tablet after food",
                scheduled_time="08:00",
                meal_constraint=MealConstraintType.AFTER_MEAL,
                priority="critical",
                missed_dose_policy="notify",
            )
        ],
        care_activities=[
            CareActivity(
                activity_id="breakfast_0800",
                title="Breakfast",
                category=CareActivityCategory.MEAL,
                schedule="08:00",
                duration_minutes=20,
                instruction="Have breakfast",
                frequency="daily",
                priority="important",
                confirmation_required=True,
                escalation_policy="follow up",
            )
        ],
    )
    store_a.put_plan(plan)

    log = store_a.get_log(patient.patient_id, "2026-03-07")
    log.confirmations.append(
        DoseConfirmation(
            patient_id=patient.patient_id,
            reminder_id="rem_1",
            schedule_entry_id="med_1",
            dose_status=DoseStatus.TAKEN,
            confirmed_at="2026-03-07T08:05:00+05:30",
            meal_condition_satisfied=True,
            note="taken",
        )
    )
    log.care_activity_confirmations.append(
        CareActivityConfirmation(
            patient_id=patient.patient_id,
            instance_id="care_1",
            activity_id="breakfast_0800",
            confirmation_status=CareActivityConfirmationStatus.DONE,
            confirmed_at="2026-03-07T08:02:00+05:30",
            note="done",
        )
    )
    log.messages.append(
        MedicationMessageRecord(
            message_id="msg_1",
            patient_id=patient.patient_id,
            date="2026-03-07",
            window_id="window_0800",
            window_slot_time="08:00",
            recipient_role=RecipientRole.PATIENT,
            channel_type=ChannelType.WHATSAPP,
            message_kind=MessageKind.DUE_REMINDER,
            content="Reminder",
            delivery_status=DeliveryStatus.DELIVERED,
            created_at="2026-03-07T07:55:00+05:30",
            dedupe_key="dedupe_1",
            metadata={"source": "test"},
        )
    )
    log.audit_events.append(
        AuditEvent(
            event_id="evt_1",
            event_type=ReviewActionType.MEDICATION_DOSE_CONFIRMED,
            timestamp="2026-03-07T08:05:00+05:30",
            actor_id="test",
            actor_name="test",
            message="confirmed",
            metadata={"k": "v"},
        )
    )
    store_a.put_log(log)
    store_a.set_simulated_now(datetime(2026, 3, 7, 3, 0, tzinfo=UTC))

    # Simulate restart by creating a new store instance.
    store_b = PostgresMedicationWorkflowStore(database_url)

    loaded_patient = store_b.get_patient(patient.patient_id)
    assert loaded_patient is not None
    assert loaded_patient.display_name == "Persist Test"

    loaded_plan = store_b.get_plan(patient.patient_id)
    assert loaded_plan is not None
    assert len(loaded_plan.medications) == 1
    assert len(loaded_plan.care_activities) == 1

    loaded_log = store_b.get_log(patient.patient_id, "2026-03-07")
    assert len(loaded_log.confirmations) == 1
    assert len(loaded_log.care_activity_confirmations) == 1
    assert len(loaded_log.messages) == 1
    assert len(loaded_log.audit_events) == 1

    simulated = store_b.get_simulated_state()
    assert simulated.simulated_now.startswith("2026-03-07T03:00:00")
