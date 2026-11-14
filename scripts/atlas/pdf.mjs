// Prints the atlas book (print.html from scripts/atlas/pdf.py) to PDF with Playwright's Chromium.
//   node scripts/atlas/pdf.mjs <print.html> <out.pdf>
//   node scripts/atlas/pdf.mjs <print.html> --measure   prints the ids of the cards whose text overflows, as JSON
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const { chromium } = createRequire(import.meta.url)('playwright');
const [src, out] = process.argv.slice(2);
const measure = out === '--measure';
const browser = await chromium.launch(process.env.ATLAS_CHROMIUM ? { executablePath: process.env.ATLAS_CHROMIUM } : {});
const page = await browser.newPage({ viewport: { width: 1123, height: 794 } });
await page.goto(pathToFileURL(resolve(src)).href, { waitUntil: 'load', timeout: 600000 });
const report = await page.evaluate(async (cut) => { await document.fonts.ready; return window.fit(cut); }, !measure);
if (measure) {
  console.log(JSON.stringify(report));
} else {
  if (report.length) console.log(`pdf: ${report.length} page(s) shortened to fit: ${report.join(', ')}`);
  await page.pdf({ path: out, width: '297mm', height: '210mm', printBackground: true, preferCSSPageSize: true, timeout: 0 });
  console.log(`pdf: ${out}`);
}
await browser.close();
