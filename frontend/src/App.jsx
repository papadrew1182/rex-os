import { useState } from "react";
import { HashRouter, Routes, Route, Link, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { ProjectProvider, useProject } from "./project";
import { NotificationProvider, NotificationBell } from "./notifications";
import ErrorBoundary from "./ErrorBoundary";
import BuildVersionChip from "./BuildVersionChip";
import { AppProvider } from "./app/AppContext";
import AssistantSidebar from "./assistant/AssistantSidebar";
import MyDayHome from "./myday/MyDayHome";
import ControlPlaneHome from "./controlPlane/ControlPlaneHome";
import ProjectDashboard from "./app/ProjectDashboard";
import LoginPage from "./pages/Login";
import Portfolio from "./pages/Portfolio";
import Companies from "./pages/Companies";
import People from "./pages/People";
import ProjectReadiness from "./pages/ProjectReadiness";
import Checklists from "./pages/Checklists";
import Milestones from "./pages/Milestones";
import Attachments from "./pages/Attachments";
import ScheduleHealth from "./pages/ScheduleHealth";
import ExecutionHealth from "./pages/ExecutionHealth";
import BudgetOverview from "./pages/BudgetOverview";
import PayApplications from "./pages/PayApplications";
import Commitments from "./pages/Commitments";
import ChangeOrders from "./pages/ChangeOrders";
import RfiManagement from "./pages/RfiManagement";
import PunchList from "./pages/PunchList";
import SubmittalManagement from "./pages/SubmittalManagement";
import DailyLogs from "./pages/DailyLogs";
import Inspections from "./pages/Inspections";
import Tasks from "./pages/Tasks";
import Drawings from "./pages/Drawings";
import Specifications from "./pages/Specifications";
import Correspondence from "./pages/Correspondence";
import Photos from "./pages/Photos";
import Meetings from "./pages/Meetings";
import Observations from "./pages/Observations";
import SafetyIncidents from "./pages/SafetyIncidents";
import Warranties from "./pages/Warranties";
import OmManuals from "./pages/OmManuals";
import InsuranceCertificates from "./pages/InsuranceCertificates";
import Notifications from "./pages/Notifications";
import AdminJobs from "./pages/AdminJobs";

function SidebarItem({ to, children }) {
  const loc = useLocation();
  const active = loc.pathname === to || (to !== "/" && loc.pathname.startsWith(to));
  return <Link to={to} className={`rex-sidebar-item${active ? " active" : ""}`}>{children}</Link>;
}

function Shell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  if (!user) return <LoginPage />;

  return (
    <ProjectProvider>
      <NotificationProvider>
      <AppProvider>
      <div className={`rex-shell${sidebarOpen ? " rex-shell--sidebar-open" : ""}`}>
        {/* Sidebar backdrop — only shown on small screens when toggled */}
        <div
          className="rex-sidebar-backdrop"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
        {/* Sidebar */}
        <aside className="rex-sidebar" onClick={() => setSidebarOpen(false)}>
          <div className="rex-sidebar-brand">REX OS</div>
          <div className="rex-sidebar-group">Overview</div>
          <SidebarItem to="/">Portfolio</SidebarItem>
          <SidebarItem to="/my-day">My Day</SidebarItem>
          <div className="rex-sidebar-group">Financials</div>
          <SidebarItem to="/budget">Budget Overview</SidebarItem>
          <SidebarItem to="/pay-apps">Pay Applications</SidebarItem>
          <SidebarItem to="/commitments">Commitments</SidebarItem>
          <SidebarItem to="/change-orders">Change Orders</SidebarItem>
          <div className="rex-sidebar-group">Field Ops</div>
          <SidebarItem to="/rfis">RFIs</SidebarItem>
          <SidebarItem to="/punch-list">Punch List</SidebarItem>
          <SidebarItem to="/submittals">Submittals</SidebarItem>
          <SidebarItem to="/daily-logs">Daily Logs</SidebarItem>
          <SidebarItem to="/inspections">Inspections</SidebarItem>
          <SidebarItem to="/tasks">Tasks</SidebarItem>
          <SidebarItem to="/meetings">Meetings</SidebarItem>
          <SidebarItem to="/observations">Observations</SidebarItem>
          <SidebarItem to="/safety">Safety Incidents</SidebarItem>
          <div className="rex-sidebar-group">Document Management</div>
          <SidebarItem to="/drawings">Drawings</SidebarItem>
          <SidebarItem to="/specifications">Specifications</SidebarItem>
          <SidebarItem to="/photos">Photos</SidebarItem>
          <SidebarItem to="/correspondence">Correspondence</SidebarItem>
          <div className="rex-sidebar-group">Closeout &amp; Warranty</div>
          <SidebarItem to="/warranties">Warranties</SidebarItem>
          <SidebarItem to="/om-manuals">O&amp;M Manuals</SidebarItem>
          <div className="rex-sidebar-group">Compliance</div>
          <SidebarItem to="/insurance">Insurance Certificates</SidebarItem>
          <div className="rex-sidebar-group">Project</div>
          <SidebarItem to="/schedule">Schedule Health</SidebarItem>
          <SidebarItem to="/execution">Execution Health</SidebarItem>
          <SidebarItem to="/checklists">Checklists</SidebarItem>
          <SidebarItem to="/milestones">Milestones</SidebarItem>
          <SidebarItem to="/attachments">Attachments</SidebarItem>
          <div className="rex-sidebar-group">Inbox</div>
          <SidebarItem to="/notifications">Notifications</SidebarItem>
          {(user.is_admin || user.global_role === "vp") && (
            <>
              <div className="rex-sidebar-group">Admin</div>
              <SidebarItem to="/companies">Companies</SidebarItem>
              <SidebarItem to="/people">People &amp; Members</SidebarItem>
              <SidebarItem to="/admin/jobs">Operations</SidebarItem>
              <SidebarItem to="/control-plane">Control Plane</SidebarItem>
            </>
          )}
          <div className="rex-sidebar-bottom">
            <div style={{ fontSize: 12, color: "var(--rex-sidebar-muted)", marginBottom: 6 }}>
              {user.first_name || user.email}
              {user.is_admin && <span className="rex-badge rex-badge-purple" style={{ marginLeft: 6, fontSize: 9 }}>ADMIN</span>}
            </div>
            <button onClick={logout} className="rex-btn rex-btn-outline" style={{
              width: "100%", justifyContent: "center", fontSize: 12, padding: "5px 0",
              color: "var(--rex-sidebar-muted)", borderColor: "rgba(255,255,255,0.15)",
            }}>Sign Out</button>
            <BuildVersionChip />
          </div>
        </aside>

        {/* Main area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: "100vh", minWidth: 0 }}>
          <Topbar onMenuToggle={() => setSidebarOpen((v) => !v)} />
          <div className="rex-content">
            <ErrorBoundary routeKey={location.pathname}>
              <Routes>
                <Route path="/" element={<Portfolio />} />
                <Route path="/project/:projectId" element={<ProjectReadiness />} />
                <Route path="/schedule" element={<ScheduleHealth />} />
                <Route path="/execution" element={<ExecutionHealth />} />
                <Route path="/checklists" element={<Checklists />} />
                <Route path="/milestones" element={<Milestones />} />
                <Route path="/attachments" element={<Attachments />} />
                <Route path="/budget" element={<BudgetOverview />} />
                <Route path="/pay-apps" element={<PayApplications />} />
                <Route path="/commitments" element={<Commitments />} />
                <Route path="/change-orders" element={<ChangeOrders />} />
                <Route path="/rfis" element={<RfiManagement />} />
                <Route path="/punch-list" element={<PunchList />} />
                <Route path="/submittals" element={<SubmittalManagement />} />
                <Route path="/daily-logs" element={<DailyLogs />} />
                <Route path="/inspections" element={<Inspections />} />
                <Route path="/tasks" element={<Tasks />} />
                <Route path="/drawings" element={<Drawings />} />
                <Route path="/specifications" element={<Specifications />} />
                <Route path="/correspondence" element={<Correspondence />} />
                <Route path="/photos" element={<Photos />} />
                <Route path="/meetings" element={<Meetings />} />
                <Route path="/observations" element={<Observations />} />
                <Route path="/safety" element={<SafetyIncidents />} />
                <Route path="/warranties" element={<Warranties />} />
                <Route path="/om-manuals" element={<OmManuals />} />
                <Route path="/insurance" element={<InsuranceCertificates />} />
                <Route path="/notifications" element={<Notifications />} />
                <Route path="/admin/jobs" element={<AdminJobs />} />
                <Route path="/companies" element={<Companies />} />
                <Route path="/people" element={<People />} />
                <Route path="/my-day" element={<MyDayHome />} />
                <Route path="/control-plane" element={<ControlPlaneHome />} />
                <Route path="/projects/:projectSlug" element={<ProjectDashboard />} />
                <Route path="/login" element={<Navigate to="/" />} />
              </Routes>
            </ErrorBoundary>
          </div>
        </div>
        <AssistantSidebar />
      </div>
      </AppProvider>
      </NotificationProvider>
    </ProjectProvider>
  );
}

function Topbar({ onMenuToggle }) {
  const { projects, selected, selectedId, select } = useProject();
  return (
    <div className="rex-topbar">
      <button
        type="button"
        className="rex-topbar-menu"
        aria-label="Toggle navigation menu"
        onClick={onMenuToggle}
      >
        <span aria-hidden="true">☰</span>
      </button>
      {selected && (
        <span className="rex-topbar-project">
          <span style={{ display: "inline-block", width: 7, height: 7, background: "var(--rex-green)", borderRadius: "50%", marginRight: 8 }} />
          {selected.name}
          {selected.project_number && <span className="rex-muted" style={{ marginLeft: 6 }}>{selected.project_number}</span>}
        </span>
      )}
      <div className="rex-topbar-right">
        <NotificationBell />
        <select
          value={selectedId || ""}
          onChange={(e) => select(e.target.value)}
          className="rex-input rex-topbar-project-select"
          aria-label="Select project"
        >
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}{p.project_number ? ` (${p.project_number})` : ""}</option>)}
        </select>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <HashRouter>
      <AuthProvider>
        <Shell />
      </AuthProvider>
    </HashRouter>
  );
}
