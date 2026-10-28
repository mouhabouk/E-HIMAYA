import { fireEvent, screen, within } from "@testing-library/react";
import { useLocation } from "react-router";
import { describe, expect, it } from "vitest";
import { renderApp } from "../test/render";
import { Layout, LanguageMenu } from "./Layout";

function MenuWithLocation() {
  const location = useLocation();
  return (
    <>
      <LanguageMenu />
      <output data-testid="location">{location.pathname + location.search}</output>
    </>
  );
}

describe("Layout", () => {
  it("language_menu: ar, fr and en; the direction follows and the route stays", () => {
    const { i18n } = renderApp(<MenuWithLocation />, { path: "/reports?status=received" });
    const group = screen.getByRole("group", { name: "اللغة" });
    const buttons = group.querySelectorAll("button");
    expect([...buttons].map((b) => b.textContent)).toEqual(["العربية", "Français", "English"]);
    expect(screen.getByRole("button", { name: "العربية" })).toHaveAttribute("aria-pressed", "true");
    expect(document.documentElement).toHaveAttribute("dir", "rtl");

    fireEvent.click(screen.getByRole("button", { name: "English" }));
    expect(i18n.language).toBe("en");
    expect(document.documentElement).toHaveAttribute("dir", "ltr");
    expect(document.documentElement).toHaveAttribute("lang", "en");
    expect(screen.getByRole("group", { name: "Language" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "English" })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: "Français" }));
    expect(document.documentElement).toHaveAttribute("dir", "ltr");
    expect(document.documentElement).toHaveAttribute("lang", "fr");

    fireEvent.click(screen.getByRole("button", { name: "العربية" }));
    expect(document.documentElement).toHaveAttribute("dir", "rtl");
    expect(screen.getByTestId("location")).toHaveTextContent("/reports?status=received");
  });

  it("main_menu: grouped by default, a group opens and closes from the keyboard", async () => {
    renderApp(<Layout />, { lang: "fr", path: "/reports" });
    const nav = await screen.findByRole("navigation", { name: "Navigation principale" });
    const ops = within(nav).getByRole("button", { name: "Opérations du jour" });
    expect(ops).toHaveAttribute("aria-expanded", "false");
    // The group of the current page is marked, and its links stay out of reach until it opens.
    expect(ops).toHaveAttribute("data-active", "true");
    expect(within(nav).queryByRole("link", { name: "Signalements" })).not.toBeInTheDocument();
    fireEvent.click(ops);
    expect(ops).toHaveAttribute("aria-expanded", "true");
    expect(within(nav).getByRole("link", { name: "Signalements" })).toHaveAttribute("aria-current", "page");
    fireEvent.keyDown(ops, { key: "Escape" });
    expect(ops).toHaveAttribute("aria-expanded", "false");
    expect(ops).toHaveFocus();
  });

  it("main_menu: the account menu changes the shape and the position, and remembers them", async () => {
    const { container } = renderApp(<Layout />, { lang: "fr", path: "/reports" });
    await screen.findByRole("navigation", { name: "Navigation principale" });
    const shell = container.querySelector(".shell");
    expect(shell).toHaveAttribute("data-menu-shape", "grouped");
    expect(shell).toHaveAttribute("data-menu-position", "top");
    fireEvent.click(screen.getByRole("button", { name: /Mon compte et réglages/ }));
    fireEvent.click(screen.getByRole("radio", { name: "À plat" }));
    fireEvent.click(screen.getByRole("radio", { name: "À droite" }));
    expect(shell).toHaveAttribute("data-menu-shape", "flat");
    expect(shell).toHaveAttribute("data-menu-position", "right");
    expect(JSON.parse(localStorage.getItem("ehimaya.menu") ?? "{}")).toEqual({ shape: "flat", position: "right" });
    // Flat: every link at once, under its group heading.
    const nav = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(within(nav).getByRole("region", { name: "Opérations du jour" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Signalements" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Se déconnecter" })).toBeInTheDocument();
  });
});
