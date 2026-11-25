import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null | undefined; // undefined while the session is being checked
  signIn: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  setUser: (user: User) => void;
}

const AuthContext = createContext<AuthState>({} as AuthState);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    api.me().then(setUser).catch(() => setUser(null));
    const expired = () => setUser(null);
    window.addEventListener("hv:signed-out", expired);
    return () => window.removeEventListener("hv:signed-out", expired);
  }, []);

  const signIn = useCallback(async (email: string, password: string) => setUser(await api.login(email, password)), []);
  const register = useCallback(
    async (name: string, email: string, password: string) => setUser(await api.register(name, email, password)),
    [],
  );
  const signOut = useCallback(async () => {
    await api.logout().catch(() => undefined);
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, signIn, register, signOut, setUser }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);

/** Shows its children only to a signed-in person; others go to sign in and come back afterwards. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (user === undefined) {
    return <div className="grid min-h-screen place-items-center text-ink-soft">Loading…</div>;
  }
  if (user === null) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  }
  return <>{children}</>;
}
