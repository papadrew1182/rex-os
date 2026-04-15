// Mock identity + permissions for useMe / usePermissions.
//
// Swapped to live data when Session 2 lands `/api/me` and
// `/api/me/permissions`. The canonical role keys are:
//   VP | PM | GENERAL_SUPER | LEAD_SUPER | ASSISTANT_SUPER | ACCOUNTANT
//
// Legacy aliases (e.g. "VP_PM", "General_Superintendent") are preserved
// in `legacy_role_aliases` so any remaining legacy code paths can still
// introspect old names during the normalization window. UI logic MUST
// branch on `primary_role_key` / `role_keys`, never on the legacy list.

export const mockMe = {
  id: "mock-user-001",
  email: "aroberts@exxircapital.com",
  full_name: "Andrew Roberts",
  primary_role_key: "VP",
  role_keys: ["VP"],
  legacy_role_aliases: ["VP_PM"],
  project_ids: [
    "40000000-0000-4000-a000-000000000001",
    "40000000-0000-4000-a000-000000000002",
    "40000000-0000-4000-a000-000000000003",
    "40000000-0000-4000-a000-000000000004",
  ],
  feature_flags: {
    assistant_sidebar: true,
    control_plane_home: true,
    my_day_home: true,
  },
};

export const mockPermissions = [
  "assistant.chat",
  "assistant.catalog.read",
  "financials.view",
  "schedule.view",
  "myday.view",
  "control_plane.view",
  "project_members.manage",
  "companies.manage",
  "photos.upload",
];
