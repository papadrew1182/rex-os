import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash, ProgressBar } from "../ui";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

function deriveStatus(a) {
  if (a.percent_complete >= 100) return "COMPLETE";
  if (a.variance_days != null && a.variance_days > 0) return "DRIFTING";
  if (!a.actual_start_date && !a.actual_finish_date && !a.percent_complete) return "NOT STARTED";
  return "ON TRACK";
}

function statusBadge(a) {
  const s = deriveStatus(a);
  const cls = s === "COMPLETE" ? "rex-badge-green" : s === "DRIFTING" ? "rex-badge-red" : "rex-badge-gray";
  return <span className={`rex-badge ${cls}`}>{s}</span>;
}

function dayOffset(date, windowStart) {
  if (!date) return null;
  return Math.floor((new Date(date + "T00:00:00").getTime() - windowStart) / 86400000);
}

// ─────────────────────────────────────────────────────────────────────────────
// URL state persistence
// ─────────────────────────────────────────────────────────────────────────────

function readUrlState() {
  const hash = window.location.hash;
  const qIdx = hash.indexOf("?");
  if (qIdx === -1) return {};
  const params = new URLSearchParams(hash.slice(qIdx + 1));
  return Object.fromEntries(params.entries());
}

function writeUrlState(state) {
  const hash = window.location.hash;
  const baseHash = hash.indexOf("?") === -1 ? hash : hash.slice(0, hash.indexOf("?"));
  const params = new URLSearchParams();
  Object.entries(state).forEach(([k, v]) => {
    if (v != null && v !== "" && !(typeof v === "boolean" && !v)) {
      params.set(k, String(v));
    }
  });
  const qs = params.toString();
  window.history.replaceState(null, "", baseHash + (qs ? `?${qs}` : ""));
}

// ─────────────────────────────────────────────────────────────────────────────
// CSV / Print export
// ─────────────────────────────────────────────────────────────────────────────

