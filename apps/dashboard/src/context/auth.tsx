import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { AuthUser } from "../auth/authService";
import { useServices } from "./services";

export type AuthStatus = "loading" | "signedOut" | "signedIn";

interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  signIn: (returnTo: string, locale: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { auth } = useServices();
  const [state, setState] = useState<{ status: AuthStatus; user: AuthUser | null }>({
    status: "loading",
    user: null,
  });

  useEffect(() => {
    let active = true;
    const unsubscribe = auth.subscribe((user) => {
      if (active) setState({ status: user ? "signedIn" : "signedOut", user });
    });
    // The callback page completes the sign-in itself; elsewhere restore the stored session.
    if (window.location.pathname !== "/callback") {
      auth
        .load()
        .then((user) => {
          if (active) setState({ status: user ? "signedIn" : "signedOut", user });
        })
        .catch(() => {
          if (active) setState({ status: "signedOut", user: null });
        });
    }
    return () => {
      active = false;
      unsubscribe();
    };
  }, [auth]);

  const signIn = useCallback((returnTo: string, locale: string) => auth.signIn(returnTo, locale), [auth]);
  const signOut = useCallback(() => auth.signOut(), [auth]);
  const value = useMemo<AuthContextValue>(
    () => ({ status: state.status, user: state.user, signIn, signOut }),
    [state, signIn, signOut],
  );
  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthContextValue {
  const v = useContext(AuthContext);
  if (!v) throw new Error("AuthProvider missing");
  return v;
}

/**
 * Roles lent on one page by the administrator's grants (L4, design-l4.md §8): inside it, the granted buttons show as
 * for an account holding that role. The API lends the same role on the granted routes only and checks the rest.
 */
export function LendRoles({ roles, children }: { roles: readonly string[]; children: ReactNode }) {
  const parent = useAuth();
  const key = [...roles].sort().join(",");
  const value = useMemo<AuthContextValue>(() => {
    const user = parent.user;
    if (!user || key === "") return parent;
    const all = [...new Set([...user.identity.roles, ...key.split(",")])];
    return { ...parent, user: { ...user, identity: { ...user.identity, roles: all } } };
  }, [parent, key]);
  return <AuthContext value={value}>{children}</AuthContext>;
}
