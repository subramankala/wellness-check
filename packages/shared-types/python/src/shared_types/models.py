from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Disposition(StrEnum):
    SELF_CARE = "self_care"
    CLINIC_FOLLOWUP = "clinic_followup"
    URGENT_CARE = "urgent_care"
    EMERGENCY_DEPARTMENT = "emergency_department"
    CALL_911 = "call_911"


class SeverityLevel(StrEnum):
    NORMAL = "normal"
    URGENT = "urgent"
    EMERGENCY = "emergency"


class SafetyAction(StrEnum):
    CONTINUE_PROTOCOL_QUESTIONS = "continue_protocol_questions"
    EXPEDITE_CLINICIAN_REVIEW = "expedite_clinician_review"
    IMMEDIATE_EMERGENCY_ESCALATION = "immediate_emergency_escalation"


class FinalDispositionDecision(StrEnum):
    SELF_CARE = "self_care"
    CALLBACK = "callback"
    URGENT_NURSE_HANDOFF = "urgent_nurse_handoff"
    EMERGENCY_INSTRUCTION = "emergency_instruction"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class TurnInputMode(StrEnum):
    STRUCTURED_UPDATES = "structured_updates"
    UTTERANCE_TEXT = "utterance_text"
    MIXED = "mixed"


class ExtractionConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SessionReviewStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    IN_REVIEW = "in_review"
    HUMAN_TAKEOVER = "human_takeover"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"


class ReviewActionType(StrEnum):
    SESSION_STARTED = "session_started"
    EXTRACTION_APPLIED = "extraction_applied"
    SAFETY_EVALUATED = "safety_evaluated"
    TRIAGE_EVALUATED = "triage_evaluated"
    DISPOSITION_LOCKED = "disposition_locked"
    HANDOFF_CREATED = "handoff_created"
    DOCUMENTATION_CREATED = "documentation_created"
    HUMAN_OVERRIDE_APPLIED = "human_override_applied"
    REVIEW_STATUS_UPDATED = "review_status_updated"
    SESSION_RESET = "session_reset"
    MEDICATION_REMINDER_GENERATED = "medication_reminder_generated"
    MEDICATION_DOSE_CONFIRMED = "medication_dose_confirmed"
    MEDICATION_ALERT_RAISED = "medication_alert_raised"
    MEDICATION_CHECKIN_RECORDED = "medication_checkin_recorded"
    MEDICATION_SUMMARY_GENERATED = "medication_summary_generated"


class MealConstraintType(StrEnum):
    BEFORE_MEAL = "before_meal"
    AFTER_MEAL = "after_meal"
    WITH_FOOD = "with_food"
    EMPTY_STOMACH = "empty_stomach"
    NONE = "none"


class DoseStatus(StrEnum):
    TAKEN = "taken"
    SKIPPED = "skipped"
    DELAYED = "delayed"
    UNSURE = "unsure"


class MedicationWorkflowStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    RESOLVED = "resolved"


class AlertOutcome(StrEnum):
    CAREGIVER_ALERT = "caregiver_alert"
    CLINICIAN_REVIEW_RECOMMENDED = "clinician_review_recommended"
    URGENT_SYMPTOM_TRIAGE_RECOMMENDED = "urgent_symptom_triage_recommended"


class SymptomEscalationLevel(StrEnum):
    WATCH = "watch"
    CAREGIVER_FOLLOW_UP = "caregiver_follow_up"
    CLINICIAN_REVIEW_RECOMMENDED = "clinician_review_recommended"
    URGENT_SYMPTOM_TRIAGE_RECOMMENDED = "urgent_symptom_triage_recommended"
    EMERGENCY_ESCALATION = "emergency_escalation"


class MedicationCriticality(StrEnum):
    ROUTINE = "routine"
    IMPORTANT = "important"
    CRITICAL = "critical"


