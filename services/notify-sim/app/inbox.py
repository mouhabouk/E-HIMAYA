# ┏━━ SIMULATION ━━ development inbox page showing the pushes and SMS the simulator received (not real deliveries)
# ┃ PRODUCTION: no equivalent page; remove the notify-sim service. Real pushes are checked on devices and in the
# ┃   Firebase console (Messaging reports), SMS in the delivery reports of the SMS provider contract.
# ┗━━━━━━━━━━━━━━━━
"""SIMULATION — self-contained HTML inbox (inline CSS and JS, no external assets), Arabic and French."""

INBOX_HTML = """<!doctype html>
<!-- SIMULATION: development inbox of e-Himaya notify-sim. Nothing shown here reached a real phone. -->
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>notify-sim · SIMULATION</title>
<style>
:root {
  --bg: #fffaf0; --panel: #ffffff; --text: #1f1a14; --muted: #6b5d4d; --line: #ecdcc4;
  --band: #b45309; --band-text: #ffffff; --band-stripe: #d97706;
  --push: #1d4ed8; --sms: #047857; --alert: #b91c1c; --chip: #fdf1dc;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1b1610; --panel: #251e15; --text: #f6efe6; --muted: #c2b29c; --line: #3d3122;
    --band: #92400e; --band-text: #fff7ed; --band-stripe: #b45309;
    --push: #93b4ff; --sms: #6ee7b7; --alert: #fca5a5; --chip: #33291c;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", "Noto Sans Arabic", Tahoma, sans-serif; }
.band { background: repeating-linear-gradient(-45deg, var(--band), var(--band) 18px, var(--band-stripe) 18px,
  var(--band-stripe) 36px); color: var(--band-text); padding: 10px 16px; font-weight: 700; text-align: center;
  letter-spacing: .02em; border-bottom: 3px solid #78350f; }
.band small { display: block; font-weight: 400; opacity: .95; }
header { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between;
  padding: 14px 16px; border-bottom: 1px solid var(--line); }
h1 { font-size: 18px; margin: 0; }
.meta { color: var(--muted); font-size: 13px; }
.meta code { direction: ltr; unicode-bidi: isolate; }
.controls { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
button { font: inherit; border: 1px solid var(--line); background: var(--panel); color: var(--text);
  padding: 6px 12px; border-radius: 8px; cursor: pointer; }
button[aria-pressed="true"] { background: var(--band); color: var(--band-text); border-color: var(--band); }
button.danger { color: var(--alert); }
main { max-width: 920px; margin: 0 auto; padding: 16px; }
.status { color: var(--muted); font-size: 13px; margin-bottom: 12px; }
.empty { text-align: center; color: var(--muted); padding: 48px 0; }
article { background: var(--panel); border: 1px solid var(--line); border-inline-start: 5px solid var(--push);
  border-radius: 10px; padding: 12px 14px; margin-bottom: 10px; }
article.sms { border-inline-start-color: var(--sms); }
article.alert { border-inline-start-color: var(--alert); }
.row { display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; font-size: 13px; color: var(--muted); }
.badge { font-weight: 700; color: var(--push); }
article.sms .badge { color: var(--sms); }
article.alert .badge { color: var(--alert); }
.target { direction: ltr; unicode-bidi: isolate; font-family: ui-monospace, Menlo, Consolas, monospace;
  overflow-wrap: anywhere; }
.title { font-weight: 700; margin: 6px 0 2px; }
.body { white-space: pre-wrap; overflow-wrap: anywhere; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.chip { background: var(--chip); border-radius: 6px; padding: 1px 8px; font-size: 12px; direction: ltr;
  unicode-bidi: isolate; font-family: ui-monospace, Menlo, Consolas, monospace; overflow-wrap: anywhere; }
</style>
</head>
<body>
<div class="band" role="alert">وضع المحاكاة · Mode simulation — not real deliveries
  <small data-l="bandNote"></small></div>
<header>
  <div>
    <h1 data-l="title"></h1>
    <div class="meta"><span data-l="project"></span> <code>{{project}}</code> ·
      <span data-l="endpoint"></span> <code>{{public_url}}</code> ·
      <span data-l="failing"></span> <code>{{fail_numbers}}</code></div>
  </div>
  <div class="controls">
    <button type="button" data-filter="all" data-l="all"></button>
    <button type="button" data-filter="push" data-l="push"></button>
    <button type="button" data-filter="sms" data-l="sms"></button>
    <button type="button" id="clear" class="danger" data-l="clear"></button>
    <button type="button" id="lang" lang="fr">Français</button>
  </div>
</header>
<main>
  <div class="status" id="status" aria-live="polite"></div>
  <div id="list"></div>
</main>
<script>
(() => {
  "use strict";
  const L = {
    ar: {
      title: "صندوق الإشعارات والرسائل القصيرة", bandNote: "لا شيء هنا وصل إلى هاتف حقيقي",
      project: "مشروع FCM:", endpoint: "العنوان:", failing: "أرقام الفشل:",
      all: "الكل", push: "إشعارات", sms: "رسائل قصيرة", clear: "مسح الكل", empty: "لا توجد رسائل بعد",
      confirm: "مسح كل الرسائل المسجّلة؟", updated: "آخر تحديث", offline: "تعذّر الاتصال بالمحاكي",
      count: "رسالة", to: "إلى", token: "رمز", segments: "أجزاء", channel: "قناة أندرويد", priority: "الأولوية",
      other: "English/Français"
    },
    fr: {
      title: "Boîte de réception des notifications et SMS", bandNote: "Rien ici n'a atteint un vrai téléphone",
      project: "Projet FCM :", endpoint: "Adresse :", failing: "Numéros en échec :",
      all: "Tout", push: "Notifications", sms: "SMS", clear: "Tout effacer", empty: "Aucun message pour l'instant",
      confirm: "Effacer tous les messages enregistrés ?", updated: "Mis à jour", offline: "Simulateur injoignable",
      count: "message(s)", to: "À", token: "Jeton", segments: "segments", channel: "canal Android",
      priority: "priorité", other: "العربية"
    }
  };
  const store = (key, value) => {
    try {
      if (value === undefined) return localStorage.getItem(key);
      localStorage.setItem(key, value);
    } catch (e) { /* storage unavailable: defaults apply */ }
    return null;
  };
  let lang = store("notify-sim.lang") === "fr" ? "fr" : "ar";
  let filter = store("notify-sim.filter") || "all";
  let items = [];
  let after = 0;
  let lastOk = null;
  let failed = false;
  const list = document.getElementById("list");
  const status = document.getElementById("status");
  const t = (key) => L[lang][key];

  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  };

  function applyLang() {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    document.querySelectorAll("[data-l]").forEach((n) => { n.textContent = t(n.dataset.l); });
    const toggle = document.getElementById("lang");
    toggle.textContent = t("other");
    toggle.lang = lang === "ar" ? "fr" : "ar";
    render();
  }

  function card(item) {
    const alert = (item.android_channel || "").startsWith("ehimaya_alerts") || (item.android_channel || "").startsWith("ehimaya_critical");
    const node = el("article", item.channel + (alert ? " alert" : ""));
    const row = el("div", "row");
    row.append(el("span", "badge", item.channel === "push" ? t("push") : t("sms")));
    const time = el("time", null, new Date(item.received_at).toLocaleString(lang === "ar" ? "ar-TN" : "fr-TN"));
    time.dateTime = item.received_at;
    row.append(time, el("span", null, "#" + item.seq));
    row.append(el("span", null, (item.channel === "push" ? t("token") : t("to")) + ":"));
    row.append(el("span", "target", item.channel === "push" ? item.token || "—" : item.to));
    node.append(row);
    if (item.title) { const n = el("div", "title", item.title); n.dir = "auto"; node.append(n); }
    const text = item.channel === "push" ? item.body : item.text;
    if (text) { const n = el("div", "body", text); n.dir = "auto"; node.append(n); }
    const chips = el("div", "chips");
    if (item.android_channel) chips.append(el("span", "chip", t("channel") + " = " + item.android_channel));
    if (item.priority) chips.append(el("span", "chip", t("priority") + " = " + item.priority));
    if (item.segments) chips.append(el("span", "chip", item.segments + " " + t("segments") + " · " + item.encoding));
    Object.entries(item.data || {}).forEach(([k, v]) => chips.append(el("span", "chip", k + " = " + v)));
    if (chips.childElementCount) node.append(chips);
    return node;
  }

  function render() {
    document.querySelectorAll("[data-filter]").forEach((b) => {
      b.setAttribute("aria-pressed", String(b.dataset.filter === filter));
    });
    const shown = items.filter((i) => filter === "all" || i.channel === filter).slice().reverse();
    list.replaceChildren(...(shown.length ? shown.map(card) : [el("div", "empty", t("empty"))]));
    status.textContent = failed ? t("offline")
      : shown.length + " " + t("count") + (lastOk ? " · " + t("updated") + " " + lastOk.toLocaleTimeString() : "");
  }

  async function poll() {
    try {
      let more = true;
      while (more) {
        const response = await fetch("api/messages?limit=200&after=" + after, { cache: "no-store" });
        if (!response.ok) throw new Error(String(response.status));
        const page = await response.json();
        items = items.concat(page.items).slice(-1000);
        more = page.items.length === 200;
        after = page.last_seq;
      }
      failed = false;
      lastOk = new Date();
    } catch (e) {
      failed = true;
    }
    render();
  }

  document.querySelectorAll("[data-filter]").forEach((b) => b.addEventListener("click", () => {
    filter = b.dataset.filter; store("notify-sim.filter", filter); render();
  }));
  document.getElementById("lang").addEventListener("click", () => {
    lang = lang === "ar" ? "fr" : "ar"; store("notify-sim.lang", lang); applyLang();
  });
  document.getElementById("clear").addEventListener("click", async () => {
    if (!window.confirm(t("confirm"))) return;
    await fetch("api/messages", { method: "DELETE" });
    items = []; render();
  });
  applyLang();
  poll();
  setInterval(poll, 3000);
})();
</script>
</body>
</html>
"""
