"""Offline archive of the project and its conversations (Yamen, 2026-11-01).

    python3 scripts/offline_archive.py --out /tmp/archive --project-files /mnt/project-files \
        --transcript <session.jsonl> [--transcript <subagent.jsonl> ...] [--resume docs/handoff/resume.md]

Builds a folder that opens in any browser without internet:

- index.html: the start page;
- conversation/: the project chat and every thread, one page each, read from the transcripts of the sessions that read
  them (the hearthbot read_project_chat / read_thread / list_threads results); attachments and thread links point to
  the local copies;
- session/: the technical log of the session(s) given (messages, tool calls, shortened tool results);
- repo/: the repository at HEAD (git archive), repo.bundle (full history: `git clone repo.bundle e-himaya`), and
  browse/: every text file of the repository as a readable page, with a file tree (repo.html);
- files/: a copy of the project files, except the raw uploads and the private data (never redistributed);
- resume.html: the summary for resuming the work.

Standard library only. Raw Office files never enter the archive: uploads/ and data-private/ are skipped.
"""

import argparse
import html
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

SKIP_FILES = ("uploads", "data-private", "archive")  # archive: the previous archive parts, never nested
MAX_VIEW = 1_500_000
CSS = """
:root{--bg:#f7f8fa;--paper:#fff;--ink:#182038;--muted:#5b6478;--line:#dfe3e8;--navy:#1f3fa0;--red:#d7141a;--chip:#eef1f5;
--me:#e8edfa;--agent:#fff;--ok:#1e7d3a}
@media (prefers-color-scheme:dark){:root{--bg:#0f1318;--paper:#161b22;--ink:#e6eaef;--muted:#9aa5b1;--line:#2a313b;
--navy:#8fa8ff;--chip:#1f2630;--me:#1b2540;--agent:#161b22}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 "Noto Naskh Arabic","Segoe UI",
Tahoma,Arial,sans-serif}a{color:var(--navy)}.wrap{max-width:1100px;margin:0 auto;padding:20px 16px 80px}
header{background:var(--paper);border:1px solid var(--line);border-top:6px solid var(--red);border-radius:10px;
padding:18px 22px;margin-bottom:16px}header h1{margin:0;font-size:26px}.sub{color:var(--muted);margin:4px 0 0}
nav.crumbs{font-size:14px;margin-bottom:10px}.layout{display:grid;grid-template-columns:260px 1fr;gap:16px}
@media(max-width:800px){.layout{grid-template-columns:1fr}}aside{background:var(--paper);border:1px solid var(--line);
border-radius:10px;padding:12px;align-self:start;position:sticky;top:10px;max-height:95vh;overflow:auto;font-size:14px}
aside a{display:block;padding:4px 6px;border-radius:6px;text-decoration:none}aside a.on{background:var(--me);font-weight:700}
.msg{background:var(--agent);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:10px 0}
.msg.user{background:var(--me);border-color:var(--navy)}.who{font-size:13px;color:var(--muted);margin-bottom:4px}
.who b{color:var(--ink)}.status{background:var(--chip);border-radius:8px;padding:8px 12px;white-space:pre-wrap;font-size:14px}
.small{font-size:13px;color:var(--muted)}.att{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.att a,.att span{background:var(--chip);border-radius:999px;padding:2px 10px;font-size:13px;text-decoration:none}
pre,code{direction:ltr;unicode-bidi:isolate;font-family:Consolas,Menlo,monospace}pre{background:var(--chip);padding:10px;
border-radius:6px;overflow:auto;font-size:13px;text-align:left;white-space:pre-wrap;word-break:break-word}
code{background:var(--chip);padding:0 4px;border-radius:4px;font-size:13px}section.card{background:var(--paper);
border:1px solid var(--line);border-radius:10px;padding:16px 20px;margin-bottom:16px}details{margin:2px 0}
summary{cursor:pointer}.tree{direction:ltr;text-align:left;font-family:Consolas,Menlo,monospace;font-size:13px}
.tree ul{list-style:none;padding-left:18px;margin:0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.tile{background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:14px 16px;text-decoration:none;color:var(--ink)}
.tile b{display:block;font-size:18px;color:var(--navy)}.ltr{direction:ltr;text-align:left}
table{border-collapse:collapse}td,th{border:1px solid var(--line);padding:4px 8px}
"""


