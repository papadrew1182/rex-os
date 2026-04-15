// ProjectDashboard — thin mounted route for /projects/:projectSlug.
//
// First-pass behavior: look up the project by slug or id, set it as
// the current project in the ProjectProvider (so the assistant
// sidebar gets the right context), and show a placeholder body.
//
// Phase 3 intent is that this is the canonical "project workspace"
// entry point. The existing 32-page shell already has per-project
// surfaces (Portfolio row click → ProjectReadiness); this new route
// is the assistant-first alternative entry and will grow into the
// primary project home in later phases.

import { useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { useProject } from "../project";
import { useCurrentContext } from "../hooks/useCurrentContext";

export default function ProjectDashboard() {
  const { projectSlug } = useParams();
  const { projects, selectedId, select } = useProject();
  const currentContext = useCurrentContext();

  // Resolve the slug to a real project. For now the "slug" is either
  // the project_number (case-insensitive) or the raw uuid. The canonical
  // slug convention is tracked in Session 2 / canonical_core_entities.
  useEffect(() => {
    if (!projects || projects.length === 0 || !projectSlug) return;
    const target = projects.find((p) =>
      p.id === projectSlug ||
      p.project_number?.toLowerCase() === projectSlug.toLowerCase() ||
      p.name?.toLowerCase().replace(/\s+/g, "-") === projectSlug.toLowerCase()
    );
    if (target && target.id !== selectedId) {
      select(target.id);
    }
  }, [projectSlug, projects, selectedId, select]);

  const project = projects?.find((p) => p.id === selectedId) || null;

  return (
    <div className="rex-project-dashboard">
      <header style={{ marginBottom: 16 }}>
        <h1 className="rex-h1" style={{ margin: 0 }}>
          {project?.name || projectSlug}
        </h1>
        <p className="rex-muted" style={{ marginTop: 6 }}>
          Project workspace entry point (slug: <code>{projectSlug}</code>).
          The persistent assistant sidebar is now contextually bound to this project —
          ask it about budget variance, RFIs, or schedule without specifying the project name.
        </p>
      </header>

      {!project && (
        <div className="rex-alert rex-alert-amber">
          Project <code>{projectSlug}</code> not found in the current portfolio.
        </div>
      )}

      {project && (
        <div className="rex-grid-3" style={{ marginBottom: 16 }}>
          <div className="rex-stat-card">
            <div className="rex-stat-label">Project #</div>
            <div className="rex-stat-num" style={{ fontSize: 22 }}>{project.project_number || "—"}</div>
          </div>
          <div className="rex-stat-card">
            <div className="rex-stat-label">Status</div>
            <div className="rex-stat-num" style={{ fontSize: 22 }}>{project.status || "—"}</div>
          </div>
          <div className="rex-stat-card">
            <div className="rex-stat-label">Current context</div>
            <div className="rex-stat-sub" style={{ fontSize: 12 }}>
              {currentContext.route.name} · entity_type={currentContext.page_context.entity_type || "—"}
            </div>
          </div>
        </div>
      )}

      <div className="rex-card" style={{ marginBottom: 16 }}>
        <h3 className="rex-h4" style={{ marginBottom: 8 }}>Jump to existing surfaces</h3>
        <p className="rex-muted" style={{ fontSize: 13, marginBottom: 10 }}>
          The phase 41–53 product surfaces are all still available. These links
          are deep entries into the same project context.
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Link to="/" className="rex-btn rex-btn-outline">Portfolio</Link>
          <Link to="/schedule" className="rex-btn rex-btn-outline">Schedule Health</Link>
          <Link to="/rfis" className="rex-btn rex-btn-outline">RFIs</Link>
          <Link to="/punch-list" className="rex-btn rex-btn-outline">Punch list</Link>
          <Link to="/submittals" className="rex-btn rex-btn-outline">Submittals</Link>
          <Link to="/checklists" className="rex-btn rex-btn-outline">Closeout checklists</Link>
        </div>
      </div>
    </div>
  );
}
