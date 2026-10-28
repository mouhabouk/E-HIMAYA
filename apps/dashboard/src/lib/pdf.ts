/**
 * PDF.js entry point of the plan viewer (phase PL1). Loaded on demand: only the plans viewer imports it. Like MapLibre
 * (src/lib/maplibre.ts), its worker is a same-origin chunk emitted by Vite's `?worker&url`, so the CSP keeps
 * `worker-src 'self'`. The file comes from the API as bytes; nothing is fetched by PDF.js itself. The legacy build:
 * the modern one needs JavaScript newer than the browsers of some rooms (Map.getOrInsertComputed).
 */
import * as pdfjs from "pdfjs-dist/legacy/build/pdf.mjs";
import workerUrl from "pdfjs-dist/legacy/build/pdf.worker.min.mjs?worker&url";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

export type PdfDocument = pdfjs.PDFDocumentProxy;
export type PdfPage = pdfjs.PDFPageProxy;

export interface OutlineEntry {
  title: string;
  page: number;
}

export function openPdf(data: ArrayBuffer): Promise<PdfDocument> {
  // A copy: PDF.js transfers the buffer to its worker, and the query cache keeps the original.
  return pdfjs.getDocument({ data: new Uint8Array(data.slice(0)), useSystemFonts: true, enableXfa: false }).promise;
}

/** An entry of the table of contents as PDF.js gives it (only the fields read here). */
interface OutlineNode {
  title: string;
  dest: string | unknown[] | null;
  items: OutlineNode[];
}

type PageRef = Parameters<PdfDocument["getPageIndex"]>[0];

/** The first two levels of the document's table of contents, with their page numbers (1-based). */
export async function outline(doc: PdfDocument): Promise<OutlineEntry[]> {
  const items = ((await doc.getOutline()) as OutlineNode[] | null) ?? [];
  const out: OutlineEntry[] = [];
  const add = async (item: OutlineNode, depth: number) => {
    try {
      const dest = typeof item.dest === "string" ? ((await doc.getDestination(item.dest)) as unknown[] | null) : item.dest;
      const ref = dest?.[0];
      if (ref && typeof ref === "object") out.push({ title: (depth ? "— " : "") + item.title, page: (await doc.getPageIndex(ref as PageRef)) + 1 });
    } catch {
      // An entry without a usable destination is left out.
    }
    if (depth === 0) for (const child of item.items) await add(child, 1);
  };
  for (const item of items) await add(item, 0);
  return out;
}

/** Pages (1-based) whose text contains every word of the query, folded like the register's search. */
export async function findPages(doc: PdfDocument, query: string): Promise<number[]> {
  const words = fold(query).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const hits: number[] = [];
  for (let n = 1; n <= doc.numPages; n++) {
    const page = await doc.getPage(n);
    const content = await page.getTextContent();
    const text = fold(content.items.map((i) => ("str" in i ? i.str : "")).join(" "));
    if (words.every((w) => text.includes(w))) hits.push(n);
  }
  return hits;
}

/** Lower case without Arabic diacritics and tatweel, alef forms as one (the PDF text often differs in these). */
export function fold(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFKC")
    .replace(/[ً-ٰٟـ]/g, "")
    .replace(/[آأإ]/g, "ا")
    .replace(/ى/g, "ي")
    .replace(/ة/g, "ه");
}
