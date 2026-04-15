// ActionCatalogPanel — full assistant catalog with readiness badges.
//
// This is the operator view of the catalog: every action, every role
// visibility list, every readiness state, regardless of whether the
// current user can see them in the sidebar launcher. Useful for
// debugging the catalog seeding and for verifying the role visibility
// matrix.

import { useContext } from "react";
import { AppContext } from "../app/AppContext";

const READINESS_ORDER = ["live", "alpha", "adapter_pending", "writeback_pending", "blocked", "disabled"];

function groupByReadiness(actions) {
  const groups = {};
  for (const a of actions || []) {
    const k = a.readiness_state || "unknown";
    (groups[k] = groups[k] || []).push(a);
  }
  return groups;
}

export default function ActionCatalogPanel() {
  const { assistant } = useContext(AppContext);
  const catalog = assistant.catalog.data;

  if (assistant.catalog.loading && !catalog) {
    return <p className="rex-muted">Loading catalog…</p>;
  }

  if (!catalog) {
    return (
      <div className="rex-empty">
        <div className="rex-empty-icon">▤</div>
        Catalog unavailable.
      </div>
    );
  }

  const groups = groupByReadiness(catalog.actions);
  const totalCount = (catalog.actions || []).length;

  return (
    <div className="rex-control-catalog">
      <div className="rex-muted" style={{ marginBottom: 10, fontSize: 13 }}>
        Catalog version <strong>{catalog.version}</strong> · {totalCount} actions across {catalog.categories?.length || 0} categories.
      </div>
      {READINESS_ORDER.map((r) => {
        const rows = groups[r] || [];
        if (rows.length === 0) return null;
        return (
          <section key={r} className="rex-control-catalog__section">
            <h3 className="rex-h4" style={{ marginBottom: 8 }}>
              {r} <span className="rex-muted">· {rows.length}</span>
            </h3>
            <div className="rex-table-wrap" style={{ marginBottom: 16 }}>
              <div className="rex-table-scroll">
                <table className="rex-table">
                  <thead>
                    <tr>
                      <th>Slug</th>
                      <th>Label</th>
                      <th>Category</th>
                      <th>Role visibility</th>
                      <th>Connectors</th>
                      <th>can_run</th>
                      <th>Legacy aliases</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((a) => (
                      <tr key={a.slug}>
                        <td style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>{a.slug}</td>
                        <td style={{ fontWeight: 600 }}>{a.label}</td>
                        <td>{a.category}</td>
                        <td style={{ fontSize: 12 }}>{(a.role_visibility || []).join(", ") || "—"}</td>
                        <td style={{ fontSize: 12 }}>{(a.required_connectors || []).join(", ") || "—"}</td>
                        <td>{a.can_run === false ? "no" : "yes"}</td>
                        <td style={{ fontFamily: "ui-monospace, monospace", fontSize: 11 }}>
                          {(a.legacy_aliases || []).join(", ") || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        );
      })}
    </div>
  );
}
