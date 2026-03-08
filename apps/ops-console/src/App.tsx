import { useEffect, useMemo, useState } from "react";

import {
  type CareOsTodayResponse,
  type DaySimulationReport,
  type FinalDispositionDecision,
  type MedicationDashboardView,
  type MedicationMessageRecord,
  type MedicationTodayView,
  type MedicationTimelineResponse,
  type ReviewStatusRequest,
  type SessionDetailView,
  type SessionReviewStatus,
  type SessionSummaryView,
  type SimulatedTimeState,
  type UnifiedDailyTimelineResponse,
  RuntimeApiClient
} from "./api";

const RUNTIME_API_BASE_URL = "http://localhost:8001";
const MEDICATION_API_BASE_URL = "http://localhost:8105";

const DISPOSITION_OPTIONS: FinalDispositionDecision[] = [
  "self_care",
  "callback",
  "urgent_nurse_handoff",
  "emergency_instruction"
];

const REVIEW_STATUS_OPTIONS: SessionReviewStatus[] = [
  "pending_review",
  "in_review",
  "human_takeover",
  "resolved"
];

const DEFAULT_PATIENT_ID = "patient_cardiac_001";
const TODAY = "2026-03-07";

export function App(): JSX.Element {
  const api = useMemo(() => new RuntimeApiClient(RUNTIME_API_BASE_URL, MEDICATION_API_BASE_URL), []);

  const [sessions, setSessions] = useState<SessionSummaryView[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionDetailView | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>("");

  const [reviewerId, setReviewerId] = useState<string>("clinician_1");
  const [reviewerName, setReviewerName] = useState<string>("On-call Clinician");
  const [overrideDisposition, setOverrideDisposition] =
    useState<FinalDispositionDecision>("callback");
  const [overrideRationale, setOverrideRationale] = useState<string>("");
  const [reviewStatus, setReviewStatus] = useState<SessionReviewStatus>("in_review");
  const [reviewNote, setReviewNote] = useState<string>("");

  const [patientId, setPatientId] = useState<string>(DEFAULT_PATIENT_ID);
  const [dashboardDate, setDashboardDate] = useState<string>(TODAY);
  const [medicationDashboard, setMedicationDashboard] = useState<MedicationDashboardView | null>(null);
  const [medicationTimeline, setMedicationTimeline] = useState<MedicationTimelineResponse | null>(null);
  const [medicationToday, setMedicationToday] = useState<MedicationTodayView | null>(null);
  const [unifiedTimeline, setUnifiedTimeline] = useState<UnifiedDailyTimelineResponse | null>(null);
  const [careOsToday, setCareOsToday] = useState<CareOsTodayResponse | null>(null);
  const [medicationNotifications, setMedicationNotifications] = useState<any[]>([]);
  const [medicationMessages, setMedicationMessages] = useState<MedicationMessageRecord[]>([]);
  const [dayReport, setDayReport] = useState<DaySimulationReport | null>(null);
  const [simTime, setSimTime] = useState<SimulatedTimeState | null>(null);

  const [confirmEntryId, setConfirmEntryId] = useState<string>("");
  const [confirmScheduledAt, setConfirmScheduledAt] = useState<string>("");
  const [confirmStatus, setConfirmStatus] = useState<string>("taken");
  const [confirmMealSatisfied, setConfirmMealSatisfied] = useState<string>("true");

  const [checkinFeeling, setCheckinFeeling] = useState<string>("okay");
  const [checkinBreathless, setCheckinBreathless] = useState<boolean>(false);
  const [checkinWeakness, setCheckinWeakness] = useState<boolean>(false);
  const [checkinNote, setCheckinNote] = useState<string>("");
  const [messageWindowId, setMessageWindowId] = useState<string>("");
  const [messageReply, setMessageReply] = useState<string>("TAKEN");

  const [importText, setImportText] = useState<string>(`{
  "patient": {
    "patient_id": "patient_cardiac_001",
    "display_name": "Cardiac Patient",
    "timezone": "UTC",
    "caregiver_name": "Care Giver",
    "caregiver_contact": "+15550009999",
    "created_at": "2026-03-07T08:00:00+00:00",
    "notes": "Imported via ops console"
  },
  "plan": {
    "patient_id": "patient_cardiac_001",
    "plan_id": "plan_cardiac_discharge_v1",
    "workflow_status": "active",
    "timezone": "UTC",
    "created_at": "2026-03-07T08:00:00+00:00",
    "medications": []
  }
}`);

  async function refreshSessions(): Promise<void> {
    try {
      const data = await api.listSessions();
      setSessions(data);
      if (!selectedSessionId && data.length > 0) {
        setSelectedSessionId(data[0].session_id);
      }
      setErrorMessage("");
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  }

  async function loadDetail(sessionId: string): Promise<void> {
    try {
      const data = await api.getSessionDetail(sessionId);
      setDetail(data);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  }

  async function refreshMedication(): Promise<void> {
    try {
      const [dashboard, timeline, todayView, notifications, report, messages, time, unified, careOs] = await Promise.all([
        api.getMedicationDashboard(patientId, dashboardDate),
        api.getMedicationTimeline(patientId, dashboardDate),
        api.getMedicationToday(patientId),
        api.getMedicationNotifications(patientId, dashboardDate),
        api.getMedicationSimulationDayReport(patientId, dashboardDate),
        api.getMedicationMessages(patientId, dashboardDate),
        api.getSimulatedTime(),
        api.getUnifiedDailyTimeline(patientId, dashboardDate),
        api.getCareOsToday(patientId)
      ]);
      setMedicationDashboard(dashboard);
      setMedicationTimeline(timeline);
      setMedicationToday(todayView);
      setMedicationNotifications(notifications);
      setDayReport(report);
      setMedicationMessages(messages);
      setSimTime(time);
      setUnifiedTimeline(unified);
      setCareOsToday(careOs);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  }

  useEffect(() => {
    void refreshSessions();
    void refreshMedication();
  }, []);

  useEffect(() => {
    if (selectedSessionId) {
      void loadDetail(selectedSessionId);
    }
  }, [selectedSessionId]);

  async function submitOverride(): Promise<void> {
    if (!selectedSessionId) {
      return;
    }
    try {
      const updated = await api.applyOverride(selectedSessionId, {
        reviewer_id: reviewerId,
        reviewer_name: reviewerName,
        new_disposition: overrideDisposition,
        rationale: overrideRationale,
        human_takeover: true
      });
      setDetail(updated);
      await refreshSessions();
      setOverrideRationale("");
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  }

  async function submitReviewStatus(): Promise<void> {
    if (!selectedSessionId) {
      return;
    }
    const payload: ReviewStatusRequest = {
      reviewer_id: reviewerId,
      reviewer_name: reviewerName,
      review_status: reviewStatus,
      note: reviewNote
    };
    try {
      const updated = await api.updateReviewStatus(selectedSessionId, payload);
      setDetail(updated);
      await refreshSessions();
      setReviewNote("");
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  }

  async function submitDoseConfirmation(): Promise<void> {
    try {
      await api.confirmDose(patientId, {
        schedule_entry_id: confirmEntryId,
        scheduled_datetime: confirmScheduledAt,
        dose_status: confirmStatus,
        confirmed_at: simTime?.simulated_now ?? new Date().toISOString(),
        meal_condition_satisfied: confirmMealSatisfied === "true",
        note: "manual confirmation"
      });
      await refreshMedication();
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  }

  async function submitCheckin(): Promise<void> {
    try {
      await api.submitSideEffectCheckin(patientId, {
        checkin_time: simTime?.simulated_now ?? new Date().toISOString(),
        feeling: checkinFeeling,
        dizziness: false,
        breathlessness: checkinBreathless,
        bleeding: false,
        nausea: false,
        weakness: checkinWeakness,
        swelling: false,
        note: checkinNote
      });
      await refreshMedication();
      setCheckinNote("");
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  }

  async function advanceTime(hours: number, minutes: number): Promise<void> {
    try {
      await api.advanceSimulatedTime(hours, minutes);
      await refreshMedication();
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  }

  async function importPlan(): Promise<void> {
    try {
      const payload = JSON.parse(importText) as Record<string, unknown>;
      await api.importMedicationPlan(payload);
      await refreshMedication();
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  }

  async function sendDueReminders(): Promise<void> {
    try {
      await api.sendDueReminders(patientId);
      await refreshMedication();
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  }

  async function simulateMessageReply(): Promise<void> {
    if (!messageWindowId) {
      setErrorMessage("window_id is required for message confirmation");
      return;
    }
    try {
      await api.submitMessageConfirmation(patientId, {
        window_id: messageWindowId,
        confirmation: messageReply.toLowerCase(),
        note: "simulated from ops console"
      });
      await refreshMedication();
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  }

  async function completeCareOsItem(itemId: string): Promise<void> {
    try {
      await api.completeCareOsItem(patientId, itemId);
      await refreshMedication();
    } catch (error) {
      setErrorMessage((error as Error).message);
    }
  }

  return (
    <main className="layout">
      <section className="panel">
        <h1>Clinician Review Dashboard</h1>
        <div className="toolbar">
          <button onClick={() => void refreshSessions()}>Refresh Sessions</button>
          {errorMessage ? <span className="error">{errorMessage}</span> : null}
        </div>
        <table>
          <thead>
            <tr>
              <th>Session</th>
              <th>Status</th>
              <th>Protocol</th>
              <th>Severity</th>
              <th>Machine</th>
              <th>Effective</th>
              <th>Review</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((session: SessionSummaryView) => (
              <tr
                key={session.session_id}
                className={selectedSessionId === session.session_id ? "selected" : ""}
                onClick={() => setSelectedSessionId(session.session_id)}
              >
                <td>{session.session_id}</td>
                <td>{session.session_status}</td>
                <td>{session.protocol_id}</td>
                <td>{session.latest_severity ?? "n/a"}</td>
                <td>{session.machine_recommended_disposition ?? "n/a"}</td>
                <td>{session.final_effective_disposition ?? "n/a"}</td>
                <td>{session.review_status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel detail">
        <h2>Triage Session Detail</h2>
        {!detail ? (
          <p>Select a session from the dashboard.</p>
        ) : (
          <>
            <div className="grid2">
              <div>
                <h3>State</h3>
                <pre>{JSON.stringify(detail.summary, null, 2)}</pre>
              </div>
              <div>
                <h3>Structured Symptom Input</h3>
                <pre>{JSON.stringify(detail.session_state.symptom_input, null, 2)}</pre>
              </div>
            </div>

            <div className="grid2">
              <div>
                <h3>Extraction History</h3>
                <pre>{JSON.stringify(detail.session_state.extraction_history, null, 2)}</pre>
              </div>
              <div>
                <h3>Safety / Triage</h3>
                <pre>
                  {JSON.stringify(
                    {
                      safety: detail.session_state.latest_safety_result,
                      triage: detail.session_state.latest_triage_result,
                      next_question: detail.session_state.question_progress?.current_next_question,
                      lock: detail.session_state.disposition_lock
                    },
                    null,
                    2
                  )}
                </pre>
              </div>
            </div>

            <div className="controls">
              <h3>Override Disposition</h3>
              <label>
                Reviewer ID
                <input value={reviewerId} onChange={(event) => setReviewerId(event.target.value)} />
              </label>
              <label>
                Reviewer Name
                <input value={reviewerName} onChange={(event) => setReviewerName(event.target.value)} />
              </label>
              <label>
                New Disposition
                <select
                  value={overrideDisposition}
                  onChange={(event) =>
                    setOverrideDisposition(event.target.value as FinalDispositionDecision)
                  }
                >
                  {DISPOSITION_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Rationale
                <textarea
                  value={overrideRationale}
                  onChange={(event) => setOverrideRationale(event.target.value)}
                />
              </label>
              <button onClick={() => void submitOverride()}>Apply Override</button>
            </div>

            <div className="controls">
              <h3>Update Review Status</h3>
              <label>
                Status
                <select
                  value={reviewStatus}
                  onChange={(event) => setReviewStatus(event.target.value as SessionReviewStatus)}
                >
                  {REVIEW_STATUS_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Note
                <input value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} />
              </label>
              <button onClick={() => void submitReviewStatus()}>Update Status</button>
            </div>
          </>
        )}
      </section>

      <section className="panel detail">
        <h2>Medication Caregiver Dashboard</h2>
        <div className="toolbar">
          <label>
            Patient ID
            <input value={patientId} onChange={(event) => setPatientId(event.target.value)} />
          </label>
          <label>
            Date
            <input value={dashboardDate} onChange={(event) => setDashboardDate(event.target.value)} />
          </label>
          <button onClick={() => void refreshMedication()}>Refresh Medication</button>
        </div>

        <div className="toolbar">
          <span>Simulated Time: {simTime?.simulated_now ?? "n/a"}</span>
          <button onClick={() => void advanceTime(0, 30)}>+30m</button>
          <button onClick={() => void advanceTime(1, 0)}>+1h</button>
          <button onClick={() => void sendDueReminders()}>Send Due Reminders</button>
        </div>

            <div className="grid2">
              <div>
                <h3>Daily Overview</h3>
                <pre>{JSON.stringify(medicationDashboard, null, 2)}</pre>
              </div>
              <div>
                <h3>Timeline</h3>
                <pre>{JSON.stringify(medicationTimeline, null, 2)}</pre>
              </div>
            </div>

        <div className="grid2">
          <div>
            <h3>Administration Windows</h3>
            {!medicationToday ? (
              <p>No today data.</p>
            ) : (
              <ul>
                {medicationToday.administration_windows.map((window) => (
                  <li key={window.window_id}>
                    <strong>{window.slot_time}</strong>{" "}
                    <span className={`badge badge-${window.window_status}`}>{window.window_status}</span>{" "}
                    <span className={`badge badge-risk-${window.window_risk_level}`}>risk {window.window_risk_level}</span>{" "}
                    <span className="badge">meal {window.meal_rule_summary}</span>
                    <br />
                    Meds: {window.meds.map((med: any) => med.medication_name).join(", ")}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h3>Unified Daily Care Plan</h3>
            {careOsToday ? (
              <p>
                Completed: {careOsToday.completed_items.length} | Pending: {careOsToday.pending_items.length} | Overdue: {careOsToday.overdue_items.length}
              </p>
            ) : null}
            {unifiedTimeline ? (
              <ul>
                {unifiedTimeline.items.map((item) => (
                  <li key={item.item_id}>
                    <strong>{item.slot_time}</strong> [{item.item_type}] {item.title}{" "}
                    <span className={`badge badge-${item.status}`}>{item.status}</span>
                    <button onClick={() => void completeCareOsItem(item.item_id)}>Done</button>
                  </li>
                ))}
              </ul>
            ) : (
              <p>No unified care timeline.</p>
            )}
          </div>
          <div>
            <h3>Caregiver Action Badges</h3>
            {!medicationToday ? (
              <p>No action recommendations.</p>
            ) : (
              <ul>
                {medicationToday.caregiver_actions.map((action) => (
                  <li key={action.action_id}>
                    <span className={`badge badge-priority-${action.priority}`}>{action.priority}</span>{" "}
                    <strong>{action.action_type}</strong> - {action.reason}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="grid2">
          <div>
            <h3>Day Summary Report</h3>
            {!dayReport ? (
              <p>No report data.</p>
            ) : (
              <>
                <p>
                  Completed windows: {dayReport.completed_windows} | Delayed/Missed windows: {dayReport.delayed_or_missed_windows}
                </p>
                <p>Top follow-ups:</p>
                <ul>
                  {dayReport.top_caregiver_follow_up_items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </>
            )}
          </div>
          <div>
            <h3>Notification Events</h3>
            <pre>{JSON.stringify(medicationNotifications, null, 2)}</pre>
          </div>
        </div>

        <div className="grid2">
          <div>
            <h3>Sent Reminder Messages</h3>
            {medicationMessages.length === 0 ? (
              <p>No outbound messages yet.</p>
            ) : (
              <ul>
                {medicationMessages.map((message) => (
                  <li key={message.message_id}>
                    <strong>{message.window_slot_time}</strong> [{message.message_kind}] [{message.delivery_status}]{" "}
                    [{message.recipient_role}]
                    <br />
                    {message.content}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h3>Simulate Patient Reply</h3>
            <label>
              Window ID
              <input value={messageWindowId} onChange={(event) => setMessageWindowId(event.target.value)} />
            </label>
            <label>
              Reply
              <select value={messageReply} onChange={(event) => setMessageReply(event.target.value)}>
                <option value="TAKEN">TAKEN</option>
                <option value="DELAYED">DELAYED</option>
                <option value="SKIPPED">SKIPPED</option>
                <option value="UNSURE">UNSURE</option>
              </select>
            </label>
            <button onClick={() => void simulateMessageReply()}>Submit Reply</button>
          </div>
        </div>

        <div className="controls">
          <h3>Manual Dose Confirmation</h3>
          <label>
            Schedule Entry ID
            <input value={confirmEntryId} onChange={(event) => setConfirmEntryId(event.target.value)} />
          </label>
          <label>
            Scheduled Datetime (ISO)
            <input
              value={confirmScheduledAt}
              onChange={(event) => setConfirmScheduledAt(event.target.value)}
            />
          </label>
          <label>
            Status
            <select value={confirmStatus} onChange={(event) => setConfirmStatus(event.target.value)}>
              <option value="taken">taken</option>
              <option value="skipped">skipped</option>
              <option value="delayed">delayed</option>
              <option value="unsure">unsure</option>
            </select>
          </label>
          <label>
            Meal Condition Satisfied
            <select
              value={confirmMealSatisfied}
              onChange={(event) => setConfirmMealSatisfied(event.target.value)}
            >
              <option value="true">true</option>
              <option value="false">false</option>
            </select>
          </label>
          <button onClick={() => void submitDoseConfirmation()}>Submit Dose Confirmation</button>
        </div>

        <div className="controls">
          <h3>Manual Side-Effect Check-in</h3>
          <label>
            Feeling
            <input value={checkinFeeling} onChange={(event) => setCheckinFeeling(event.target.value)} />
          </label>
          <label>
            Breathlessness
            <input
              type="checkbox"
              checked={checkinBreathless}
              onChange={(event) => setCheckinBreathless(event.target.checked)}
            />
          </label>
          <label>
            Weakness
            <input
              type="checkbox"
              checked={checkinWeakness}
              onChange={(event) => setCheckinWeakness(event.target.checked)}
            />
          </label>
          <label>
            Note
            <input value={checkinNote} onChange={(event) => setCheckinNote(event.target.value)} />
          </label>
          <button onClick={() => void submitCheckin()}>Submit Check-in</button>
        </div>

        <div className="controls">
          <h3>Plan Import (JSON)</h3>
          <textarea value={importText} onChange={(event) => setImportText(event.target.value)} />
          <button onClick={() => void importPlan()}>Import Medication Plan</button>
        </div>
      </section>
    </main>
  );
}
