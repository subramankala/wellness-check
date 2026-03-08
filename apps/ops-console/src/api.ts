export type SessionStatus = "active" | "completed";
export type SessionReviewStatus =
  | "pending_review"
  | "in_review"
  | "human_takeover"
  | "reviewed"
  | "resolved";
export type FinalDispositionDecision =
  | "self_care"
  | "callback"
  | "urgent_nurse_handoff"
  | "emergency_instruction";

export type SessionSummaryView = {
  session_id: string;
  protocol_id: string;
  session_status: SessionStatus;
  review_status: SessionReviewStatus;
  latest_severity: string | null;
  machine_recommended_disposition: FinalDispositionDecision | null;
  final_effective_disposition: FinalDispositionDecision | null;
  human_takeover: boolean;
};

export type SessionDetailView = {
  summary: SessionSummaryView;
  session_state: any;
};

export type HumanOverrideRequest = {
  reviewer_id: string;
  reviewer_name: string;
  new_disposition: FinalDispositionDecision;
  rationale: string;
  human_takeover: boolean;
};

export type ReviewStatusRequest = {
  reviewer_id: string;
  reviewer_name: string;
  review_status: SessionReviewStatus;
  note?: string;
};

export type MedicationDashboardView = {
  patient: {
    patient_id: string;
    display_name: string;
    caregiver_name: string;
    caregiver_contact: string;
    timezone: string;
  };
  date: string;
  due_now: any[];
  upcoming: any[];
  overdue: any[];
  completed: any[];
  skipped_or_delayed: any[];
  active_alerts: any[];
  side_effect_checkins: any[];
  daily_adherence_score: number;
  caregiver_summary_text: string;
};

export type MedicationTimelineResponse = {
  patient_id: string;
  date: string;
  timeline: any[];
};

export type MedicationTodayView = {
  patient_id: string;
  date: string;
  administration_windows: any[];
  due_now: any[];
  overdue: any[];
  completed: any[];
  care_activities_due_now: any[];
  care_activities_overdue: any[];
  symptom_alerts: any[];
  caregiver_action_needed: string[];
  caregiver_actions: any[];
  unified_daily_plan: UnifiedDailyTimelineResponse | null;
  end_of_day_summary: Record<string, unknown>;
};

export type UnifiedDailyTimelineResponse = {
  patient_id: string;
  date: string;
  patient_timezone: string;
  local_now: string;
  items: Array<{
    order_key: string;
    item_type: string;
    item_id: string;
    slot_time: string;
    title: string;
    category: string;
    status: string;
    priority: string;
    details: Record<string, string>;
  }>;
};

export type CareOsTodayResponse = {
  patient_id: string;
  date: string;
  patient_timezone: string;
  local_now: string;
  timeline: UnifiedDailyTimelineResponse;
  completed_items: any[];
  pending_items: any[];
  overdue_items: any[];
  next_item: any | null;
  caregiver_actions_needed: any[];
  symptom_escalation_flags: string[];
  medication_adherence_summary: Record<string, unknown>;
};

export type DaySimulationReport = {
  patient_id: string;
  date: string;
  administration_windows: any[];
  completed_windows: number;
  delayed_or_missed_windows: number;
  critical_missed_dose_events: any[];
  symptom_alerts: any[];
  caregiver_notifications: any[];
  adherence_summary: Record<string, unknown>;
  top_caregiver_follow_up_items: string[];
};

export type MedicationMessageRecord = {
  message_id: string;
  patient_id: string;
  date: string;
  window_id: string;
  window_slot_time: string;
  recipient_role: "patient" | "caregiver";
  channel_type: string;
  message_kind:
    | "due_reminder"
    | "overdue_followup"
    | "confirmation_received"
    | "care_activity_reminder";
  content: string;
  delivery_status: string;
  created_at: string;
  metadata: Record<string, string>;
};

