/**
 * Safe Markdown rendering of the national memory (phase 8 §2/§4).
 *
 * Two layers, so one mistake cannot open an XSS hole:
 *  1. markdown-it with `html: false`: raw HTML in the source is escaped, never passed through; images are disabled
 *     (they would load third-party origins the CSP refuses anyway); links are validated by markdown-it
 *     (no javascript:, vbscript:, file: or data: URLs).
 *  2. DOMPurify on the produced HTML with a short allowlist of tags and attributes, http(s)/mailto links only,
 *     and every link opened in a new tab without referrer or opener.
 */
import DOMPurify from "dompurify";
import MarkdownIt from "markdown-it";

const md = new MarkdownIt({ html: false, linkify: false, typographer: false, breaks: true });
md.disable(["image"]);

const ALLOWED_TAGS = [
  "p",
  "br",
  "strong",
  "em",
  "s",
  "code",
  "pre",
  "blockquote",
  "ul",
  "ol",
  "li",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "hr",
  "a",
  "table",
  "thead",
  "tbody",
  "tr",
  "th",
  "td",
];
const ALLOWED_ATTR = ["href", "title", "start"];
const SAFE_URL = /^(?:https?:|mailto:)/i;

const purify = DOMPurify();
purify.addHook("afterSanitizeAttributes", (node) => {
  if (node.nodeName !== "A") return;
  const href = node.getAttribute("href") ?? "";
  if (!SAFE_URL.test(href)) {
    node.removeAttribute("href");
    return;
  }
  node.setAttribute("target", "_blank");
  node.setAttribute("rel", "noopener noreferrer nofollow");
});

/** Markdown → sanitized HTML string (only the allowlisted tags remain). */
export function renderMarkdown(source: string): string {
  const html = md.render(source);
  return purify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR: [...ALLOWED_ATTR, "target", "rel"],
    ALLOWED_URI_REGEXP: SAFE_URL,
    ALLOW_DATA_ATTR: false,
  });
}

/**
 * Search excerpts carry `<mark>` only (everything else escaped by the API). They are split into text and marked
 * parts and rendered as React text, never as HTML, so a stray tag can only ever show as text.
 */
export function excerptParts(excerpt: string): { text: string; marked: boolean }[] {
  const parts: { text: string; marked: boolean }[] = [];
  const re = /<mark>([\s\S]*?)<\/mark>/g;
  let last = 0;
  for (let m = re.exec(excerpt); m; m = re.exec(excerpt)) {
    if (m.index > last) parts.push({ text: decodeEntities(excerpt.slice(last, m.index)), marked: false });
    parts.push({ text: decodeEntities(m[1] ?? ""), marked: true });
    last = m.index + m[0].length;
  }
  if (last < excerpt.length) parts.push({ text: decodeEntities(excerpt.slice(last)), marked: false });
  return parts.filter((p) => p.text !== "");
}

const ENTITIES: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'", "#x27": "'" };

/** The API escapes the excerpt as HTML: undo the five entities it produces (the result is rendered as text). */
function decodeEntities(s: string): string {
  return s.replace(/&(amp|lt|gt|quot|#39|#x27);/g, (_, e: string) => ENTITIES[e] ?? "");
}