class CareActivityCategory(StrEnum):
    MEDICATION = "medication"
    MEAL = "meal"
    ACTIVITY = "activity"
    PHYSIO = "physio"
    WOUND_CARE = "wound_care"
    VITALS_CHECK = "vitals_check"
    SYMPTOM_CHECK = "symptom_check"
    HYDRATION = "hydration"
    SLEEP = "sleep"
    APPOINTMENT = "appointment"
    TEST = "test"


class CareActivityConfirmationStatus(StrEnum):
    DONE = "done"
    DELAYED = "delayed"
    SKIPPED = "skipped"


class RecipientRole(StrEnum):
    PATIENT = "patient"
    CAREGIVER = "caregiver"


class ChannelType(StrEnum):
    MOCK_TEXT = "mock_text"
    WHATSAPP = "whatsapp"


class DeliveryStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class MessageKind(StrEnum):
    DUE_REMINDER = "due_reminder"
    OVERDUE_FOLLOWUP = "overdue_followup"
    CONFIRMATION_RECEIVED = "confirmation_received"
    CARE_ACTIVITY_REMINDER = "care_activity_reminder"


class HealthResponse(BaseModel):
    service: str
    status: str


class StructuredSymptomInput(BaseModel):
    patient_id: str
    protocol_id: str
    chief_complaint: str
    symptom_summary: str
    observed_signals: list[str] = Field(default_factory=list)
    answers: dict[str, str] = Field(default_factory=dict)


class StructuredSymptomUpdate(BaseModel):
    patient_id: str | None = None
    chief_complaint: str | None = None
    symptom_summary: str | None = None
    observed_signals: list[str] = Field(default_factory=list)
    answers: dict[str, str] = Field(default_factory=dict)


class UserUtteranceInput(BaseModel):
    utterance_text: str
    protocol_id: str | None = None
    session_id: str | None = None


class ExtractedField(BaseModel):
    field_path: str
    value: str
    confidence: ExtractionConfidence


class ExtractionResult(BaseModel):
    mode: TurnInputMode
    utterance_text: str
    extracted_fields: list[ExtractedField] = Field(default_factory=list)
    structured_update: StructuredSymptomUpdate = Field(default_factory=StructuredSymptomUpdate)
    unmatched_text: str = ""
    extraction_notes: list[str] = Field(default_factory=list)


class TriageQuestion(BaseModel):
    key: str
    text: str
    required: bool


class PolicyTraceEntry(BaseModel):
    stage: str
    rule_name: str
    matched: bool
    detail: str


class TriageResult(BaseModel):
    patient_id: str
    protocol_id: str
    severity_level: SeverityLevel
    disposition: Disposition | None
    next_required_question: TriageQuestion | None
    missing_required_questions: list[str] = Field(default_factory=list)
    triggered_red_flags: list[str] = Field(default_factory=list)
    ready_for_disposition: bool
    rationale: str


class SafetyResult(BaseModel):
    patient_id: str
    severity_level: SeverityLevel
    triggered_rules: list[str] = Field(default_factory=list)
    allowed_actions: list[SafetyAction] = Field(default_factory=list)
    policy_trace: list[PolicyTraceEntry] = Field(default_factory=list)


class SessionBootstrap(BaseModel):
    request_id: str
    session_id: str
    channel: str
    protocol_id: str
    caller_language: str | None = None
    caller_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationTurn(BaseModel):
    speaker: str
    text: str
    timestamp: str | None = None


class AnsweredField(BaseModel):
    key: str
    value: str
    turn_index: int


class QuestionProgress(BaseModel):
    asked_questions: list[str] = Field(default_factory=list)
    answered_questions: list[AnsweredField] = Field(default_factory=list)
    current_next_question: TriageQuestion | None = None


class DispositionLock(BaseModel):
    final_disposition: FinalDispositionDecision
    locked_turn_index: int
    lock_reason: str