export type SendDueRemindersResponse = {
  patient_id: string;
  date: string;
  patient_timezone: string;
  local_now: string;
  sent_messages: MedicationMessageRecord[];
};

export type SimulatedTimeState = {
  dev_mode: boolean;
  simulated_now: string;
  timezone: string;
};

export class RuntimeApiClient {
  constructor(
    private readonly runtimeBaseUrl: string,
    private readonly medicationBaseUrl: string
  ) {}

  async listSessions(): Promise<SessionSummaryView[]> {
    const response = await fetch(`${this.runtimeBaseUrl}/runtime/sessions`);
    if (!response.ok) {
      throw new Error("Failed to list sessions");
    }
    return (await response.json()) as SessionSummaryView[];
  }

  async getSessionDetail(sessionId: string): Promise<SessionDetailView> {
    const response = await fetch(`${this.runtimeBaseUrl}/runtime/session/${sessionId}/detail`);
    if (!response.ok) {
      throw new Error(`Failed to get session detail for ${sessionId}`);
    }
    return (await response.json()) as SessionDetailView;
  }

  async applyOverride(sessionId: string, payload: HumanOverrideRequest): Promise<SessionDetailView> {
    const response = await fetch(`${this.runtimeBaseUrl}/runtime/session/${sessionId}/override`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      throw new Error(`Failed to apply override for ${sessionId}`);
    }
    return (await response.json()) as SessionDetailView;
  }

