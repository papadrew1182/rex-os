import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { HashRouter, Routes, Route, Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { ProjectProvider, useProject } from "./project";
import { NotificationProvider, NotificationBell } from "./notifications";
import ErrorBoundary from "./ErrorBoundary";
import BuildVersionChip from "./BuildVersionChip";
import { AppProvider } from "./app/AppContext";
import AssistantSidebar from "./assistant/AssistantSidebar";
import AiPanel, { AiFab } from "./AiPanel";
import { PageLoader } from "./ui";

const MyDayHome = lazy(() => import("./myday/MyDayHome"));
const ControlPlaneHome = lazy(() => import("./controlPlane/ControlPlaneHome"));
const ProjectDashboard = lazy(() => import("./app/ProjectDashboard"));
const LoginPage = lazy(() => import("./pages/Login"));
const Portfolio = lazy(() => import("./pages/Portfolio"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Companies = lazy(() => import("./pages/Companies"));
const People = lazy(() => import("./pages/People"));
const ProjectReadiness = lazy(() => import("./pages/ProjectReadiness"));
const Checklists = lazy(() => import("./pages/Checklists"));
const Milestones = lazy(() => import("./pages/Milestones"));
const Attachments = lazy(() => import("./pages/Attachments"));
const ScheduleHealth = lazy(() => import("./pages/ScheduleHealth"));
const ExecutionHealth = lazy(() => import("./pages/ExecutionHealth"));
const BudgetOverview = lazy(() => import("./pages/BudgetOverview"));
const PayApplications = lazy(() => import("./pages/PayApplications"));
const Commitments = lazy(() => import("./pages/Commitments"));
const ChangeOrders = lazy(() => import("./pages/ChangeOrders"));
const RfiManagement = lazy(() => import("./pages/RfiManagement"));
const PunchList = lazy(() => import("./pages/PunchList"));
const SubmittalManagement = lazy(() => import("./pages/SubmittalManagement"));
const DailyLogs = lazy(() => import("./pages/DailyLogs"));
const Inspections = lazy(() => import("./pages/Inspections"));
const Tasks = lazy(() => import("./pages/Tasks"));
const Drawings = lazy(() => import("./pages/Drawings"));
const Specifications = lazy(() => import("./pages/Specifications"));
const Correspondence = lazy(() => import("./pages/Correspondence"));
const Photos = lazy(() => import("./pages/Photos"));
const Meetings = lazy(() => import("./pages/Meetings"));
const Observations = lazy(() => import("./pages/Observations"));
const SafetyIncidents = lazy(() => import("./pages/SafetyIncidents"));
const Warranties = lazy(() => import("./pages/Warranties"));
const OmManuals = lazy(() => import("./pages/OmManuals"));
const InsuranceCertificates = lazy(() => import("./pages/InsuranceCertificates"));
const Notifications = lazy(() => import("./pages/Notifications"));
const AdminJobs = lazy(() => import("./pages/AdminJobs"));

function SidebarItem({ to, children, onClick }) {
  const loc = useLocation();
  const active = loc.pathname === to || (to !== "/" && loc.pathname.startsWith(to));
  return <Link to={to} className={`rex-sidebar-item${active ? " active" : ""}`} onClick={onClick}>{children}</Link>;
}

function SidebarSection({ title, defaultCollapsed = false, children }) {
  const key = `rex_nav_collapsed_${title.toLowerCase().replace(/\s+/g, "_")}`;
  const [collapsed, setCollapsed] = useState(() => {
    const saved = localStorage.getItem(key);
    if (saved === "1") return true;
    if (saved === "0") return false;
    return defaultCollapsed;
  });

  function toggle() {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem(key, next ? "1" : "0");
  }

  return (
    <div className="rex-sidebar-section">
      <button type="button" className="rex-sidebar-group rex-sidebar-group-btn" onClick={toggle}>
        <span>{title}</span>
        <span className={`rex-chevron${collapsed ? " collapsed" : ""}`}>⌄</span>
      </button>
      {!collapsed && children}
    </div>
  );
}

function MobileBottomNav({ onOpenAi }) {
  const location = useLocation();
  const navigate = useNavigate();
  const items = useMemo(() => ([
    { label: "Home", path: "/" },
    { label: "Portfolio", path: "/portfolio" },
    { label: "My Day", path: "/my-day" },
    { label: "AI", path: "__ai__" },
  ]), []);

  return (
    <nav className="rex-mobile-nav" aria-label="Mobile quick navigation">
      {items.map((item) => {
        const active = item.path !== "__ai__" && location.pathname === item.path;
        return (
          <button
            type="button"
            key={item.label}
            className={`rex-mobile-nav-btn${active ? " active" : ""}`}
            onClick={() => (item.path === "__ai__" ? onOpenAi() : navigate(item.path))}
          >
            {item.label}
          </button>
        );
      })}
    </nav>
  );
}

function Shell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [routeLoading, setRouteLoading] = useState(false);

  useEffect(() => {
    if (!user) return undefined;
    setRouteLoading(true);
    const timer = window.setTimeout(() => setRouteLoading(false), 350);
    return () => window.clearTimeout(timer);
  }, [user, location.pathname, location.search]);

  if (!user) {
    return (
      <Suspense fallback={<PageLoader text="Loading login…" />}>
        <LoginPage />
      </Suspense>
    );
  }

  return (
    <ProjectProvider>
      <NotificationProvider>
        <AppProvider>
          <div className={`rex-shell${sidebarOpen ? " rex-shell--sidebar-open" : ""}`}>
            <div className="rex-sidebar-backdrop" onClick={() => setSidebarOpen(false)} aria-hidden="true" />

            <aside className="rex-sidebar" onClick={() => setSidebarOpen(false)}>
              <div className="rex-sidebar-brand">REX OS</div>

              <div className="rex-sidebar-group">Overview</div>
              <SidebarItem to="/">Dashboard</SidebarItem>
              <SidebarItem to="/portfolio">Portfolio</SidebarItem>
              <SidebarItem to="/my-day">My Day</SidebarItem>

              <SidebarSection title="Financials" defaultCollapsed>
                <SidebarItem to="/budget">Budget Overview</SidebarItem>
                <SidebarItem to="/pay-apps">Pay Applications</SidebarItem>
                <SidebarItem to="/commitments">Commitments</SidebarItem>
                <SidebarItem to="/change-orders">Change Orders</SidebarItem>
              </SidebarSection>

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

              <SidebarSection title="Document Management" defaultCollapsed>
                <SidebarItem to="/drawings">Drawings</SidebarItem>
                <SidebarItem to="/specifications">Specifications</SidebarItem>
                <SidebarItem to="/photos">Photos</SidebarItem>
                <SidebarItem to="/correspondence">Correspondence</SidebarItem>
              </SidebarSection>

              <SidebarSection title="Closeout & Warranty" defaultCollapsed>
                <SidebarItem to="/warranties">Warranties</SidebarItem>
                <SidebarItem to="/om-manuals">O&M Manuals</SidebarItem>
              </SidebarSection>

              <SidebarSection title="Compliance" defaultCollapsed>
                <SidebarItem to="/insurance">Insurance Certificates</SidebarItem>
              </SidebarSection>

              <SidebarSection title="Project" defaultCollapsed>
                <SidebarItem to="/schedule">Schedule Health</SidebarItem>
                <SidebarItem to="/execution">Execution Health</SidebarItem>
                <SidebarItem to="/checklists">Checklists</SidebarItem>
                <SidebarItem to="/milestones">Milestones</SidebarItem>
                <SidebarItem to="/attachments">Attachments</SidebarItem>
              </SidebarSection>

              <div className="rex-sidebar-group">Inbox</div>
              <SidebarItem to="/notifications">Notifications</SidebarItem>

              {(user.is_admin || user.global_role === "vp") && (
                <>
                  <div className="rex-sidebar-group">Admin</div>
                  <SidebarItem to="/companies">Companies</SidebarItem>
                  <SidebarItem to="/people">People & Members</SidebarItem>
                  <SidebarItem to="/admin/jobs">Operations</SidebarItem>
                  <SidebarItem to="/control-plane">Control Plane</SidebarItem>
                </>
              )}

              <div className="rex-sidebar-bottom">
                <div style={{ fontSize: 12, color: "var(--rex-sidebar-muted)", marginBottom: 6 }}>
                  {user.first_name || user.email}
                  {user.is_admin && <span className="rex-badge rex-badge-purple" style={{ marginLeft: 6, fontSize: 9 }}>ADMIN</span>}
                </div>
                <button
                  onClick={logout}
                  className="rex-btn rex-btn-outline"
                  style={{
                    width: "100%",
                    justifyContent: "center",
                    fontSize: 12,
                    padding: "5px 0",
                    color: "var(--rex-sidebar-muted)",
                    borderColor: "rgba(255,255,255,0.15)",
                  }}
                >
                  Sign Out
                </button>
                <BuildVersionChip />
              </div>
            </aside>

            <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: "100vh", minWidth: 0 }}>
              <Topbar onMenuToggle={() => setSidebarOpen((v) => !v)} />
              <div className={`rex-route-loader${routeLoading ? " active" : ""}`} aria-hidden="true" />
              <div className="rex-content">
                <div className="rex-content-inner">
                  <ErrorBoundary routeKey={location.pathname}>
                    <Suspense fallback={<PageLoader text="Loading page…" />}>
                      <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/portfolio" element={<Portfolio />} />
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
                    </Suspense>
                  </ErrorBoundary>
                </div>
              </div>
            </div>

            <AiFab onClick={() => setAiOpen(true)} />
            <AiPanel open={aiOpen} onClose={() => setAiOpen(false)} />
            <MobileBottomNav onOpenAi={() => setAiOpen(true)} />
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
      <button type="button" className="rex-topbar-menu" aria-label="Toggle navigation menu" onClick={onMenuToggle}>
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
        <select value={selectedId || ""} onChange={(e) => select(e.target.value)} className="rex-input rex-topbar-project-select" aria-label="Select project">
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
