// ControlPlaneHome — operator surface for the Rex OS control plane.
//
// First-pass tabs (contract-driven, mocked for now):
//   Connectors  — health + sync status
//   Actions     — assistant catalog with readiness badges
//   Automations — scheduled job registry with readiness
//   Queue       — writeback / action approval queue (placeholder)
//   Roles       — role/capability inspector (placeholder)
//
// Everything is read-only in this first pass. Admin controls land in
// Phase 8 when the control plane becomes the operational dashboard.

import { useState } from "react";
import ConnectorHealthPanel from "./ConnectorHealthPanel";
import ActionCatalogPanel from "./ActionCatalogPanel";
import AutomationRegistryPanel from "./AutomationRegistryPanel";
import QueueReviewPanel from "./QueueReviewPanel";
import RoleCapabilityPanel from "./RoleCapabilityPanel";
import IntegrationDiagnosticsPanel from "./IntegrationDiagnosticsPanel";

const TABS = [
  { key: "connectors", label: "Connectors" },
  { key: "actions", label: "Actions" },
  { key: "automations", label: "Automations" },
  { key: "queue", label: "Queue" },
  { key: "roles", label: "Roles & capabilities" },
  { key: "integration", label: "Integration" },
];

export default function ControlPlaneHome() {
  const [activeTab, setActiveTab] = useState("connectors");

  return (
    <div className="rex-control-plane">
      <header className="rex-control-plane__header">
        <h1 className="rex-h1" style={{ margin: 0 }}>Control Plane</h1>
        <p className="rex-muted" style={{ marginTop: 6 }}>
          Operator visibility into connectors, action readiness, automation jobs,
          writeback queue, and role/capability wiring.
        </p>
      </header>

      <nav className="rex-tab-bar" role="tablist" aria-label="Control plane sections">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.key}
            className={`rex-tab${activeTab === tab.key ? " active" : ""}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="rex-control-plane__body">
        {activeTab === "connectors" && <ConnectorHealthPanel />}
        {activeTab === "actions" && <ActionCatalogPanel />}
        {activeTab === "automations" && <AutomationRegistryPanel />}
        {activeTab === "queue" && <QueueReviewPanel />}
        {activeTab === "roles" && <RoleCapabilityPanel />}
        {activeTab === "integration" && <IntegrationDiagnosticsPanel />}
      </div>
    </div>
  );
}