  async updateReviewStatus(sessionId: string, payload: ReviewStatusRequest): Promise<SessionDetailView> {
    const response = await fetch(`${this.runtimeBaseUrl}/runtime/session/${sessionId}/review-status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      throw new Error(`Failed to update review status for ${sessionId}`);
    }
    return (await response.json()) as SessionDetailView;
  }

  async getMedicationDashboard(patientId: string, date: string): Promise<MedicationDashboardView> {
    const response = await fetch(`${this.medicationBaseUrl}/medication/${patientId}/dashboard?date=${date}`);
    if (!response.ok) {
      throw new Error(`Failed to load medication dashboard for ${patientId}`);
    }
    return (await response.json()) as MedicationDashboardView;
  }

  async getMedicationTimeline(patientId: string, date: string): Promise<MedicationTimelineResponse> {
    const response = await fetch(`${this.medicationBaseUrl}/medication/${patientId}/timeline?date=${date}`);
    if (!response.ok) {
      throw new Error(`Failed to load medication timeline for ${patientId}`);
    }
    return (await response.json()) as MedicationTimelineResponse;
  }

  async getUnifiedDailyTimeline(patientId: string, date: string): Promise<UnifiedDailyTimelineResponse> {
    const response = await fetch(`${this.medicationBaseUrl}/medication/${patientId}/daily-care-timeline?date=${date}`);
    if (!response.ok) {
      throw new Error(`Failed to load unified daily timeline for ${patientId}`);
    }
    return (await response.json()) as UnifiedDailyTimelineResponse;
  }

  async getCareOsToday(patientId: string): Promise<CareOsTodayResponse> {
    const response = await fetch(`${this.medicationBaseUrl}/careos/${patientId}/today`);
    if (!response.ok) {
      throw new Error(`Failed to load care OS today view for ${patientId}`);
    }
    return (await response.json()) as CareOsTodayResponse;
  }

  async completeCareOsItem(patientId: string, itemId: string, reason = "ops-console"): Promise<void> {
    const response = await fetch(`${this.medicationBaseUrl}/careos/${patientId}/timeline/${itemId}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason })
    });
    if (!response.ok) {
      throw new Error(`Failed to complete care OS item ${itemId}`);
    }
  }

  async getMedicationToday(patientId: string): Promise<MedicationTodayView> {
    const response = await fetch(`${this.medicationBaseUrl}/medication/${patientId}/today`);
    if (!response.ok) {
      throw new Error(`Failed to load medication today view for ${patientId}`);
    }
    return (await response.json()) as MedicationTodayView;
  }

  async getMedicationNotifications(patientId: string, date: string): Promise<any[]> {
    const response = await fetch(`${this.medicationBaseUrl}/medication/${patientId}/notifications?date=${date}`);
    if (!response.ok) {
      throw new Error(`Failed to load medication notifications for ${patientId}`);
    }
    return (await response.json()) as any[];
  }

  async getMedicationSimulationDayReport(patientId: string, date: string): Promise<DaySimulationReport> {
    const response = await fetch(
      `${this.medicationBaseUrl}/medication/${patientId}/simulate-day-report?date=${date}`
    );
    if (!response.ok) {
      throw new Error(`Failed to load medication simulation report for ${patientId}`);
    }
    return (await response.json()) as DaySimulationReport;
  }

  async sendDueReminders(patientId: string): Promise<SendDueRemindersResponse> {
    const response = await fetch(`${this.medicationBaseUrl}/medication/${patientId}/send-due-reminders`, {
      method: "POST"
    });
    if (!response.ok) {
      throw new Error(`Failed to send due reminders for ${patientId}`);
    }
    return (await response.json()) as SendDueRemindersResponse;
  }

  async getMedicationMessages(patientId: string, date: string): Promise<MedicationMessageRecord[]> {
    const response = await fetch(`${this.medicationBaseUrl}/medication/${patientId}/messages?date=${date}`);
    if (!response.ok) {
      throw new Error(`Failed to load medication messages for ${patientId}`);
    }
    return (await response.json()) as MedicationMessageRecord[];
  }

  async submitMessageConfirmation(patientId: string, payload: Record<string, unknown>): Promise<void> {
    const response = await fetch(`${this.medicationBaseUrl}/medication/${patientId}/message-confirmation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      throw new Error(`Failed to submit message confirmation for ${patientId}`);
    }
  }

  async submitCareActivityConfirmation(patientId: string, payload: Record<string, unknown>): Promise<void> {
    const response = await fetch(`${this.medicationBaseUrl}/medication/${patientId}/care-activity-confirmation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      throw new Error(`Failed to submit care activity confirmation for ${patientId}`);
    }
  }

  async confirmDose(patientId: string, payload: Record<string, unknown>): Promise<void> {
    const response = await fetch(`${this.medicationBaseUrl}/medication/${patientId}/dose-confirmation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      throw new Error(`Failed to confirm dose for ${patientId}`);
    }
  }

  async submitSideEffectCheckin(patientId: string, payload: Record<string, unknown>): Promise<void> {
    const response = await fetch(`${this.medicationBaseUrl}/medication/${patientId}/side-effect-checkin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      throw new Error(`Failed to submit check-in for ${patientId}`);
    }
  }

  async getSimulatedTime(): Promise<SimulatedTimeState> {
    const response = await fetch(`${this.medicationBaseUrl}/medication/simulated-time`);
    if (!response.ok) {
      throw new Error("Failed to load simulated time");
    }
    return (await response.json()) as SimulatedTimeState;
  }

  async setSimulatedTime(simulatedNow: string): Promise<SimulatedTimeState> {
    const response = await fetch(`${this.medicationBaseUrl}/medication/simulated-time/set`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ simulated_now: simulatedNow })
    });
    if (!response.ok) {
      throw new Error("Failed to set simulated time");
    }
    return (await response.json()) as SimulatedTimeState;
  }

  async advanceSimulatedTime(hours: number, minutes: number): Promise<SimulatedTimeState> {
    const response = await fetch(`${this.medicationBaseUrl}/medication/simulated-time/advance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hours, minutes })
    });
    if (!response.ok) {
      throw new Error("Failed to advance simulated time");
    }
    return (await response.json()) as SimulatedTimeState;
  }

  async importMedicationPlan(payload: Record<string, unknown>): Promise<void> {
    const response = await fetch(`${this.medicationBaseUrl}/medication/plan/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      throw new Error("Failed to import medication plan");
    }
  }
}
