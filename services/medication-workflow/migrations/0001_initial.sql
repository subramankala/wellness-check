CREATE TABLE IF NOT EXISTS mw_patients (
    patient_id TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mw_plans (
    patient_id TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mw_daily_logs (
    patient_id TEXT NOT NULL,
    day TEXT NOT NULL,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (patient_id, day)
);

CREATE INDEX IF NOT EXISTS mw_daily_logs_patient_idx ON mw_daily_logs (patient_id);
CREATE INDEX IF NOT EXISTS mw_daily_logs_day_idx ON mw_daily_logs (day);

CREATE TABLE IF NOT EXISTS mw_runtime_state (
    state_key TEXT PRIMARY KEY,
    state_value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