def page(title: str, body: str, depth: int, rtl: bool = True) -> str:
    up = "../" * depth
    return (
        f'<!doctype html><html lang="{"ar" if rtl else "en"}" dir="{"rtl" if rtl else "ltr"}"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
        f'<link rel="stylesheet" href="{up}style.css"></head><body><div class="wrap">'
        f'<nav class="crumbs"><a href="{up}index.html">الصفحة الرئيسية</a></nav>{body}</div></body></html>'
    )


# ---------------------------------------------------------------- Markdown (the subset the messages use)


def inline(text: str, link) -> str:
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{html.escape(link(m.group(2)))}">{m.group(1)}</a>', out)
    out = re.sub(r'(?<!["=>])(https?://[^\s<]+)', r'<a href="\1">\1</a>', out)
    return out


def markdown(text: str, link) -> str:
    lines, out, para, lst = text.split("\n"), [], [], None
    in_code = False

    def flush():
        nonlocal para, lst
        if para:
            out.append("<p>" + "<br>".join(inline(p, link) for p in para) + "</p>")
            para = []
        if lst:
            out.append(f"</{lst}>")
            lst = None

    for line in lines:
        if line.strip().startswith("```"):
            flush()
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        m = re.match(r"^\s*(#{1,4})\s+(.*)", line)
        b = re.match(r"^(\s*)[-*]\s+(.*)", line)
        n = re.match(r"^(\s*)\d+[.)]\s+(.*)", line)
        if m:
            flush()
            level = min(6, len(m.group(1)) + 2)
            out.append(f"<h{level}>{inline(m.group(2), link)}</h{level}>")
        elif b or n:
            if para:
                out.append("<p>" + "<br>".join(inline(p, link) for p in para) + "</p>")
                para = []
            kind = "ul" if b else "ol"
            if lst != kind:
                if lst:
                    out.append(f"</{lst}>")
                out.append(f"<{kind}>")
                lst = kind
            item = (b or n).group(2)
            indent = len((b or n).group(1))
            out.append(f'<li style="margin-inline-start:{indent * 8}px">{inline(item, link)}</li>')
        elif not line.strip():
            flush()
        else:
            if lst:
                out.append(f"</{lst}>")
                lst = None
            para.append(line)
    flush()
    if in_code:
        out.append("</pre>")
    return "\n".join(out)


# ---------------------------------------------------------------- transcripts


def tool_results(path: Path):
    """(tool name, input, result text) for every tool call of a transcript."""
    uses = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            content = (o.get("message") or {}).get("content")
            if not isinstance(content, list):
                continue
            for b in content:
                if b.get("type") == "tool_use":
                    uses[b["id"]] = (b["name"], b.get("input") or {})
                elif b.get("type") == "tool_result" and b.get("tool_use_id") in uses:
                    c = b.get("content")
                    text = c if isinstance(c, str) else "".join(x.get("text", "") for x in (c or []) if isinstance(x, dict))
                    name, args = uses[b["tool_use_id"]]
                    yield name, args, text


def payload(text: str):
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        # The wrapper's own lines may sit around the JSON: retry from the first '{"'.
        start = text.find('{"')
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None


def gather(transcripts: list[Path]):
    chat: dict[str, dict] = {}
    threads: dict[str, dict[str, dict]] = {}
    titles: dict[str, dict] = {}
    for t in transcripts:
        for name, args, text in tool_results(t):
            if not name.startswith("mcp__hearthbot__"):
                continue
            data = payload(text)
            if not isinstance(data, dict):
                continue
            if name.endswith("read_project_chat"):
                for m in data.get("messages", []):
                    chat[m["id"]] = m
            elif name.endswith("read_thread"):
                tid = data.get("thread_id") or args.get("thread_id")
                for m in data.get("messages", []):
                    threads.setdefault(tid, {})[m["id"]] = m
            elif name.endswith("list_threads"):
                for s in data.get("sessions", []):
                    titles[s["thread_id"]] = s
    return chat, threads, titles


# ---------------------------------------------------------------- files index


