// covers: NFR-13 (docs/sql/console.md): the SQL window of the national system administrator.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import {
  canUseSqlConsole,
  resultAsTsv,
  statementAt,
  tableQuery,
  viewRows,
  type SqlHistoryEntry,
} from "../lib/sqlApi";
import { fakeApi, renderApp } from "../test/render";
import { SqlConsolePage } from "./SqlConsolePage";

const MAIN = {
  name: "main",
  host: "db.ehimaya.local",
  port: 5432,
  database: "ehimaya",
  user: "ehimaya_console",
  sslmode: "require",
  read_only: true,
  timeout_s: 15,
  max_rows: 1000,
  export_max_rows: 50000,
};

const ENTRY: SqlHistoryEntry = {
  id: "11111111-1111-1111-1111-111111111111",
  connection: "main",
  sql: "SELECT code, name_ar FROM geo.delegation WHERE gouvernorat_code = 11",
  title: "معتمديات تونس",
  pinned: true,
  status: "ok",
  command: "SELECT",
  rows: 21,
  truncated: false,
  duration_ms: 12,
  error: null,
  run_count: 3,
  created_at: "2026-11-09T09:00:00Z",
  last_run_at: "2026-11-09T10:00:00Z",
  updated_at: "2026-11-09T10:00:00Z",
};

function api(extra: Parameters<typeof fakeApi>[0] = {}) {
  return fakeApi({
    sqlConnections: vi.fn().mockResolvedValue([MAIN]),
    sqlSchema: vi.fn().mockResolvedValue([
      {
        name: "geo",
        tables: [
          {
            name: "delegation",
            kind: "table",
            approx_rows: 279,
            comment: null,
            columns: [{ name: "code", type: "text", not_null: true }],
          },
        ],
      },
    ]),
    sqlExamples: vi.fn().mockResolvedValue([
      { id: "Q01", section: "استعلامات أساسية", title: "الولايات", description: "…", sql: "SELECT 1 AS one" },
    ]),
    sqlHistory: vi.fn().mockResolvedValue([ENTRY]),
    ...extra,
  });
}

