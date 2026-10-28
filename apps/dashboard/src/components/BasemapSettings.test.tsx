// covers: docs/phase-r/design-basemap.md §3: the paid imagery provider set, tested and switched on by the national
// system administrator; the stored key is shown by its last characters only and kept unless a new one is typed.
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BASEMAP_SETTINGS, fakeBasemapApi } from "../test/basemapFixtures";
import { fakeApi, fakeAuth, renderApp } from "../test/render";
import { BasemapSettingsCard } from "./BasemapSettings";

const admin = { sub: "u-admin", name: "Admin", realm_access: { roles: ["sysadmin"] }, scope_level: "national" };

describe("BasemapSettingsCard", () => {
  it("tests then enables the provider without ever showing the key", async () => {
    const b = fakeBasemapApi();
    renderApp(<BasemapSettingsCard />, { api: fakeApi(b), auth: fakeAuth(admin), lang: "ar" });
    expect(await screen.findByText("مفتاح محفوظ (\u2068••••9f3a\u2069). اترك الحقل فارغا للإبقاء عليه.")).toBeInTheDocument();
    expect(screen.getByLabelText("مسار الصور (API)")).toHaveValue(BASEMAP_SETTINGS.url_template);
    fireEvent.click(screen.getByRole("button", { name: "تجربة الاتصال" }));
    expect(await screen.findByText("الاتصال ناجح: وصلت صورة من المزوّد في 214 ملّي ثانية.")).toBeInTheDocument();
    expect(b.testBasemap).toHaveBeenCalledWith(expect.objectContaining({ provider: "esri", api_key: null }));
    fireEvent.change(screen.getByLabelText("مفتاح الترخيص"), { target: { value: "new-key-5678" } });
    fireEvent.click(screen.getByLabelText("تفعيل هذا المزوّد لكل الخرائط"));
    fireEvent.click(screen.getByRole("button", { name: "حفظ" }));
    await waitFor(() =>
      expect(b.saveBasemapSettings).toHaveBeenCalledWith(expect.objectContaining({ api_key: "new-key-5678", enabled: true })),
    );
    await waitFor(() => expect(screen.getByLabelText("مفتاح الترخيص")).toHaveValue(""));
  });
});
