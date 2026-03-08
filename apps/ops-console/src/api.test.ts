import { describe, expect, it, vi } from "vitest";

import { RuntimeApiClient } from "./api";

describe("RuntimeApiClient", () => {
  it("handles runtime list/detail/override flows", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{ session_id: "s1", protocol_id: "post_op_fever_v1" }]
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ summary: { session_id: "s1" }, session_state: {} })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ summary: { session_id: "s1" }, session_state: { final_effective_disposition: "callback" } })
      });

    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    const client = new RuntimeApiClient("http://localhost:8001", "http://localhost:8105");
    const list = await client.listSessions();
    expect(list[0].session_id).toBe("s1");

    const detail = await client.getSessionDetail("s1");
    expect(detail.summary.session_id).toBe("s1");

    const updated = await client.applyOverride("s1", {
      reviewer_id: "u1",
      reviewer_name: "Dr One",
      new_disposition: "callback",
      rationale: "reviewed",
      human_takeover: true
    });
    expect(updated.session_state.final_effective_disposition).toBe("callback");
  });

  it("handles medication dashboard and timeline flows", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ patient: { patient_id: "p1" }, due_now: [], upcoming: [], overdue: [], completed: [], skipped_or_delayed: [], active_alerts: [], side_effect_checkins: [], daily_adherence_score: 100, caregiver_summary_text: "ok", date: "2026-03-07" })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ patient_id: "p1", date: "2026-03-07", timeline: [] })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ patient_id: "p1", date: "2026-03-07", due_now: [], overdue: [], completed: [], symptom_alerts: [], caregiver_action_needed: [], end_of_day_summary: {} })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ patient_id: "p1", date: "2026-03-07", patient_timezone: "UTC", local_now: "2026-03-07T08:00:00+00:00", items: [] })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          patient_id: "p1",
          date: "2026-03-07",
          patient_timezone: "UTC",
          local_now: "2026-03-07T08:00:00+00:00",
          timeline: { patient_id: "p1", date: "2026-03-07", patient_timezone: "UTC", local_now: "2026-03-07T08:00:00+00:00", items: [] },
          completed_items: [],
          pending_items: [],
          overdue_items: [],
          next_item: null,
          caregiver_actions_needed: [],
          symptom_escalation_flags: [],
          medication_adherence_summary: {}
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ([])
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          patient_id: "p1",
          date: "2026-03-07",
          administration_windows: [],
          completed_windows: 0,
          delayed_or_missed_windows: 0,
          critical_missed_dose_events: [],
          symptom_alerts: [],
          caregiver_notifications: [],
          adherence_summary: {},
          top_caregiver_follow_up_items: []
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ([])
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          patient_id: "p1",
          date: "2026-03-07",
          patient_timezone: "UTC",
          local_now: "2026-03-07T08:00:00+00:00",
          sent_messages: []
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({})
      });

    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    const client = new RuntimeApiClient("http://localhost:8001", "http://localhost:8105");
    const dashboard = await client.getMedicationDashboard("p1", "2026-03-07");
    expect(dashboard.patient.patient_id).toBe("p1");

    const timeline = await client.getMedicationTimeline("p1", "2026-03-07");
    expect(timeline.patient_id).toBe("p1");

    const today = await client.getMedicationToday("p1");
    expect(today.patient_id).toBe("p1");

    const unified = await client.getUnifiedDailyTimeline("p1", "2026-03-07");
    expect(unified.patient_id).toBe("p1");

    const careOs = await client.getCareOsToday("p1");
    expect(careOs.patient_id).toBe("p1");

    const notifications = await client.getMedicationNotifications("p1", "2026-03-07");
    expect(notifications).toEqual([]);

    const report = await client.getMedicationSimulationDayReport("p1", "2026-03-07");
    expect(report.patient_id).toBe("p1");

    const messages = await client.getMedicationMessages("p1", "2026-03-07");
    expect(messages).toEqual([]);

    const send = await client.sendDueReminders("p1");
    expect(send.patient_id).toBe("p1");

    await client.submitMessageConfirmation("p1", {
      window_id: "window_1",
      confirmation: "taken"
    });
  });
});