function downloadCsv(filename, rows, headers) {
  const escape = (v) => {
    if (v == null) return "";
    const s = String(v);
    if (s.includes(",") || s.includes('"') || s.includes("\n")) return `"${s.replace(/"/g, '""')}"`;
    return s;
  };
  const csv = [
    headers.join(","),
    ...rows.map(r => headers.map(h => escape(r[h])).join(",")),
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function exportActivitiesCsv(activities, project) {
  const headers = ["wbs_code", "activity_number", "name", "start_date", "end_date", "actual_start_date", "actual_finish_date", "baseline_start", "baseline_end", "duration_days", "percent_complete", "variance_days", "float_days", "is_critical", "status"];
  const rows = activities.map(a => ({
    ...a,
    is_critical: a.is_critical ? "CRITICAL" : "",
    status: deriveStatus(a),
  }));
  downloadCsv(`schedule-activities-${project?.project_number || "project"}-${new Date().toISOString().slice(0, 10)}.csv`, rows, headers);
}

function exportCriticalCsv(activities, project) {
  const headers = ["wbs_code", "activity_number", "name", "end_date", "actual_finish_date", "percent_complete", "variance_days", "float_days", "is_critical"];
  const rows = activities.map(a => ({
    ...a,
    is_critical: a.is_critical ? "CRITICAL" : "NEAR-CRITICAL",
  }));
  downloadCsv(`critical-path-${project?.project_number || "project"}-${new Date().toISOString().slice(0, 10)}.csv`, rows, headers);
}

function renderPrintTable(activities, tab) {
  if (tab === "lookahead") {
    // Group by week
    function weekKey(dateStr) {
      const d = new Date(dateStr + "T00:00:00");
      const day = d.getDay();
      const monday = new Date(d.getTime() - ((day + 6) % 7) * 86400000);
      return monday.toISOString().slice(0, 10);
    }
    const grouped = {};
    activities.forEach(a => {
      const k = weekKey(a.start_date);
      if (!grouped[k]) grouped[k] = [];
      grouped[k].push(a);
    });
    const weeks = Object.keys(grouped).sort();
    return weeks.map(wk => `
      <h3 style="margin:16px 0 6px;font-size:13px;color:#2D1B4E;">Week of ${fmtDate(wk)}</h3>
      <table>
        <thead><tr><th>Activity</th><th>WBS</th><th>Start</th><th>End</th><th>% Complete</th><th>Critical</th></tr></thead>
        <tbody>
          ${grouped[wk].map(a => `
            <tr>
              <td>${a.activity_number ? a.activity_number + " — " : ""}${a.name || ""}</td>
              <td>${a.wbs_code || "—"}</td>
              <td>${fmtDate(a.start_date)}</td>
              <td>${fmtDate(a.end_date)}</td>
              <td>${a.percent_complete != null ? Math.round(a.percent_complete) + "%" : "—"}</td>
              <td class="${a.is_critical ? "crit" : ""}">${a.is_critical ? "CRITICAL" : "—"}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `).join("");
  }
  if (tab === "critical") {
    return `<table>
      <thead><tr><th>Activity</th><th>WBS</th><th>Planned End</th><th>Actual End</th><th>% Comp</th><th>Variance</th><th>Float</th><th>Status</th></tr></thead>
      <tbody>
        ${activities.map(a => `
          <tr>
            <td>${a.activity_number ? a.activity_number + " — " : ""}${a.name || ""}</td>
            <td>${a.wbs_code || "—"}</td>
            <td>${fmtDate(a.end_date)}</td>
            <td>${fmtDate(a.actual_finish_date)}</td>
            <td>${a.percent_complete != null ? Math.round(a.percent_complete) + "%" : "—"}</td>
            <td class="${(a.variance_days || 0) > 0 ? "crit" : ""}">${a.variance_days != null ? (a.variance_days > 0 ? "+" + a.variance_days : a.variance_days) + "d" : "—"}</td>
            <td>${a.float_days ?? "—"}</td>
            <td class="${a.is_critical ? "crit" : ""}">${a.is_critical ? "CRITICAL" : "NEAR"}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>`;
  }
  // Activities (default)
  return `<table>
    <thead><tr><th>WBS</th><th>Activity #</th><th>Name</th><th>Start</th><th>End</th><th>% Comp</th><th>Variance</th><th>Float</th><th>Status</th></tr></thead>
    <tbody>
      ${activities.map(a => `
        <tr>
          <td>${a.wbs_code || "—"}</td>
          <td>${a.activity_number || "—"}</td>
          <td>${a.name || ""}</td>
          <td>${fmtDate(a.start_date)}</td>
          <td>${fmtDate(a.end_date)}</td>
          <td>${a.percent_complete != null ? Math.round(a.percent_complete) + "%" : "—"}</td>
          <td class="${(a.variance_days || 0) > 0 ? "crit" : ""}">${a.variance_days != null ? (a.variance_days > 0 ? "+" + a.variance_days : a.variance_days) + "d" : "—"}</td>
          <td>${a.float_days ?? "—"}</td>
          <td>${deriveStatus(a)}</td>
        </tr>
      `).join("")}
    </tbody>
  </table>`;
}

function exportPrint(filteredActivities, tab, project, filterSummary) {
  const w = window.open("", "_blank", "width=900,height=700");
  if (!w) { alert("Popup blocked. Please allow popups for this site."); return; }
  const tableHtml = renderPrintTable(filteredActivities, tab);
  const tabLabel = tab === "critical" ? "Critical Path" : tab === "lookahead" ? "Lookahead" : "Schedule Activities";
  w.document.write(`<!DOCTYPE html>
<html><head><title>Schedule — ${project?.name || ""}</title>
<style>
  body { font-family: 'DM Sans', -apple-system, sans-serif; color: #1E293B; padding: 24px; font-size: 12px; }
  h1 { font-family: 'Syne', serif; font-weight: 800; color: #2D1B4E; margin: 0 0 4px 0; font-size: 24px; }
  .meta { color: #475569; font-size: 11px; margin-bottom: 16px; }
  .filters { background: #FBF9FE; border-left: 3px solid #6b45a1; padding: 8px 12px; margin-bottom: 16px; font-size: 11px; }
  table { width: 100%; border-collapse: collapse; }
  th { background: #6b45a1; color: white; text-transform: uppercase; font-size: 10px; padding: 6px 8px; text-align: left; }
  td { padding: 5px 8px; border-bottom: 1px solid #E2E0E8; font-size: 11px; }
  tr:nth-child(even) td { background: #FBF9FE; }
  .crit { color: #DC2626; font-weight: 700; }
  .footer { margin-top: 16px; color: #64748B; font-size: 10px; }
  @media print { @page { margin: 0.5in; } }
</style></head><body>
<h1>${tabLabel}</h1>
<div class="meta">Project: <strong>${project?.name || ""}</strong>${project?.project_number ? ` (${project.project_number})` : ""} · Generated ${new Date().toLocaleString()}</div>
${filterSummary ? `<div class="filters"><strong>Filters:</strong> ${filterSummary}</div>` : ""}
${tableHtml}
<div class="footer">Rex OS — ${filteredActivities.length} record${filteredActivities.length !== 1 ? "s" : ""}</div>
</body></html>`);
  w.document.close();
  setTimeout(() => { w.focus(); w.print(); }, 250);
}

// ─────────────────────────────────────────────────────────────────────────────
// Gantt helpers
// ─────────────────────────────────────────────────────────────────────────────

function buildTree(activities, criticalOnly) {
  const filtered = criticalOnly ? activities.filter(a => a.is_critical) : activities;
  const byParent = {};
  filtered.forEach(a => {
    const p = a.parent_id || "root";
    if (!byParent[p]) byParent[p] = [];
    byParent[p].push(a);
  });
  const idSet = new Set(filtered.map(a => a.id));
  const result = [];
  function walk(parentId, depth) {
    const kids = (byParent[parentId === null ? "root" : parentId] || [])
      .slice()
      .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
    kids.forEach(a => {
      result.push({ ...a, _depth: depth, _hasChildren: !!byParent[a.id] });
      walk(a.id, depth + 1);
    });
  }
  walk(null, 0);
  return result;
}

// ─────────────────────────────────────────────────────────────────────────────
// Gantt View
// ─────────────────────────────────────────────────────────────────────────────

function GanttView({ activities, openDetail }) {
  const [zoom, setZoom] = useState("month");
  const [showBaseline, setShowBaseline] = useState(false);
  const [showActuals, setShowActuals] = useState(true);
  const [criticalOnly, setCriticalOnly] = useState(false);
  const [expanded, setExpanded] = useState(() => new Set());
  const treeScrollRef = useRef(null);
  const timelineScrollRef = useRef(null);
  const syncingRef = useRef(false);

  const pxPerDay = zoom === "week" ? 24 : zoom === "month" ? 6 : 2;
  const ROW_HEIGHT = 34;

  const ganttWindow = useMemo(() => {
    const dates = [];
    activities.forEach(a => {
      [a.start_date, a.end_date, a.baseline_start, a.baseline_end, a.actual_start_date, a.actual_finish_date].forEach(d => {
        if (d) dates.push(new Date(d + "T00:00:00").getTime());
      });
    });
    if (dates.length === 0) {
      const now = Date.now();
      return { start: now - 30 * 86400000, end: now + 90 * 86400000 };
    }
    return { start: Math.min(...dates) - 7 * 86400000, end: Math.max(...dates) + 7 * 86400000 };
  }, [activities]);

  const totalDays = Math.ceil((ganttWindow.end - ganttWindow.start) / 86400000);
  const timelineWidth = totalDays * pxPerDay;

  const tree = useMemo(() => buildTree(activities, criticalOnly), [activities, criticalOnly]);

  // Default all nodes expanded
  useEffect(() => {
    const ids = new Set(tree.filter(n => n._hasChildren).map(n => n.id));
    setExpanded(ids);
  }, [tree.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const visibleRows = useMemo(() => {
    const result = [];
    const collapsedAncestors = new Set();
    tree.forEach(node => {
      // If any ancestor is collapsed, skip
      let skip = false;
      // Walk up: find parent chain
      if (node._depth > 0) {
        // Check if this node's parent is collapsed
        // We track collapsed ancestors by checking if parent isn't expanded
        if (collapsedAncestors.has(node.parent_id)) {
          skip = true;
          if (node._hasChildren) collapsedAncestors.add(node.id);
        }
      }
      if (!skip) {
        result.push(node);
        if (node._hasChildren && !expanded.has(node.id)) {
          collapsedAncestors.add(node.id);
        }
      }
    });
    return result;
  }, [tree, expanded]);

  function toggleExpanded(id) {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // Sync scroll between tree and timeline
  function onTreeScroll(e) {
    if (syncingRef.current) return;
    syncingRef.current = true;
    if (timelineScrollRef.current) timelineScrollRef.current.scrollTop = e.target.scrollTop;
    syncingRef.current = false;
  }
  function onTimelineScroll(e) {
    if (syncingRef.current) return;
    syncingRef.current = true;
    if (treeScrollRef.current) treeScrollRef.current.scrollTop = e.target.scrollTop;
    syncingRef.current = false;
  }

  // Month axis labels
  const monthLabels = useMemo(() => {
    const labels = [];
    const d = new Date(ganttWindow.start);
    d.setDate(1);
    while (d.getTime() <= ganttWindow.end) {
      const offset = Math.floor((d.getTime() - ganttWindow.start) / 86400000);
      labels.push({
        label: d.toLocaleDateString(undefined, { month: "short", year: "numeric" }),
        left: offset * pxPerDay,
      });
      d.setMonth(d.getMonth() + 1);
    }
    return labels;
  }, [ganttWindow, pxPerDay]);

  const todayOffset = dayOffset(new Date().toISOString().slice(0, 10), ganttWindow.start);
  const todayLeft = todayOffset * pxPerDay;

  const AXIS_HEIGHT = 28;
  const TREE_WIDTH = 440;

  return (
    <div className="rex-gantt-wrap">
      {/* Toolbar */}
      <div className="rex-gantt-toolbar">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="rex-muted" style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em" }}>Zoom:</span>
          {["week", "month", "quarter"].map(z => (
            <button
              key={z}
              className={`rex-btn ${zoom === z ? "rex-btn-primary" : "rex-btn-outline"}`}
              style={{ padding: "4px 12px", fontSize: 12 }}
              onClick={() => setZoom(z)}
            >
              {z.charAt(0).toUpperCase() + z.slice(1)}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          {[
            { key: "showBaseline", label: "Baseline", val: showBaseline, set: setShowBaseline },
            { key: "showActuals", label: "Actuals", val: showActuals, set: setShowActuals },
            { key: "criticalOnly", label: "Critical only", val: criticalOnly, set: setCriticalOnly },
          ].map(({ key, label, val, set }) => (
            <label key={key} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 13, color: "var(--rex-text)", cursor: "pointer" }}>
              <input type="checkbox" checked={val} onChange={e => set(e.target.checked)} style={{ cursor: "pointer" }} />
              {label}
            </label>
          ))}
        </div>
        <span className="rex-muted" style={{ fontSize: 12 }}>{visibleRows.length} rows</span>
      </div>

      {/* Gantt body */}
      <div className="rex-gantt-body">
        {/* Left: Tree grid */}
        <div className="rex-gantt-tree-wrap" style={{ width: TREE_WIDTH, minWidth: TREE_WIDTH }}>
          {/* Axis header spacer */}
          <div className="rex-gantt-axis-spacer" style={{ height: AXIS_HEIGHT }}>
            <div style={{ display: "flex", alignItems: "center", height: "100%", paddingLeft: 12, gap: 8 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: "var(--rex-text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Activity</span>
            </div>
          </div>
          {/* Tree rows */}
          <div
            className="rex-gantt-tree-rows"
            ref={treeScrollRef}
            onScroll={onTreeScroll}
            style={{ overflowY: "auto", maxHeight: 520 }}
          >
            {visibleRows.map(node => (
              <div
                key={node.id}
                className="rex-gantt-tree-row"
                style={{ height: ROW_HEIGHT, paddingLeft: 10 + node._depth * 16 }}
                onClick={() => openDetail(node)}
              >
                {node._hasChildren && (
                  <button
                    className="rex-gantt-expand-btn"
                    onClick={e => { e.stopPropagation(); toggleExpanded(node.id); }}
                    title={expanded.has(node.id) ? "Collapse" : "Expand"}
                  >
                    {expanded.has(node.id) ? "▾" : "▸"}
                  </button>
                )}
                {!node._hasChildren && <span style={{ width: 16, display: "inline-block" }} />}
                <span className="rex-gantt-tree-num" style={{ fontFamily: "monospace", fontSize: 11, color: "var(--rex-text-muted)", marginRight: 4 }}>
                  {node.activity_number || ""}
                </span>
                <span className="rex-gantt-tree-name" style={{ fontSize: 12, fontWeight: node._hasChildren ? 700 : 500, color: "var(--rex-text-bold)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {node.name}
                </span>
                {node.wbs_code && (
                  <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--rex-text-muted)", fontFamily: "monospace", paddingRight: 8, whiteSpace: "nowrap" }}>
                    {node.wbs_code}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Right: Timeline */}
        <div
          className="rex-gantt-timeline-wrap"
          ref={timelineScrollRef}
          onScroll={onTimelineScroll}
          style={{ flex: 1, overflowX: "auto", overflowY: "auto", position: "relative" }}
        >
          <div style={{ minWidth: timelineWidth, position: "relative" }}>
            {/* Month axis */}
            <div className="rex-gantt-axis" style={{ height: AXIS_HEIGHT, position: "relative", borderBottom: "1px solid var(--rex-border)" }}>
              {monthLabels.map((m, i) => (
                <div
                  key={i}
                  style={{
                    position: "absolute",
                    left: m.left,
                    top: 0,
                    height: "100%",
                    display: "flex",
                    alignItems: "center",
                    paddingLeft: 6,
                    fontSize: 11,
                    fontWeight: 700,
                    color: "var(--rex-text-muted)",
                    borderLeft: "1px solid var(--rex-border)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {m.label}
                </div>
              ))}
              {/* Today marker in axis */}
              <div style={{ position: "absolute", left: todayLeft, top: 0, bottom: 0, width: 2, background: "var(--rex-red)", zIndex: 5 }} />
            </div>

            {/* Bar rows */}
            <div style={{ position: "relative" }}>
              {/* Today vertical line through all rows */}
              <div style={{ position: "absolute", left: todayLeft, top: 0, bottom: 0, width: 2, background: "var(--rex-red)", opacity: 0.4, zIndex: 10, pointerEvents: "none" }} />

              {visibleRows.map((a, idx) => {
                const planStartOff = dayOffset(a.start_date, ganttWindow.start);
                const planEndOff = dayOffset(a.end_date, ganttWindow.start);
                const hasBar = planStartOff != null && planEndOff != null;
                const planLeft = hasBar ? planStartOff * pxPerDay : 0;
                const planWidth = hasBar ? Math.max(2, (planEndOff - planStartOff + 1) * pxPerDay) : 0;
                const barColor = a.is_critical ? "var(--rex-red)" : "var(--rex-accent)";

                return (
                  <div
                    key={a.id}
                    className="rex-gantt-bar-row"
                    style={{
                      height: ROW_HEIGHT,
                      position: "relative",
                      background: idx % 2 === 0 ? "transparent" : "var(--rex-bg-stripe)",
                      borderBottom: "1px solid var(--rex-border)",
                    }}
                  >
                    {/* Baseline outline */}
                    {showBaseline && a.baseline_start && a.baseline_end && (() => {
                      const bStart = dayOffset(a.baseline_start, ganttWindow.start);
                      const bEnd = dayOffset(a.baseline_end, ganttWindow.start);
                      if (bStart == null || bEnd == null) return null;
                      return (
                        <div style={{
                          position: "absolute",
                          left: bStart * pxPerDay,
                          width: Math.max(2, (bEnd - bStart + 1) * pxPerDay),
                          top: 4,
                          height: 20,
                          border: "1px dashed #999",
                          borderRadius: 3,
                          pointerEvents: "none",
                          zIndex: 1,
                        }} />
                      );
                    })()}

                    {/* Planned bar with percent fill */}
                    {hasBar && (
                      <div
                        onClick={() => openDetail(a)}
                        title={`${a.name} — ${Math.round(a.percent_complete || 0)}% complete`}
                        style={{
                          position: "absolute",
                          left: planLeft,
                          width: planWidth,
                          top: 7,
                          height: 16,
                          background: "var(--rex-bg-stripe)",
                          border: `1px solid ${barColor}`,
                          borderRadius: 3,
                          cursor: "pointer",
                          overflow: "hidden",
                          zIndex: 2,
                        }}
                      >
                        <div style={{
                          width: `${Math.min(100, a.percent_complete || 0)}%`,
                          height: "100%",
                          background: barColor,
                          opacity: 0.85,
                        }} />
                      </div>
                    )}

                    {/* Actual bar */}
                    {showActuals && a.actual_start_date && a.actual_finish_date && (() => {
                      const aStart = dayOffset(a.actual_start_date, ganttWindow.start);
                      const aEnd = dayOffset(a.actual_finish_date, ganttWindow.start);
                      if (aStart == null || aEnd == null) return null;
                      return (
                        <div style={{
                          position: "absolute",
                          left: aStart * pxPerDay,
                          width: Math.max(2, (aEnd - aStart + 1) * pxPerDay),
                          top: 26,
                          height: 4,
                          background: "var(--rex-green)",
                          borderRadius: 2,
                          pointerEvents: "none",
                          zIndex: 2,
                        }} />
                      );
                    })()}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared Detail Panel
// ─────────────────────────────────────────────────────────────────────────────

function DetailPanel({ activity, onClose, peopleMap, companiesMap, costCodesMap }) {
  const [links, setLinks] = useState(null);
  const [constraints, setConstraints] = useState(null);

  useEffect(() => {
    if (!activity) return;
    setLinks(null);
    setConstraints(null);
    Promise.all([
      api(`/activity-links?schedule_id=${activity.schedule_id}&limit=500`).catch(() => []),
      api(`/schedule-constraints?activity_id=${activity.id}&limit=20`).catch(() => []),
    ]).then(([lks, cs]) => {
      setLinks(lks || []);
      setConstraints((cs || []).filter(c => c.status === "active"));
    });
  }, [activity?.id]);

  useEffect(() => {
    if (!activity) return;
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activity, onClose]);

  if (!activity) return null;

  const preds = (links || []).filter(l => l.to_activity_id === activity.id);
  const succs = (links || []).filter(l => l.from_activity_id === activity.id);

  // Resolve names from links
  const linkActivityName = (id) => {
    // We don't have the full activities list here, just show the id short form
    return id ? id.slice(0, 8) + "…" : "—";
  };

  const companyName = activity.assigned_company_id ? (companiesMap[activity.assigned_company_id]?.name || activity.assigned_company_id.slice(0, 8) + "…") : "—";
  const personName = activity.assigned_person_id ? (() => {
    const p = peopleMap[activity.assigned_person_id];
    return p ? `${p.first_name || ""} ${p.last_name || ""}`.trim() : activity.assigned_person_id.slice(0, 8) + "…";
  })() : "—";
  const costCodeLabel = activity.cost_code_id ? (costCodesMap[activity.cost_code_id]?.code || activity.cost_code_id.slice(0, 8) + "…") : "—";

  return (
    <div className="rex-detail-panel">
      <div className="rex-detail-panel-header">
        <div>
          <div className="rex-h3">{activity.activity_number ? `${activity.activity_number} — ` : ""}{activity.name}</div>
          <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
            {activity.is_critical && <span className="rex-badge rex-badge-red">CRITICAL</span>}
            {activity.activity_type && <span className="rex-badge rex-badge-purple">{activity.activity_type}</span>}
            {activity.wbs_code && <span className="rex-badge rex-badge-gray">WBS {activity.wbs_code}</span>}
          </div>
        </div>
        <button className="rex-detail-panel-close" onClick={onClose}>×</button>
      </div>

      <div className="rex-grid-3" style={{ marginBottom: 12 }}>
        <Card title="Schedule">
          <Row label="Planned Start" value={fmtDate(activity.start_date)} />
          <Row label="Planned Finish" value={fmtDate(activity.end_date)} />
          <Row label="Actual Start" value={fmtDate(activity.actual_start_date)} />
          <Row label="Actual Finish" value={fmtDate(activity.actual_finish_date)} />
          <Row label="Duration" value={activity.duration_days != null ? `${activity.duration_days}d` : "—"} />
          <div style={{ marginTop: 6 }}>
            <div className="rex-row-label" style={{ fontSize: 12, color: "var(--rex-text-muted)", marginBottom: 4 }}>% Complete</div>
            <ProgressBar pct={activity.percent_complete || 0} />
            <div style={{ fontSize: 12, color: "var(--rex-text-muted)", marginTop: 2 }}>{Math.round(activity.percent_complete || 0)}%</div>
          </div>
        </Card>
        <Card title="Baseline & Drift">
          <Row label="Baseline Start" value={fmtDate(activity.baseline_start)} />
          <Row label="Baseline End" value={fmtDate(activity.baseline_end)} />
          <Row label="Variance" value={activity.variance_days != null ? `${activity.variance_days}d` : "—"} />
          <Row label="Float" value={activity.float_days != null ? `${activity.float_days}d` : "—"} />
        </Card>
        <Card title="Assignment">
          <Row label="Company" value={companyName} />
          <Row label="Person" value={personName} />
          <Row label="Cost Code" value={costCodeLabel} />
          <Row label="Location" value={activity.location || "—"} />
        </Card>
      </div>

      {/* Predecessors */}
      {links === null ? (
        <p className="rex-muted" style={{ fontSize: 12 }}>Loading links…</p>
      ) : preds.length > 0 ? (
        <Card title="Predecessors" style={{ marginBottom: 10 }}>
          {preds.map(l => (
            <div key={l.id} className="rex-row" style={{ fontSize: 12 }}>
              <span className="rex-row-label">{l.link_type || "FS"}{l.lag_days ? ` +${l.lag_days}d` : ""}</span>
              <span className="rex-row-value" style={{ fontFamily: "monospace" }}>{linkActivityName(l.from_activity_id)}</span>
            </div>
          ))}
        </Card>
      ) : null}

      {/* Successors */}
      {links !== null && succs.length > 0 && (
        <Card title="Successors" style={{ marginBottom: 10 }}>
          {succs.map(l => (
            <div key={l.id} className="rex-row" style={{ fontSize: 12 }}>
              <span className="rex-row-label">{l.link_type || "FS"}{l.lag_days ? ` +${l.lag_days}d` : ""}</span>
              <span className="rex-row-value" style={{ fontFamily: "monospace" }}>{linkActivityName(l.to_activity_id)}</span>
            </div>
          ))}
        </Card>
      )}

      {/* Constraints */}
      {constraints !== null && constraints.length > 0 && (
        <Card title="Constraints" style={{ marginBottom: 10 }}>
          {constraints.map(c => (
            <div key={c.id} className="rex-row" style={{ fontSize: 12, alignItems: "center" }}>
              <span className="rex-row-label">{c.constraint_type} · {c.source_type}</span>
              <span>
                <span className={`rex-badge ${c.severity === "red" ? "rex-badge-red" : "rex-badge-amber"}`} style={{ marginRight: 4 }}>{c.severity}</span>
                {c.notes && <span style={{ color: "var(--rex-text-muted)" }}>{c.notes}</span>}
              </span>
            </div>
          ))}
        </Card>
      )}

      {activity.notes && (
        <Card title="Notes">
          <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{activity.notes}</p>
        </Card>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Health View
// ─────────────────────────────────────────────────────────────────────────────

function HealthView({ data }) {
  const v = data.project_average_variance_days;
  const vc = v > 5 ? "red" : v > 0 ? "amber" : "green";

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <Badge status={data.health_status} />
        <span className="rex-muted">{data.schedule_count} schedule{data.schedule_count !== 1 ? "s" : ""} · {data.total_activities} activities</span>
      </div>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Activities" value={data.total_activities} />
        <StatCard label="Critical" value={data.critical_count} color={data.critical_count > 0 ? "red" : ""} />
        <StatCard label="Completed" value={data.completed_count} color="green" />
        <StatCard label="Avg Variance" value={`${v >= 0 ? "+" : ""}${v.toFixed(1)}d`} color={vc} />
        <StatCard label="Constraints" value={data.active_constraint_count} color={data.active_constraint_count > 0 ? "amber" : ""} />
      </div>

      {data.active_constraint_count > 0 && (
        <Card title="Constraints by Severity" style={{ marginBottom: 20 }}>
          {Object.entries(data.constraints_by_severity).map(([s, c]) => <Row key={s} label={s} value={c} />)}
        </Card>
      )}

      {data.schedules?.length > 0 && (
        <div>
          <h3 className="rex-h3" style={{ marginBottom: 10 }}>Schedule Drift Details</h3>
          {data.schedules.map((s) => (
            <div key={s.schedule_id} className="rex-card" style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <div><strong>{s.schedule_name}</strong> <span className="rex-muted" style={{ marginLeft: 6 }}>{s.schedule_type}</span></div>
                <Badge status={s.status} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, fontSize: 13 }}>
                <div><div style={{ fontWeight: 700 }}>{s.total_activities}</div><div className="rex-muted" style={{ fontSize: 11 }}>Activities</div></div>
                <div><div style={{ fontWeight: 700 }}>{s.critical_count}</div><div className="rex-muted" style={{ fontSize: 11 }}>Critical</div></div>
                <div><div style={{ fontWeight: 700, color: `var(--rex-${s.average_variance_days > 5 ? "red" : s.average_variance_days > 0 ? "amber" : "green"})` }}>{s.average_variance_days >= 0 ? "+" : ""}{s.average_variance_days.toFixed(1)}d</div><div className="rex-muted" style={{ fontSize: 11 }}>Avg Variance</div></div>
                <div><div style={{ fontWeight: 700 }}>{s.active_constraint_count}</div><div className="rex-muted" style={{ fontSize: 11 }}>Constraints</div></div>
              </div>
              {s.worst_variance_activity && (
                <div className="rex-alert rex-alert-red" style={{ marginTop: 8 }}>
                  <strong>Worst drift:</strong> {s.worst_variance_activity.name} <span style={{ fontWeight: 800 }}>+{s.worst_variance_activity.variance_days}d</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {data.schedules?.length === 0 && <p className="rex-muted" style={{ marginTop: 12 }}>No schedules for this project.</p>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Activities View
// ─────────────────────────────────────────────────────────────────────────────

const SORT_KEYS = ["name", "wbs_code", "start_date", "end_date", "variance_days", "float_days", "percent_complete"];

function ActivitiesView({ filteredActivities, openDetail }) {
  const [sortKey, setSortKey] = useState("start_date");
  const [sortAsc, setSortAsc] = useState(true);

  function handleSort(key) {
    if (sortKey === key) setSortAsc(a => !a);
    else { setSortKey(key); setSortAsc(true); }
  }

  function SortTh({ k, label, right }) {
    const active = sortKey === k;
    return (
      <th
        onClick={() => handleSort(k)}
        style={{ cursor: "pointer", textAlign: right ? "right" : "left", userSelect: "none" }}
      >
        {label} {active ? (sortAsc ? "▲" : "▼") : ""}
      </th>
    );
  }

  const sorted = useMemo(() => {
    return [...filteredActivities].sort((a, b) => {
      let va = a[sortKey] ?? "";
      let vb = b[sortKey] ?? "";
      if (typeof va === "string") va = va.toLowerCase();
      if (typeof vb === "string") vb = vb.toLowerCase();
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });
  }, [filteredActivities, sortKey, sortAsc]);

  return (
    <div>
      <div style={{ marginBottom: 10 }}>
        <span className="rex-muted">{filteredActivities.length} activit{filteredActivities.length !== 1 ? "ies" : "y"}</span>
      </div>

      {sorted.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No activities match the current filters.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <SortTh k="wbs_code" label="WBS" />
                <SortTh k="activity_number" label="Activity #" />
                <SortTh k="name" label="Name" />
                <SortTh k="start_date" label="Planned Start" />
                <SortTh k="end_date" label="Planned End" />
                <th>Actual Start</th>
                <th>Actual End</th>
                <th>Baseline End</th>
                <SortTh k="percent_complete" label="% Complete" right />
                <SortTh k="variance_days" label="Variance" right />
                <SortTh k="float_days" label="Float" right />
                <th>Critical</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(a => {
                const variance = a.variance_days;
                const vColor = variance == null ? "" : variance > 5 ? "var(--rex-red)" : variance > 0 ? "var(--rex-amber)" : "var(--rex-green)";
                return (
                  <tr key={a.id} onClick={() => openDetail(a)}>
                    <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{a.wbs_code || "—"}</span></td>
                    <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{a.activity_number || "—"}</span></td>
                    <td>{a.name}</td>
                    <td>{fmtDate(a.start_date)}</td>
                    <td>{fmtDate(a.end_date)}</td>
                    <td>{fmtDate(a.actual_start_date)}</td>
                    <td>{fmtDate(a.actual_finish_date)}</td>
                    <td>{fmtDate(a.baseline_end)}</td>
                    <td style={{ textAlign: "right" }}>{a.percent_complete != null ? `${Math.round(a.percent_complete)}%` : "—"}</td>
                    <td style={{ textAlign: "right", color: vColor, fontWeight: variance > 0 ? 700 : 400 }}>{variance != null ? (variance > 0 ? `+${variance}d` : `${variance}d`) : "—"}</td>
                    <td style={{ textAlign: "right" }}>{a.float_days ?? "—"}</td>
                    <td>{a.is_critical ? <span className="rex-badge rex-badge-red">CRITICAL</span> : <span className="rex-badge rex-badge-gray">—</span>}</td>
                    <td>{statusBadge(a)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Lookahead View
// ─────────────────────────────────────────────────────────────────────────────

function LookaheadView({ filteredActivities, openDetail }) {
  const [constraints, setConstraints] = useState({});

  // Lookahead: next 4 weeks from today
  const today = useMemo(() => new Date(), []);
  const horizon = useMemo(() => new Date(today.getTime() + 28 * 86400000), [today]);

  const lookaheadActivities = useMemo(() => {
    return filteredActivities.filter(a => {
      const start = a.start_date ? new Date(a.start_date + "T00:00:00") : null;
      return start && start >= today && start <= horizon;
    });
  }, [filteredActivities, today, horizon]);

  // Fetch constraints for lookahead activities
  useEffect(() => {
    const ids = lookaheadActivities.slice(0, 100).map(a => a.id);
    if (ids.length === 0) return;
    const cMap = {};
    Promise.all(ids.map(async id => {
      try {
        const cs = await api(`/schedule-constraints?activity_id=${id}&limit=20`);
        cMap[id] = (cs || []).filter(c => c.status === "active");
      } catch {}
    })).then(() => setConstraints({ ...cMap }));
  }, [lookaheadActivities.length, lookaheadActivities.map(a => a.id).join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  function weekKey(dateStr) {
    const d = new Date(dateStr + "T00:00:00");
    const day = d.getDay();
    const monday = new Date(d.getTime() - ((day + 6) % 7) * 86400000);
    return monday.toISOString().slice(0, 10);
  }

  const grouped = useMemo(() => {
    const g = {};
    lookaheadActivities.forEach(a => {
      const k = weekKey(a.start_date);
      if (!g[k]) g[k] = [];
      g[k].push(a);
    });
    return g;
  }, [lookaheadActivities]);

  function constraintBadge(actId, sourceType, a) {
    const cs = (constraints[actId] || []).filter(c => c.source_type === sourceType);
    if (cs.length === 0) return <span className="rex-badge rex-badge-green">CLEAR</span>;
    const worst = cs.reduce((w, c) => (c.severity === "red" ? "red" : (w === "red" ? "red" : "yellow")), "yellow");
    const cls = worst === "red" ? "rex-badge-red" : "rex-badge-amber";
    return (
      <button
        className={`rex-badge ${cls}`}
        style={{ border: "none", cursor: "pointer" }}
        onClick={e => { e.stopPropagation(); openDetail(a); }}
        title="View constraints in detail"
      >
        {cs.length}
      </button>
    );
  }

  const weeks = Object.keys(grouped).sort();

  return (
    <div>
      <p className="rex-muted" style={{ marginBottom: 16 }}>
        Activities starting in the next 4 weeks ({lookaheadActivities.length} total). Constraint cells open detail panel.
      </p>
      {weeks.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No activities scheduled in the next 4 weeks.</div>
      ) : (
        weeks.map(wk => (
          <div key={wk} style={{ marginBottom: 24 }}>
            <h3 className="rex-h3" style={{ marginBottom: 8 }}>Week of {fmtDate(wk)}</h3>
            <div className="rex-table-wrap">
              <table className="rex-table">
                <thead>
                  <tr>
                    <th>Activity</th>
                    <th>WBS</th>
                    <th>Start</th>
                    <th>End</th>
                    <th>RFI</th>
                    <th>Submittal</th>
                    <th>Commitment</th>
                    <th>Insurance</th>
                    <th>Critical</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {grouped[wk].map(a => (
                    <tr key={a.id} onClick={() => openDetail(a)}>
                      <td>{a.activity_number ? `${a.activity_number} — ` : ""}{a.name}</td>
                      <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{a.wbs_code || "—"}</span></td>
                      <td>{fmtDate(a.start_date)}</td>
                      <td>{fmtDate(a.end_date)}</td>
                      <td onClick={e => e.stopPropagation()}>{constraintBadge(a.id, "rfi", a)}</td>
                      <td onClick={e => e.stopPropagation()}>{constraintBadge(a.id, "submittal", a)}</td>
                      <td onClick={e => e.stopPropagation()}>{constraintBadge(a.id, "commitment", a)}</td>
                      <td onClick={e => e.stopPropagation()}>{constraintBadge(a.id, "insurance", a)}</td>
                      <td>{a.is_critical ? <span className="rex-badge rex-badge-red">CP</span> : "—"}</td>
                      <td>
                        <button
                          className="rex-btn rex-btn-outline"
                          style={{ padding: "2px 8px", fontSize: 11 }}
                          onClick={e => { e.stopPropagation(); openDetail(a); }}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Critical Path View
// ─────────────────────────────────────────────────────────────────────────────

function CriticalView({ filteredActivities, openDetail }) {
  const [worstDriftFirst, setWorstDriftFirst] = useState(true);

  const criticalActivities = useMemo(() => {
    const base = filteredActivities.filter(a => a.is_critical || (a.float_days != null && a.float_days < 5));
    return [...base].sort((a, b) => {
      if (worstDriftFirst) {
        return (b.variance_days || 0) - (a.variance_days || 0);
      }
      if (a.is_critical !== b.is_critical) return b.is_critical - a.is_critical;
      if (a.float_days !== b.float_days) return (a.float_days || 0) - (b.float_days || 0);
      return (b.variance_days || 0) - (a.variance_days || 0);
    });
  }, [filteredActivities, worstDriftFirst]);

  const driftCount = criticalActivities.filter(a => a.variance_days != null && a.variance_days > 0).length;

  return (
    <div>
      <div className="rex-grid-4" style={{ marginBottom: 20 }}>
        <StatCard label="Critical Activities" value={criticalActivities.filter(a => a.is_critical).length} color="red" />
        <StatCard label="Near-Critical (Float < 5d)" value={criticalActivities.filter(a => !a.is_critical && a.float_days != null && a.float_days < 5).length} color="amber" />
        <StatCard label="Drifting Critical" value={driftCount} color={driftCount > 0 ? "red" : ""} />
        <StatCard label="Total Tracked" value={criticalActivities.length} />
      </div>

      <div style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 10 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
          <input type="checkbox" checked={worstDriftFirst} onChange={e => setWorstDriftFirst(e.target.checked)} />
          Worst drift first
        </label>
      </div>

      {criticalActivities.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No critical or near-critical activities match current filters.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Activity</th>
                <th>WBS</th>
                <th>Planned Finish</th>
                <th>Actual Finish</th>
                <th style={{ textAlign: "right" }}>% Complete</th>
                <th style={{ textAlign: "right" }}>Variance</th>
                <th style={{ textAlign: "right" }}>Float</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {criticalActivities.map(a => {
                const variance = a.variance_days;
                const vColor = variance == null ? "" : variance > 5 ? "var(--rex-red)" : variance > 0 ? "var(--rex-amber)" : "var(--rex-green)";
                const isNear = !a.is_critical;
                return (
                  <tr
                    key={a.id}
                    onClick={() => openDetail(a)}
                    style={isNear ? { background: "var(--rex-amber-bg)" } : undefined}
                  >
                    <td>{a.activity_number ? `${a.activity_number} — ` : ""}{a.name}</td>
                    <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{a.wbs_code || "—"}</span></td>
                    <td>{fmtDate(a.end_date)}</td>
                    <td>{fmtDate(a.actual_finish_date)}</td>
                    <td style={{ textAlign: "right" }}>{a.percent_complete != null ? `${Math.round(a.percent_complete)}%` : "—"}</td>
                    <td style={{ textAlign: "right", color: vColor, fontWeight: variance > 0 ? 700 : 400 }}>{variance != null ? (variance > 0 ? `+${variance}d` : `${variance}d`) : "—"}</td>
                    <td style={{ textAlign: "right" }}>{a.float_days ?? "—"}</td>
                    <td>{a.is_critical ? <span className="rex-badge rex-badge-red">CRITICAL</span> : <span className="rex-badge rex-badge-amber">NEAR</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main export: ScheduleHealth workbench
// ─────────────────────────────────────────────────────────────────────────────

export default function ScheduleHealth() {
  const { selected: project, selectedId } = useProject();

  // ── Shared data ──────────────────────────────────────────────────────────
  const [healthData, setHealthData] = useState(null);
  const [healthError, setHealthError] = useState(null);
  const [schedules, setSchedules] = useState([]);
  const [activities, setActivities] = useState(null);
  const [dataError, setDataError] = useState(null);
  const [people, setPeople] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [costCodes, setCostCodes] = useState([]);

  // ── Shared UI state ───────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState("gantt");
  const [selectedActivity, setSelectedActivity] = useState(null);
  const [scheduleId, setScheduleId] = useState("");

  // ── Filter state ──────────────────────────────────────────────────────────
  const [search, setSearch] = useState("");
  const [criticalOnly, setCriticalOnly] = useState(false);
  const [wbsRoot, setWbsRoot] = useState("");
  const [assignedCompany, setAssignedCompany] = useState("");
  const [assignedPerson, setAssignedPerson] = useState("");
  const [costCodeId, setCostCodeId] = useState("");
  const [location, setLocation] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  // ── Read URL state on mount ───────────────────────────────────────────────
  useEffect(() => {
    const s = readUrlState();
    if (s.tab) setActiveTab(s.tab);
    if (s.search) setSearch(s.search);
    if (s.criticalOnly === "true") setCriticalOnly(true);
    if (s.wbsRoot) setWbsRoot(s.wbsRoot);
    if (s.assignedCompany) setAssignedCompany(s.assignedCompany);
    if (s.assignedPerson) setAssignedPerson(s.assignedPerson);
    if (s.costCodeId) setCostCodeId(s.costCodeId);
    if (s.location) setLocation(s.location);
    if (s.dateFrom) setDateFrom(s.dateFrom);
    if (s.dateTo) setDateTo(s.dateTo);
    if (s.scheduleId) setScheduleId(s.scheduleId);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Sync filter state → URL ───────────────────────────────────────────────
  useEffect(() => {
    writeUrlState({ tab: activeTab, search, criticalOnly, wbsRoot, assignedCompany, assignedPerson, costCodeId, location, dateFrom, dateTo, scheduleId });
  }, [activeTab, search, criticalOnly, wbsRoot, assignedCompany, assignedPerson, costCodeId, location, dateFrom, dateTo, scheduleId]);

  // ── Fetch health summary ──────────────────────────────────────────────────
  useEffect(() => {
    if (!selectedId) return;
    setHealthData(null); setHealthError(null);
    api(`/projects/${selectedId}/schedule-health`).then(setHealthData).catch(e => setHealthError(e.message));
  }, [selectedId]);

  // ── Fetch all schedules + activities (once, shared) ───────────────────────
  useEffect(() => {
    if (!selectedId) return;
    setActivities(null); setDataError(null); setSchedules([]);
    (async () => {
      try {
        const sched = await api(`/schedules?project_id=${selectedId}&limit=50`);
        setSchedules(sched || []);
        const lists = await Promise.all(
          (sched || []).map(s => api(`/schedule-activities?schedule_id=${s.id}&limit=500`).catch(() => []))
        );
        setActivities(lists.flat());
      } catch (e) {
        setDataError(e.message);
      }
    })();
  }, [selectedId]);

  // ── Fetch lookup data ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!selectedId) return;
    api("/people?limit=500").then(setPeople).catch(() => {});
    api("/companies?limit=500").then(setCompanies).catch(() => {});
    api(`/cost-codes?project_id=${selectedId}&limit=500`).then(setCostCodes).catch(() => {});
  }, [selectedId]);

  // ── Lookup maps ───────────────────────────────────────────────────────────
  const peopleMap = useMemo(() => Object.fromEntries((people || []).map(p => [p.id, p])), [people]);
  const companiesMap = useMemo(() => Object.fromEntries((companies || []).map(c => [c.id, c])), [companies]);
  const costCodesMap = useMemo(() => Object.fromEntries((costCodes || []).map(c => [c.id, c])), [costCodes]);

  // ── WBS roots for filter dropdown ─────────────────────────────────────────
  const wbsRoots = useMemo(() => {
    if (!activities) return [];
    const roots = new Set();
    activities.forEach(a => {
      if (a.wbs_code) roots.add(a.wbs_code.split(".")[0]);
    });
    return [...roots].sort();
  }, [activities]);

  // ── Filtered activities (shared across all tabs) ──────────────────────────
  const filteredActivities = useMemo(() => {
    if (!activities) return [];
    const q = search.toLowerCase();
    return activities.filter(a => {
      if (scheduleId && a.schedule_id !== scheduleId) return false;
      if (q && !(a.name || "").toLowerCase().includes(q) && !(a.activity_number || "").toLowerCase().includes(q) && !(a.wbs_code || "").toLowerCase().includes(q) && !(a.location || "").toLowerCase().includes(q)) return false;
      if (wbsRoot && !(a.wbs_code || "").startsWith(wbsRoot)) return false;
      if (assignedCompany && a.assigned_company_id !== assignedCompany) return false;
      if (assignedPerson && a.assigned_person_id !== assignedPerson) return false;
      if (costCodeId && a.cost_code_id !== costCodeId) return false;
      if (location && !(a.location || "").toLowerCase().includes(location.toLowerCase())) return false;
      if (criticalOnly && !a.is_critical) return false;
      if (dateFrom && a.start_date && a.start_date < dateFrom) return false;
      if (dateTo && a.end_date && a.end_date > dateTo) return false;
      return true;
    });
  }, [activities, scheduleId, search, wbsRoot, assignedCompany, assignedPerson, costCodeId, location, criticalOnly, dateFrom, dateTo]);

  function resetFilters() {
    setSearch(""); setCriticalOnly(false); setWbsRoot(""); setAssignedCompany(""); setAssignedPerson(""); setCostCodeId(""); setLocation(""); setDateFrom(""); setDateTo(""); setScheduleId("");
  }

  const openDetail = useCallback((a) => setSelectedActivity(a), []);
  const closeDetail = useCallback(() => setSelectedActivity(null), []);

  // ── Build filter summary string for print ────────────────────────────────
  const filterSummary = useMemo(() => {
    const parts = [];
    if (search) parts.push(`search="${search}"`);
    if (criticalOnly) parts.push("critical only");
    if (wbsRoot) parts.push(`WBS root=${wbsRoot}`);
    if (assignedCompany) parts.push(`company=${companiesMap[assignedCompany]?.name || assignedCompany}`);
    if (assignedPerson) { const p = peopleMap[assignedPerson]; parts.push(`person=${p ? `${p.first_name} ${p.last_name}` : assignedPerson}`); }
    if (costCodeId) parts.push(`cost code=${costCodesMap[costCodeId]?.code || costCodeId}`);
    if (dateFrom) parts.push(`from=${dateFrom}`);
    if (dateTo) parts.push(`to=${dateTo}`);
    return parts.join("; ");
  }, [search, criticalOnly, wbsRoot, assignedCompany, assignedPerson, costCodeId, dateFrom, dateTo, companiesMap, peopleMap, costCodesMap]);

  // ── Export handlers ───────────────────────────────────────────────────────
  function handleExportCsv() {
    if (activeTab === "critical") exportCriticalCsv(filteredActivities.filter(a => a.is_critical || (a.float_days != null && a.float_days < 5)), project);
    else exportActivitiesCsv(filteredActivities, project);
  }

  function handleExportPrint() {
    exportPrint(filteredActivities, activeTab, project, filterSummary);
  }

  if (!selectedId) return <p className="rex-muted">Select a project.</p>;

  const loading = activities === null && !dataError;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Schedule Workbench</h1>
      <p className="rex-muted" style={{ marginBottom: 12 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      {/* ── Persistent Toolbar ── */}
      <div className="rex-card" style={{ marginBottom: 12, padding: "12px 14px" }}>
        {schedules.length > 1 && (
          <div className="rex-form-row" style={{ marginBottom: 10 }}>
            <div className="rex-form-group" style={{ flex: "0 0 auto" }}>
              <label htmlFor="sched-sel" style={{ fontSize: 12, fontWeight: 700, color: "var(--rex-text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>Schedule</label>
              <select id="sched-sel" className="rex-input" value={scheduleId} onChange={e => setScheduleId(e.target.value)} style={{ width: 220 }}>
                <option value="">All schedules</option>
                {schedules.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          </div>
        )}
        <div className="rex-form-row" style={{ alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          <input
            className="rex-input"
            placeholder="Search name, number, WBS, or location…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ flex: 1, minWidth: 220 }}
          />
          <select className="rex-input" value={wbsRoot} onChange={e => setWbsRoot(e.target.value)} style={{ width: 130 }}>
            <option value="">All WBS</option>
            {wbsRoots.map(r => <option key={r} value={r}>WBS {r}</option>)}
          </select>
          <select className="rex-input" value={assignedCompany} onChange={e => setAssignedCompany(e.target.value)} style={{ width: 160 }}>
            <option value="">All companies</option>
            {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select className="rex-input" value={assignedPerson} onChange={e => setAssignedPerson(e.target.value)} style={{ width: 160 }}>
            <option value="">All people</option>
            {people.map(p => <option key={p.id} value={p.id}>{p.first_name} {p.last_name}</option>)}
          </select>
          <select className="rex-input" value={costCodeId} onChange={e => setCostCodeId(e.target.value)} style={{ width: 160 }}>
            <option value="">All cost codes</option>
            {costCodes.map(c => <option key={c.id} value={c.id}>{c.code}</option>)}
          </select>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--rex-text)", cursor: "pointer", whiteSpace: "nowrap" }}>
            <input type="checkbox" checked={criticalOnly} onChange={e => setCriticalOnly(e.target.checked)} style={{ cursor: "pointer" }} />
            Critical only
          </label>
          <button className="rex-btn rex-btn-outline" onClick={resetFilters} title="Clear all filters" style={{ whiteSpace: "nowrap" }}>Clear</button>
          {activeTab !== "health" && activeTab !== "gantt" && (
            <>
              <button className="rex-btn rex-btn-outline" onClick={handleExportCsv} title="Export CSV" style={{ whiteSpace: "nowrap" }}>CSV</button>
              <button className="rex-btn rex-btn-outline" onClick={handleExportPrint} title="Export print-friendly" style={{ whiteSpace: "nowrap" }}>Print</button>
            </>
          )}
        </div>
      </div>

      {/* ── Tab bar ── */}
      <div className="rex-tab-bar">
        {[
          { key: "gantt", label: "Gantt" },
          { key: "health", label: "Health" },
          { key: "activities", label: "Activities" },
          { key: "lookahead", label: "Lookahead" },
          { key: "critical", label: "Critical Path" },
        ].map(({ key, label }) => (
          <button
            key={key}
            className={`rex-tab${activeTab === key ? " active" : ""}`}
            onClick={() => setActiveTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Data loading states ── */}
      {dataError && <Flash type="error" message={dataError} />}
      {loading && activeTab !== "health" && <PageLoader text="Loading schedule data…" />}

      {/* ── Tab content ── */}
      {activeTab === "gantt" && !loading && !dataError && (
        <GanttView activities={filteredActivities} schedules={schedules} openDetail={openDetail} />
      )}

      {activeTab === "health" && (
        healthError ? <Flash type="error" message={healthError} /> :
        !healthData ? <PageLoader text="Loading schedule health…" /> :
        <HealthView data={healthData} project={project} />
      )}

      {activeTab === "activities" && !loading && !dataError && (
        <ActivitiesView filteredActivities={filteredActivities} openDetail={openDetail} />
      )}

      {activeTab === "lookahead" && !loading && !dataError && (
        <LookaheadView filteredActivities={filteredActivities} openDetail={openDetail} />
      )}

      {activeTab === "critical" && !loading && !dataError && (
        <CriticalView filteredActivities={filteredActivities} openDetail={openDetail} />
      )}

      {/* ── Shared detail panel ── */}
      <DetailPanel
        activity={selectedActivity}
        onClose={closeDetail}
        peopleMap={peopleMap}
        companiesMap={companiesMap}
        costCodesMap={costCodesMap}
      />
    </div>
  );
}
