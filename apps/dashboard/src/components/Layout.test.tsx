import { fireEvent, screen } from "@testing-library/react";
import { useLocation } from "react-router";
import { describe, expect, it } from "vitest";
import { renderApp } from "../test/render";
import { LanguageMenu } from "./Layout";

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
});
