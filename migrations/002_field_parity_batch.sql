-- Migration 002: Field parity batch (Phases 3-5)
-- Phase 3: Commitment estimated completion date
ALTER TABLE rex.commitments ADD COLUMN IF NOT EXISTS estimated_completion_date DATE;

-- Phase 4: RFI manager, Punch closed_by + is_critical_path, Submittal manager + is_critical_path
ALTER TABLE rex.rfis ADD COLUMN IF NOT EXISTS rfi_manager UUID REFERENCES rex.people(id);
ALTER TABLE rex.punch_items ADD COLUMN IF NOT EXISTS closed_by UUID REFERENCES rex.people(id);
ALTER TABLE rex.punch_items ADD COLUMN IF NOT EXISTS is_critical_path BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE rex.submittals ADD COLUMN IF NOT EXISTS submittal_manager_id UUID REFERENCES rex.people(id);
ALTER TABLE rex.submittals ADD COLUMN IF NOT EXISTS is_critical_path BOOLEAN NOT NULL DEFAULT false;

-- Phase 5: Change event line items
CREATE TABLE IF NOT EXISTS rex.change_event_line_items (
    id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    change_event_id UUID NOT NULL REFERENCES rex.change_events(id),
    cost_code_id UUID REFERENCES rex.cost_codes(id),
    description TEXT NOT NULL,
    amount NUMERIC NOT NULL DEFAULT 0,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ce_line_items_event ON rex.change_event_line_items(change_event_id);
