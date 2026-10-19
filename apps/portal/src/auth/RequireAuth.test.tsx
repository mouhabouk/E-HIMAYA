import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LanguageSwitch, SignInButtons } from "../components/Layout";
import { fakeAuth, renderApp } from "../test/render";
import { RequireAuth } from "./RequireAuth";

const Protected = () => (
  <RequireAuth>
    <p>secret</p>
  </RequireAuth>
);

describe("RequireAuth", () => {
  it("lets a signed-in user through", async () => {
    renderApp(<Protected />);
    expect(await screen.findByText("secret")).toBeInTheDocument();
  });

  it("redirects to Keycloak when signed out, keeping the return path and language", async () => {
    const signIn = vi.fn(() => Promise.resolve());
    renderApp(<Protected />, { auth: { ...fakeAuth(null), signIn }, path: "/invite/tok?x=1", lang: "fr" });
    await screen.findByText("Redirection vers la page de connexion…");
    expect(signIn).toHaveBeenCalledWith("/invite/tok?x=1", "fr", undefined);
  });
});

describe("sign in / create account", () => {
  it("asks Keycloak for the registration page with prompt=create", () => {
    const signIn = vi.fn(() => Promise.resolve());
    renderApp(<SignInButtons />, { auth: { ...fakeAuth(null), signIn }, lang: "en" });
    fireEvent.click(screen.getByRole("button", { name: "Create an account" }));
    expect(signIn).toHaveBeenLastCalledWith("/orgs/mine", "en", { create: true });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(signIn).toHaveBeenLastCalledWith("/orgs/mine", "en", undefined);
  });
});

describe("language switch", () => {
  it("flips the document direction between RTL and LTR for the three languages", () => {
    renderApp(<LanguageSwitch />);
    expect(document.documentElement.dir).toBe("rtl");
    expect(screen.getByRole("button", { name: "العربية" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Français" }));
    expect(document.documentElement.dir).toBe("ltr");
    expect(document.documentElement.lang).toBe("fr");
    fireEvent.click(screen.getByRole("button", { name: "English" }));
    expect(document.documentElement.lang).toBe("en");
    expect(screen.getByRole("button", { name: "English" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "العربية" }));
    expect(document.documentElement.dir).toBe("rtl");
  });
});