class HandoffPayload(BaseModel):
    handoff_required: bool
    disposition: FinalDispositionDecision | None
    destination: str
    priority: str
    reason: str
    metadata: dict[str, str] = Field(default_factory=dict)
    version: int = 1
    supersedes_version: int | None = None


class DocumentationPayload(BaseModel):
    clinician_summary: str
    patient_summary: str
    structured_note: dict[str, Any]
    version: int = 1
    supersedes_version: int | None = None


class MedicationScheduleEntry(BaseModel):
    entry_id: str
    display_name: str = ""
    generic_name: str | None = None
    medication_name: str
    dose_instructions: str
    scheduled_time: str
    meal_constraint: MealConstraintType = MealConstraintType.NONE
    priority: str = "routine"
    criticality_level: MedicationCriticality = MedicationCriticality.ROUTINE
    monitoring_notes: str = ""
    missed_dose_policy: str = ""
    side_effect_watch_items: list[str] = Field(default_factory=list)


class CareActivity(BaseModel):
    activity_id: str
    title: str
    category: CareActivityCategory
    schedule: str
    duration_minutes: int | None = None
    instruction: str
    frequency: str
    priority: str = "routine"
    confirmation_required: bool = True
    escalation_policy: str | None = None


class MedicationPlan(BaseModel):
    patient_id: str
    plan_id: str
    workflow_status: MedicationWorkflowStatus = MedicationWorkflowStatus.ACTIVE
    timezone: str = "UTC"
    created_at: str
    medications: list[MedicationScheduleEntry] = Field(default_factory=list)
    care_activities: list[CareActivity] = Field(default_factory=list)


class PatientRecord(BaseModel):
    patient_id: str
    display_name: str
    timezone: str = "UTC"
    patient_contact: str = ""
    caregiver_name: str
    caregiver_contact: str
    created_at: str
    notes: str = ""


class MedicationReminder(BaseModel):
    reminder_id: str
    patient_id: str
    plan_id: str
    schedule_entry_id: str
    medication_name: str
    scheduled_datetime: str
    meal_constraint: MealConstraintType = MealConstraintType.NONE
    priority: str = "routine"
    criticality_level: MedicationCriticality = MedicationCriticality.ROUTINE
    status: str = "upcoming"
    local_scheduled_time: str | None = None


class CareActivityInstance(BaseModel):
    instance_id: str
    patient_id: str
    plan_id: str
    activity_id: str
    title: str
    category: CareActivityCategory
    scheduled_datetime: str
    local_scheduled_time: str | None = None
    duration_minutes: int | None = None
    instruction: str
    frequency: str
    priority: str = "routine"
    confirmation_required: bool = True
    escalation_policy: str | None = None
    status: str = "upcoming"


class DoseConfirmation(BaseModel):
    patient_id: str
    reminder_id: str
    schedule_entry_id: str
    dose_status: DoseStatus
    confirmed_at: str
    meal_condition_satisfied: bool | None = None
    note: str = ""


class CareActivityConfirmation(BaseModel):
    patient_id: str
    instance_id: str
    activity_id: str
    confirmation_status: CareActivityConfirmationStatus
    confirmed_at: str
    note: str = ""


class SideEffectCheckin(BaseModel):
    patient_id: str
    checkin_time: str
    feeling: str
    dizziness: bool = False
    breathlessness: bool = False
    bleeding: bool = False
    nausea: bool = False
    weakness: bool = False
    swelling: bool = False
    note: str = ""
    chest_pain: bool = False
    confusion: bool = False
    near_fainting: bool = False
    severe_weakness: bool = False


class AdherenceAlert(BaseModel):
    alert_id: str
    patient_id: str
    date: str
    severity: str
    category: str
    message: str
    caregiver_alert: bool
    clinician_review_recommended: bool
    urgent_symptom_triage_recommended: bool


class SymptomEscalationProfile(BaseModel):
    patient_id: str
    checkin_time: str
    escalation_level: SymptomEscalationLevel
    triggered_flags: list[str] = Field(default_factory=list)
    rationale: str


