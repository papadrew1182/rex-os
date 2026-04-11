-- ============================================================================
-- Rex 2.0 — Canonical DDL (All 6 Domains, 57 tables)
-- Generated: 2026-04-08
-- Convention: rex.* schema | uuid PKs | timestamptz | is_ booleans | text enums
-- Zero Procore columns — all external IDs via connector_mappings
--
-- Prerequisite: 001_create_schema.sql (creates rex schema + set_updated_at())
-- ============================================================================


-- ============================================================================
-- DOMAIN 1 — FOUNDATION (9 tables)
-- ============================================================================

-- 1. projects
CREATE TABLE IF NOT EXISTS rex.projects (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL,
    project_number  text,
    status          text NOT NULL CHECK (status IN ('active','inactive','archived','pre_construction','completed')),
    project_type    text CHECK (project_type IN ('retail','multifamily','commercial','industrial','residential','mixed_use')),
    address_line1   text,
    city            text,
    state           text,
    zip             text,
    start_date      date,
    end_date        date,
    contract_value  numeric,
    square_footage  numeric,
    description     text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- 2. companies
CREATE TABLE IF NOT EXISTS rex.companies (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name                text NOT NULL,
    trade               text,
    company_type        text NOT NULL CHECK (company_type IN ('subcontractor','supplier','architect','engineer','owner','gc','consultant')),
    status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','suspended','prequalified')),
    phone               text,
    email               text,
    address_line1       text,
    city                text,
    state               text,
    zip                 text,
    license_number      text,
    insurance_expiry    date,
    insurance_carrier   text,
    bonding_capacity    numeric,
    notes               text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- 3. people
CREATE TABLE IF NOT EXISTS rex.people (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      uuid REFERENCES rex.companies(id),
    first_name      text NOT NULL,
    last_name       text NOT NULL,
    email           text,
    phone           text,
    title           text,
    role_type       text NOT NULL CHECK (role_type IN ('internal','external')),
    is_active       boolean NOT NULL DEFAULT true,
    notes           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- 4. user_accounts
CREATE TABLE IF NOT EXISTS rex.user_accounts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id       uuid NOT NULL REFERENCES rex.people(id),
    email           text NOT NULL,
    password_hash   text NOT NULL,
    global_role     text CHECK (global_role IN ('vp','pm')),
    is_admin        boolean NOT NULL DEFAULT false,
    is_active       boolean NOT NULL DEFAULT true,
    mfa_secret      text,
    last_login      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_user_accounts_person_id UNIQUE (person_id),
    CONSTRAINT uq_user_accounts_email     UNIQUE (email)
);

-- 5. sessions
CREATE TABLE IF NOT EXISTS rex.sessions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_account_id uuid NOT NULL REFERENCES rex.user_accounts(id),
    token_hash      text NOT NULL,
    device_info     text,
    expires_at      timestamptz NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- 6. role_templates
CREATE TABLE IF NOT EXISTS rex.role_templates (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    text NOT NULL,
    slug                    text NOT NULL UNIQUE,
    description             text,
    is_internal             boolean NOT NULL DEFAULT true,
    default_access_level    text NOT NULL CHECK (default_access_level IN ('admin','standard','read_only','field_only')),
    visible_tools           jsonb NOT NULL DEFAULT '[]'::jsonb,
    visible_panels          jsonb NOT NULL DEFAULT '[]'::jsonb,
    quick_action_groups     jsonb NOT NULL DEFAULT '[]'::jsonb,
    can_write               jsonb NOT NULL DEFAULT '[]'::jsonb,
    can_approve             jsonb NOT NULL DEFAULT '[]'::jsonb,
    notification_defaults   jsonb NOT NULL DEFAULT '{}'::jsonb,
    home_screen             text NOT NULL DEFAULT 'my_day' CHECK (home_screen IN ('my_day','portfolio','field_ops','financials')),
    is_system               boolean NOT NULL DEFAULT false,
    sort_order              int NOT NULL DEFAULT 0,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- 7. project_members
CREATE TABLE IF NOT EXISTS rex.project_members (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES rex.projects(id),
    person_id           uuid NOT NULL REFERENCES rex.people(id),
    company_id          uuid REFERENCES rex.companies(id),
    role_template_id    uuid REFERENCES rex.role_templates(id),
    access_level        text CHECK (access_level IN ('admin','standard','read_only','field_only')),
    is_primary          boolean NOT NULL DEFAULT false,
    is_active           boolean NOT NULL DEFAULT true,
    start_date          date,
    end_date            date,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_project_members_project_person UNIQUE (project_id, person_id)
);

-- One active primary per project+role
CREATE UNIQUE INDEX IF NOT EXISTS uq_project_members_active_primary
    ON rex.project_members (project_id, role_template_id)
    WHERE is_primary = true AND is_active = true;

-- 8. role_template_overrides
CREATE TABLE IF NOT EXISTS rex.role_template_overrides (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_member_id   uuid NOT NULL REFERENCES rex.project_members(id),
    override_key        text NOT NULL,
    override_value      jsonb NOT NULL,
    override_mode       text NOT NULL CHECK (override_mode IN ('replace','add','remove')),
    reason              text,
    created_by          uuid REFERENCES rex.people(id),
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- 9. connector_mappings (universal — used by all domains)
CREATE TABLE IF NOT EXISTS rex.connector_mappings (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rex_table       text NOT NULL,
    rex_id          uuid NOT NULL,
    connector       text NOT NULL,
    external_id     text NOT NULL,
    external_url    text,
    synced_at       timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_connector_mapping UNIQUE (rex_table, connector, external_id)
);

CREATE INDEX IF NOT EXISTS idx_connector_mappings_rex
    ON rex.connector_mappings(rex_table, rex_id);


-- ============================================================================
-- DOMAIN 2 — SCHEDULE (5 tables)
-- ============================================================================

-- 10. schedules
CREATE TABLE IF NOT EXISTS rex.schedules (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid NOT NULL REFERENCES rex.projects(id),
    name            text NOT NULL,
    schedule_type   text NOT NULL CHECK (schedule_type IN ('master','baseline','lookahead','what_if')),
    status          text NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived','draft')),
    start_date      date NOT NULL,
    end_date        date,
    created_by      uuid REFERENCES rex.people(id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- 11. schedule_activities
CREATE TABLE IF NOT EXISTS rex.schedule_activities (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id             uuid NOT NULL REFERENCES rex.schedules(id),
    parent_id               uuid REFERENCES rex.schedule_activities(id),
    activity_number         text,
    name                    text NOT NULL,
    activity_type           text NOT NULL CHECK (activity_type IN ('task','milestone','section','hammock')),
    start_date              date NOT NULL,
    end_date                date NOT NULL,
    duration_days           int,
    percent_complete        numeric NOT NULL DEFAULT 0 CHECK (percent_complete >= 0 AND percent_complete <= 100),
    is_critical             boolean NOT NULL DEFAULT false,
    is_manually_scheduled   boolean NOT NULL DEFAULT false,
    baseline_start          date,
    baseline_end            date,
    variance_days           int,
    float_days              int,
    assigned_company_id     uuid REFERENCES rex.companies(id),
    assigned_person_id      uuid REFERENCES rex.people(id),
    cost_code_id            uuid,                                       -- FK deferred until cost_codes exists
    location                text,
    notes                   text,
    sort_order              int NOT NULL DEFAULT 0,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- 12. activity_links
CREATE TABLE IF NOT EXISTS rex.activity_links (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id         uuid NOT NULL REFERENCES rex.schedules(id),
    from_activity_id    uuid NOT NULL REFERENCES rex.schedule_activities(id),
    to_activity_id      uuid NOT NULL REFERENCES rex.schedule_activities(id),
    link_type           text NOT NULL DEFAULT 'fs' CHECK (link_type IN ('fs','ff','ss','sf')),
    lag_days            int NOT NULL DEFAULT 0,
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- 13. schedule_constraints
CREATE TABLE IF NOT EXISTS rex.schedule_constraints (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_id         uuid NOT NULL REFERENCES rex.schedule_activities(id),
    constraint_type     text NOT NULL CHECK (constraint_type IN (
                            'rfi_pending','submittal_pending','no_commitment',
                            'insurance_expired','permit_pending','material_lead','inspection_required')),
    source_type         text NOT NULL CHECK (source_type IN ('rfi','submittal','commitment','insurance','permit','inspection')),
    source_id           uuid,
    status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active','resolved','overridden')),
    severity            text NOT NULL CHECK (severity IN ('green','yellow','red')),
    notes               text,
    resolved_at         timestamptz,
    resolved_by         uuid REFERENCES rex.people(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- 14. schedule_snapshots
CREATE TABLE IF NOT EXISTS rex.schedule_snapshots (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_id         uuid NOT NULL REFERENCES rex.schedule_activities(id),
    snapshot_date       date NOT NULL,
    start_date          date NOT NULL,
    end_date            date NOT NULL,
    percent_complete    numeric NOT NULL DEFAULT 0,
    is_critical         boolean NOT NULL DEFAULT false,
    variance_days       int,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_schedule_snapshots_activity_date UNIQUE (activity_id, snapshot_date)
);


-- ============================================================================
-- DOMAIN 3 — FIELD OPS (12 tables)
-- ============================================================================

-- 15. daily_logs
CREATE TABLE IF NOT EXISTS rex.daily_logs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid NOT NULL REFERENCES rex.projects(id),
    log_date        date NOT NULL,
    status          text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','submitted','approved')),
    weather_summary text,
    temp_high_f     int,
    temp_low_f      int,
    is_weather_delay boolean NOT NULL DEFAULT false,
    work_summary    text,
    delay_notes     text,
    safety_notes    text,
    visitor_notes   text,
    created_by      uuid REFERENCES rex.people(id),
    approved_by     uuid REFERENCES rex.people(id),
    approved_at     timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id, log_date)
);

-- 16. manpower_entries
CREATE TABLE IF NOT EXISTS rex.manpower_entries (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    daily_log_id    uuid NOT NULL REFERENCES rex.daily_logs(id),
    company_id      uuid NOT NULL REFERENCES rex.companies(id),
    worker_count    int NOT NULL,
    hours           numeric NOT NULL,
    description     text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE(daily_log_id, company_id)
);

-- 17. punch_items
CREATE TABLE IF NOT EXISTS rex.punch_items (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES rex.projects(id),
    punch_number        int NOT NULL,
    title               text NOT NULL,
    description         text,
    status              text NOT NULL DEFAULT 'draft' CHECK (status IN (
                            'draft','open','work_required','ready_for_review','ready_to_close','closed')),
    priority            text NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high')),
    punch_type          text,
    assigned_company_id uuid REFERENCES rex.companies(id),
    assigned_to         uuid REFERENCES rex.people(id),
    punch_manager_id    uuid REFERENCES rex.people(id),
    final_approver_id   uuid REFERENCES rex.people(id),
    location            text,
    drawing_id          uuid,                                           -- FK deferred until drawings exists
    cost_code_id        uuid,                                           -- FK deferred until cost_codes exists
    cost_impact         text CHECK (cost_impact IN ('yes','no','tbd')),
    schedule_impact     text CHECK (schedule_impact IN ('yes','no','tbd')),
    due_date            date,
    closed_date         date,
    days_open           int,
    created_by          uuid REFERENCES rex.people(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- 18. inspections
CREATE TABLE IF NOT EXISTS rex.inspections (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              uuid NOT NULL REFERENCES rex.projects(id),
    inspection_number       text NOT NULL,
    title                   text NOT NULL,
    inspection_type         text NOT NULL CHECK (inspection_type IN (
                                'municipal','quality','safety','pre_concrete','framing',
                                'mep_rough','mep_final','other')),
    status                  text NOT NULL DEFAULT 'scheduled' CHECK (status IN (
                                'scheduled','in_progress','passed','failed','partial','cancelled')),
    scheduled_date          date NOT NULL,
    completed_date          date,
    inspector_name          text,
    inspecting_company_id   uuid REFERENCES rex.companies(id),
    responsible_person_id   uuid REFERENCES rex.people(id),
    location                text,
    activity_id             uuid REFERENCES rex.schedule_activities(id),
    comments                text,
    created_by              uuid REFERENCES rex.people(id),
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- 19. inspection_items
CREATE TABLE IF NOT EXISTS rex.inspection_items (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inspection_id   uuid NOT NULL REFERENCES rex.inspections(id),
    item_number     int NOT NULL,
    description     text NOT NULL,
    result          text NOT NULL CHECK (result IN ('pass','fail','n_a','not_inspected')),
    comments        text,
    punch_item_id   uuid REFERENCES rex.punch_items(id),
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- 20. observations
CREATE TABLE IF NOT EXISTS rex.observations (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              uuid NOT NULL REFERENCES rex.projects(id),
    observation_number      int NOT NULL,
    title                   text NOT NULL,
    observation_type        text NOT NULL CHECK (observation_type IN (
                                'safety','quality','housekeeping','environmental','commissioning')),
    status                  text NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','closed')),
    priority                text NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high','critical')),
    description             text NOT NULL,
    corrective_action       text,
    location                text,
    assigned_to             uuid REFERENCES rex.people(id),
    assigned_company_id     uuid REFERENCES rex.companies(id),
    due_date                date,
    closed_date             date,
    created_by              uuid REFERENCES rex.people(id),
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- 21. safety_incidents
CREATE TABLE IF NOT EXISTS rex.safety_incidents (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              uuid NOT NULL REFERENCES rex.projects(id),
    incident_number         text NOT NULL,
    title                   text NOT NULL,
    incident_type           text NOT NULL CHECK (incident_type IN (
                                'near_miss','first_aid','recordable','lost_time','property_damage','environmental')),
    severity                text NOT NULL CHECK (severity IN ('minor','moderate','serious','critical')),
    status                  text NOT NULL DEFAULT 'open' CHECK (status IN (
                                'open','under_investigation','corrective_action','closed')),
    incident_date           date NOT NULL,
    incident_time           time,
    location                text,
    description             text NOT NULL,
    root_cause              text,
    corrective_action       text,
    affected_person_id      uuid REFERENCES rex.people(id),
    affected_company_id     uuid REFERENCES rex.companies(id),
    reported_by             uuid REFERENCES rex.people(id),
    is_osha_recordable      boolean NOT NULL DEFAULT false,
    lost_time_days          int,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- 22. photo_albums
CREATE TABLE IF NOT EXISTS rex.photo_albums (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid NOT NULL REFERENCES rex.projects(id),
    name            text NOT NULL,
    description     text,
    is_default      boolean NOT NULL DEFAULT false,
    sort_order      int NOT NULL DEFAULT 0,
    created_by      uuid REFERENCES rex.people(id),
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- 23. photos
CREATE TABLE IF NOT EXISTS rex.photos (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid NOT NULL REFERENCES rex.projects(id),
    photo_album_id  uuid REFERENCES rex.photo_albums(id),
    filename        text NOT NULL,
    file_size       bigint NOT NULL,
    content_type    text NOT NULL,
    storage_url     text NOT NULL,
    storage_key     text NOT NULL,
    thumbnail_url   text,
    taken_at        timestamptz,
    location        text,
    latitude        numeric,
    longitude       numeric,
    description     text,
    tags            jsonb,
    source_type     text,
    source_id       uuid,
    uploaded_by     uuid REFERENCES rex.people(id),
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_photos_source
    ON rex.photos(source_type, source_id);

-- 24. tasks
CREATE TABLE IF NOT EXISTS rex.tasks (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              uuid NOT NULL REFERENCES rex.projects(id),
    task_number             int NOT NULL,
    title                   text NOT NULL,
    description             text,
    status                  text NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','complete','void')),
    priority                text NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high')),
    category                text CHECK (category IN ('safety','quality','coordination','admin','closeout','hygiene')),
    assigned_to             uuid REFERENCES rex.people(id),
    assigned_company_id     uuid REFERENCES rex.companies(id),
    due_date                date NOT NULL,
    completed_date          date,
    created_by              uuid REFERENCES rex.people(id),
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- 25. meetings
CREATE TABLE IF NOT EXISTS rex.meetings (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid NOT NULL REFERENCES rex.projects(id),
    meeting_type    text NOT NULL,
    title           text NOT NULL,
    meeting_date    date NOT NULL,
    start_time      time,
    end_time        time,
    location        text,
    agenda          text,
    minutes         text,
    attendees       jsonb,
    packet_url      text,
    created_by      uuid REFERENCES rex.people(id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- 26. meeting_action_items
CREATE TABLE IF NOT EXISTS rex.meeting_action_items (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id      uuid NOT NULL REFERENCES rex.meetings(id),
    item_number     int NOT NULL,
    description     text NOT NULL,
    assigned_to     uuid REFERENCES rex.people(id),
    due_date        date,
    status          text NOT NULL DEFAULT 'open' CHECK (status IN ('open','complete','void')),
    task_id         uuid REFERENCES rex.tasks(id),
    created_at      timestamptz NOT NULL DEFAULT now()
);


-- ============================================================================
-- DOMAIN 4 — FINANCIALS (14 tables)
-- ============================================================================

-- 27. cost_codes
CREATE TABLE IF NOT EXISTS rex.cost_codes (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid NOT NULL REFERENCES rex.projects(id),
    code            text NOT NULL,
    name            text NOT NULL,
    parent_id       uuid REFERENCES rex.cost_codes(id),
    cost_type       text NOT NULL CHECK (cost_type IN ('labor','material','equipment','subcontract','other')),
    sort_order      int NOT NULL DEFAULT 0,
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_cost_codes_project_code UNIQUE (project_id, code)
);

-- Deferred FK: schedule_activities.cost_code_id → cost_codes
DO $$ BEGIN
    ALTER TABLE rex.schedule_activities
        ADD CONSTRAINT fk_schedule_activities_cost_code
        FOREIGN KEY (cost_code_id) REFERENCES rex.cost_codes(id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 28. budget_line_items
CREATE TABLE IF NOT EXISTS rex.budget_line_items (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES rex.projects(id),
    cost_code_id        uuid NOT NULL REFERENCES rex.cost_codes(id),
    description         text,
    original_budget     numeric NOT NULL DEFAULT 0,
    approved_changes    numeric NOT NULL DEFAULT 0,
    revised_budget      numeric NOT NULL DEFAULT 0,
    committed_costs     numeric NOT NULL DEFAULT 0,
    direct_costs        numeric NOT NULL DEFAULT 0,
    pending_changes     numeric NOT NULL DEFAULT 0,
    projected_cost      numeric NOT NULL DEFAULT 0,
    over_under          numeric NOT NULL DEFAULT 0,
    notes               text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- 29. budget_snapshots
CREATE TABLE IF NOT EXISTS rex.budget_snapshots (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES rex.projects(id),
    budget_line_item_id uuid NOT NULL REFERENCES rex.budget_line_items(id),
    snapshot_date       date NOT NULL,
    revised_budget      numeric NOT NULL,
    projected_cost      numeric NOT NULL,
    over_under          numeric NOT NULL,
    committed_costs     numeric NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_budget_snapshots_item_date UNIQUE (budget_line_item_id, snapshot_date)
);

-- 30. prime_contracts
CREATE TABLE IF NOT EXISTS rex.prime_contracts (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES rex.projects(id),
    contract_number     text NOT NULL,
    title               text NOT NULL,
    status              text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','executed','closed')),
    original_value      numeric NOT NULL DEFAULT 0,
    approved_cos        numeric NOT NULL DEFAULT 0,
    revised_value       numeric NOT NULL DEFAULT 0,
    billed_to_date      numeric NOT NULL DEFAULT 0,
    retention_rate      numeric NOT NULL DEFAULT 10,
    executed_date       date,
    owner_company_id    uuid REFERENCES rex.companies(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- 31. commitments
CREATE TABLE IF NOT EXISTS rex.commitments (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              uuid NOT NULL REFERENCES rex.projects(id),
    vendor_id               uuid NOT NULL REFERENCES rex.companies(id),
    commitment_number       text NOT NULL,
    title                   text NOT NULL,
    contract_type           text NOT NULL CHECK (contract_type IN ('subcontract','purchase_order','service_agreement')),
    status                  text NOT NULL DEFAULT 'draft' CHECK (status IN (
                                'draft','out_for_bid','approved','executed','closed','void')),
    executed_date           date,
    original_value          numeric NOT NULL DEFAULT 0,
    approved_cos            numeric NOT NULL DEFAULT 0,
    revised_value           numeric NOT NULL DEFAULT 0,
    invoiced_to_date        numeric NOT NULL DEFAULT 0,
    remaining_to_invoice    numeric NOT NULL DEFAULT 0,
    retention_rate          numeric NOT NULL DEFAULT 10,
    retention_held          numeric NOT NULL DEFAULT 0,
    scope_of_work           text,
    notes                   text,
    created_by              uuid REFERENCES rex.people(id),
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- 32. commitment_line_items
CREATE TABLE IF NOT EXISTS rex.commitment_line_items (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    commitment_id   uuid NOT NULL REFERENCES rex.commitments(id),
    cost_code_id    uuid NOT NULL REFERENCES rex.cost_codes(id),
    description     text NOT NULL,
    quantity        numeric NOT NULL DEFAULT 0,
    unit            text,
    unit_cost       numeric NOT NULL DEFAULT 0,
    amount          numeric NOT NULL DEFAULT 0,
    sort_order      int NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- 33. change_events
CREATE TABLE IF NOT EXISTS rex.change_events (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES rex.projects(id),
    event_number        text NOT NULL,
    title               text NOT NULL,
    description         text,
    status              text NOT NULL DEFAULT 'open' CHECK (status IN ('open','pending','approved','closed','void')),
    change_reason       text NOT NULL CHECK (change_reason IN (
                            'owner_change','design_change','unforeseen','allowance','contingency')),
    event_type          text NOT NULL CHECK (event_type IN ('tbd','allowance','contingency','owner_change','transfer')),
    scope               text NOT NULL DEFAULT 'tbd' CHECK (scope IN ('in_scope','out_of_scope','tbd')),
    estimated_amount    numeric NOT NULL DEFAULT 0,
    rfi_id              uuid,                                           -- FK deferred until rfis exists
    prime_contract_id   uuid REFERENCES rex.prime_contracts(id),
    created_by          uuid REFERENCES rex.people(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- 34. potential_change_orders
CREATE TABLE IF NOT EXISTS rex.potential_change_orders (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    change_event_id     uuid NOT NULL REFERENCES rex.change_events(id),
    commitment_id       uuid NOT NULL REFERENCES rex.commitments(id),
    pco_number          text NOT NULL,
    title               text NOT NULL,
    status              text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','pending','approved','rejected','void')),
    amount              numeric NOT NULL DEFAULT 0,
    cost_code_id        uuid REFERENCES rex.cost_codes(id),
    description         text,
    created_by          uuid REFERENCES rex.people(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- 35. commitment_change_orders
CREATE TABLE IF NOT EXISTS rex.commitment_change_orders (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    commitment_id       uuid NOT NULL REFERENCES rex.commitments(id),
    cco_number          text NOT NULL,
    title               text NOT NULL,
    status              text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','pending','approved','executed','void')),
    total_amount        numeric NOT NULL DEFAULT 0,
    executed_date       date,
    description         text,
    created_by          uuid REFERENCES rex.people(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- 36. pco_cco_links
CREATE TABLE IF NOT EXISTS rex.pco_cco_links (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pco_id          uuid NOT NULL REFERENCES rex.potential_change_orders(id),
    cco_id          uuid NOT NULL REFERENCES rex.commitment_change_orders(id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE(pco_id, cco_id)
);

-- 37. billing_periods
CREATE TABLE IF NOT EXISTS rex.billing_periods (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid NOT NULL REFERENCES rex.projects(id),
    period_number   int NOT NULL,
    start_date      date NOT NULL,
    end_date        date NOT NULL,
    due_date        date NOT NULL,
    status          text NOT NULL DEFAULT 'open' CHECK (status IN ('open','locked','closed')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_billing_periods_project_number UNIQUE (project_id, period_number)
);

-- 38. direct_costs
CREATE TABLE IF NOT EXISTS rex.direct_costs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid NOT NULL REFERENCES rex.projects(id),
    cost_code_id    uuid NOT NULL REFERENCES rex.cost_codes(id),
    vendor_id       uuid REFERENCES rex.companies(id),
    description     text NOT NULL,
    amount          numeric NOT NULL DEFAULT 0,
    direct_cost_date date NOT NULL,
    invoice_number  text,
    payment_method  text CHECK (payment_method IN ('check','ach','credit_card','wire')),
    created_by      uuid REFERENCES rex.people(id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- 39. payment_applications
CREATE TABLE IF NOT EXISTS rex.payment_applications (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    commitment_id           uuid NOT NULL REFERENCES rex.commitments(id),
    billing_period_id       uuid NOT NULL REFERENCES rex.billing_periods(id),
    pay_app_number          int NOT NULL,
    status                  text NOT NULL DEFAULT 'draft' CHECK (status IN (
                                'draft','submitted','under_review','approved','paid','rejected')),
    period_start            date NOT NULL,
    period_end              date NOT NULL,
    this_period_amount      numeric NOT NULL DEFAULT 0,
    total_completed         numeric NOT NULL DEFAULT 0,
    retention_held          numeric NOT NULL DEFAULT 0,
    retention_released      numeric NOT NULL DEFAULT 0,
    net_payment_due         numeric NOT NULL DEFAULT 0,
    submitted_date          date,
    approved_date           date,
    paid_date               date,
    created_by              uuid REFERENCES rex.people(id),
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- 40. lien_waivers
CREATE TABLE IF NOT EXISTS rex.lien_waivers (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_application_id  uuid NOT NULL REFERENCES rex.payment_applications(id),
    vendor_id               uuid NOT NULL REFERENCES rex.companies(id),
    waiver_type             text NOT NULL CHECK (waiver_type IN (
                                'conditional_progress','unconditional_progress',
                                'conditional_final','unconditional_final')),
    status                  text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','received','approved','missing')),
    amount                  numeric NOT NULL DEFAULT 0,
    through_date            date NOT NULL,
    received_date           date,
    attachment_id           uuid,                                       -- FK deferred until attachments exists
    notes                   text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- Deferred FK: punch_items.cost_code_id → cost_codes
DO $$ BEGIN
    ALTER TABLE rex.punch_items
        ADD CONSTRAINT fk_punch_items_cost_code
        FOREIGN KEY (cost_code_id) REFERENCES rex.cost_codes(id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- ============================================================================
-- DOMAIN 5 — DOCUMENT MANAGEMENT (9 tables)
-- ============================================================================

-- 41. drawing_areas
CREATE TABLE IF NOT EXISTS rex.drawing_areas (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid NOT NULL REFERENCES rex.projects(id),
    name            text NOT NULL,
    sort_order      int NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- 42. drawings
CREATE TABLE IF NOT EXISTS rex.drawings (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              uuid NOT NULL REFERENCES rex.projects(id),
    drawing_area_id         uuid NOT NULL REFERENCES rex.drawing_areas(id),
    drawing_number          text NOT NULL,
    title                   text NOT NULL,
    discipline              text NOT NULL CHECK (discipline IN (
                                'architectural','structural','mechanical','electrical','plumbing','civil')),
    current_revision        int NOT NULL DEFAULT 0,
    current_revision_date   date,
    is_current              boolean NOT NULL DEFAULT true,
    image_url               text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- 43. drawing_revisions
CREATE TABLE IF NOT EXISTS rex.drawing_revisions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    drawing_id      uuid NOT NULL REFERENCES rex.drawings(id),
    revision_number int NOT NULL,
    revision_date   date NOT NULL,
    description     text,
    image_url       text NOT NULL,
    uploaded_by     uuid REFERENCES rex.people(id),
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Deferred FK: punch_items.drawing_id → drawings
DO $$ BEGIN
    ALTER TABLE rex.punch_items
        ADD CONSTRAINT fk_punch_items_drawing
        FOREIGN KEY (drawing_id) REFERENCES rex.drawings(id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 44. specifications
CREATE TABLE IF NOT EXISTS rex.specifications (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES rex.projects(id),
    section_number      text NOT NULL,
    title               text NOT NULL,
    division            text NOT NULL,
    current_revision    int NOT NULL DEFAULT 0,
    revision_date       date,
    attachment_id       uuid,                                           -- FK deferred until attachments exists
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- 45. rfis
CREATE TABLE IF NOT EXISTS rex.rfis (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid NOT NULL REFERENCES rex.projects(id),
    rfi_number      text NOT NULL,
    subject         text NOT NULL,
    status          text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','open','answered','closed','void')),
    priority        text NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high')),
    question        text NOT NULL,
    answer          text,
    cost_impact     text CHECK (cost_impact IN ('yes','no','tbd')),
    schedule_impact text CHECK (schedule_impact IN ('yes','no','tbd')),
    cost_code_id    uuid REFERENCES rex.cost_codes(id),
    assigned_to     uuid REFERENCES rex.people(id),
    ball_in_court   uuid REFERENCES rex.people(id),
    created_by      uuid REFERENCES rex.people(id),
    due_date        date,
    answered_date   date,
    days_open       int,
    drawing_id      uuid REFERENCES rex.drawings(id),
    spec_section    text,
    location        text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- Deferred FK: change_events.rfi_id → rfis
DO $$ BEGIN
    ALTER TABLE rex.change_events
        ADD CONSTRAINT fk_change_events_rfi
        FOREIGN KEY (rfi_id) REFERENCES rex.rfis(id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 46. submittal_packages
CREATE TABLE IF NOT EXISTS rex.submittal_packages (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid NOT NULL REFERENCES rex.projects(id),
    package_number  text NOT NULL,
    title           text NOT NULL,
    status          text NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
    total_submittals int NOT NULL DEFAULT 0,
    approved_count  int NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- 47. submittals
CREATE TABLE IF NOT EXISTS rex.submittals (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              uuid NOT NULL REFERENCES rex.projects(id),
    submittal_package_id    uuid REFERENCES rex.submittal_packages(id),
    submittal_number        text NOT NULL,
    title                   text NOT NULL,
    status                  text NOT NULL DEFAULT 'draft' CHECK (status IN (
                                'draft','pending','submitted','approved','approved_as_noted','rejected','closed')),
    submittal_type          text NOT NULL CHECK (submittal_type IN (
                                'shop_drawing','product_data','sample','mock_up','test_report','other')),
    spec_section            text,
    current_revision        int NOT NULL DEFAULT 0,
    cost_code_id            uuid REFERENCES rex.cost_codes(id),
    schedule_activity_id    uuid REFERENCES rex.schedule_activities(id),
    assigned_to             uuid REFERENCES rex.people(id),
    ball_in_court           uuid REFERENCES rex.people(id),
    responsible_contractor  uuid REFERENCES rex.companies(id),
    created_by              uuid REFERENCES rex.people(id),
    due_date                date,
    submitted_date          date,
    approved_date           date,
    lead_time_days          int,
    required_on_site        date,
    location                text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- 48. attachments (polymorphic)
CREATE TABLE IF NOT EXISTS rex.attachments (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid NOT NULL REFERENCES rex.projects(id),
    source_type     text NOT NULL,
    source_id       uuid NOT NULL,
    filename        text NOT NULL,
    file_size       bigint NOT NULL,
    content_type    text NOT NULL,
    storage_url     text NOT NULL,
    storage_key     text NOT NULL,
    uploaded_by     uuid REFERENCES rex.people(id),
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_attachments_source
    ON rex.attachments(source_type, source_id);

-- Deferred FK: lien_waivers.attachment_id → attachments
DO $$ BEGIN
    ALTER TABLE rex.lien_waivers
        ADD CONSTRAINT fk_lien_waivers_attachment
        FOREIGN KEY (attachment_id) REFERENCES rex.attachments(id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Deferred FK: specifications.attachment_id → attachments
DO $$ BEGIN
    ALTER TABLE rex.specifications
        ADD CONSTRAINT fk_specifications_attachment
        FOREIGN KEY (attachment_id) REFERENCES rex.attachments(id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 49. correspondence
CREATE TABLE IF NOT EXISTS rex.correspondence (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              uuid NOT NULL REFERENCES rex.projects(id),
    correspondence_number   text NOT NULL,
    subject                 text NOT NULL,
    correspondence_type     text NOT NULL CHECK (correspondence_type IN (
                                'letter','email','memo','notice','transmittal')),
    status                  text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','sent','received','closed')),
    from_person_id          uuid REFERENCES rex.people(id),
    to_person_id            uuid REFERENCES rex.people(id),
    body                    text,
    sent_date               date,
    received_date           date,
    created_by              uuid REFERENCES rex.people(id),
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);


-- ============================================================================
-- DOMAIN 6 — CLOSEOUT & WARRANTY (8 tables)
-- ============================================================================

-- 50. closeout_templates
CREATE TABLE IF NOT EXISTS rex.closeout_templates (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL,
    project_type    text NOT NULL CHECK (project_type IN ('retail','multifamily','all')),
    is_default      boolean NOT NULL DEFAULT false,
    created_by      uuid REFERENCES rex.people(id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- 51. closeout_template_items
CREATE TABLE IF NOT EXISTS rex.closeout_template_items (
    id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id                 uuid NOT NULL REFERENCES rex.closeout_templates(id),
    category                    text NOT NULL CHECK (category IN ('documentation','general','mep','exterior','interior')),
    item_number                 int NOT NULL,
    name                        text NOT NULL,
    default_assignee_role       text CHECK (default_assignee_role IN ('vp','general_super','lead_super','asst_super','accountant')),
    days_before_substantial     int,
    sort_order                  int NOT NULL DEFAULT 0,
    created_at                  timestamptz NOT NULL DEFAULT now()
);

-- 52. closeout_checklists
CREATE TABLE IF NOT EXISTS rex.closeout_checklists (
    id                              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id                      uuid NOT NULL REFERENCES rex.projects(id),
    template_id                     uuid REFERENCES rex.closeout_templates(id),
    substantial_completion_date     date,
    total_items                     int NOT NULL DEFAULT 0,
    completed_items                 int NOT NULL DEFAULT 0,
    percent_complete                numeric NOT NULL DEFAULT 0,
    created_by                      uuid REFERENCES rex.people(id),
    created_at                      timestamptz NOT NULL DEFAULT now(),
    updated_at                      timestamptz NOT NULL DEFAULT now()
);

-- 53. closeout_checklist_items
CREATE TABLE IF NOT EXISTS rex.closeout_checklist_items (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    checklist_id            uuid NOT NULL REFERENCES rex.closeout_checklists(id),
    category                text NOT NULL CHECK (category IN ('documentation','general','mep','exterior','interior')),
    item_number             int NOT NULL,
    name                    text NOT NULL,
    status                  text NOT NULL DEFAULT 'not_started' CHECK (status IN ('not_started','in_progress','complete','n_a')),
    assigned_company_id     uuid REFERENCES rex.companies(id),
    assigned_person_id      uuid REFERENCES rex.people(id),
    due_date                date,
    completed_date          date,
    completed_by            uuid REFERENCES rex.people(id),
    notes                   text,
    sort_order              int NOT NULL DEFAULT 0,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- 54. warranties
CREATE TABLE IF NOT EXISTS rex.warranties (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          uuid NOT NULL REFERENCES rex.projects(id),
    commitment_id       uuid REFERENCES rex.commitments(id),
    company_id          uuid NOT NULL REFERENCES rex.companies(id),
    cost_code_id        uuid REFERENCES rex.cost_codes(id),
    scope_description   text NOT NULL,
    warranty_type       text NOT NULL CHECK (warranty_type IN (
                            'standard','extended','manufacturer','labor_only','material_only')),
    duration_months     int NOT NULL,
    start_date          date NOT NULL,
    expiration_date     date NOT NULL,
    status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active','expiring_soon','expired','claimed')),
    is_letter_received  boolean NOT NULL DEFAULT false,
    is_om_received      boolean NOT NULL DEFAULT false,
    notes               text,
    created_by          uuid REFERENCES rex.people(id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- 55. warranty_claims
CREATE TABLE IF NOT EXISTS rex.warranty_claims (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    warranty_id             uuid NOT NULL REFERENCES rex.warranties(id),
    claim_number            int NOT NULL,
    title                   text NOT NULL,
    description             text NOT NULL,
    status                  text NOT NULL DEFAULT 'open' CHECK (status IN (
                                'open','in_progress','resolved','disputed','closed')),
    priority                text NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high','critical')),
    reported_date           date NOT NULL,
    resolved_date           date,
    days_open               int,
    location                text,
    cost_to_repair          numeric,
    is_covered_by_warranty  boolean NOT NULL DEFAULT true,
    reported_by             uuid REFERENCES rex.people(id),
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- 56. warranty_alerts
CREATE TABLE IF NOT EXISTS rex.warranty_alerts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    warranty_id     uuid NOT NULL REFERENCES rex.warranties(id),
    alert_type      text NOT NULL CHECK (alert_type IN ('90_day','30_day','expired')),
    alert_date      date NOT NULL,
    is_sent         boolean NOT NULL DEFAULT false,
    sent_at         timestamptz,
    recipient_id    uuid REFERENCES rex.people(id),
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- 57. completion_milestones
CREATE TABLE IF NOT EXISTS rex.completion_milestones (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              uuid NOT NULL REFERENCES rex.projects(id),
    milestone_type          text NOT NULL CHECK (milestone_type IN (
                                'substantial_completion','final_completion','tco',
                                'final_co','holdback_release','rough_in','sheetrock_prime',
                                'foundation_podium','topped_out','first_turnover_tco')),
    milestone_name          text NOT NULL,
    scheduled_date          date,
    actual_date             date,
    variance_days           int,
    status                  text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','achieved','overdue')),
    is_evidence_complete    boolean NOT NULL DEFAULT false,
    evidence_requirements   jsonb,
    certified_by            uuid REFERENCES rex.people(id),
    notes                   text,
    sort_order              int NOT NULL DEFAULT 0,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_completion_milestones_project_type UNIQUE (project_id, milestone_type)
);


-- ============================================================================
-- TRIGGERS — auto-update updated_at on mutable tables
-- ============================================================================

DO $$
DECLARE
    tbl text;
    trigger_tables text[] := ARRAY[
        'projects','companies','people','user_accounts','role_templates',
        'project_members','schedules','schedule_activities','schedule_constraints',
        'daily_logs','punch_items','inspections','observations','safety_incidents',
        'tasks','meetings','cost_codes','budget_line_items','prime_contracts',
        'commitments','change_events','potential_change_orders',
        'commitment_change_orders','direct_costs','payment_applications',
        'lien_waivers','drawings','specifications','rfis','submittal_packages',
        'submittals','correspondence','closeout_templates','closeout_checklists',
        'closeout_checklist_items','warranties','warranty_claims',
        'completion_milestones'
    ];
BEGIN
    FOREACH tbl IN ARRAY trigger_tables LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_%I_updated_at ON rex.%I; '
            'CREATE TRIGGER trg_%I_updated_at BEFORE UPDATE ON rex.%I '
            'FOR EACH ROW EXECUTE FUNCTION rex.set_updated_at();',
            tbl, tbl, tbl, tbl
        );
    END LOOP;
END $$;


-- ============================================================================
-- TABLE COUNT VERIFICATION
-- ============================================================================
-- Domain 1 — Foundation:          9 tables
-- Domain 2 — Schedule:            5 tables
-- Domain 3 — Field Ops:          12 tables
-- Domain 4 — Financials:         14 tables
-- Domain 5 — Document Management: 9 tables
-- Domain 6 — Closeout & Warranty: 8 tables
-- ─────────────────────────────────────────
-- TOTAL:                         57 tables
-- ============================================================================
