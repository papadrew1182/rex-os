import { useMemo } from "react";
import { useAuth } from "../auth";
import { useProject } from "../project";
import { Card, StatCard, Badge } from "../ui";

function Header({ title, subtitle, roleLabel }) {
  return (
    <div className="rex-page-header">
      <div>
        <h1 className="rex-h1">{title}</h1>
        <p className="rex-muted" style={{ marginTop: 6 }}>{subtitle}</p>
      </div>
      <span className="rex-role-chip">{roleLabel}</span>
    </div>
  );
}

function VPDashboard({ selected }) {
  return (
    <>
      <Header title="Executive Overview" subtitle="Portfolio and risk signal summary" roleLabel="VP" />
      <div className="rex-grid-4" style={{ marginTop: 16 }}>
        <StatCard label="Active Projects" value="12" sub="2 at risk" />
        <StatCard label="Open RFIs" value="34" color="amber" sub="6 overdue" />
        <StatCard label="Submittals" value="51" sub="9 pending approval" />
        <StatCard label="Change Events" value="18" color="red" sub="$842k exposure" />
      </div>
      <div className="rex-grid-2" style={{ marginTop: 16 }}>
        <Card title="Priority Risks">
          <div className="rex-row"><span className="rex-row-label">{selected?.name || "Bishop Modern"}</span><Badge status="warning" label="Schedule Risk" /></div>
          <div className="rex-row"><span className="rex-row-label">Ridgeview Medical</span><Badge status="fail" label="Cost Variance" /></div>
          <div className="rex-row"><span className="rex-row-label">North Campus Lab</span><Badge status="pending" label="Awaiting Owner" /></div>
        </Card>
        <Card title="This Week">
          <div className="rex-row"><span className="rex-row-label">Assistant auto-commits</span><span className="rex-row-value">61</span></div>
          <div className="rex-row"><span className="rex-row-label">Approval-required actions</span><span className="rex-row-value">13</span></div>
          <div className="rex-row"><span className="rex-row-label">Undo operations</span><span className="rex-row-value">4</span></div>
        </Card>
      </div>
    </>
  );
}

function PMDashboard({ selected }) {
  return (
    <>
      <Header title="Project Manager Dashboard" subtitle={`Operational pulse for ${selected?.name || "current project"}`} roleLabel="PM" />
      <div className="rex-grid-4" style={{ marginTop: 16 }}>
        <StatCard label="Open Tasks" value="27" sub="8 due this week" />
        <StatCard label="RFIs" value="12" color="amber" sub="3 aging > 10d" />
        <StatCard label="Submittals" value="19" sub="7 awaiting response" />
        <StatCard label="Daily Logs" value="6" color="green" sub="last 7 days" />
      </div>
      <div className="rex-grid-2" style={{ marginTop: 16 }}>
        <Card title="Approvals Queue">
          <div className="rex-row"><span className="rex-row-label">Financial decisions</span><Badge status="warning" label="4 pending" /></div>
          <div className="rex-row"><span className="rex-row-label">External effects</span><Badge status="pending" label="2 pending" /></div>
          <div className="rex-row"><span className="rex-row-label">Failed actions</span><Badge status="fail" label="1 failed" /></div>
        </Card>
        <Card title="Upcoming Milestones">
          <div className="rex-row"><span className="rex-row-label">Steel delivery complete</span><span className="rex-row-value">May 22</span></div>
          <div className="rex-row"><span className="rex-row-label">MEP rough-in start</span><span className="rex-row-value">May 25</span></div>
          <div className="rex-row"><span className="rex-row-label">Owner walkthrough</span><span className="rex-row-value">May 29</span></div>
        </Card>
      </div>
    </>
  );
}

function GeneralSuperDashboard({ selected }) {
  return (
    <>
      <Header title="General Superintendent" subtitle={`Field execution for ${selected?.name || "active site"}`} roleLabel="GENERAL SUPER" />
      <div className="rex-grid-4" style={{ marginTop: 16 }}>
        <StatCard label="Two-Week Tasks" value="41" sub="11 critical path" />
        <StatCard label="Inspections" value="7" color="amber" sub="2 failed" />
        <StatCard label="Safety Items" value="5" color="red" sub="1 high severity" />
        <StatCard label="Punch Items" value="24" sub="9 open" />
      </div>
      <div className="rex-grid-2" style={{ marginTop: 16 }}>
        <Card title="Field Priorities">
          <div className="rex-row"><span className="rex-row-label">Level 2 drywall</span><Badge status="in_progress" label="In progress" /></div>
          <div className="rex-row"><span className="rex-row-label">Roof curb install</span><Badge status="warning" label="Weather risk" /></div>
          <div className="rex-row"><span className="rex-row-label">Fire stop closeout</span><Badge status="pending" label="Pending signoff" /></div>
        </Card>
        <Card title="Daily Log Snapshot">
          <div className="rex-row"><span className="rex-row-label">Labor count</span><span className="rex-row-value">62</span></div>
          <div className="rex-row"><span className="rex-row-label">Equipment active</span><span className="rex-row-value">14</span></div>
          <div className="rex-row"><span className="rex-row-label">Weather delay hrs</span><span className="rex-row-value">1.5</span></div>
        </Card>
      </div>
    </>
  );
}

function LeadSuperDashboard({ selected }) {
  return (
    <>
      <Header title="Lead Superintendent" subtitle={`Crew-level execution for ${selected?.name || "selected project"}`} roleLabel="LEAD / ASSISTANT SUPER" />
      <div className="rex-grid-4" style={{ marginTop: 16 }}>
        <StatCard label="Today Tasks" value="16" sub="5 blocking" />
        <StatCard label="Open Punch" value="11" color="amber" sub="4 priority" />
        <StatCard label="RFIs Watching" value="8" sub="2 urgent" />
        <StatCard label="Photos Uploaded" value="37" color="green" sub="today" />
      </div>
      <div className="rex-grid-2" style={{ marginTop: 16 }}>
        <Card title="Immediate Actions">
          <div className="rex-row"><span className="rex-row-label">Concrete pour prep</span><Badge status="pending" label="Pending" /></div>
          <div className="rex-row"><span className="rex-row-label">Door hardware verify</span><Badge status="in_progress" label="In progress" /></div>
          <div className="rex-row"><span className="rex-row-label">Masonry mockup</span><Badge status="achieved" label="Complete" /></div>
        </Card>
        <Card title="Crew Notes">
          <div className="rex-row"><span className="rex-row-label">Foreman updates posted</span><span className="rex-row-value">9</span></div>
          <div className="rex-row"><span className="rex-row-label">Open blockers</span><span className="rex-row-value">3</span></div>
          <div className="rex-row"><span className="rex-row-label">Inspections scheduled</span><span className="rex-row-value">2</span></div>
        </Card>
      </div>
    </>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { selected } = useProject();

  const role = useMemo(() => {
    if (!user) return "pm";
    if (user.is_admin || user.global_role === "vp") return "vp";
    if (user.global_role === "pm") return "pm";
    if (user.global_role === "general_super") return "general_super";
    if (user.global_role === "lead_super" || user.global_role === "assistant_super") return "lead_super";
    return "pm";
  }, [user]);

  if (role === "vp") return <VPDashboard selected={selected} />;
  if (role === "general_super") return <GeneralSuperDashboard selected={selected} />;
  if (role === "lead_super") return <LeadSuperDashboard selected={selected} />;
  return <PMDashboard selected={selected} />;
}