class CaregiverNotificationEvent(BaseModel):
    event_id: str
    patient_id: str
    date: str
    event_type: str
    severity: str
    message: str
    action: AlertOutcome | str
    created_at: str


class DailyMedicationLog(BaseModel):
    patient_id: str
    date: str
    reminders: list[MedicationReminder] = Field(default_factory=list)
    confirmations: list[DoseConfirmation] = Field(default_factory=list)
    care_activity_instances: list[CareActivityInstance] = Field(default_factory=list)
    care_activity_confirmations: list[CareActivityConfirmation] = Field(default_factory=list)
    vitals_checkins: list["VitalsCheckinRecord"] = Field(default_factory=list)
    symptom_checkins: list["SymptomCheckinRecord"] = Field(default_factory=list)
    side_effect_checkins: list[SideEffectCheckin] = Field(default_factory=list)
    alerts: list[AdherenceAlert] = Field(default_factory=list)
    notifications: list[CaregiverNotificationEvent] = Field(default_factory=list)
    symptom_escalations: list[SymptomEscalationProfile] = Field(default_factory=list)
    messages: list["MedicationMessageRecord"] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)


class CaregiverSummary(BaseModel):
    patient_id: str
    date: str
    patient_timezone: str = "UTC"
    local_now: str = ""
    total_doses: int
    taken_count: int
    skipped_count: int
    delayed_count: int
    unsure_count: int
    adherence_rate: float
    total_doses_today: int = 0
    doses_due_so_far: int = 0
    doses_completed_so_far: int = 0
    overdue_so_far: int = 0
    final_day_adherence_rate: float | None = None
    current_progress_rate: float | None = None
    active_alerts: list[AdherenceAlert] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    summary_text: str = ""


class MedicationDashboardView(BaseModel):
    patient: PatientRecord
    date: str
    due_now: list[MedicationReminder] = Field(default_factory=list)
    upcoming: list[MedicationReminder] = Field(default_factory=list)
    overdue: list[MedicationReminder] = Field(default_factory=list)
    completed: list[MedicationReminder] = Field(default_factory=list)
    skipped_or_delayed: list[DoseConfirmation] = Field(default_factory=list)
    active_alerts: list[AdherenceAlert] = Field(default_factory=list)
    side_effect_checkins: list[SideEffectCheckin] = Field(default_factory=list)
    daily_adherence_score: float
    caregiver_summary_text: str


class MedicationTimelineItem(BaseModel):
    order_key: str
    scheduled_datetime: str
    medication_name: str
    schedule_entry_id: str
    status: str
    meal_constraint: MealConstraintType
    priority: str
    confirmation_status: DoseStatus | None = None


class MedicationTimelineResponse(BaseModel):
    patient_id: str
    date: str
    timeline: list[MedicationTimelineItem] = Field(default_factory=list)


class UnifiedDailyTimelineItem(BaseModel):
    order_key: str
    item_type: str
    item_id: str
    slot_time: str
    title: str
    category: str
    status: str
    priority: str
    details: dict[str, Any] = Field(default_factory=dict)


class UnifiedDailyTimelineResponse(BaseModel):
    patient_id: str
    date: str
    patient_timezone: str = "UTC"
    local_now: str = ""
    items: list[UnifiedDailyTimelineItem] = Field(default_factory=list)


class CareOsTodayResponse(BaseModel):
    patient_id: str
    date: str
    patient_timezone: str
    local_now: str
    timeline: UnifiedDailyTimelineResponse
    completed_items: list[UnifiedDailyTimelineItem] = Field(default_factory=list)
    pending_items: list[UnifiedDailyTimelineItem] = Field(default_factory=list)
    overdue_items: list[UnifiedDailyTimelineItem] = Field(default_factory=list)
    next_item: UnifiedDailyTimelineItem | None = None
    caregiver_actions_needed: list[CaregiverActionRecommendation] = Field(default_factory=list)
    symptom_escalation_flags: list[str] = Field(default_factory=list)
    medication_adherence_summary: CaregiverSummary


