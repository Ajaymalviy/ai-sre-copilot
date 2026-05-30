-- AI SRE Copilot — PostgreSQL Schema
-- Yeh file automatically run hoti hai first boot pe

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Incidents Table ───────────────────────────
CREATE TABLE IF NOT EXISTS incidents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_name      VARCHAR(255) NOT NULL,
    severity        VARCHAR(50)  NOT NULL DEFAULT 'warning',  -- critical, warning, info
    status          VARCHAR(50)  NOT NULL DEFAULT 'open',     -- open, investigating, resolved, closed
    source          VARCHAR(100),                              -- prometheus, loki, etc.
    labels          JSONB        DEFAULT '{}',
    annotations     JSONB        DEFAULT '{}',
    fired_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── Agent Results Table ───────────────────────
CREATE TABLE IF NOT EXISTS agent_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id     UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    agent_name      VARCHAR(100) NOT NULL,   -- MetricsAgent, LogsAgent, etc.
    status          VARCHAR(50)  NOT NULL DEFAULT 'pending',  -- pending, running, done, failed
    input_data      JSONB        DEFAULT '{}',
    output_data     JSONB        DEFAULT '{}',
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── RCA Results Table ─────────────────────────
CREATE TABLE IF NOT EXISTS rca_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id     UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    root_cause      TEXT,
    confidence      FLOAT DEFAULT 0.0,       -- 0.0 to 1.0
    evidence        JSONB DEFAULT '{}',
    runbooks_used   JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Fix Proposals Table ───────────────────────
CREATE TABLE IF NOT EXISTS fix_proposals (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id     UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    fix_plan        TEXT NOT NULL,
    fix_commands    JSONB DEFAULT '[]',      -- actual kubectl/bash commands
    risk_level      VARCHAR(50) DEFAULT 'low',  -- low, medium, high
    status          VARCHAR(50) DEFAULT 'pending',  -- pending, approved, rejected, executed
    approved_by     VARCHAR(255),
    approved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── HITL Decisions Table ──────────────────────
CREATE TABLE IF NOT EXISTS hitl_decisions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id     UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    fix_proposal_id UUID REFERENCES fix_proposals(id),
    decision        VARCHAR(50) NOT NULL,    -- approved, rejected, escalated
    decided_by      VARCHAR(255),
    reason          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_incidents_status   ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity);
CREATE INDEX IF NOT EXISTS idx_incidents_fired_at ON incidents(fired_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_results_incident ON agent_results(incident_id);
CREATE INDEX IF NOT EXISTS idx_rca_incident       ON rca_results(incident_id);
CREATE INDEX IF NOT EXISTS idx_fix_incident       ON fix_proposals(incident_id);

-- ── Updated_at auto-trigger ───────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_incidents_updated_at
    BEFORE UPDATE ON incidents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ── Sample data (dev only) ────────────────────
INSERT INTO incidents (alert_name, severity, status, source, labels) VALUES
('HighCPUUsage',    'warning',  'open', 'prometheus', '{"service": "payment-api", "namespace": "production"}'),
('OOMKilled',       'critical', 'open', 'prometheus', '{"service": "auth-service",  "namespace": "production"}')
ON CONFLICT DO NOTHING;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sre_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO sre_user;