def copy_files(src: Path, dst: Path) -> dict[str, str]:
    """Copy the project files (minus raw uploads and private data); index them by file name."""
    index: dict[str, str] = {}
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        if rel.parts and rel.parts[0] in SKIP_FILES:
            dirs[:] = []
            continue
        dirs.sort()
        for f in sorted(files):
            target = dst / rel / f
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(root) / f, target)
            index.setdefault(f.lower(), str((rel / f).as_posix()))
    return index


def files_tree(dst: Path) -> str:
    def walk(d: Path, depth: int) -> str:
        items = []
        for p in sorted(d.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            rel = p.relative_to(dst.parent).as_posix()
            if p.is_dir():
                items.append(f"<li><details{' open' if depth == 0 else ''}><summary>📁 {html.escape(p.name)}</summary>"
                             f"<ul>{walk(p, depth + 1)}</ul></details></li>")
            else:
                size = p.stat().st_size
                items.append(f'<li><a href="{html.escape(rel)}">{html.escape(p.name)}</a> '
                             f'<span class="small">{size / 1024:.0f} KB</span></li>')
        return "".join(items)

    return f'<div class="tree"><ul>{walk(dst, 0)}</ul></div>'


# ---------------------------------------------------------------- conversation pages


def when(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, AttributeError):
        return ts or ""


def render_message(m: dict, link, files: dict[str, str], depth: int, thread_pages: dict[str, str]) -> str:
    body = m.get("body") or ""
    who = m.get("author_name") or ("Claude" if m.get("author") == "agent" else m.get("author", ""))
    cls = "user" if m.get("author") == "user" else "agent"
    inner = ""
    data = None
    if body.startswith("{"):
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = None
    if isinstance(data, dict) and "kind" in data:
        kind = data.get("kind")
        if kind == "status":
            inner = f'<div class="status">{html.escape(data.get("text", ""))}</div>'
            who += " · قائمة التقدم"
        elif kind == "thread_started":
            tid = data.get("thread_root_id", "")
            target = thread_pages.get(tid)
            inner = f'<div class="small">بدأ خيطا جديدا: <a href="{target}">{html.escape(tid)}</a></div>' if target else \
                '<div class="small">بدأ خيطا جديدا</div>'
        else:
            text = data.get("text") or data.get("content") or data.get("question") or ""
            extra = ""
            if data.get("options"):
                extra = "<ul>" + "".join(f"<li>{html.escape(o.get('label', ''))}: {html.escape(o.get('consequence', ''))}</li>"
                                         for o in data["options"] if isinstance(o, dict)) + "</ul>"
            inner = f'<div class="small">[{html.escape(str(kind))}]</div>{markdown(str(text), link)}{extra}'
    else:
        inner = markdown(body, link) if body else ""
    atts = []
    for a in m.get("attached_outputs") or []:
        name = a.get("filename") or a.get("title") or a.get("href") or "مرفق"
        if a.get("kind") == "file":
            local = files.get(name.lower())
            atts.append(f'<a href="{"../" * depth}files/{html.escape(local)}">📎 {html.escape(name)}</a>' if local
                        else f'<span title="غير موجود في النسخة">📎 {html.escape(name)}</span>')
        elif a.get("href"):
            atts.append(f'<a href="{html.escape(a["href"])}">🔗 {html.escape(name)}</a>')
    replies = f' · {m["reply_count"]} رد في الخيط' if m.get("reply_count") else ""
    return (f'<div class="msg {cls}" id="{html.escape(m.get("id", ""))}"><div class="who"><b>{html.escape(who)}</b> · '
            f'{when(m.get("created_at", ""))}{replies}</div>{inner}'
            f'{"<div class=att>" + "".join(atts) + "</div>" if atts else ""}</div>')


def conversation(out: Path, chat, threads, titles, files) -> list[tuple[str, str, int]]:
    conv = out / "conversation"
    conv.mkdir(parents=True, exist_ok=True)
    order = sorted(threads, key=lambda t: min(m.get("created_at", "") for m in threads[t].values()))
    pages = {tid: f"thread-{i + 1:02d}.html" for i, tid in enumerate(order)}

    def link(url: str) -> str:
        if url.startswith("#cmsg_"):
            return pages.get(url[1:], url)
        if url.startswith("/mnt/project-files/"):
            rel = url[len("/mnt/project-files/"):]
            return "../files/" + rel
        return url

    def title_of(tid: str) -> str:
        if tid in titles:
            return titles[tid].get("title") or tid
        first = min(threads[tid].values(), key=lambda m: m.get("created_at", ""))
        return (first.get("body") or tid)[:60]

    def sidebar(current: str) -> str:
        items = [f'<a href="index.html" class="{"on" if current == "chat" else ""}">💬 محادثة المشروع ({len(chat)})</a>']
        for tid in order:
            items.append(f'<a href="{pages[tid]}" class="{"on" if current == tid else ""}">🧵 {html.escape(title_of(tid))} '
                         f'<span class="small">({len(threads[tid])})</span></a>')
        items.append('<a href="../session/index.html">🛠 السجل التقني للجلسة</a>')
        return "<aside>" + "".join(items) + "</aside>"

    msgs = sorted(chat.values(), key=lambda m: m.get("created_at", ""))
    body = "".join(render_message(m, link, files, 1, pages) for m in msgs)
    (conv / "index.html").write_text(page("محادثة المشروع", (
        '<header><h1>محادثة المشروع</h1><p class="sub">الرسائل بينك وبين المنسق، ومنها بدأت الخيوط</p></header>'
        f'<div class="layout">{sidebar("chat")}<main>{body}</main></div>'), 1), encoding="utf-8")
    summary = []
    for tid in order:
        msgs = sorted(threads[tid].values(), key=lambda m: m.get("created_at", ""))
        meta = titles.get(tid, {})
        head = (f'<header><h1>{html.escape(title_of(tid))}</h1><p class="sub">{len(msgs)} رسالة · من {when(msgs[0].get("created_at", ""))} '
                f'إلى {when(msgs[-1].get("created_at", ""))}{" · الحالة: " + html.escape(meta.get("state", "")) if meta else ""}</p></header>')
        body = "".join(render_message(m, link, files, 1, pages) for m in msgs)
        (conv / pages[tid]).write_text(page(title_of(tid), f'{head}<div class="layout">{sidebar(tid)}<main>{body}</main></div>', 1),
                                       encoding="utf-8")
        summary.append((title_of(tid), "conversation/" + pages[tid], len(msgs)))
    return summary


# ---------------------------------------------------------------- session log


def session_log(out: Path, transcripts: list[Path]) -> int:
    d = out / "session"
    d.mkdir(parents=True, exist_ok=True)
    links, count = [], 0
    for i, t in enumerate(transcripts):
        parts = []
        uses = {}
        with t.open(encoding="utf-8") as f:
            for line in f:
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if o.get("type") not in ("user", "assistant"):
                    continue
                msg = o.get("message") or {}
                ts = when(o.get("timestamp", ""))
                content = msg.get("content")
                if isinstance(content, str):
                    count += 1
                    parts.append(f'<div class="msg user"><div class="who"><b>إدخال</b> · {ts}</div>'
                                 f'<pre>{html.escape(content[:6000])}</pre></div>')
                    continue
                for b in content or []:
                    kind = b.get("type")
                    if kind == "text" and b.get("text", "").strip():
                        count += 1
                        role = "Claude" if msg.get("role") == "assistant" else "إدخال"
                        parts.append(f'<div class="msg {"agent" if role == "Claude" else "user"}"><div class="who"><b>{role}</b> · {ts}</div>'
                                     f'<pre>{html.escape(b["text"][:6000])}</pre></div>')
                    elif kind == "tool_use":
                        uses[b["id"]] = b["name"]
                        args = json.dumps(b.get("input"), ensure_ascii=False, indent=1)
                        parts.append(f'<details class="small"><summary>🔧 {html.escape(b["name"])} · {ts}</summary>'
                                     f'<pre>{html.escape(args[:4000])}</pre></details>')
                    elif kind == "tool_result":
                        c = b.get("content")
                        text = c if isinstance(c, str) else "".join(x.get("text", "") for x in (c or []) if isinstance(x, dict))
                        parts.append(f'<details class="small"><summary>↩ نتيجة {html.escape(uses.get(b.get("tool_use_id"), ""))}</summary>'
                                     f'<pre>{html.escape(text[:2000])}{" …" if len(text) > 2000 else ""}</pre></details>')
        name = f"session-{i + 1}.html"
        (d / name).write_text(page(f"السجل التقني {i + 1}", (
            f'<header><h1>السجل التقني للجلسة {i + 1}</h1><p class="sub">{html.escape(t.name)}: الرسائل كاملة، '
            'ونداءات الأدوات ونتائجها مختصرة (تُفتح بالنقر)</p></header>' + "".join(parts)), 1), encoding="utf-8")
        links.append(f'<li><a href="{name}">{html.escape(t.name)}</a></li>')
    (d / "index.html").write_text(page("السجلات التقنية", (
        '<header><h1>السجلات التقنية</h1><p class="sub">سجل العمل الداخلي للجلسات المتاحة في هذه البيئة</p></header>'
        f'<section class="card"><ul>{"".join(links)}</ul></section>'), 1), encoding="utf-8")
    return count


# ---------------------------------------------------------------- repository


def repository(out: Path, repo: Path) -> tuple[int, int]:
    raw = out / "repo"
    raw.mkdir(parents=True, exist_ok=True)
    tar = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", "HEAD"], check=True, capture_output=True).stdout
    subprocess.run(["tar", "-x", "-C", str(raw)], input=tar, check=True)
    subprocess.run(["git", "-C", str(repo), "bundle", "create", str(out / "repo.bundle"), "--all"], check=True,
                   capture_output=True)
    files = subprocess.run(["git", "-C", str(repo), "ls-files"], check=True, capture_output=True, text=True).stdout.split("\n")
    files = [f for f in files if f and (raw / f).is_file()]
    browse = out / "browse"
    viewable = set()
    for f in files:
        p = raw / f
        if p.suffix.lower() in (".html", ".htm", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".webp"):
            continue
        if p.stat().st_size > MAX_VIEW:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        viewable.add(f)
        depth = f.count("/") + 1
        target = browse / (f + ".html")
        target.parent.mkdir(parents=True, exist_ok=True)

        def link(url: str, base=Path(f).parent) -> str:
            if re.match(r"^[a-z]+:", url) or url.startswith("#"):
                return url
            path, _, frag = url.partition("#")
            rel = os.path.normpath(base / path).replace(os.sep, "/")
            if rel in viewable or (raw / rel).suffix in (".md", ".py", ".ts", ".tsx", ".dart", ".yml", ".json", ".js", ".sh"):
                return os.path.relpath(rel, base).replace(os.sep, "/") + ".html" + (f"#{frag}" if frag else "")
            return "../" * depth + "repo/" + rel

        if p.suffix.lower() == ".md":
            content = f'<section class="card">{markdown(text, link)}</section>'
        else:
            content = f'<pre>{html.escape(text)}</pre>'
        crumbs = f'<p class="small ltr"><a href="{"../" * depth}repo.html">repo</a> / {html.escape(f)} · ' \
                 f'<a href="{"../" * depth}repo/{html.escape(f)}">الملف الأصلي</a></p>'
        target.write_text(page(f, crumbs + content, depth, rtl=p.suffix.lower() == ".md"), encoding="utf-8")

    tree: dict = {}
    for f in files:
        node = tree
        for part in f.split("/")[:-1]:
            node = node.setdefault(part + "/", {})
        node[f.split("/")[-1]] = f

    def walk(node: dict, depth: int) -> str:
        items = []
        for k in sorted(node, key=lambda k: (not k.endswith("/"), k.lower())):
            v = node[k]
            if isinstance(v, dict):
                items.append(f"<li><details{' open' if depth == 0 else ''}><summary>📁 {html.escape(k)}</summary><ul>{walk(v, depth + 1)}</ul></details></li>")
            else:
                href = f"browse/{v}.html" if v in viewable else f"repo/{v}"
                items.append(f'<li><a href="{html.escape(href)}">{html.escape(k)}</a></li>')
        return "".join(items)

    (out / "repo.html").write_text(page("المستودع", (
        '<header><h1>المستودع <span class="ltr">e-Himaya</span></h1><p class="sub">كل ملفات الكود والوثائق كما في آخر إيداع. '
        'الملفات النصية تُقرأ هنا مباشرة، والتقارير HTML تُفتح كما هي.</p></header>'
        f'<section class="card"><div class="tree"><ul>{walk(tree, 0)}</ul></div></section>'), 0), encoding="utf-8")
    return len(files), len(viewable)


# ---------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--repo", default=Path(__file__).resolve().parents[1], type=Path)
    ap.add_argument("--project-files", type=Path)
    ap.add_argument("--transcript", action="append", type=Path, default=[])
    ap.add_argument("--log", action="append", type=Path, default=[], help="transcripts shown in the technical log")
    ap.add_argument("--resume", type=Path)
    a = ap.parse_args()
    out = a.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "style.css").write_text(CSS, encoding="utf-8")

    files = {}
    if a.project_files:
        files = copy_files(a.project_files, out / "files")
        (out / "files.html").write_text(page("ملفات المشروع", (
            '<header><h1>ملفات المشروع</h1><p class="sub">كل التسليمات: التقارير، الوثائق، العروض، المخططات، الصور، الفيديو. '
            'الملفات الخام التي رفعتها (uploads) والمعطيات الخاصة لا تدخل النسخة.</p></header>'
            f'<section class="card">{files_tree(out / "files")}</section>'), 0), encoding="utf-8")
    chat, threads, titles = gather(a.transcript)
    summary = conversation(out, chat, threads, titles, files)
    logged = session_log(out, a.log)
    nfiles, nview = repository(out, a.repo)
    resume_link = ""
    if a.resume:
        text = a.resume.read_text(encoding="utf-8")
        (out / "resume.html").write_text(page("حوصلة الاستئناف", f'<section class="card">{markdown(text, lambda u: u)}</section>', 0),
                                         encoding="utf-8")
        shutil.copy2(a.resume, out / "resume.md")
        resume_link = '<a class="tile" href="resume.html"><b>حوصلة الاستئناف</b>كل ما تحتاجه جلسة جديدة لتواصل العمل</a>'
    reports = sorted(p.name for p in (out / "repo" / "docs").glob("*report*.html"))
    rep = "".join(f'<li><a href="repo/docs/{r}">{r}</a></li>' for r in reports)
    threads_list = "".join(f'<li><a href="{p}">{html.escape(t)}</a> <span class="small">({n} رسالة)</span></li>' for t, p, n in summary)
    total = len(chat) + sum(len(v) for v in threads.values())
    (out / "index.html").write_text(page("ء-حماية: نسخة المشروع والمحادثة", (
        '<header><h1>ء-حماية <span class="ltr">e-Himaya</span>: نسخة المشروع والمحادثة</h1>'
        f'<p class="sub">نسخة تعمل دون إنترنت، أُعدّت في {datetime.now().strftime("%Y-%m-%d %H:%M")}. '
        f'{total} رسالة في محادثة المشروع و{len(threads)} خيطا، و{nfiles} ملفا في المستودع.</p></header>'
        '<div class="grid">'
        '<a class="tile" href="conversation/index.html"><b>المحادثة</b>محادثة المشروع وكل الخيوط، بالمرفقات وروابط داخلية</a>'
        '<a class="tile" href="repo.html"><b>المستودع</b>شجرة الكود والوثائق، كل ملف نصي يُقرأ في المتصفح</a>'
        '<a class="tile" href="files.html"><b>ملفات المشروع</b>التسليمات: الوثائق والعروض والمخططات والصور</a>'
        f'{resume_link}'
        '<a class="tile" href="session/index.html"><b>السجل التقني</b>عمل الجلسة الأخيرة خطوة خطوة</a>'
        '</div>'
        f'<section class="card"><h2>الخيوط</h2><ol>{threads_list}</ol></section>'
        f'<section class="card"><h2>تقارير المراحل</h2><ul class="ltr">{rep}</ul></section>'
        '<section class="card"><h2>استرجاع المستودع بتاريخه الكامل</h2><p>الملف <code>repo.bundle</code> يحمل كل الإيداعات والفروع:</p>'
        '<pre>git clone repo.bundle e-himaya</pre><p>والمجلد <code>repo/</code> نسخة من آخر إيداع دون تاريخ.</p></section>'
        f'<p class="small">سجلات تقنية: {logged} رسالة. ملفات نصية قابلة للقراءة: {nview}.</p>'), 0), encoding="utf-8")
    print(json.dumps({"chat": len(chat), "threads": {titles.get(t, {}).get("title", t): len(v) for t, v in threads.items()},
                      "repo_files": nfiles, "viewable": nview, "project_files": len(files), "log_messages": logged},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