class CareOsSummaryResponse(BaseModel):
    patient_id: str
    date: str
    patient_timezone: str
    total_items: int
    completed_count: int
    pending_count: int
    overdue_count: int
    next_item: UnifiedDailyTimelineItem | None = None
    caregiver_summary_text: str
    symptom_escalation_flags: list[str] = Field(default_factory=list)
    medication_adherence_summary: CaregiverSummary


class AdministrationWindow(BaseModel):
    window_id: str
    slot_time: str
    meds: list[MedicationReminder] = Field(default_factory=list)
    meal_rule_summary: str
    all_completed: bool
    window_risk_level: str
    window_status: str


class CaregiverActionRecommendation(BaseModel):
    action_id: str
    action_type: str
    priority: str
    reason: str
    related_window_id: str | None = None
    related_alert_id: str | None = None


class DaySimulationReport(BaseModel):
    patient_id: str
    date: str
    administration_windows: list[AdministrationWindow] = Field(default_factory=list)
    completed_windows: int
    delayed_or_missed_windows: int
    critical_missed_dose_events: list[AdherenceAlert] = Field(default_factory=list)
    symptom_alerts: list[AdherenceAlert] = Field(default_factory=list)
    caregiver_notifications: list[CaregiverNotificationEvent] = Field(default_factory=list)
    adherence_summary: CaregiverSummary
    top_caregiver_follow_up_items: list[str] = Field(default_factory=list)


class MedicationMessageRecord(BaseModel):
    message_id: str
    patient_id: str
    date: str
    window_id: str
    window_slot_time: str
    recipient_role: RecipientRole
    channel_type: ChannelType
    message_kind: MessageKind
    content: str
    delivery_status: DeliveryStatus
    created_at: str
    dedupe_key: str = ""
    escalation_stage: int | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class MessageConfirmationRequest(BaseModel):
    window_id: str
    confirmation: DoseStatus
    responder_role: RecipientRole = RecipientRole.PATIENT
    confirmed_at: str | None = None
    meal_condition_satisfied: bool | None = None
    note: str = ""
    message_id: str | None = None


class CareActivityConfirmationRequest(BaseModel):
    instance_id: str
    confirmation: CareActivityConfirmationStatus
    confirmed_at: str | None = None
    note: str = ""


class TimelineActionRequest(BaseModel):
    reason: str = ""
    actor_id: str = "caregiver"
    actor_name: str = "caregiver"
    allow_high_risk_medication_edit: bool = False


class TimelineDelayRequest(TimelineActionRequest):
    minutes: int = 15


class PatchCareActivityRequest(BaseModel):
    title: str | None = None
    schedule: str | None = None
    duration_minutes: int | None = None
    instruction: str | None = None
    frequency: str | None = None
    priority: str | None = None
    confirmation_required: bool | None = None
    escalation_policy: str | None = None
    actor_id: str = "caregiver"
    actor_name: str = "caregiver"
    reason: str = ""


class VitalsCheckinRequest(BaseModel):
    checkin_time: str
    blood_pressure_systolic: int | None = None
    blood_pressure_diastolic: int | None = None
    pulse_bpm: int | None = None
    blood_sugar_mg_dl: int | None = None
    note: str = ""


class VitalsCheckinRecord(BaseModel):
    patient_id: str
    checkin_time: str
    blood_pressure_systolic: int | None = None
    blood_pressure_diastolic: int | None = None
    pulse_bpm: int | None = None
    blood_sugar_mg_dl: int | None = None
    note: str = ""


class SymptomCheckinRequest(BaseModel):
    checkin_time: str
    feeling: str = ""
    chest_pain: bool = False
    breathlessness: bool = False
    dizziness: bool = False
    swelling: bool = False
    confusion: bool = False
    severe_weakness: bool = False
    bleeding: bool = False
    note: str = ""


