import { useState } from "react";
import { login as doLogin } from "../api";
import { useAuth } from "../auth";

export default function LoginPage() {
  const { setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const data = await doLogin(email, password);
      const res = await fetch("/api/auth/me", { headers: { Authorization: `Bearer ${data.token}` } });
      if (!res.ok) throw new Error("Failed to load profile");
      setUser(await res.json());
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", background: "var(--rex-sidebar-bg)" }}>
      <form onSubmit={submit} style={{ background: "#fff", padding: "2.5rem 2rem", borderRadius: 8, boxShadow: "var(--rex-shadow-md)", width: 360 }}>
        <div style={{ fontFamily: "'Syne', sans-serif", fontSize: 24, fontWeight: 800, color: "var(--rex-accent)", marginBottom: 24 }}>REX OS</div>
        {error && <div className="rex-alert rex-alert-red" style={{ marginBottom: 12 }}>{error}</div>}
        <label className="rex-section-label" style={{ display: "block", marginBottom: 6 }}>Email</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="aroberts@exxircapital.com"
          className="rex-input" style={{ width: "100%", marginBottom: 14 }} autoComplete="email" />
        <label className="rex-section-label" style={{ display: "block", marginBottom: 6 }}>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="rex2026!"
          className="rex-input" style={{ width: "100%", marginBottom: 18 }} autoComplete="current-password" />
        <button disabled={loading} className="rex-btn rex-btn-primary" style={{ width: "100%", justifyContent: "center", padding: "10px 0" }}>
          {loading ? "Signing in..." : "Sign In"}
        </button>
        <p className="rex-muted" style={{ textAlign: "center", marginTop: 12 }}>Demo: aroberts@exxircapital.com / rex2026!</p>
      </form>
    </div>
  );
}
