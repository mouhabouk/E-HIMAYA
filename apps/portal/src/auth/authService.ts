import { ErrorResponse, UserManager, WebStorageStateStore, type User } from "oidc-client-ts";
import type { TokenSource } from "../lib/api";
import { identityFromToken, type PortalIdentity } from "./identity";

export interface AuthUser {
  accessToken: string;
  identity: PortalIdentity;
}

/** Authentication boundary used by the app; implemented with oidc-client-ts, faked in tests. */
export interface AuthService extends TokenSource {
  /** Restore the session from storage (renewing it when the access token already expired). */
  load(): Promise<AuthUser | null>;
  /** Start the Authorization Code + PKCE redirect to Keycloak (`create`: registration page, `prompt=create`). */
  signIn(returnTo: string, locale: string, options?: { create?: boolean }): Promise<void>;
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
    scope: "openid profile email",
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
    async signIn(returnTo, locale, options) {
      await manager.signinRedirect({
        state: { returnTo },
        extraQueryParams: options?.create ? { ui_locales: locale, prompt: "create" } : { ui_locales: locale },
      });
    },
    completeSignIn() {
      // Guard against double invocation (React StrictMode): the code can only be exchanged once.
      completing ??= manager.signinRedirectCallback().then((user) => {
        current = toAuthUser(user);
        return safeReturnTo(user.state);
      });
      return completing;
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