class SymptomCheckinRecord(BaseModel):
    patient_id: str
    checkin_time: str
    feeling: str = ""
    chest_pain: bool = False
    breathlessness: bool = False
    dizziness: bool = False
    swelling: bool = False
    confusion: bool = False
    severe_weakness: bool = False
    bleeding: bool = False
    escalation_level: SymptomEscalationLevel
    note: str = ""


class SendDueRemindersResponse(BaseModel):
    patient_id: str
    date: str
    patient_timezone: str
    local_now: str
    sent_messages: list[MedicationMessageRecord] = Field(default_factory=list)


class SendOverdueFollowupsResponse(BaseModel):
    patient_id: str
    date: str
    patient_timezone: str
    local_now: str
    sent_messages: list[MedicationMessageRecord] = Field(default_factory=list)


class MedicationTodayView(BaseModel):
    patient_id: str
    date: str
    patient_timezone: str = "UTC"
    local_now: str = ""
    administration_windows: list[AdministrationWindow] = Field(default_factory=list)
    due_now: list[MedicationReminder] = Field(default_factory=list)
    overdue: list[MedicationReminder] = Field(default_factory=list)
    completed: list[MedicationReminder] = Field(default_factory=list)
    care_activities_due_now: list[CareActivityInstance] = Field(default_factory=list)
    care_activities_overdue: list[CareActivityInstance] = Field(default_factory=list)
    symptom_alerts: list[AdherenceAlert] = Field(default_factory=list)
    caregiver_action_needed: list[str] = Field(default_factory=list)
    caregiver_actions: list[CaregiverActionRecommendation] = Field(default_factory=list)
    unified_daily_plan: UnifiedDailyTimelineResponse | None = None
    end_of_day_summary: CaregiverSummary


class SimulatedTimeState(BaseModel):
    dev_mode: bool = True
    simulated_now: str
    timezone: str = "UTC"


class SetSimulatedTimeRequest(BaseModel):
    simulated_now: str


class AdvanceSimulatedTimeRequest(BaseModel):
    minutes: int = 0
    hours: int = 0


class MedicationPlanImportRequest(BaseModel):
    patient: PatientRecord
    plan: MedicationPlan


class MedicationPlanExportResponse(BaseModel):
    patient: PatientRecord
    plan: MedicationPlan


class UpdateMedicationScheduleEntryRequest(BaseModel):
    medication_name: str
    dose_instructions: str
    scheduled_time: str
    meal_constraint: MealConstraintType = MealConstraintType.NONE
    priority: str = "routine"
    monitoring_notes: str = ""
    side_effect_watch_items: list[str] = Field(default_factory=list)


class DailyMedicationExportResponse(BaseModel):
    patient: PatientRecord
    plan: MedicationPlan
    log: DailyMedicationLog
    summary: CaregiverSummary


class HumanOverrideRequest(BaseModel):
    reviewer_id: str
    reviewer_name: str
    new_disposition: FinalDispositionDecision
    rationale: str
    human_takeover: bool = True


class HumanOverrideRecord(BaseModel):
    reviewer_id: str
    reviewer_name: str
    reviewed_at: str
    machine_recommended_disposition: FinalDispositionDecision
    overridden_disposition: FinalDispositionDecision
    override_rationale: str
    acuity_change: str
    human_takeover: bool


class AuditEvent(BaseModel):
    event_id: str
    event_type: ReviewActionType
    timestamp: str
    actor_id: str
    actor_name: str
    message: str
    metadata: dict[str, str] = Field(default_factory=dict)


