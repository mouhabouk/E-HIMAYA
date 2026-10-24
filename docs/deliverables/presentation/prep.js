const sharp = require('sharp'), fs = require('fs'), path = require('path');
const R = process.env.REPO || '../../..';
fs.mkdirSync('img', { recursive: true });
async function icon(n, color, file) {
  let s = fs.readFileSync(`icons/${n}.svg`, 'utf8').replace('<svg', `<svg fill="#${color}"`);
  await sharp(Buffer.from(s)).resize(256, 256).png().toFile(file);
}
async function rounded(src, crop, out, r) {
  let img = sharp(src); if (crop) img = img.extract(crop);
  const buf = await img.png().toBuffer(); const { width, height } = await sharp(buf).metadata();
  const mask = Buffer.from(`<svg width="${width}" height="${height}"><rect width="${width}" height="${height}" rx="${r}" ry="${r}"/></svg>`);
  await sharp(buf).composite([{ input: mask, blend: 'dest-in' }]).png().toFile(out);
}
(async () => {
  for (const f of fs.readdirSync('icons')) { const n = path.basename(f, '.svg'); await icon(n, 'FFFFFF', `img/w-${n}.png`); }
  await rounded(`${R}/docs/phase-ui/mobile-home-light.jpg`, null, 'img/phone.png', 40);
  await rounded(`${R}/docs/phase-ui/dash-ar-light.jpg`, { left: 0, top: 530, width: 1280, height: 370 }, 'img/dash-kpi.png', 18);
  await rounded(`${R}/docs/phase-ui/dash-ar-light.jpg`, { left: 0, top: 0, width: 1280, height: 230 }, 'img/dash-nav.png', 18);
  // logo on white disc for dark slides
  const logo = await sharp(`${R}/apps/mobile/assets/brand/logo.png`).resize(360, 360).png().toBuffer();
  const disc = Buffer.from('<svg width="480" height="480"><circle cx="240" cy="240" r="240" fill="#FFFFFF"/></svg>');
  await sharp(disc).composite([{ input: logo, left: 60, top: 60 }]).png().toFile('img/logo-disc.png');
  fs.copyFileSync(`${R}/apps/mobile/assets/brand/logo.png`, 'img/logo.png');
  console.log('ok');
})();
