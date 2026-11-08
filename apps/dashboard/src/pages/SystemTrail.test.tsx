// covers: NFR-06, NFR-13 (docs/phase-h/design-h5.md): the system logs window and the change journal ("mouchard").
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { canReadSystemTrail, type ChangeEntry } from "../lib/systemApi";
import { fakeApi, renderApp } from "../test/render";
import { ChangesPage } from "./ChangesPage";
import { SystemLogsPage } from "./SystemLogsPage";

const UPDATE: ChangeEntry = {
  id: 7,
  at: "2026-11-08T10:00:00Z",
  op: "U",
  schema_name: "org",
  table_name: "organization",
  row_key: { id: "org-1" },
  columns: ["capacity", "name"],
  hidden: ["name"],
  old_values: { capacity: 40 },
  new_values: { capacity: 55 },
  actor_kind: "public",
  actor: "public-0a1b2c3d4e",
  actor_name: null,
  request_id: "abcdef1234567890",
  gouvernorat_code: 61,
};

describe("system trail", () => {
  it("is for national technical administrators only", () => {
    expect(canReadSystemTrail({ roles: ["sysadmin"], national: true })).toBe(
      true,
    );
    expect(
      canReadSystemTrail({ roles: ["security_admin"], national: true }),
    ).toBe(true);
    expect(canReadSystemTrail({ roles: ["sysadmin"], national: false })).toBe(
      false,
    );
    expect(canReadSystemTrail({ roles: ["ops_manager"], national: true })).toBe(
      false,
    );
  });

  it("shows each change with its values, hides what was never kept and links to the request's logs", async () => {
    const changes = vi
      .fn()
      .mockResolvedValue({ items: [UPDATE], next_cursor: null });
    const changeSummary = vi.fn().mockResolvedValue({
      hours: 24,
      total: 3,
      by_op: [
        { key: "U", count: 2 },
        { key: "I", count: 1 },
      ],
      by_schema: [{ key: "org", count: 3 }],
      by_actor_kind: [{ key: "public", count: 3 }],
      tables: ["org.organization", "org.member"],
    });
    renderApp(<ChangesPage />, {
      api: fakeApi({ changes, changeSummary }),
      lang: "ar",
    });
    expect(
      await screen.findByText("تحيين", { selector: ".change-op" }),
    ).toBeInTheDocument();
    expect(screen.getByText("40")).toBeInTheDocument();
    expect(screen.getByText("55")).toBeInTheDocument();
    expect(screen.getByText(/محجوب/)).toBeInTheDocument();
    expect(screen.getByText("public-0a1b2c3d4e")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "abcdef123456" })).toHaveAttribute(
      "href",
      "/system-logs?request_id=abcdef1234567890",
    );
    fireEvent.change(screen.getByLabelText("العملية"), {
      target: { value: "D" },
    });
    await waitFor(() =>
      expect(changes).toHaveBeenLastCalledWith(
        expect.objectContaining({ op: "D" }),
        expect.anything(),
      ),
    );
  });

  it("lists the errors by service and follows one request", async () => {
    const systemLogs = vi.fn().mockResolvedValue({
      query: '{service=~".+"}',
      items: [
        {
          at: "2026-11-08T10:00:00Z",
          service: "api",
          level: "error",
          event: "http.request",
          request_id: "abcdef1234567890",
          fields: {
            event: "http.request",
            level: "error",
            status: 500,
            route: "/api/v1/x",
          },
          text: null,
        },
      ],
    });
    const systemLogSummary = vi
      .fn()
      .mockResolvedValue({
        hours: 24,
        services: [{ service: "api", errors: 4, warnings: 2 }],
      });
    renderApp(<SystemLogsPage />, {
      api: fakeApi({ systemLogs, systemLogSummary }),
      lang: "ar",
    });
    expect(await screen.findByText("4 خطأ، 2 تحذير")).toBeInTheDocument();
    expect(await screen.findByText(/status=500/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "abcdef123456" }));
    await waitFor(() =>
      expect(systemLogs).toHaveBeenLastCalledWith(
        expect.objectContaining({
          request_id: "abcdef1234567890",
          service: "",
        }),
        expect.anything(),
      ),
    );
  });

  it("says when the log collection is off", async () => {
    const off = new ApiError(503, "logs_not_configured");
    renderApp(<SystemLogsPage />, {
      api: fakeApi({
        systemLogs: vi.fn().mockRejectedValue(off),
        systemLogSummary: vi.fn().mockRejectedValue(off),
      }),
      lang: "ar",
    });
    expect(
      await screen.findByText(/تجميع السجلات غير مشغّل/),
    ).toBeInTheDocument();
  });
});
