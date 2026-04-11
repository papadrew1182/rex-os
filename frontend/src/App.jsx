import { HashRouter, Routes, Route, Link, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { ProjectProvider, useProject } from "./project";
import ErrorBoundary from "./ErrorBoundary";
import LoginPage from "./pages/Login";
import Portfolio from "./pages/Portfolio";
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

function SidebarItem({ to, children }) {
  const loc = useLocation();
  const active = loc.pathname === to || (to !== "/" && loc.pathname.startsWith(to));
  return <Link to={to} className={`rex-sidebar-item${active ? " active" : ""}`}>{children}</Link>;
}

function Shell() {
  const { user, logout } = useAuth();
  const loc = useLocation();
  if (!user) return <LoginPage />;

  return (
    <ProjectProvider>
      <div className="rex-shell">
        {/* Sidebar */}
        <aside className="rex-sidebar">
          <div className="rex-sidebar-brand">REX OS</div>
          <div className="rex-sidebar-group">Overview</div>
          <SidebarItem to="/">Portfolio</SidebarItem>
          <div className="rex-sidebar-group">Financials</div>
          <SidebarItem to="/budget">Budget Overview</SidebarItem>
          <SidebarItem to="/pay-apps">Pay Applications</SidebarItem>
          <SidebarItem to="/commitments">Commitments</SidebarItem>
          <SidebarItem to="/change-orders">Change Orders</SidebarItem>
          <div className="rex-sidebar-group">Field Ops</div>
          <SidebarItem to="/rfis">RFIs</SidebarItem>
          <SidebarItem to="/punch-list">Punch List</SidebarItem>
          <SidebarItem to="/submittals">Submittals</SidebarItem>
          <div className="rex-sidebar-group">Project</div>
          <SidebarItem to="/schedule">Schedule Health</SidebarItem>
          <SidebarItem to="/execution">Execution Health</SidebarItem>
          <SidebarItem to="/checklists">Checklists</SidebarItem>
          <SidebarItem to="/milestones">Milestones</SidebarItem>
          <SidebarItem to="/attachments">Attachments</SidebarItem>
          <div className="rex-sidebar-bottom">
            <div style={{ fontSize: 12, color: "var(--rex-sidebar-muted)", marginBottom: 6 }}>
              {user.first_name || user.email}
              {user.is_admin && <span className="rex-badge rex-badge-purple" style={{ marginLeft: 6, fontSize: 9 }}>ADMIN</span>}
            </div>
            <button onClick={logout} className="rex-btn rex-btn-outline" style={{
              width: "100%", justifyContent: "center", fontSize: 12, padding: "5px 0",
              color: "var(--rex-sidebar-muted)", borderColor: "rgba(255,255,255,0.15)",
            }}>Sign Out</button>
          </div>
        </aside>

        {/* Main area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: "100vh" }}>
          <Topbar />
          <div className="rex-content">
            <ErrorBoundary>
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
                <Route path="/login" element={<Navigate to="/" />} />
              </Routes>
            </ErrorBoundary>
          </div>
        </div>
      </div>
    </ProjectProvider>
  );
}

function Topbar() {
  const { projects, selected, selectedId, select } = useProject();
  return (
    <div className="rex-topbar">
      {selected && (
        <span className="rex-topbar-project">
          <span style={{ display: "inline-block", width: 7, height: 7, background: "var(--rex-green)", borderRadius: "50%", marginRight: 8 }} />
          {selected.name}
          {selected.project_number && <span className="rex-muted" style={{ marginLeft: 6 }}>{selected.project_number}</span>}
        </span>
      )}
      <div className="rex-topbar-right">
        <select value={selectedId || ""} onChange={(e) => select(e.target.value)} className="rex-input" style={{ width: 180, padding: "5px 8px" }}>
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
