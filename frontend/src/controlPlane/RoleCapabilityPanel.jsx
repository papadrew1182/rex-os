// RoleCapabilityPanel — canonical role + permission inspector.
//
// Surfaces the current user's identity and the canonical role model,
// so operators can verify that the RBAC system returns the expected
// role_keys + permissions against their login. Session 2 lands the
// data-driven role registry — this panel is mounted now as the
// operator-facing window into whatever that registry returns.

import { useMe } from "../hooks/useMe";
import { usePermissions } from "../hooks/usePermissions";

const CANONICAL_ROLES = [
  { key: "VP", label: "VP" },
  { key: "PM", label: "PM" },
  { key: "GENERAL_SUPER", label: "General Super" },
  { key: "LEAD_SUPER", label: "Lead Super" },
  { key: "ASSISTANT_SUPER", label: "Assistant Super" },
  { key: "ACCOUNTANT", label: "Accountant" },
];

export default function RoleCapabilityPanel() {
  const { me, loading } = useMe();
  const { permissions } = usePermissions();

  if (loading || !me) {
    return <p className="rex-muted">Loading identity…</p>;
  }

  const userRoles = new Set(me.role_keys || []);

  return (
    <div className="rex-control-roles">
      <section style={{ marginBottom: 20 }}>
        <h3 className="rex-h4">Current user</h3>
        <div className="rex-card" style={{ marginTop: 8 }}>
          <div className="rex-row">
            <span className="rex-row-label">Name</span>
            <span className="rex-row-value">{me.full_name}</span>
          </div>
          <div className="rex-row">
            <span className="rex-row-label">Email</span>
            <span className="rex-row-value">{me.email}</span>
          </div>
          <div className="rex-row">
            <span className="rex-row-label">Primary role</span>
            <span className="rex-row-value">{me.primary_role_key}</span>
          </div>
          <div className="rex-row">
            <span className="rex-row-label">All role keys</span>
            <span className="rex-row-value">{(me.role_keys || []).join(", ")}</span>
          </div>
          <div className="rex-row">
            <span className="rex-row-label">Legacy aliases (informational)</span>
            <span className="rex-row-value" style={{ color: "var(--rex-text-faint)" }}>
              {(me.legacy_role_aliases || []).join(", ") || "—"}
            </span>
          </div>
          <div className="rex-row">
            <span className="rex-row-label">Accessible projects</span>
            <span className="rex-row-value">{(me.project_ids || []).length}</span>
          </div>
        </div>
      </section>

      <section style={{ marginBottom: 20 }}>
        <h3 className="rex-h4">Canonical role matrix</h3>
        <p className="rex-muted" style={{ fontSize: 12, marginBottom: 8 }}>
          Rex OS canonical roles. Legacy names (<em>VP_PM</em>, <em>General_Superintendent</em>, etc.)
          are still accepted as aliases during the normalization window but should
          not drive UI logic.
        </p>
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr><th>Key</th><th>Label</th><th>Assigned to you</th></tr>
            </thead>
            <tbody>
              {CANONICAL_ROLES.map((r) => (
                <tr key={r.key}>
                  <td style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>{r.key}</td>
                  <td>{r.label}</td>
                  <td>{userRoles.has(r.key) ? "yes" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h3 className="rex-h4">Current permissions</h3>
        <p className="rex-muted" style={{ fontSize: 12, marginBottom: 8 }}>
          Permissions returned by <code>GET /api/me/permissions</code>. The
          assistant and control plane branch entirely on these strings —
          no frontend-only permission logic.
        </p>
        {permissions.length === 0 ? (
          <p className="rex-muted">No permissions granted.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexWrap: "wrap", gap: 6 }}>
            {permissions.map((p) => (
              <li key={p} className="rex-badge rex-badge-purple" style={{ fontFamily: "ui-monospace, monospace" }}>
                {p}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
