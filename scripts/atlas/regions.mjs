// The regions a flowchart box points at, read in the page (shared by capture.mjs and capture_portal.mjs).

/** Regions a flowchart box can point at, in reading order (top to bottom, right to left). */
export function regions() {
  const main = document.querySelector("main") ?? document.body;
  const out = [];
  const seen = new Set();
  const txt = (el) => (el?.innerText ?? "").replace(/\s+/g, " ").trim().slice(0, 90);
  const add = (kind, el, label) => {
    if (!el || seen.has(el)) return;
    const r = el.getBoundingClientRect();
    if (r.width < 24 || r.height < 12) return;
    seen.add(el);
    out.push({ kind, label: label || txt(el), x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY),
      w: Math.round(r.width), h: Math.round(r.height) });
  };
  const nav = document.querySelector("nav[aria-label]");
  if (nav) add("menu", nav, "القائمة الرئيسية");
  const h1 = main.querySelector("h1");
  if (h1) add("title", h1.closest("header") ?? h1, txt(h1));
  const lead = h1?.closest("header")?.parentElement?.querySelector(":scope > p, header + p, p.muted");
  if (lead) add("lead", lead);
  [...main.querySelectorAll("[role=tablist], .tabs, .segmented")].slice(0, 2).forEach((t) => add("tabs", t, txt(t)));
  [...main.querySelectorAll(".maplibregl-map")].slice(0, 1).forEach((m) => add("map", m, "الخريطة"));
  [...main.querySelectorAll("h2, h3")].slice(0, 9).forEach((h) => {
    const box = h.closest("section, article, .card, fieldset") ?? h;
    add("section", box, txt(h));
  });
  [...main.querySelectorAll("table")].slice(0, 2).forEach((t) => {
    const head = [...t.querySelectorAll("th")].map((th) => txt(th)).filter(Boolean).slice(0, 5).join("، ");
    add("table", t.closest(".table-wrap, .card") ?? t, head ? `جدول: ${head}` : "جدول");
  });
  [...main.querySelectorAll("form")].slice(0, 2).forEach((f) => add("form", f, txt(f.querySelector("legend, h2, h3, label")) || "استمارة"));
  [...main.querySelectorAll(".btn--primary, button[type=submit]")].slice(0, 3).forEach((b) => add("action", b, txt(b)));
  const lead2 = out.find((o) => o.kind === "lead");
  return { regions: out.sort((a, b) => (Math.abs(a.y - b.y) < 14 ? b.x - a.x : a.y - b.y)), lead: lead2?.label ?? "",
    height: Math.min(Math.max(document.documentElement.scrollHeight,
      ...[...document.querySelectorAll("main, main *")].filter((e) => /(auto|scroll)/.test(getComputedStyle(e).overflowY))
        .map((e) => e.scrollHeight + e.getBoundingClientRect().top)), 2400), title: txt(h1) };
}
