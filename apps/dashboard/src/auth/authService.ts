import { ErrorResponse, UserManager, WebStorageStateStore, type User } from "oidc-client-ts";
import type { TokenSource } from "../lib/api";
import { identityFromToken, type StaffIdentity } from "./identity";

export interface AuthUser {
  accessToken: string;
  identity: StaffIdentity;
}

/** Authentication boundary used by the app; implemented with oidc-client-ts, faked in tests. */
export interface AuthService extends TokenSource {
  /** Restore the session from storage (renewing it when the access token already expired). */
  load(): Promise<AuthUser | null>;
  /** Start the Authorization Code + PKCE redirect to Keycloak. */
  signIn(returnTo: string, locale: string): Promise<void>;
  /** Finish the redirect on /callback; resolves with the path to return to. */
  completeSignIn(): Promise<string>;
  signOut(): Promise<void>;
  /** Called with the new user after every renewal, or null when the session ends. */
  subscribe(listener: (user: AuthUser | null) => void): () => void;
}

function toAuthUser(user: User | null): AuthUser | null {
  if (!user?.access_token) return null;
  try {
    return { accessToken: user.access_token, identity: identityFromToken(user.access_token) };
  } catch {
    return null;
  }
}

// Set before the one sign-in again that a "mfa_required" answer triggers, cleared by a token that proves the second
// factor; a second refusal in the same tab is shown instead of looping through the login page.
const STEP_UP_KEY = "ehimaya.mfaStepUp";

function safeReturnTo(state: unknown): string {
  const path = (state as { returnTo?: unknown } | undefined)?.returnTo;
  // Only same-origin absolute paths; never "//host" (open redirect).
  return typeof path === "string" && path.startsWith("/") && !path.startsWith("//") ? path : "/";
}

export interface OidcSettings {
  issuer: string;
  clientId: string;
  origin?: string;
}

export function createOidcAuthService({ issuer, clientId, origin = window.location.origin }: OidcSettings): AuthService {
  const manager = new UserManager({
    authority: issuer,
    client_id: clientId,
    redirect_uri: `${origin}/callback`,
    post_logout_redirect_uri: `${origin}/`,
    response_type: "code",
    scope: "openid profile",
    // Renewal uses the refresh token (public client + PKCE); no hidden iframe.
    automaticSilentRenew: true,
    accessTokenExpiringNotificationTimeInSeconds: 60,
    monitorSession: false,
    loadUserInfo: false,
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
  });

  let current: AuthUser | null = null;
  let renewing: Promise<string | null> | null = null;
  let completing: Promise<string> | null = null;
  const listeners = new Set<(user: AuthUser | null) => void>();

  const emit = (user: AuthUser | null) => {
    current = user;
    for (const l of listeners) l(user);
  };

  manager.events.addUserLoaded((user) => emit(toAuthUser(user)));
  manager.events.addUserUnloaded(() => emit(null));
  manager.events.addUserSignedOut(() => emit(null));
  manager.events.addSilentRenewError(() => {
    // Refresh token expired or revoked (SSO idle timeout): the session is over.
    void manager.removeUser().then(() => emit(null));
  });
  manager.events.addAccessTokenExpired(() => {
    void renew();
  });

  function renew(): Promise<string | null> {
    renewing ??= manager
      .signinSilent()
      .then((user) => {
        const u = toAuthUser(user);
        if (u) current = u;
        return u?.accessToken ?? null;
      })
      .catch(async (error: unknown) => {
        // The authorization server refused the refresh token (e.g. invalid_grant after the SSO idle
        // timeout): the session is over, so sign out locally and let the app redirect to the login page.
        // Network errors keep the session so that a later attempt can succeed.
        if (error instanceof ErrorResponse) {
          await manager.removeUser();
          emit(null);
        }
        return null;
      })
      .finally(() => {
        renewing = null;
      });
    return renewing;
  }

  return {
    getAccessToken: () => current?.accessToken ?? null,
    renew,
    async load() {
      const user = await manager.getUser();
      if (!user) return null;
      if (user.expired) {
        if (!user.refresh_token) {
          await manager.removeUser();
          return null;
        }
        const token = await renew();
        return token ? current : null;
      }
      current = toAuthUser(user);
      return current;
    },
    async signIn(returnTo, locale) {
      await manager.signinRedirect({ state: { returnTo }, extraQueryParams: { ui_locales: locale } });
    },
    completeSignIn() {
      // Guard against double invocation (React StrictMode): the code can only be exchanged once.
      completing ??= manager.signinRedirectCallback().then((user) => {
        current = toAuthUser(user);
        if (current?.identity.mfa) {
          try {
            window.sessionStorage.removeItem(STEP_UP_KEY);
          } catch {
            // storage unavailable: nothing to clear
          }
        }
        return safeReturnTo(user.state);
      });
      return completing;
    },
    rejected(reason) {
      if (reason === "session_revoked") {
        // Signed out elsewhere: forget the session; RequireAuth sends the user to the login page.
        void manager.removeUser().then(() => emit(null));
        return;
      }
      try {
        if (window.sessionStorage.getItem(STEP_UP_KEY)) return;
        window.sessionStorage.setItem(STEP_UP_KEY, "1");
      } catch {
        return;
      }
      // The token was issued while the OTP device was being set up (amr = pwd only): sign in again, with the code.
      const returnTo = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      void manager.signinRedirect({ state: { returnTo }, prompt: "login" });
    },
    async signOut() {
      const user = await manager.getUser();
      current = null;
      await manager.signoutRedirect(user?.id_token ? { id_token_hint: user.id_token } : undefined);
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