describe("SQL window", () => {
  it("is for the national system administrator only", () => {
    expect(canUseSqlConsole({ roles: ["sysadmin"], national: true })).toBe(true);
    expect(canUseSqlConsole({ roles: ["sysadmin"], national: false })).toBe(false);
    expect(canUseSqlConsole({ roles: ["security_admin"], national: true })).toBe(false);
  });

  it("runs the statement under the cursor only", () => {
    const text = "SELECT 1;\n-- a; comment\nSELECT ';' AS semi;\nSELECT 3";
    expect(statementAt(text, 2)).toBe("SELECT 1");
    expect(statementAt(text, text.indexOf("AS semi"))).toBe("-- a; comment\nSELECT ';' AS semi");
    expect(statementAt(text, text.length)).toBe("SELECT 3");
    expect(statementAt("SELECT 1;", 9)).toBe("SELECT 1");
    expect(resultAsTsv({ columns: [{ name: "a", type: "text" }], rows: [["x\ty"], [null]] })).toBe("a\nx y\n");
  });

  it("shows the connection without its password, runs a query and exports the result", async () => {
    const sqlQuery = vi.fn().mockResolvedValue({
      command: "SELECT",
      columns: [
        { name: "code", type: "text" },
        { name: "population", type: "int4" },
      ],
      rows: [
        ["TN-11-12", 19679],
        ["TN-11-06", null],
      ],
      row_count: 2,
      truncated: false,
      duration_ms: 38,
      notices: [],
      executed_at: "2026-11-09T10:00:00Z",
    });
    const sqlTestConnection = vi.fn().mockResolvedValue({
      name: "main",
      ok: true,
      version: "PostgreSQL 17.6 on x86_64",
      role: "ehimaya_console",
      size: "2.4 GB",
      superuser: false,
      can_write: false,
      latency_ms: 12,
    });
    const sqlExport = vi.fn().mockResolvedValue({ blob: new Blob(["x"]), filename: "ehimaya-main.xlsx" });
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: () => undefined }));
    renderApp(<SqlConsolePage />, { api: api({ sqlQuery, sqlTestConnection, sqlExport }), lang: "ar", path: "/sql" });

    expect(await screen.findByDisplayValue("db.ehimaya.local")).toBeInTheDocument();
    expect(screen.getByDisplayValue("محفوظة في الخادم")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "اختبار الاتصال" }));
    expect(await screen.findByText("دور للقراءة فقط")).toBeInTheDocument();

    const box = screen.getByLabelText("نص الاستعلام");
    fireEvent.change(box, { target: { value: "SELECT code, population FROM geo.delegation;" } });
    fireEvent.keyDown(box, { key: "Enter", ctrlKey: true });
    await waitFor(() =>
      expect(sqlQuery).toHaveBeenCalledWith({ connection: "main", sql: "SELECT code, population FROM geo.delegation" }),
    );
    const table = await screen.findByRole("table", { name: "نتيجة الاستعلام" });
    expect(within(table).getByText("TN-11-12")).toBeInTheDocument();
    expect(within(table).getByText("NULL")).toBeInTheDocument();
    expect(screen.getByText("الأسطر: 2")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Excel" }));
    await waitFor(() =>
      expect(sqlExport).toHaveBeenCalledWith({
        connection: "main",
        sql: "SELECT code, population FROM geo.delegation",
        format: "xlsx",
      }),
    );
    vi.unstubAllGlobals();
  });

  it("shows a refusal with where it happened", async () => {
    const sqlQuery = vi.fn().mockRejectedValue(
      new ApiError(422, "unknown", { code: "42703", message: 'column "nope" does not exist', position: 8 }),
    );
    renderApp(<SqlConsolePage />, { api: api({ sqlQuery }), lang: "ar", path: "/sql" });
    const box = await screen.findByLabelText("نص الاستعلام");
    fireEvent.change(box, { target: { value: "SELECT nope FROM audit.log" } });
    fireEvent.click(screen.getByRole("button", { name: /Ctrl\+Enter/ }));
    expect(await screen.findByText(/column "nope" does not exist/)).toBeInTheDocument();
    expect(screen.getByText("الموضع: السطر 1، العمود 8")).toBeInTheDocument();
  });

  it("keeps a history the administrator pins, renames, reruns and deletes", async () => {
    const sqlEditHistory = vi.fn().mockResolvedValue({ ...ENTRY, pinned: false });
    const sqlDeleteHistory = vi.fn().mockResolvedValue(undefined);
    const sqlQuery = vi.fn().mockResolvedValue({
      command: "SELECT",
      columns: [{ name: "code", type: "text" }],
      rows: [],
      row_count: 0,
      truncated: false,
      duration_ms: 1,
      notices: [],
      executed_at: "2026-11-09T10:00:00Z",
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderApp(<SqlConsolePage />, {
      api: api({ sqlEditHistory, sqlDeleteHistory, sqlQuery }),
      lang: "ar",
      path: "/sql",
    });
    const entry = (await screen.findByText("معتمديات تونس")).closest("li");
    if (!entry) throw new Error("no entry");
    const row = within(entry);
    expect(row.getByText("شُغّل 3 مرة", { exact: false })).toBeInTheDocument();

    fireEvent.click(row.getByRole("button", { name: "إلغاء التثبيت" }));
    await waitFor(() => expect(sqlEditHistory).toHaveBeenCalledWith(ENTRY.id, { pinned: false }));

    fireEvent.click(row.getByRole("button", { name: "تسمية" }));
    fireEvent.change(row.getByLabelText("عنوان الاستعلام"), { target: { value: "  تونس  " } });
    fireEvent.click(row.getByRole("button", { name: "حفظ" }));
    await waitFor(() => expect(sqlEditHistory).toHaveBeenCalledWith(ENTRY.id, { title: "تونس" }));

    fireEvent.click(row.getByRole("button", { name: "تشغيل" }));
    await waitFor(() => expect(sqlQuery).toHaveBeenCalledWith({ connection: "main", sql: ENTRY.sql }));

    fireEvent.click(row.getByRole("button", { name: "حذف" }));
    await waitFor(() => expect(sqlDeleteHistory).toHaveBeenCalledWith(ENTRY.id));
    vi.restoreAllMocks();
  });

  it("filters and sorts rows by column, and writes the same filters for the database", () => {
    const rows = [
      ["TN-11-12", "التحرير", 19679],
      ["TN-11-06", "الحرايرية", null],
      ["TN-11-13", "الزهور", 35484],
    ];
    expect(viewRows(rows, { 1: "الح" }, null)).toEqual([rows[1]]);
    expect(viewRows(rows, { 2: "null" }, null)).toEqual([rows[1]]);
    expect(viewRows(rows, {}, { column: 2, desc: true }).map((r) => r[0])).toEqual(["TN-11-13", "TN-11-12", "TN-11-06"]);
    expect(tableQuery("geo", "delegation", ["code", "name_ar", "Pop"], { 1: "o'_%", 2: "NULL" }, { column: 0, desc: true }, 1000)).toBe(
      "SELECT *\nFROM geo.delegation\nWHERE name_ar::text ILIKE '%o''\\_\\%%'\n  AND \"Pop\" IS NULL\nORDER BY code DESC NULLS LAST\nLIMIT 1000",
    );
  });

  it("shows a table's rows when it is clicked, then filters them by column and applies the filter to the whole table", async () => {
    const sqlQuery = vi.fn().mockResolvedValue({
      command: "SELECT",
      columns: [
        { name: "code", type: "text" },
        { name: "name_ar", type: "text" },
      ],
      rows: [
        ["TN-11-12", "التحرير"],
        ["TN-11-06", "الحرايرية"],
      ],
      row_count: 2,
      truncated: false,
      duration_ms: 3,
      notices: [],
      executed_at: "2026-11-09T10:00:00Z",
    });
    renderApp(<SqlConsolePage />, { api: api({ sqlQuery }), lang: "ar", path: "/sql" });
    fireEvent.click(await screen.findByRole("button", { name: /^geo/ }));
    fireEvent.click(screen.getByRole("button", { name: /^delegation/ }));
    await waitFor(() =>
      expect(sqlQuery).toHaveBeenCalledWith({ connection: "main", sql: "SELECT *\nFROM geo.delegation\nLIMIT 100" }),
    );
    const table = await screen.findByRole("table", { name: "نتيجة الاستعلام" });
    expect(within(table).getByText("الحرايرية")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("بحث عن عمود بالاسم"), { target: { value: "name" } });
    expect(within(table).queryByText("TN-11-12")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("فلترة العمود name_ar"), { target: { value: "تحر" } });
    expect(within(table).getByText("التحرير")).toBeInTheDocument();
    expect(within(table).queryByText("الحرايرية")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "طبّق على كامل الجدول" }));
    await waitFor(() =>
      expect(sqlQuery).toHaveBeenLastCalledWith({
        connection: "main",
        sql: "SELECT *\nFROM geo.delegation\nWHERE name_ar::text ILIKE '%تحر%'\nLIMIT 1000",
      }),
    );
    expect(screen.getByLabelText("فلترة العمود name_ar")).toHaveValue("تحر");
  });

  it("says when the window is turned off on the server", async () => {
    renderApp(<SqlConsolePage />, {
      api: fakeApi({ sqlConnections: vi.fn().mockRejectedValue(new ApiError(503, "unknown", "sql_console_disabled")) }),
      lang: "ar",
      path: "/sql",
    });
    expect(await screen.findByText(/نافذة SQL موقوفة/)).toBeInTheDocument();
  });
});
