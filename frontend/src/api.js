const TOKEN_KEY = "rex_token";

// API base URL.
//   - In dev: empty string → uses Vite proxy at /api → http://localhost:9000
//   - In prod (Vercel): set VITE_API_URL to the Railway backend URL,
//     e.g. https://rex-os-backend.up.railway.app
// Trailing slash stripped so we always join cleanly.
export const API_BASE = (import.meta.env?.VITE_API_URL || "").replace(/\/$/, "");

export function apiUrl(path) {
  // path may start with "/api/..." or just "/..." — both work
  if (path.startsWith("/api")) return `${API_BASE}${path}`;
  return `${API_BASE}/api${path}`;
}

function url(path) {
  return apiUrl(path);
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export async function api(path, opts = {}) {
  const token = getToken();
  const headers = { ...(opts.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (opts.body && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  const res = await fetch(url(path), { ...opts, headers });
  if (res.status === 401) {
    clearToken();
    window.location.hash = "#/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  if (res.headers.get("content-type")?.includes("json")) return res.json();
  return res;
}

export async function login(email, password) {
  const res = await fetch(url("/auth/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Login failed");
  }
  const data = await res.json();
  setToken(data.token);
  return data;
}
