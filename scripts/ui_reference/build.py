"""Build the e-Himaya UI reference workbook (Yamen, 2026-11-08).

One row for every text, button, field, icon, colour and shape of every surface: the sign-in page (Keycloak),
the dashboard, the portal, the citizen app and the staff app. Each row says where the element appears, the
file and line that show it, the file and line to change, and, for screens and fields, the API endpoints and
the database tables behind them. Everything is read from the source, so running it again keeps the
reference true after each change.

    cd services/api && .venv/bin/python ../../scripts/ui_reference/backend_dump.py > /tmp/backend.json
    python3 scripts/ui_reference/build.py --backend /tmp/backend.json --out ehimaya-ui-reference.xlsx \
        [--keycloak-themes <folder holding theme/base and theme/keycloak.v2 from the Keycloak themes jar>]

Matches between a field and a database column are automatic (same name) and say so in the workbook.
Needs openpyxl.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, NamedStyle, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

REPO = Path(__file__).resolve().parents[2]
GITHUB = "https://github.com/mouhabouk/e-himaya/blob/{sha}/{path}#L{line}"
KEYCLOAK_GITHUB = "https://github.com/keycloak/keycloak/blob/26.8.1/themes/src/main/resources/{path}#L{line}"
LANGS = ("ar", "fr", "en")

# ---------------------------------------------------------------------------------------------- utilities


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def read(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def find_line(path: Path, needle: str, start: int = 1) -> int:
    for i, line in enumerate(read(path), 1):
        if i >= start and needle in line:
            return i
    return 0


@dataclass
class Ref:
    """A place in the code: a repository file, or a Keycloak theme file outside the repository."""

    path: str
    line: int
    keycloak: bool = False

    def text(self) -> str:
        return f"{self.path}:{self.line}" if self.line else self.path

    def url(self, sha: str) -> str:
        if self.keycloak:
            return KEYCLOAK_GITHUB.format(path=self.path, line=self.line or 1)
        return GITHUB.format(sha=sha, path=self.path, line=self.line or 1)


# ------------------------------------------------------------------------------------------ translations


def json_strings(path: Path) -> dict[str, tuple[str, int]]:
    """Flatten a pretty-printed i18n JSON file to {dotted.key: (text, line)}."""
    out: dict[str, tuple[str, int]] = {}
    stack: list[str] = []
    arrays: list[list[int]] = []  # index counters for open arrays, parallel to stack entries that are arrays
    kinds: list[str] = []
    for i, raw in enumerate(read(path), 1):
        s = raw.strip()
        m = re.match(r'^"((?:[^"\\]|\\.)*)"\s*:\s*(.*?),?$', s)
        if m:
            key = json.loads(f'"{m.group(1)}"')
            rest = m.group(2)
            if rest == "{":
                stack.append(key)
                kinds.append("o")
            elif rest == "[":
                stack.append(key)
                kinds.append("a")
                arrays.append([0])
            elif rest.startswith("{") or rest.startswith("["):
                continue  # one-line object or array: not used for UI text
            else:
                value = json.loads(rest)
                if isinstance(value, str):
                    out[".".join([*stack, key])] = (value, i)
            continue
        if kinds and kinds[-1] == "a" and s.rstrip(",") == "{":
            stack.append(str(arrays[-1][0]))
            arrays[-1][0] += 1
            kinds.append("o")
            continue
        if kinds and kinds[-1] == "a" and s.startswith('"'):
            idx = arrays[-1][0]
            arrays[-1][0] += 1
            out[".".join([*stack, str(idx)])] = (json.loads(s.rstrip(",")), i)
            continue
        if s.rstrip(",") in ("}", "]") and stack:
            if kinds.pop() == "a":
                arrays.pop()
            stack.pop()
    return out


def check_flatten(path: Path, flat: dict[str, tuple[str, int]]) -> None:
    def walk(node, prefix=""):
        if isinstance(node, dict):
            for k, v in node.items():
                yield from walk(v, f"{prefix}{k}.")
        elif isinstance(node, list):
            for k, v in enumerate(node):
                yield from walk(v, f"{prefix}{k}.")
        elif isinstance(node, str):
            yield prefix[:-1]

    expected = set(walk(json.loads(path.read_text(encoding="utf-8"))))
    missing = expected - set(flat)
    if missing:
        raise SystemExit(f"{rel(path)}: {len(missing)} keys not located, e.g. {sorted(missing)[:3]}")


def arb_strings(path: Path) -> dict[str, tuple[str, int]]:
    out = {}
    for i, raw in enumerate(read(path), 1):
        m = re.match(r'^\s*"([A-Za-z]\w*)"\s*:\s*(".*")\s*,?\s*$', raw)
        if m:
            out[m.group(1)] = (json.loads(m.group(2)), i)
    return out


def properties_strings(path: Path) -> dict[str, tuple[str, int]]:
    out = {}
    if not path.exists():
        return out
    for i, raw in enumerate(read(path), 1):
        if raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        value = value.encode("latin-1", "backslashreplace").decode("unicode_escape") if "\\u" in value else value
        out[key.strip()] = (value.strip(), i)
    return out


# --------------------------------------------------------------------------------------- classification

ELEMENT_RULES: list[tuple[str, str]] = [
    (r"aria-label|semanticsLabel|Semantics\(|tooltip:", "وصف لقارئ الشاشة أو تلميح"),
    (r"placeholder|hintText", "نص توضيحي داخل حقل"),
    (r"<button|Button\b|Button\(|onClick|onPressed|type=\"submit\"", "زر"),
    (r"<label|labelText|\blabel[=:]|InputDecoration", "تسمية حقل"),
    (r"<th\b|DataColumn|<caption", "عنوان عمود في جدول"),
    (r"<option|DropdownMenuItem|ButtonSegment|ChoiceChip|FilterChip|<select", "خيار في قائمة"),
    (r"<h[1-4]\b|AppBar|SliverAppBar|\btitle[:=]|PageHeader|<legend", "عنوان"),
    (r"toast|SnackBar|showSnack|notify\(", "رسالة منبثقة"),
    (r"role=\"alert\"|errorText|setError|\berror\b", "رسالة خطأ"),
    (r"<a\b|<Link\b|<NavLink\b|href=", "رابط"),
    (r"<Tab\b|Tab\(|role=\"tab\"", "تبويب"),
    (r"checkbox|Checkbox|Switch\(|SwitchListTile|type=\"radio\"|Radio", "خانة اختيار"),
    (r"confirm\(|AlertDialog|<dialog|Dialog\b", "نافذة حوار"),
    (r"document\.title", "عنوان نافذة المتصفح"),
]

KEY_RULES: list[tuple[str, str]] = [
    (r"^nav\.", "عنصر في قائمة التنقل"),
    (r"(^|\.)(error|errors|failed|invalid)|Error$|Failed$", "رسالة خطأ"),
    (r"(title|heading|Title|Heading)$", "عنوان"),
    (r"(placeholder|Placeholder|hint|Hint)$", "نص توضيحي داخل حقل"),
    (r"(label|Label)$", "تسمية حقل"),
    (r"(^|\.)(save|cancel|submit|send|delete|confirm|close|add|edit|retry|next|back)$|^action", "زر"),
    (r"(empty|Empty|none|None)$", "رسالة عند غياب البيانات"),
    (r"(help|Help|hintText|description|Desc)$", "نص مساعد"),
]


def classify(line: str, context: str, key: str, dynamic: bool) -> str:
    for pattern, label in ELEMENT_RULES:
        if re.search(pattern, line):
            return label
    for pattern, label in KEY_RULES:
        if re.search(pattern, key):
            return label
    for pattern, label in ELEMENT_RULES[:9]:
        if re.search(pattern, context):
            return label
    return "نص متغيّر حسب القيمة" if dynamic else "نص"


ICON_NEAR = re.compile(r'<(?:Icon|IconTile)\b[^>]*\bname=\{?"(\w+)"|\bicon[=:]\s*\{?"(\w+)"|Icons\.(\w+)')


def near_icon(lines: list[str], i: int) -> str:
    for j in (i, i - 1, i + 1):
        if 0 <= j < len(lines):
            m = ICON_NEAR.search(lines[j])
            if m:
                return next(g for g in m.groups() if g)
    return ""


# ------------------------------------------------------------------------------------------------ usages


@dataclass
class Usage:
    key: str
    file: Path
    line: int
    kind: str
    icon: str
    dynamic: bool


def source_files(root: Path, exts: tuple[str, ...]) -> list[Path]:
    out = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in exts or not path.is_file():
            continue
        name = path.name
        if ".test." in name or name.endswith("_test.dart") or "/test/" in path.as_posix() or ".g.dart" in name:
            continue
        if "/l10n/" in path.as_posix() and path.suffix == ".dart":
            continue
        out.append(path)
    return out


PLURAL = re.compile(r"_(zero|one|two|few|many|other)$")


def web_usages(files: list[Path], keys: set[str]) -> list[Usage]:
    bases = defaultdict(list)
    for k in keys:
        bases[PLURAL.sub("", k)].append(k)
    literal = re.compile(r"""["']([A-Za-z][\w-]*(?:\.[\w-]+)+)["']""")
    template = re.compile(r"`([A-Za-z][\w-]*(?:\.[\w-]+)*\.)\$\{")
    ordered = sorted(keys)
    prefix_cache: dict[str, list[str]] = {}

    def by_prefix(prefix: str) -> list[str]:
        if prefix not in prefix_cache:
            prefix_cache[prefix] = [k for k in ordered if k.startswith(prefix)]
        return prefix_cache[prefix]

    out = []
    for path in files:
        lines = read(path)
        for i, line in enumerate(lines):
            context = " ".join(lines[max(0, i - 3) : i + 1])
            seen = set()
            for m in literal.finditer(line):
                for k in bases.get(m.group(1), []):
                    if k not in seen:
                        seen.add(k)
                        out.append(Usage(k, path, i + 1, classify(line, context, k, False), near_icon(lines, i), False))
            for m in template.finditer(line):
                prefix = m.group(1)
                for k in by_prefix(prefix):
                    if k not in seen:
                        seen.add(k)
                        out.append(Usage(k, path, i + 1, classify(line, context, k, True), near_icon(lines, i), True))
    return out


def dart_usages(files: list[Path], keys: set[str]) -> list[Usage]:
    pattern = re.compile(r"\b(?:l10n|loc|failed|strings|t)\.(\w+)|AppLocalizations\.of\(\w+\)!?\.(\w+)")
    out = []
    for path in files:
        lines = read(path)
        for i, line in enumerate(lines):
            context = " ".join(lines[max(0, i - 3) : i + 1])
            for m in pattern.finditer(line):
                k = m.group(1) or m.group(2)
                if k in keys:
                    out.append(Usage(k, path, i + 1, classify(line, context, k, False), near_icon(lines, i), False))
    return out


# ----------------------------------------------------------------------------------------- screen mapping

IMPORT = re.compile(r"""from\s+["'](\.{1,2}/[^"']+)["']|import\(\s*["'](\.{1,2}/[^"']+)["']\s*\)""")


def resolve_import(base: Path, spec: str) -> Path | None:
    target = (base.parent / spec).resolve()
    for cand in (target, *(target.with_suffix(e) for e in (".tsx", ".ts")), target / "index.tsx", target / "index.ts"):
        if cand.is_file():
            return cand
    return None


def import_graph(files: list[Path]) -> dict[Path, set[Path]]:
    importers: dict[Path, set[Path]] = defaultdict(set)
    for path in files:
        for m in IMPORT.finditer(path.read_text(encoding="utf-8")):
            target = resolve_import(path, m.group(1) or m.group(2))
            if target:
                importers[target.resolve()].add(path.resolve())
    return importers


def web_routes(app_file: Path) -> dict[Path, list[str]]:
    """Map page files to their routes, from <Route path=... element={<XPage />}> in App.tsx."""
    text = app_file.read_text(encoding="utf-8")
    comp_file: dict[str, Path] = {}
    for m in re.finditer(r"import\s*\{([^}]+)\}\s*from\s*[\"'](\./pages/[^\"']+)[\"']", text):
        target = resolve_import(app_file, m.group(2))
        for name in m.group(1).split(","):
            name = name.strip().split(" as ")[-1].strip()
            if name and target:
                comp_file[name] = target.resolve()
    for m in re.finditer(
        r"const\s+(\w+)\s*=\s*(?:lazy|page)\(\s*\(\)\s*=>\s*import\([\"'](\./pages/[^\"']+)[\"']", text
    ):
        target = resolve_import(app_file, m.group(2))
        if target:
            comp_file[m.group(1)] = target.resolve()
    routes: dict[Path, list[str]] = defaultdict(list)
    stack: list[str] = []  # paths of the open parent <Route ...> elements
    pos = 0
    token = re.compile(r"<Route\b|</Route>")
    while True:
        m = token.search(text, pos)
        if not m:
            break
        if m.group(0) == "</Route>":
            if stack:
                stack.pop()
            pos = m.end()
            continue
        # Find the end of this opening tag: the first ">" outside braces.
        depth, i = 0, m.end()
        while i < len(text):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            elif ch == ">" and depth == 0:
                break
            i += 1
        tag = text[m.end() : i]
        closed = tag.rstrip().endswith("/")
        pm = re.search(r'\bpath="([^"]*)"', tag)
        own = pm.group(1) if pm else ""
        full = "/".join(x.strip("/") for x in [*stack, own] if x.strip("/"))
        full = "/" + full if not full.startswith("/") else full
        el_part = tag[tag.find("element") :] if "element" in tag else ""
        for name in re.findall(r"<([A-Z]\w+)\b", el_part):
            if name in comp_file:
                routes[comp_file[name]].append(full)
                break
        if not closed:
            stack.append(own)
        pos = i + 1
    return routes


def screens_for(path: Path, page_routes: dict[Path, list[str]], importers: dict[Path, set[Path]], label) -> str:
    path = path.resolve()
    if path in page_routes:
        return "، ".join(sorted(set(page_routes[path])))
    seen, frontier, pages = {path}, [path], set()
    for _ in range(4):
        nxt = []
        for f in frontier:
            for imp in importers.get(f, ()):
                if imp in seen:
                    continue
                seen.add(imp)
                if imp in page_routes:
                    pages.add(imp)
                else:
                    nxt.append(imp)
        frontier = nxt
    if any(p.name in ("App.tsx", "Layout.tsx", "main.tsx") for p in seen) and not pages:
        return label
    routes = sorted({r for p in pages for r in page_routes[p]})
    if not routes:
        return label
    if len(routes) > 4:
        return f"مكوّن مشترك في {len(routes)} مسارا ({'، '.join(routes[:3])}…)"
    return "مكوّن مشترك: " + "، ".join(routes)


def dart_screen(path: Path, root: Path) -> str:
    parts = path.relative_to(root).parts
    name = path.stem.replace("_screen", "").replace("_screens", "")
    if parts[0] == "features":
        return f"{parts[1]} › {name}" if name != parts[1] else parts[1]
    if parts[0] == "staff":
        return f"الأعوان › {name}"
    return f"{parts[0]} › {name}"


# ------------------------------------------------------------------------------------------- API mapping


def norm_path(path: str) -> str:
    path = path.split("?")[0]
    path = re.sub(r"\$\{[^}]*\}|\$\w+|\{[^}]*\}", "{}", path)
    return path.rstrip("/") or "/"


def web_api_methods(lib: Path) -> dict[str, tuple[str, str]]:
    """{method name: (HTTP verb, normalised path)} from api.request(...) calls in src/lib/*.ts."""
    methods: dict[str, tuple[str, str]] = {}
    for path in sorted(lib.glob("*.ts")):
        if ".test." in path.name:
            continue
        text = path.read_text(encoding="utf-8")
        consts = {m.group(1): m.group(2) for m in re.finditer(r"const\s+(\w+)\s*=\s*[\"`]([^\"`]*)[\"`]", text)}
        funcs = {
            m.group(1): m.group(2)
            for m in re.finditer(r"const\s+(\w+)\s*=\s*\([^)]*\)\s*(?::\s*\w+)?\s*=>\s*`([^`]*)`", text)
        }
        for m in re.finditer(r"function\s+(\w+)\([^)]*\)[^{]*\{\s*return\s*`([^`]*)`", text):
            funcs[m.group(1)] = m.group(2)
        starts = [(m.start(), m.group(1)) for m in re.finditer(r"^\s+(\w+):\s*(?:async\s*)?\(", text, re.M)]
        for n, (start, name) in enumerate(starts):
            chunk = text[start : starts[n + 1][0] if n + 1 < len(starts) else len(text)]
            rm = re.search(r"api\.request(?:<[^(]*?>)?\(\s*(\"[^\"]*\"|`[^`]*`|\w+\([^)]*\)|\w+)", chunk, re.S)
            if not rm:
                continue
            expr = rm.group(1)
            if expr[0] in '"`':
                url = expr[1:-1]
            elif "(" in expr:
                url = funcs.get(expr.split("(")[0], "")
            else:
                url = consts.get(expr, "")
            for _ in range(3):
                url = re.sub(r"\$\{(\w+)\}", lambda mm: consts.get(mm.group(1), mm.group(0)), url)
                url = re.sub(r"\$\{(\w+)\([^)]*\)\}", lambda mm: funcs.get(mm.group(1), mm.group(0)), url)
            if "/api/" not in url:
                continue
            vm = re.search(r'method:\s*"(\w+)"', chunk)
            methods.setdefault(name, (vm.group(1) if vm else "GET", norm_path(url)))
    return methods


GENERIC = {"get", "set", "map", "filter", "then", "catch", "list", "delete", "find", "push", "join", "has", "add"}


def web_calls(path: Path, methods: dict[str, tuple[str, str]]) -> list[tuple[str, str, int]]:
    out = []
    for i, line in enumerate(read(path), 1):
        for m in re.finditer(r"\b\w*[aA]pi\w*\.(\w+)\(", line):
            name = m.group(1)
            if name in methods and name not in GENERIC:
                verb, url = methods[name]
                out.append((verb, url, i))
    return out


def dart_api(root: Path) -> tuple[dict[Path, list[tuple[str, str, int]]], dict[str, tuple[str, str]]]:
    """Endpoints named in each Dart file, and the staff API's methods ({name: (verb, path)})."""
    by_file: dict[Path, list[tuple[str, str, int]]] = defaultdict(list)
    for path in source_files(root, (".dart",)):
        for i, line in enumerate(read(path), 1):
            if line.strip().startswith("///") or line.strip().startswith("//"):
                continue
            for m in re.finditer(r"['\"](?:\$\w+|\$\{[^}]+\})?(/api/v1/[^'\"]*)['\"]", line):
                verb = re.search(r"\.(get|post|put|patch|delete)\b|'(GET|POST|PUT|PATCH|DELETE)'", line, re.I)
                v = (verb.group(1) or verb.group(2)).upper() if verb else "GET"
                by_file[path.resolve()].append((v, norm_path(m.group(1)), i))
    staff = root / "staff" / "staff_api.dart"
    methods: dict[str, tuple[str, str]] = {}
    if staff.exists():
        text = staff.read_text(encoding="utf-8")
        starts = [(m.start(), m.group(1)) for m in re.finditer(r"^\s+Future<.*?>\s+(\w+)\(", text, re.M)]
        for n, (start, name) in enumerate(starts):
            chunk = text[start : starts[n + 1][0] if n + 1 < len(starts) else len(text)]
            cm = re.search(r"_call\(\s*'(\w+)',\s*['\"]([^'\"]+)['\"]", chunk)
            if cm:
                methods[name] = (cm.group(1), norm_path("/api/v1/crew" + cm.group(2)))
    return by_file, methods


@dataclass
class Backend:
    routes: list[dict]
    tables: dict[str, dict]
    index: dict[tuple[str, tuple[str, ...]], list[dict]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Backend:
        data = json.loads(path.read_text(encoding="utf-8"))
        b = cls(data["routes"], {f"{t['schema']}.{t['table']}": t for t in data["tables"]})
        for r in b.routes:
            for verb in r["methods"]:
                b.index.setdefault((verb, tuple(norm_path(r["path"]).split("/"))), []).append(r)
        return b

    def match(self, verb: str, url: str) -> dict | None:
        segs = tuple(url.split("/"))
        hit = self.index.get((verb, segs))
        if hit:
            return hit[0]
        for (v, cand), routes in self.index.items():
            if v == verb and len(cand) == len(segs) and all(a == b or "{}" in (a, b) for a, b in zip(cand, segs)):
                return routes[0]
        return None


# --------------------------------------------------------------------------------------------- workbook

NAVY = "1F3FA0"
GOLD = "C9A24A"
HEAD = PatternFill("solid", fgColor=NAVY)
BAND = PatternFill("solid", fgColor="F3F5FA")
THIN = Side(style="thin", color="D5DAE6")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
FONT = "IBM Plex Sans Arabic"


def sheet(wb: Workbook, title: str, headers: list[str], widths: list[int]) -> Worksheet:
    ws = wb.create_sheet(title)
    ws.sheet_view.rightToLeft = True
    ws.append(headers)
    for col, (h, w) in enumerate(zip(headers, widths), 1):
        c = ws.cell(row=1, column=col)
        c.fill = HEAD
        c.font = Font(name=FONT, bold=True, color="FFFFFF", size=11)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.row_dimensions[1].height = 34
    ws.freeze_panes = "B2"
    return ws


STYLES: dict[str, NamedStyle] = {}


def styles(wb: Workbook) -> None:
    # Named styles: one shared definition per look, much faster than styling each cell.
    for name, fill, link in (
        ("cell", None, False),
        ("band", BAND, False),
        ("link", None, True),
        ("link-band", BAND, True),
    ):
        st = NamedStyle(name=name)
        st.font = Font(name=FONT, size=10, color=NAVY, underline="single") if link else Font(name=FONT, size=10)
        st.alignment = Alignment(vertical="top", wrap_text=True)
        st.border = BORDER
        if fill:
            st.fill = fill
        wb.add_named_style(st)
        STYLES[name] = st


def add(ws: Worksheet, values: list, links: dict[int, str] | None = None, fill: str | None = None) -> None:
    ws.append([v if v is not None else "" for v in values])
    r = ws._rows_written = getattr(ws, "_rows_written", 1) + 1
    band = r % 2 == 0
    links = links or {}
    for col, c in enumerate(ws[r], 1):
        if col in links:
            c.hyperlink = links[col]
            c.style = "link-band" if band else "link"
        else:
            c.style = "band" if band else "cell"
    if fill:
        ws.cell(row=r, column=fill_col(ws)).fill = PatternFill("solid", fgColor=fill)


def fill_col(ws: Worksheet) -> int:
    return getattr(ws, "_swatch_col", 1)


def finish(ws: Worksheet) -> None:
    ws.auto_filter.ref = f"A1:{get_column_letter(ws.max_column)}{ws.max_row}"


TEXT_HEADERS = [
    "#",
    "الشاشة أو المسار",
    "ملف الشاشة",
    "نوع العنصر",
    "النص بالعربية",
    "النص بالفرنسية",
    "النص بالإنجليزية",
    "المفتاح البرمجي",
    "موضع الظهور في البرنامج (ملف:سطر)",
    "يُغيَّر النص العربي في (ملف:سطر)",
    "يُغيَّر النص الفرنسي في",
    "يُغيَّر النص الإنجليزي في",
    "أيقونة مجاورة",
    "البيانات المرتبطة (مطابقة آلية)",
]
TEXT_WIDTHS = [6, 26, 26, 18, 40, 34, 34, 30, 34, 30, 26, 26, 14, 36]


def field_link(key: str, kind: str, endpoints: list[tuple[str, str, int]], backend: Backend) -> str:
    if kind not in ("تسمية حقل", "نص توضيحي داخل حقل", "عنوان عمود في جدول", "خانة اختيار"):
        return ""
    last = key.split(".")[-1]
    last = re.sub(r"(Label|Placeholder|Hint|Help|Title)$", "", last) or last
    name = snake(last)
    if len(name) < 3:
        return ""
    for verb, url, _ in endpoints:
        route = backend.match(verb, url)
        if not route:
            continue
        if verb in ("POST", "PUT", "PATCH") and name in route["body"]:
            cols = [
                f"{t}.{name}"
                for t in route["tables"]
                if any(c["name"] == name for c in backend.tables.get(t, {}).get("columns", []))
            ]
            return f"حقل «{name}» في {verb} {route['path']}" + (f" ← {cols[0]}" if cols else "")
        for t in route["tables"]:
            if any(c["name"] == name for c in backend.tables.get(t, {}).get("columns", [])):
                return f"{t}.{name} (عبر {verb} {route['path']})"
    return ""


def text_sheet(
    wb: Workbook,
    title: str,
    sha: str,
    strings: dict[str, dict[str, tuple[str, int]]],
    files: dict[str, Path],
    usages: list[Usage],
    screen_of,
    endpoints_of,
    backend: Backend,
) -> dict:
    ws = sheet(wb, title, TEXT_HEADERS, TEXT_WIDTHS)
    used = set()
    n = 0
    for u in sorted(usages, key=lambda u: (screen_of(u.file), rel(u.file), u.line)):
        used.add(u.key)
        n += 1
        ar = strings["ar"].get(u.key, ("", 0))
        fr = strings["fr"].get(u.key, ("", 0))
        en = strings["en"].get(u.key, ("", 0))
        where = Ref(rel(u.file), u.line)
        refs = [Ref(rel(files[lang]), strings[lang].get(u.key, ("", 0))[1]) for lang in LANGS]
        add(
            ws,
            [
                n,
                screen_of(u.file),
                u.file.name,
                u.kind,
                ar[0],
                fr[0],
                en[0],
                u.key + (" (يُختار حسب القيمة)" if u.dynamic else ""),
                where.text(),
                refs[0].text(),
                refs[1].text(),
                refs[2].text(),
                u.icon,
                field_link(u.key, u.kind, endpoints_of(u.file), backend),
            ],
            {9: where.url(sha), 10: refs[0].url(sha), 11: refs[1].url(sha), 12: refs[2].url(sha)},
        )
    unused = sorted(set(strings["ar"]) - used)
    for k in unused:
        n += 1
        refs = [Ref(rel(files[lang]), strings[lang].get(k, ("", 0))[1]) for lang in LANGS]
        add(
            ws,
            [
                n,
                "لا يظهر مباشرة (مفتاح غير مستعمل أو يُبنى اسمه أثناء التشغيل)",
                "",
                "نص",
                strings["ar"][k][0],
                strings["fr"].get(k, ("", 0))[0],
                strings["en"].get(k, ("", 0))[0],
                k,
                "",
                refs[0].text(),
                refs[1].text(),
                refs[2].text(),
                "",
                "",
            ],
            {10: refs[0].url(sha), 11: refs[1].url(sha), 12: refs[2].url(sha)},
        )
    finish(ws)
    return {"rows": n, "keys": len(strings["ar"]), "used": len(used), "unused": len(unused)}


# ---------------------------------------------------------------------------------- sign-in page (Keycloak)


def keycloak_sheet(wb: Workbook, sha: str, kc_themes: Path | None) -> int:
    theme = REPO / "infra/keycloak/themes/ehimaya/login"
    ftl = theme / "login.ftl"
    css = theme / "resources/css/ehimaya.css"
    js = theme / "resources/js/languages.js"
    realms = REPO / "infra/keycloak/realms"
    public, staff = realms / "ehimaya-public-realm.json", realms / "ehimaya-staff-realm.json"
    ours = {lang: properties_strings(theme / f"messages/messages_{lang}.properties") for lang in LANGS}
    base = {
        lang: properties_strings(kc_themes / f"theme/base/login/messages/messages_{lang}.properties")
        if kc_themes
        else {}
        for lang in LANGS
    }

    def text(key: str) -> list[str]:
        return [(ours[lang].get(key) or base[lang].get(key) or ("", 0))[0] for lang in LANGS]

    def change(key: str) -> tuple[str, str]:
        if key in ours["ar"]:
            r = Ref(rel(theme / "messages/messages_ar.properties"), ours["ar"][key][1])
            return r.text(), r.url(sha)
        r = Ref(rel(theme / "messages/messages_ar.properties"), 0)
        return f"أضف السطر {key}=… إلى {r.path} (النص الحالي من قالب Keycloak الأساسي)", r.url(sha)

    def kc(path: str, needle: str) -> Ref:
        line = find_line(kc_themes / path, needle) if kc_themes and (kc_themes / path).exists() else 0
        return Ref(path, line, keycloak=True)

    def here(path: Path, needle: str, start: int = 1) -> Ref:
        return Ref(rel(path), find_line(path, needle, start))

    rows: list[tuple] = []

    def row(element, kind, texts, shown: Ref, change_text, change_url, data, note=""):
        rows.append((element, kind, *texts, shown, change_text, change_url, data, note))

    ct, cu = here(css, "الجمهورية التونسية").text(), here(css, "الجمهورية التونسية").url(sha)
    row(
        "الترويسة الرسمية: الجمهورية التونسية / وزارة الداخلية / الديوان الوطني للحماية المدنية",
        "عنوان",
        [
            "الجمهورية التونسية · وزارة الداخلية · الديوان الوطني للحماية المدنية",
            "République tunisienne · Ministère de l’Intérieur · Office national de la protection civile",
            "Republic of Tunisia · Ministry of the Interior · National Office of Civil Protection",
        ],
        here(css, "#kc-header::before"),
        f"{ct} (العربية)، {here(css, 'République tunisienne').text()} (FR)، {here(css, 'Republic of Tunisia').text()} (EN)",
        cu,
        "لا شيء: نص ثابت في ملف التنسيق",
    )
    row(
        "اسم المنظومة فوق البطاقة «ء-حماية»",
        "عنوان",
        text("loginTitleHtml"),
        here(theme / "messages/messages_ar.properties", "loginTitleHtml"),
        *change("loginTitleHtml"),
        "لا شيء",
    )
    row(
        "الشعار «تطبيق ذكي في خدمة المواطن والمؤسسات، سلامتكم أولويتنا»",
        "نص",
        [
            "تطبيق ذكي في خدمة المواطن والمؤسسات، سلامتكم أولويتنا",
            "Une application intelligente au service du citoyen et des entreprises. Votre sécurité, notre priorité",
            "A smart application serving citizens and organisations. Your safety, our priority",
        ],
        here(css, "#kc-header::after"),
        f"{here(css, 'تطبيق ذكي في خدمة').text()} (العربية)، {here(css, 'Une application intelligente').text()} (FR)، {here(css, 'A smart application').text()} (EN)",
        here(css, "تطبيق ذكي في خدمة").url(sha),
        "لا شيء: نص ثابت في ملف التنسيق",
    )
    row(
        "عنوان البطاقة للمواطن والمتطوع والمؤسسة «الدخول إلى آلو - حماية»",
        "عنوان",
        [t.replace(" ", " ") for t in text("ehimayaAppLoginTitle")],
        here(ftl, "ehimayaAppLoginTitle"),
        *change("ehimayaAppLoginTitle"),
        f"يظهر في المجال ehimaya-public فقط ({here(public, '"realm"').text()})",
    )
    row(
        "عنوان البطاقة للأعوان «الدخول إلى ء-حماية»",
        "عنوان",
        text("loginAccountTitle"),
        here(ftl, "loginAccountTitle"),
        *change("loginAccountTitle"),
        "يظهر في المجال ehimaya-staff ومجال الإدارة",
    )
    row(
        "حقل اسم المستخدم أو البريد الإلكتروني",
        "تسمية حقل",
        text("usernameOrEmail"),
        here(ftl, 'name="username"'),
        *change("usernameOrEmail"),
        f"قاعدة Keycloak: الجدول USER_ENTITY (USERNAME، EMAIL، REALM_ID). الدخول بالبريد مسموح بالإعداد loginWithEmailAllowed ({here(public, 'loginWithEmailAllowed').text()})",
    )
    row(
        "حقل كلمة العبور",
        "تسمية حقل",
        text("password"),
        here(ftl, 'name="password"'),
        *change("password"),
        "قاعدة Keycloak: الجدول CREDENTIAL (TYPE = 'password'، SECRET_DATA بصيغة مُجزّأة لا تُقرأ، CREDENTIAL_DATA تحمل الخوارزمية)، "
        f"مربوط بالمستخدم عبر USER_ID → USER_ENTITY.ID. شروط الكلمة: passwordPolicy ({here(public, 'passwordPolicy').text()}). "
        "خادم e-Himaya لا يرى كلمة العبور ولا يخزّنها: يتسلّم رمز OIDC فقط.",
    )
    fp = kc("theme/keycloak.v2/login/field.ftl", "doForgotPassword")
    row(
        "رابط «نسيت كلمة المرور؟»",
        "رابط",
        text("doForgotPassword"),
        fp,
        *change("doForgotPassword"),
        f"يظهر لأن resetPasswordAllowed = true ({here(public, 'resetPasswordAllowed').text()} للمواطن، {here(staff, 'resetPasswordAllowed').text()} للأعوان). "
        "يفتح مسار reset-credentials في Keycloak: يرسل رسالة عبر خادم البريد (smtpServer في ملف المجال) ثم يكتب كلمة جديدة في CREDENTIAL.",
        "الرابط مرسوم في قالب Keycloak الأساسي field.ftl، لا في مستودعنا. لإخفائه: resetPasswordAllowed = false.",
    )
    row(
        "خانة «تذكرني»",
        "خانة اختيار",
        text("rememberMe"),
        here(ftl, "rememberMe"),
        *change("rememberMe"),
        "تظهر فقط إذا فُعّل rememberMe في المجال (غير مفعّل حاليا في الملفين، فلا تظهر).",
    )
    row(
        "زر «تسجيل دخول»",
        "زر",
        text("doLogIn"),
        kc("theme/keycloak.v2/login/buttons.ftl", "doLogIn"),
        *change("doLogIn"),
        "يرسل النموذج kc-form-login إلى Keycloak (url.loginAction). شكله في ehimaya.css: "
        + here(css, ".pf-v5-c-button.pf-m-primary").text(),
    )
    row(
        "سطر «مستخدم جديد؟ تسجيل جديد»",
        "رابط",
        [f"{a} {b}" for a, b in zip(text("noAccount"), text("doRegister"))],
        here(ftl, "noAccount"),
        *change("noAccount"),
        f"يظهر حين registrationAllowed = true: للمواطن ({here(public, 'registrationAllowed').text()})، ومُعطّل للأعوان ({here(staff, 'registrationAllowed').text()}). "
        "يكتب حسابا جديدا في USER_ENTITY و CREDENTIAL، ثم ينشئ الخادم ملف identity.profile عند أول دخول.",
        "النص الثاني: المفتاح doRegister",
    )
    row(
        "رسالة التحقق الآلي (إثبات العمل)",
        "نص",
        text("ehimayaPowWorking"),
        here(ftl, "ehimayaPowWorking"),
        *change("ehimayaPowWorking"),
        "يحسبه المتصفح (resources/js/pow.js) ويتحقق منه مزوّد e-Himaya في Keycloak (infra/keycloak/providers)",
        "رسائله الأخرى: ehimayaPowDone، ehimayaPowFailed، ehimayaPowNoScript، ehimayaProofRequired",
    )
    row(
        "دوائر اللغة الذهبية (ع، FR، EN)",
        "زر",
        ["ع · FR · EN"] * 3,
        here(js, "function build()"),
        f"الترتيب والحروف: {here(js, 'var ORDER').text()} و {here(js, 'var SHORT').text()}؛ الشكل: {here(css, '.ehimaya-lang__circle').text()}",
        here(js, "var ORDER").url(sha),
        f"اللغات المتاحة: supportedLocales، والافتراضية defaultLocale = ar ({here(public, 'defaultLocale').text()})",
    )
    row(
        "دائرة تبديل اللون (أزرق ملكي ↔ أحمر ملكي)",
        "زر",
        ["اللون الأحمر الملكي / اللون الأزرق الملكي", "Rouge royal / Bleu royal", "Royal red / Royal blue"],
        here(js, "function themeButton()"),
        f"النصوص: {here(js, 'var THEME_LABELS').text()}؛ الشكل: {here(css, '.ehimaya-theme').text()}؛ ألوان الأحمر: {here(css, 'html.ehimaya-red').text()}",
        here(js, "var THEME_LABELS").url(sha),
        "يُحفظ الاختيار في المتصفح فقط (localStorage: ehimaya-login-colour)، لا في قاعدة البيانات",
    )
    row(
        "الشعار (الدرع) بجانب اسم المنظومة",
        "أيقونة",
        ["", "", ""],
        here(css, "#kc-header-wrapper::before"),
        here(css, "#kc-header-wrapper::before").text(),
        here(css, "#kc-header-wrapper::before").url(sha),
        "الصورة في resources/img",
    )
    row(
        "الخلفية الليلية والفقاعات الزجاجية",
        "شكل",
        ["", "", ""],
        here(css, "bubbles.svg"),
        "تُولَّد الصورتان من scripts/login_bubbles.py (bubbles.svg للأزرق و bubbles-red.svg للأحمر)",
        Ref("scripts/login_bubbles.py", 1).url(sha),
        "لا شيء",
    )
    row(
        "الإطار الذهبي حول الصفحة",
        "شكل",
        ["", "", ""],
        here(css, "body::before"),
        f"على الحاسوب: {here(css, 'body::before').text()}؛ على الهاتف: {here(css, '.pf-v5-c-login::after').text()}",
        here(css, "body::before").url(sha),
        "لا شيء",
    )
    row(
        "الخط IBM Plex Sans Arabic",
        "شكل",
        ["", "", ""],
        here(css, "@font-face"),
        here(css, "--pf-v5-global--FontFamily--text").text(),
        here(css, "--pf-v5-global--FontFamily--text").url(sha),
        "ملفات الخط في resources/fonts",
    )

    headers = [
        "#",
        "العنصر",
        "النوع",
        "النص بالعربية",
        "النص بالفرنسية",
        "النص بالإنجليزية",
        "موضع الظهور في البرنامج (ملف:سطر)",
        "يُغيَّر من (ملف:سطر)",
        "قاعدة البيانات والإعدادات المرتبطة",
        "ملاحظة",
    ]
    ws = sheet(wb, "صفحة الدخول", headers, [5, 34, 12, 34, 34, 34, 40, 46, 60, 40])
    for n, (element, kind, ar, fr, en, shown, change_text, change_url, data, note) in enumerate(rows, 1):
        add(
            ws,
            [n, element, kind, ar, fr, en, shown.text(), change_text, data, note],
            {7: shown.url(sha), 8: change_url},
        )
    finish(ws)
    return len(rows)


# ------------------------------------------------------------------------------------------------ icons


def icon_sheet(wb: Workbook, sha: str, surfaces: list[tuple[str, Path, Path | None, object]]) -> int:
    ws = sheet(
        wb,
        "الأيقونات",
        [
            "#",
            "الواجهة",
            "اسم الأيقونة",
            "مصدرها (ملف:سطر)",
            "موضع الاستعمال (ملف:سطر)",
            "الشاشة",
            "عدد مرات الاستعمال",
        ],
        [5, 16, 22, 36, 40, 34, 12],
    )
    n = 0
    for label, src, icon_file, screen_of in surfaces:
        defs: dict[str, int] = {}
        if icon_file and icon_file.exists():
            for i, line in enumerate(read(icon_file), 1):
                m = re.match(r"^\s{2}(\w+):\s*$|^\s{2}(\w+):\s*\"M", line)
                if m:
                    defs[m.group(1) or m.group(2)] = i
        uses: list[tuple[str, Path, int]] = []
        exts = (".dart",) if icon_file is None else (".tsx", ".ts")
        for path in source_files(src, exts):
            if icon_file and path.resolve() == icon_file.resolve():
                continue
            for i, line in enumerate(read(path), 1):
                if icon_file is None:
                    for m in re.finditer(r"\bIcons\.(\w+)", line):
                        uses.append((m.group(1), path, i))
                else:
                    for m in re.finditer(r'\b(?:name|icon)[=:]\s*\{?"(\w+)"', line):
                        if m.group(1) in defs:
                            uses.append((m.group(1), path, i))
        counts = Counter(u[0] for u in uses)
        for name, path, line in sorted(uses, key=lambda u: (u[0], rel(u[1]), u[2])):
            n += 1
            origin = Ref(rel(icon_file), defs.get(name, 0)) if icon_file else None
            where = Ref(rel(path), line)
            add(
                ws,
                [
                    n,
                    label,
                    name,
                    origin.text() if origin else "Material Icons (مكتبة Flutter)",
                    where.text(),
                    screen_of(path),
                    counts[name],
                ],
                ({4: origin.url(sha)} if origin else {}) | {5: where.url(sha)},
            )
    finish(ws)
    return n


# ------------------------------------------------------------------------------------- colours and shapes

HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def hex6(value: str) -> str | None:
    m = HEX.search(value)
    if not m:
        return None
    h = m.group(0)[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return h[:6].upper()


def css_vars(path: Path) -> list[tuple[str, str, str, int]]:
    """(selector, --name, value, line) for every custom property defined in a stylesheet."""
    out = []
    selector = ""
    for i, line in enumerate(read(path), 1):
        s = line.strip()
        if s.endswith("{") and not s.startswith("@"):
            selector = s[:-1].strip()
        elif s.startswith("@media") or s.startswith("@supports"):
            selector = s[:-1].strip()
        m = re.match(r"^\s*(--[\w-]+)\s*:\s*(.+?);?\s*$", line)
        if m:
            out.append((selector, m.group(1), m.group(2).rstrip(";"), i))
    return out


def colour_and_shape_sheets(wb: Workbook, sha: str, web: list[tuple[str, Path, Path]], mobile: Path) -> tuple[int, int]:
    colours = sheet(
        wb,
        "الألوان",
        [
            "#",
            "الواجهة",
            "الاسم البرمجي",
            "القيمة",
            "العيّنة",
            "النطاق (الوضع)",
            "يُعرَّف ويُغيَّر في (ملف:سطر)",
            "عدد مرات الاستعمال",
            "دوره",
        ],
        [5, 14, 34, 34, 10, 34, 40, 12, 30],
    )
    colours._swatch_col = 5
    shapes = sheet(
        wb,
        "الأشكال",
        [
            "#",
            "الواجهة",
            "النوع",
            "الاسم أو القيمة",
            "يُعرَّف ويُغيَّر في (ملف:سطر)",
            "عدد مرات الاستعمال",
            "أول موضع استعمال",
        ],
        [5, 14, 18, 44, 40, 12, 40],
    )
    nc = ns = 0

    def role(name: str, selector: str) -> str:
        parts = []
        if "dark" in selector:
            parts.append("الوضع الليلي")
        if "red" in selector:
            parts.append("اللون الأحمر الملكي")
        for word, label in (
            ("bg", "خلفية"),
            ("surface", "سطح"),
            ("card", "بطاقة"),
            ("ink", "نص"),
            ("text", "نص"),
            ("muted", "نص ثانوي"),
            ("line", "خط فاصل"),
            ("border", "حدود"),
            ("primary", "اللون الأساسي"),
            ("navy", "الأزرق"),
            ("red", "الأحمر"),
            ("danger", "خطر"),
            ("success", "نجاح"),
            ("warn", "تنبيه"),
            ("gold", "ذهبي"),
            ("focus", "إطار التركيز"),
            ("sim", "شارة المحاكاة"),
            ("cat", "لون الفئة"),
        ):
            if word in name:
                parts.append(label)
                break
        return "، ".join(parts)

    for label, css, src in web:
        defs = css_vars(css)
        texts = [p.read_text(encoding="utf-8") for p in source_files(src, (".tsx", ".ts", ".css"))]
        blob = "\n".join(texts)
        values = {name: value for _, name, value, _ in defs}

        def resolve(value: str, depth: int = 0) -> str | None:
            h = hex6(value)
            if h or depth > 4:
                return h
            m = re.search(r"var\((--[\w-]+)", value)
            return resolve(values.get(m.group(1), ""), depth + 1) if m else None

        for selector, name, value, line in defs:
            uses = len(re.findall(re.escape(f"var({name}") + r"[,)]", blob))
            ref = Ref(rel(css), line)
            is_shape = any(
                w in name
                for w in (
                    "radius",
                    "shadow",
                    "space",
                    "gap",
                    "size",
                    "width",
                    "height",
                    "font",
                    "weight",
                    "z-",
                    "duration",
                    "ease",
                )
            )
            swatch = resolve(value)
            if is_shape or not (swatch or "gradient" in value or "rgb" in value or "hsl" in value):
                kind = next(
                    (
                        lab
                        for w, lab in (
                            ("radius", "استدارة الزوايا"),
                            ("shadow", "ظل"),
                            ("font", "خط"),
                            ("space", "مسافة"),
                            ("gap", "مسافة"),
                            ("size", "مقاس"),
                            ("width", "مقاس"),
                            ("height", "مقاس"),
                        )
                        if w in name
                    ),
                    "متغيّر تنسيق",
                )
                ns += 1
                add(
                    shapes,
                    [
                        ns,
                        label,
                        kind,
                        f"{name}: {value}" + (f"   [{selector}]" if selector and selector != ":root" else ""),
                        ref.text(),
                        uses,
                        "",
                    ],
                    {5: ref.url(sha)},
                )
                continue
            nc += 1
            add(
                colours,
                [nc, label, name, value, "", selector or ":root", ref.text(), uses, role(name, selector)],
                {7: ref.url(sha)},
                fill=swatch,
            )

        # Colours written directly (not through a variable), grouped by value.
        literal: dict[str, list[tuple[Path, int]]] = defaultdict(list)
        for path in [css, *source_files(src, (".tsx", ".ts"))]:
            for i, line in enumerate(read(path), 1):
                if re.match(r"^\s*--[\w-]+\s*:", line) or line.strip().startswith(("//", "*", "/*")):
                    continue
                for m in HEX.finditer(line):
                    if re.search(r"[\w-]#", line[max(0, m.start() - 1) : m.start() + 1]):
                        continue
                    literal[hex6(m.group(0))].append((path, i))
        for h, places in sorted(literal.items(), key=lambda kv: -len(kv[1])):
            first = Ref(rel(places[0][0]), places[0][1])
            nc += 1
            add(
                colours,
                [
                    nc,
                    label,
                    "لون مكتوب مباشرة",
                    f"#{h}",
                    "",
                    "—",
                    first.text(),
                    len(places),
                    "مكتوب في الملف دون متغيّر",
                ],
                {7: first.url(sha)},
                fill=h,
            )

        for prop, kind in (
            ("border-radius", "استدارة الزوايا"),
            ("box-shadow", "ظل"),
            ("border", "حدود"),
            ("font-size", "حجم الخط"),
        ):
            found: dict[str, list[int]] = defaultdict(list)
            for i, line in enumerate(read(css), 1):
                m = re.match(rf"^\s*{prop}\s*:\s*(.+?);?\s*$", line)
                if m:
                    found[m.group(1)].append(i)
            for value, lines in sorted(found.items(), key=lambda kv: -len(kv[1])):
                ref = Ref(rel(css), lines[0])
                ns += 1
                add(
                    shapes,
                    [ns, label, kind, f"{prop}: {value}", ref.text(), len(lines), ref.text()],
                    {5: ref.url(sha), 7: ref.url(sha)},
                )

    # Mobile: named colours in the design tokens, then colours and radii written elsewhere.
    tokens = mobile / "core/ui/tokens.dart"
    dart_files = source_files(mobile, (".dart",))
    blob = "\n".join(p.read_text(encoding="utf-8") for p in dart_files)
    cls = ""
    for i, line in enumerate(read(tokens), 1):
        cm = re.match(r"^\s*(?:abstract\s+)?(?:final\s+)?class\s+(\w+)", line)
        if cm:
            cls = cm.group(1)
        sm = re.search(r"\bstatic const (\w+) = (?:Neutrals\._\(|.*)$", line)
        if sm and "Neutrals._(" in line:
            cls = f"Neutrals.{sm.group(1)}"
        m = re.search(r"(?:static const\s+)?(\w+)\s*[:=]\s*Color\(0x([0-9A-Fa-f]{8})\)", line)
        if m:
            name = f"{cls}.{m.group(1)}"
            uses = len(re.findall(rf"\b{re.escape(cls.split('.')[0])}\.{m.group(1)}\b|\.{m.group(1)}\b", blob))
            ref = Ref(rel(tokens), i)
            nc += 1
            add(
                colours,
                [
                    nc,
                    "تطبيقا الهاتف",
                    name,
                    f"#{m.group(2)[2:].upper()}",
                    "",
                    cls,
                    ref.text(),
                    uses,
                    role(m.group(1).lower(), cls.lower()),
                ],
                {7: ref.url(sha)},
                fill=m.group(2)[2:].upper(),
            )
    literal = defaultdict(list)
    radii = defaultdict(list)
    for path in dart_files:
        if path.resolve() == tokens.resolve():
            continue
        for i, line in enumerate(read(path), 1):
            for m in re.finditer(r"Color\(0x([0-9A-Fa-f]{8})\)", line):
                literal[m.group(1)[2:].upper()].append((path, i))
            for m in re.finditer(
                r"(BorderRadius\.circular\([\d.]+\)|Radius\.circular\([\d.]+\)|StadiumBorder\(\)|CircleBorder\(\))",
                line,
            ):
                radii[m.group(1)].append((path, i))
    for h, places in sorted(literal.items(), key=lambda kv: -len(kv[1])):
        first = Ref(rel(places[0][0]), places[0][1])
        nc += 1
        add(
            colours,
            [
                nc,
                "تطبيقا الهاتف",
                "لون مكتوب مباشرة",
                f"#{h}",
                "",
                "—",
                first.text(),
                len(places),
                "مكتوب في الملف دون رمز تصميم",
            ],
            {7: first.url(sha)},
            fill=h,
        )
    for value, places in sorted(radii.items(), key=lambda kv: -len(kv[1])):
        first = Ref(rel(places[0][0]), places[0][1])
        ns += 1
        add(
            shapes,
            [ns, "تطبيقا الهاتف", "استدارة الزوايا", value, first.text(), len(places), first.text()],
            {5: first.url(sha), 7: first.url(sha)},
        )
    finish(colours)
    finish(shapes)
    return nc, ns


# ---------------------------------------------------------------------------------- screens → API → tables


def data_sheet(wb: Workbook, sha: str, entries: list[tuple[str, str, Path, str, str, int]], backend: Backend) -> int:
    ws = sheet(
        wb,
        "الشاشات والبيانات",
        [
            "#",
            "الواجهة",
            "الشاشة",
            "ملف الاستدعاء (ملف:سطر)",
            "الطلب",
            "المسار في الخادم",
            "دالّة الخادم (ملف:سطر)",
            "الجداول المستعملة (المخطط.الجدول)",
            "حقول الطلب",
        ],
        [5, 14, 30, 40, 9, 44, 46, 56, 40],
    )
    seen = set()
    n = 0
    for surface, screen, path, verb, url, line in sorted(entries, key=lambda e: (e[0], e[1], e[4], e[3])):
        sig = (surface, screen, verb, url)
        if sig in seen:
            continue
        seen.add(sig)
        route = backend.match(verb, url)
        call = Ref(rel(path), line)
        if route:
            handler = Ref(route["file"], route["line"])
            tables = route["tables"] or route["package_tables"]
            note = "" if route["tables"] else " (على مستوى الوحدة)"
            n += 1
            add(
                ws,
                [
                    n,
                    surface,
                    screen,
                    call.text(),
                    verb,
                    route["path"],
                    f"{route['function']} · {handler.text()}",
                    "، ".join(tables) + note,
                    "، ".join(route["body"]),
                ],
                {4: call.url(sha), 7: handler.url(sha)},
            )
        else:
            n += 1
            add(
                ws,
                [n, surface, screen, call.text(), verb, url, "لم يُعثر على المسار في الخادم", "", ""],
                {4: call.url(sha)},
            )
    finish(ws)
    return n


# --------------------------------------------------------------------------------------------------- main


def readme(wb: Workbook, sha: str, stats: dict) -> None:
    ws = wb.active
    ws.title = "اقرأني"
    ws.sheet_view.rightToLeft = True
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 110
    title = ws.cell(row=1, column=1, value="دليل عناصر واجهات ء-حماية")
    title.font = Font(name=FONT, bold=True, size=18, color=NAVY)
    ws.cell(
        row=2, column=1, value=f"مولَّد آليا من الشيفرة، الإصدار {sha[:8]}، بالسكريبت scripts/ui_reference/build.py"
    ).font = Font(name=FONT, size=10, color="5B6478")
    lines = [
        (
            "ما هذا الدليل",
            "كل نص وزر وحقل وأيقونة ولون وشكل في الواجهات الخمس، مع مكان ظهوره، والملف والسطر الذي يرسمه، والملف والسطر الذي يُغيَّر منه، والبيانات التي يرتبط بها.",
        ),
        (
            "كيف أغيّر نصا",
            "ابحث عنه في ورقة واجهته (التصفية في رأس كل عمود)، ثم افتح الرابط في عمود «يُغيَّر النص العربي في»: يفتح الملف على السطر المطلوب في GitHub. غيّر الفرنسية والإنجليزية معه.",
        ),
        (
            "كيف أغيّر لونا أو شكلا",
            "ورقتا «الألوان» و«الأشكال»: كل متغيّر تصميم مع عيّنة لونه وعدد مرات استعماله. تغيير المتغيّر يغيّر كل مكان يستعمله. الألوان المكتوبة مباشرة مذكورة وحدها لأن تغييرها يكون في كل موضع.",
        ),
        (
            "الروابط",
            "روابط المستودع مثبّتة على هذا الإصدار، فتبقى صحيحة حتى بعد تغيّر الأسطر. بعد التعديلات أعد توليد الدليل ليتبع الأسطر الجديدة.",
        ),
        (
            "صفحة الدخول",
            "من Keycloak: بعض العناصر في قالب Keycloak الأساسي لا في مستودعنا (مثل «نسيت كلمة المرور؟»). يُغيَّر نصها بإضافة مفتاحها إلى ملف رسائل السمة ehimaya، والورقة تذكر ذلك. كلمة العبور في قاعدة Keycloak وحدها.",
        ),
        (
            "المطابقة مع قاعدة البيانات",
            "آلية: عمود «البيانات المرتبطة» يربط الحقل بعمود في جدول يحمل الاسم نفسه ويستعمله طلب الشاشة. ورقة «الشاشات والبيانات» تربط كل شاشة بطلباتها ودوالّ الخادم والجداول. «على مستوى الوحدة» تعني أن الجداول مأخوذة من وحدة الخادم كلها.",
        ),
        (
            "المفاتيح غير المستعملة",
            "في آخر كل ورقة: مفاتيح لا يظهر اسمها حرفيا في الشيفرة. أغلبها يُبنى اسمه أثناء التشغيل، فلا تُحذف قبل التحقق.",
        ),
        (
            "إعادة التوليد",
            "cd services/api && .venv/bin/python ../../scripts/ui_reference/backend_dump.py > /tmp/backend.json ثم python3 scripts/ui_reference/build.py --backend /tmp/backend.json --out ehimaya-ui-reference.xlsx",
        ),
    ]
    r = 4
    for k, v in lines:
        ws.cell(row=r, column=1, value=k).font = Font(name=FONT, bold=True, size=11, color=NAVY)
        c = ws.cell(row=r, column=2, value=v)
        c.font = Font(name=FONT, size=11)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 46
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="المحتوى").font = Font(name=FONT, bold=True, size=13, color=GOLD)
    r += 1
    for k, v in stats.items():
        ws.cell(row=r, column=1, value=k).font = Font(name=FONT, bold=True, size=11)
        ws.cell(row=r, column=2, value=v).font = Font(name=FONT, size=11)
        r += 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--keycloak-themes", type=Path)
    ap.add_argument("--sha")
    args = ap.parse_args()
    sha = args.sha or subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    backend = Backend.load(args.backend)

    wb = Workbook()
    styles(wb)
    stats: dict[str, str] = {}
    stats["صفحة الدخول"] = f"{keycloak_sheet(wb, sha, args.keycloak_themes)} عنصرا"
    entries: list[tuple[str, str, Path, str, str, int]] = []
    icon_surfaces = []
    web_css = []

    for app, label, sheet_title in (("dashboard", "لوحة التحكم", "لوحة التحكم"), ("portal", "البوابة", "البوابة")):
        src = REPO / "apps" / app / "src"
        files = {lang: src / "i18n" / f"{lang}.json" for lang in LANGS}
        strings = {lang: json_strings(p) for lang, p in files.items()}
        for lang in LANGS:
            check_flatten(files[lang], strings[lang])
        code = source_files(src, (".tsx", ".ts"))
        code = [p for p in code if "/i18n/" not in p.as_posix()]
        page_routes = web_routes(src / "App.tsx")
        importers = import_graph(code)
        frame = "إطار اللوحة (يظهر في كل الصفحات)" if app == "dashboard" else "إطار البوابة (يظهر في كل الصفحات)"
        cache: dict[Path, str] = {}

        def screen_of(path: Path, page_routes=page_routes, importers=importers, frame=frame, cache=cache) -> str:
            path = path.resolve()
            if path not in cache:
                cache[path] = screens_for(path, page_routes, importers, frame)
            return cache[path]

        methods = web_api_methods(src / "lib")
        calls: dict[Path, list[tuple[str, str, int]]] = {}

        def endpoints_of(path: Path, methods=methods, calls=calls) -> list[tuple[str, str, int]]:
            path = path.resolve()
            if path not in calls:
                calls[path] = web_calls(path, methods)
            return calls[path]

        usages = web_usages(code, set(strings["ar"]))
        s = text_sheet(wb, sheet_title, sha, strings, files, usages, screen_of, endpoints_of, backend)
        stats[label] = f"{s['rows']} صفا · {s['keys']} نصا مترجما · {s['unused']} مفتاحا لا يظهر حرفيا"
        for path in code:
            for verb, url, line in endpoints_of(path):
                entries.append((label, screen_of(path), path, verb, url, line))
        icon_surfaces.append((label, src, src / "components" / "Icon.tsx", screen_of))
        web_css.append((label, src / "styles" / "global.css", src))

    mobile = REPO / "apps" / "mobile" / "lib"
    files = {lang: mobile / "l10n" / f"app_{lang}.arb" for lang in LANGS}
    strings = {lang: arb_strings(p) for lang, p in files.items()}
    dart = source_files(mobile, (".dart",))
    by_file, staff_methods = dart_api(mobile)
    folder_endpoints: dict[Path, list[tuple[str, str, int]]] = defaultdict(list)
    for path, eps in by_file.items():
        folder_endpoints[path.parent].extend((v, u, ln) for v, u, ln in eps)

    def dart_endpoints(path: Path) -> list[tuple[str, str, int]]:
        path = path.resolve()
        out = list(by_file.get(path, []))
        if "/staff/" in path.as_posix():
            for i, line in enumerate(read(path), 1):
                for m in re.finditer(r"\b\w*[aA]pi\w*\.(\w+)\(", line):
                    if m.group(1) in staff_methods:
                        v, u = staff_methods[m.group(1)]
                        out.append((v, u, i))
        else:
            out.extend(folder_endpoints.get(path.parent, []))
        return out

    def is_staff(p: Path) -> bool:
        return "/staff/" in p.as_posix() or p.name == "main_staff.dart"

    def mscreen(p: Path) -> str:
        return dart_screen(p.resolve(), mobile.resolve())

    for title, pick in (("تطبيق المواطن", lambda p: not is_staff(p)), ("تطبيق الأعوان", is_staff)):
        chosen = [p for p in dart if pick(p)]
        usages = dart_usages(chosen, set(strings["ar"]))
        s = text_sheet(wb, title, sha, strings, files, usages, mscreen, dart_endpoints, backend)
        stats[title] = f"{s['rows']} صفا · {s['used']} نصا مستعملا في هذا التطبيق"
        for path in chosen:
            for verb, url, line in by_file.get(path.resolve(), []) + (
                [(v, u, ln) for v, u, ln in dart_endpoints(path) if (v, u, ln) not in by_file.get(path.resolve(), [])]
                if is_staff(path)
                else []
            ):
                entries.append((title, mscreen(path), path, verb, url, line))
    icon_surfaces.append(("تطبيقا الهاتف", mobile, None, mscreen))

    stats["الأيقونات"] = f"{icon_sheet(wb, sha, icon_surfaces)} استعمالا"
    kc_css = REPO / "infra/keycloak/themes/ehimaya/login/resources/css/ehimaya.css"
    web_css.append(("صفحة الدخول", kc_css, kc_css.parent.parent))
    nc, ns = colour_and_shape_sheets(wb, sha, web_css, mobile)
    stats["الألوان"] = f"{nc} لونا"
    stats["الأشكال"] = f"{ns} قيمة"
    stats["الشاشات والبيانات"] = f"{data_sheet(wb, sha, entries, backend)} ربطا بين شاشة وطلب ودالّة وجداول"
    readme(wb, sha, stats)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(args.out)
    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
