import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";

type AuthState = {
  user: User | null;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      setUser(await api<User>("/account/me"));
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) console.error(error);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    await api<void>("/auth/logout", { method: "POST" });
    setUser(null);
  }

  useEffect(() => void refresh(), []);
  const value = useMemo(() => ({ user, loading, refresh, logout }), [user, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
