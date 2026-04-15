from app.routes.auth import router as auth_router
from app.routes.ops import router as ops_router
from app.routes.companies import router as companies_router
from app.routes.connector_mappings import router as connector_mappings_router
from app.routes.people import router as people_router
from app.routes.project_members import router as project_members_router
from app.routes.projects import router as projects_router
from app.routes.role_templates import router as role_templates_router
from app.routes.schedules import router as schedules_router
from app.routes.schedule_activities import router as schedule_activities_router
from app.routes.activity_links import router as activity_links_router
from app.routes.schedule_constraints import router as schedule_constraints_router
from app.routes.schedule_snapshots import router as schedule_snapshots_router
from app.routes.daily_logs import router as daily_logs_router
from app.routes.manpower_entries import router as manpower_entries_router
from app.routes.punch_items import router as punch_items_router
from app.routes.inspections import router as inspections_router
from app.routes.inspection_items import router as inspection_items_router
from app.routes.observations import router as observations_router
from app.routes.safety_incidents import router as safety_incidents_router
from app.routes.photo_albums import router as photo_albums_router
from app.routes.photos import router as photos_router
from app.routes.tasks import router as tasks_router
from app.routes.meetings import router as meetings_router
from app.routes.meeting_action_items import router as meeting_action_items_router
from app.routes.cost_codes import router as cost_codes_router
from app.routes.budget_line_items import router as budget_line_items_router
from app.routes.budget_snapshots import router as budget_snapshots_router
from app.routes.prime_contracts import router as prime_contracts_router
from app.routes.commitments import router as commitments_router
from app.routes.commitment_line_items import router as commitment_line_items_router
from app.routes.change_events import router as change_events_router
from app.routes.potential_change_orders import router as potential_change_orders_router
from app.routes.commitment_change_orders import router as commitment_change_orders_router
from app.routes.pco_cco_links import router as pco_cco_links_router
from app.routes.billing_periods import router as billing_periods_router
from app.routes.direct_costs import router as direct_costs_router
from app.routes.payment_applications import router as payment_applications_router, project_router as pay_app_project_router
from app.routes.lien_waivers import router as lien_waivers_router
from app.routes.drawing_areas import router as drawing_areas_router
from app.routes.drawings import router as drawings_router
from app.routes.drawing_revisions import router as drawing_revisions_router
from app.routes.specifications import router as specifications_router
from app.routes.rfis import router as rfis_router
from app.routes.submittal_packages import router as submittal_packages_router
from app.routes.submittals import router as submittals_router
from app.routes.attachments import router as attachments_router
from app.routes.correspondence import router as correspondence_router
from app.routes.closeout_readiness import router as closeout_readiness_router
from app.routes.closeout_templates import router as closeout_templates_router
from app.routes.closeout_template_items import router as closeout_template_items_router
from app.routes.closeout_checklists import router as closeout_checklists_router
from app.routes.closeout_checklist_items import router as closeout_checklist_items_router
from app.routes.warranties import router as warranties_router
from app.routes.warranty_claims import router as warranty_claims_router
from app.routes.warranty_alerts import router as warranty_alerts_router
from app.routes.completion_milestones import router as completion_milestones_router
from app.routes.budget_summary import router as budget_summary_router
from app.routes.change_event_line_items import router as change_event_line_items_router
from app.routes.insurance_certificates import router as insurance_certificates_router
from app.routes.admin_jobs import router as admin_jobs_router
from app.routes.notifications import router as notifications_router
from app.routes.om_manuals import router as om_manuals_router

# ── Session 1 (feat/ai-spine): AI spine router ──────────────────────────────
# Lives at backend/routers/assistant.py so the AI spine contract is owned
# separately from the existing app/routes/ domain routers. Imported here so
# it joins the same all_routers loader that main.py consumes without any
# change to main.py. DO NOT REMOVE — reverting this line breaks the
# /api/assistant/* endpoints and makes them fall through to the SPA fallback.
from routers.assistant import router as assistant_router

all_routers = [
    # Ops
    ops_router,
    # Auth
    auth_router,
    # Foundation
    projects_router, companies_router, people_router, role_templates_router,
    project_members_router, connector_mappings_router,
    # Schedule
    schedules_router, schedule_activities_router, activity_links_router,
    schedule_constraints_router, schedule_snapshots_router,
    # Field Ops
    daily_logs_router, manpower_entries_router, punch_items_router,
    inspections_router, inspection_items_router, observations_router,
    safety_incidents_router, photo_albums_router, photos_router,
    tasks_router, meetings_router, meeting_action_items_router,
    # Financials
    cost_codes_router, budget_line_items_router, budget_snapshots_router,
    prime_contracts_router, commitments_router, commitment_line_items_router,
    change_events_router, potential_change_orders_router,
    commitment_change_orders_router, pco_cco_links_router,
    billing_periods_router, direct_costs_router,
    payment_applications_router, pay_app_project_router, lien_waivers_router,
    budget_summary_router, change_event_line_items_router,
    # Document Management
    drawing_areas_router, drawings_router, drawing_revisions_router,
    specifications_router, rfis_router, submittal_packages_router,
    submittals_router, attachments_router, correspondence_router,
    # Closeout & Warranty
    closeout_templates_router, closeout_template_items_router,
    closeout_checklists_router, closeout_checklist_items_router,
    warranties_router, warranty_claims_router, warranty_alerts_router,
    completion_milestones_router,
    closeout_readiness_router,
    om_manuals_router,
    # Insurance
    insurance_certificates_router,
    # Jobs & Notifications
    admin_jobs_router,
    notifications_router,
    # AI spine (Session 1 / feat/ai-spine) — keep last so it is the newest
    # addition in git blame and easy to find.
    assistant_router,
]
