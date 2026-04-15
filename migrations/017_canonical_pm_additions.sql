-- ============================================================
-- Migration 016 -- Canonical PM additions: decisions registry
-- ============================================================
-- Session 2 (feat/canonical-connectors) lane.
-- Charter-original slot: 010_canonical_project_mgmt.sql
-- Real-repo slot: 016
--
-- Creates rex.meeting_decisions and rex.pending_decisions. The charter's
-- other PM entities (rfis, submittals, tasks, meetings, meeting_action_items,
-- daily_logs, inspections, observations, punch_items) already exist in
-- rex2_canonical_ddl and do not need reshaping.
--
-- Meeting decisions are DURABLE "we decided X in this meeting" rows.
-- Distinct from meeting_action_items which track follow-ups.
--
-- Pending decisions are decisions that need to be made but haven't been
-- yet. These drive the assistant's "pending decisions" nudge surface
-- and the control-plane decision backlog.
--
-- Idempotent: CREATE IF NOT EXISTS.
-- Depends on: rex.meetings, rex.projects, rex.people.
-- ============================================================


-- 1. rex.meeting_decisions ---------------------------------------------
-- Decisions captured in a meeting. One meeting can have many decisions.
-- Each decision has a title, a body, the decision owner, optional links
-- to the project entity it relates to.
CREATE TABLE IF NOT EXISTS rex.meeting_decisions (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id          uuid NOT NULL REFERENCES rex.meetings(id) ON DELETE CASCADE,
    project_id          uuid NOT NULL REFERENCES rex.projects(id) ON DELETE CASCADE,
    decision_number     int NOT NULL,
    title               text NOT NULL,
    body                text,
    decision_date       date NOT NULL,
    status              text NOT NULL DEFAULT 'recorded'
                          CHECK (status IN ('recorded','ratified','rescinded','superseded')),
    owner_person_id     uuid REFERENCES rex.people(id),
    related_entity_type text,
    related_entity_id   uuid,
    superseded_by_id    uuid REFERENCES rex.meeting_decisions(id),
    created_by          uuid REFERENCES rex.people(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (meeting_id, decision_number)
);

CREATE INDEX IF NOT EXISTS idx_rex_meeting_decisions_project ON rex.meeting_decisions (project_id);
CREATE INDEX IF NOT EXISTS idx_rex_meeting_decisions_status ON rex.meeting_decisions (status);
CREATE INDEX IF NOT EXISTS idx_rex_meeting_decisions_owner ON rex.meeting_decisions (owner_person_id);


-- 2. rex.pending_decisions ---------------------------------------------
-- Decisions that NEED to be made. Independent of any specific meeting
-- because a pending decision often pre-exists the meeting that
-- eventually resolves it. When a pending_decision gets resolved, a
-- meeting_decision is created and resolved_decision_id points back.
CREATE TABLE IF NOT EXISTS rex.pending_decisions (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES rex.projects(id) ON DELETE CASCADE,
    title               text NOT NULL,
    description         text,
    priority            text NOT NULL DEFAULT 'medium'
                          CHECK (priority IN ('low','medium','high','critical')),
    status              text NOT NULL DEFAULT 'open'
                          CHECK (status IN ('open','in_review','resolved','deferred','cancelled')),
    blocks_description  text,
    due_date            date,
    decision_maker_id   uuid REFERENCES rex.people(id),
    raised_by           uuid REFERENCES rex.people(id),
    raised_at           timestamptz NOT NULL DEFAULT now(),
    resolved_at         timestamptz,
    resolved_decision_id uuid REFERENCES rex.meeting_decisions(id),
    related_entity_type text,
    related_entity_id   uuid,
    notes               text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rex_pending_decisions_project ON rex.pending_decisions (project_id);
CREATE INDEX IF NOT EXISTS idx_rex_pending_decisions_status ON rex.pending_decisions (status);
CREATE INDEX IF NOT EXISTS idx_rex_pending_decisions_priority ON rex.pending_decisions (priority);
CREATE INDEX IF NOT EXISTS idx_rex_pending_decisions_maker ON rex.pending_decisions (decision_maker_id);


-- updated_at triggers
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rex_meeting_decisions_updated_at') THEN
        CREATE TRIGGER trg_rex_meeting_decisions_updated_at
            BEFORE UPDATE ON rex.meeting_decisions
            FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rex_pending_decisions_updated_at') THEN
        CREATE TRIGGER trg_rex_pending_decisions_updated_at
            BEFORE UPDATE ON rex.pending_decisions
            FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();
    END IF;
END $$;