class RuntimeSessionState(BaseModel):
    session: SessionBootstrap
    status: SessionStatus
    symptom_input: StructuredSymptomInput
    turns: list[ConversationTurn] = Field(default_factory=list)
    question_progress: QuestionProgress = Field(default_factory=QuestionProgress)
    latest_safety_result: SafetyResult | None = None
    latest_triage_result: TriageResult | None = None
    latest_extraction_result: ExtractionResult | None = None
    extraction_history: list[ExtractionResult] = Field(default_factory=list)
    disposition_lock: DispositionLock | None = None
    machine_recommended_disposition: FinalDispositionDecision | None = None
    final_effective_disposition: FinalDispositionDecision | None = None
    review_status: SessionReviewStatus = SessionReviewStatus.PENDING_REVIEW
    human_takeover: bool = False
    override_record: HumanOverrideRecord | None = None
    handoff_payload: HandoffPayload | None = None
    documentation_payload: DocumentationPayload | None = None
    handoff_versions: list[HandoffPayload] = Field(default_factory=list)
    documentation_versions: list[DocumentationPayload] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)


class SessionSummaryView(BaseModel):
    session_id: str
    protocol_id: str
    session_status: SessionStatus
    review_status: SessionReviewStatus
    latest_severity: SeverityLevel | None = None
    machine_recommended_disposition: FinalDispositionDecision | None = None
    final_effective_disposition: FinalDispositionDecision | None = None
    human_takeover: bool


class SessionDetailView(BaseModel):
    summary: SessionSummaryView
    session_state: RuntimeSessionState


class RuntimeEvaluationRequest(BaseModel):
    session: SessionBootstrap
    symptom_input: StructuredSymptomInput
    turns: list[ConversationTurn] = Field(default_factory=list)


class RuntimeEvaluationResponse(BaseModel):
    session: SessionBootstrap
    safety_result: SafetyResult
    triage_result: TriageResult
    final_disposition: FinalDispositionDecision | None
    next_required_question: TriageQuestion | None
    handoff_payload: HandoffPayload | None = None
    documentation_payload: DocumentationPayload | None = None
    notes: list[str] = Field(default_factory=list)


class TurnProcessingResult(BaseModel):
    session_state: RuntimeSessionState
    final_disposition: FinalDispositionDecision | None
    disposition_locked_this_turn: bool
    next_required_question: TriageQuestion | None


class HandoffCreateRequest(BaseModel):
    session: SessionBootstrap
    symptom_input: StructuredSymptomInput
    final_disposition: FinalDispositionDecision
    safety_result: SafetyResult
    triage_result: TriageResult


class DocumentationCreateRequest(BaseModel):
    session: SessionBootstrap
    symptom_input: StructuredSymptomInput
    final_disposition: FinalDispositionDecision | None
    safety_result: SafetyResult
    triage_result: TriageResult


class RuntimeSessionStartRequest(BaseModel):
    session: SessionBootstrap
    initial_symptom_input: StructuredSymptomInput | None = None


class RuntimeSessionTurnRequest(BaseModel):
    session_id: str
    turn: ConversationTurn
    symptom_update: StructuredSymptomUpdate | None = None
    utterance_input: UserUtteranceInput | None = None


class SessionReviewStatusUpdateRequest(BaseModel):
    reviewer_id: str
    reviewer_name: str
    review_status: SessionReviewStatus
    note: str | None = None


class DoseConfirmationRequest(BaseModel):
    schedule_entry_id: str
    scheduled_datetime: str
    dose_status: DoseStatus
    confirmed_at: str
    meal_condition_satisfied: bool | None = None
    note: str = ""


class SideEffectCheckinRequest(BaseModel):
    checkin_time: str
    feeling: str
    dizziness: bool = False
    breathlessness: bool = False
    bleeding: bool = False
    nausea: bool = False
    weakness: bool = False
    swelling: bool = False
    note: str = ""
    chest_pain: bool = False
    confusion: bool = False
    near_fainting: bool = False
    severe_weakness: bool = False


class DueNowResponse(BaseModel):
    patient_id: str
    at: str
    patient_timezone: str = "UTC"
    local_now: str = ""
    due_now: list[MedicationReminder] = Field(default_factory=list)
    next_upcoming: MedicationReminder | None = None
