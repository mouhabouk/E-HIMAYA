import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LanguageMenu } from "../components/Layout";
import { fakeAuth, OPERATOR_CLAIMS, renderApp } from "../test/render";
import { RequireAuth } from "./RequireAuth";

const Protected = () => (
  <RequireAuth>
    <p>secret</p>
  </RequireAuth>
);

describe("RequireAuth", () => {
  it("lets staff with a read role and a scope through", async () => {
    renderApp(<Protected />);
    expect(await screen.findByText("secret")).toBeInTheDocument();
  });

  it("shows the no-access page without a staff read role", async () => {
    const auth = fakeAuth({ ...OPERATOR_CLAIMS, realm_access: { roles: ["org_admin", "offline_access"] } });
    renderApp(<Protected />, { auth, lang: "fr" });
    expect(await screen.findByRole("heading", { name: "Accès refusé" })).toBeInTheDocument();
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("shows the no-access page without a geographic scope", async () => {
    const auth = fakeAuth({ sub: "u", realm_access: { roles: ["operator"] } });
    renderApp(<Protected />, { auth, lang: "fr" });
    expect(await screen.findByText(/ni à un gouvernorat ni au périmètre national/)).toBeInTheDocument();
  });

  it("redirects to Keycloak when signed out, keeping the return path and language", async () => {
    const signIn = vi.fn(() => Promise.resolve());
    renderApp(<Protected />, { auth: { ...fakeAuth(null), signIn }, path: "/reports?x=1" });
    await screen.findByText("جارٍ التحويل إلى صفحة الدخول…");
    expect(signIn).toHaveBeenCalledWith("/reports?x=1", "ar");
  });
});

describe("language switch", () => {
  it("flips the document direction between RTL and LTR", async () => {
    renderApp(<LanguageMenu />);
    expect(document.documentElement.dir).toBe("rtl");
    fireEvent.click(await screen.findByRole("button", { name: "Français" }));
    expect(document.documentElement.dir).toBe("ltr");
    expect(document.documentElement.lang).toBe("fr");
    fireEvent.click(screen.getByRole("button", { name: "English" }));
    expect(document.documentElement.dir).toBe("ltr");
    expect(document.documentElement.lang).toBe("en");
    fireEvent.click(screen.getByRole("button", { name: "العربية" }));
    expect(document.documentElement.dir).toBe("rtl");
  });
});
