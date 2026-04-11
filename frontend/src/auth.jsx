import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { getToken, clearToken, api } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined); // undefined = loading

  const refreshUser = useCallback(() => {
    if (!getToken()) { setUser(null); return; }
    api("/auth/me")
      .then(setUser)
      .catch(() => { clearToken(); setUser(null); });
  }, []);

  useEffect(() => { refreshUser(); }, [refreshUser]);

  const logout = () => { clearToken(); setUser(null); };

  if (user === undefined) return <p style={{ padding: "2rem" }}>Loading...</p>;
  return <AuthCtx.Provider value={{ user, setUser, logout }}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  return useContext(AuthCtx);
}
