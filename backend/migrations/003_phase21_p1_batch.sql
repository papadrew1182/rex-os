-- Migration 003: Phase 21 P1 parity batch
-- Schedule actuals + WBS
ALTER TABLE rex.schedule_activities ADD COLUMN IF NOT EXISTS actual_start_date DATE;
ALTER TABLE rex.schedule_activities ADD COLUMN IF NOT EXISTS actual_finish_date DATE;
ALTER TABLE rex.schedule_activities ADD COLUMN IF NOT EXISTS wbs_code TEXT;

-- Completion milestones forecast + progress
ALTER TABLE rex.completion_milestones ADD COLUMN IF NOT EXISTS forecast_date DATE;
ALTER TABLE rex.completion_milestones ADD COLUMN IF NOT EXISTS percent_complete NUMERIC NOT NULL DEFAULT 0 CHECK (percent_complete >= 0 AND percent_complete <= 100);

-- Warranties product + manufacturer
ALTER TABLE rex.warranties ADD COLUMN IF NOT EXISTS system_or_product TEXT;
ALTER TABLE rex.warranties ADD COLUMN IF NOT EXISTS manufacturer TEXT;

-- Insurance certificates table
CREATE TABLE IF NOT EXISTS rex.insurance_certificates (
    id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES rex.companies(id),
    policy_type TEXT NOT NULL CHECK (policy_type IN ('gl','wc','auto','umbrella','other')),
    carrier TEXT,
    policy_number TEXT,
    effective_date DATE,
    expiry_date DATE,
    limit_amount NUMERIC,
    status TEXT NOT NULL DEFAULT 'current' CHECK (status IN ('current','expiring_soon','expired','missing')),
    attachment_id UUID,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_insurance_certs_company ON rex.insurance_certificates(company_id);
CREATE INDEX IF NOT EXISTS idx_insurance_certs_expiry ON rex.insurance_certificates(expiry_date);
