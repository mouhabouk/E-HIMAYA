// Slide transitions and timings written the way PowerPoint writes them, so they show in the Transitions tab and can be
// changed there (effect, duration, "After" time). Morph falls back to a fade in viewers without it (PowerPoint before
// 2019, LibreOffice). The timings are stored on every slide but the show does not advance on its own until "Use Timings"
// is ticked in the Slide Show tab: the committee asks questions, the presenter keeps control.
//   await applyTransitions(file, [{ effect: 'fade'|'morph', durMs, afterSec }, ...])   one entry per slide, in order
const fs = require('fs');
const JSZip = require('jszip');

const NS = {
  mc: 'http://schemas.openxmlformats.org/markup-compatibility/2006',
  p14: 'http://schemas.microsoft.com/office/powerpoint/2010/main',
  p159: 'http://schemas.microsoft.com/office/powerpoint/2015/09/main',
};

function transitionXml({ effect = 'fade', durMs = 700, afterSec }) {
  const adv = afterSec ? ` advTm="${Math.round(afterSec * 1000)}"` : '';
  const fallback = `<p:transition spd="${durMs >= 1000 ? 'slow' : 'med'}"${adv}><p:fade/></p:transition>`;
  if (effect === 'morph') {
    return `<mc:AlternateContent xmlns:mc="${NS.mc}"><mc:Choice xmlns:p159="${NS.p159}" Requires="p159">` +
      `<p:transition spd="slow" p14:dur="${durMs}"${adv}><p159:morph option="byObject"/></p:transition></mc:Choice>` +
      `<mc:Fallback>${fallback}</mc:Fallback></mc:AlternateContent>`;
  }
  return `<mc:AlternateContent xmlns:mc="${NS.mc}"><mc:Choice xmlns:p14="${NS.p14}" Requires="p14">` +
    `<p:transition spd="${durMs >= 1000 ? 'slow' : 'med'}" p14:dur="${durMs}"${adv}><p:fade/></p:transition></mc:Choice>` +
    `<mc:Fallback>${fallback}</mc:Fallback></mc:AlternateContent>`;
}

async function applyTransitions(file, plan, { useTimings = false } = {}) {
  const zip = await JSZip.loadAsync(fs.readFileSync(file));
  // Slide order comes from presentation.xml, not from the file names.
  const pres = await zip.file('ppt/presentation.xml').async('string');
  const rels = await zip.file('ppt/_rels/presentation.xml.rels').async('string');
  const ids = [...pres.matchAll(/<p:sldId [^>]*r:id="(rId\d+)"/g)].map(m => m[1]);
  const files = ids.map(id => 'ppt/' + new RegExp(`Id="${id}"[^>]*Target="([^"]+)"`).exec(rels)[1]);
  if (files.length !== plan.length) throw new Error(`plan has ${plan.length} entries for ${files.length} slides`);
  for (const [k, f] of files.entries()) {
    let x = await zip.file(f).async('string');
    x = x.replace(/<mc:AlternateContent[^>]*>(?:(?!<\/mc:AlternateContent>)[\s\S])*?<p:transition[\s\S]*?<\/mc:AlternateContent>/g, '')
      .replace(/<p:transition[\s\S]*?(<\/p:transition>|\/>)/g, '');
    // PowerPoint declares p14 on the slide root; the Choice/Fallback pair is then read by every version.
    if (!x.includes('xmlns:p14=')) x = x.replace('<p:sld ', `<p:sld xmlns:p14="${NS.p14}" `);
    const at = x.includes('</p:clrMapOvr>') ? '</p:clrMapOvr>' : '</p:cSld>';
    if (!x.includes(at)) throw new Error('no anchor in ' + f);
    x = x.replace(at, at + transitionXml(plan[k]));
    zip.file(f, x);
  }
  // The show keeps the timings but waits for the presenter unless useTimings is set.
  let props = await zip.file('ppt/presProps.xml').async('string');
  props = props.replace(/<p:showPr[\s\S]*?(<\/p:showPr>|\/>)/, '');
  props = props.replace(/<p:presentationPr([^>]*?)\/>/, '<p:presentationPr$1></p:presentationPr>');
  props = props.replace(/(<p:presentationPr[^>]*>)/, `$1<p:showPr showNarration="1" useTimings="${useTimings ? 1 : 0}"><p:present/><p:sldAll/><p:penClr><a:prstClr val="red"/></p:penClr></p:showPr>`);
  if (!props.includes('xmlns:a=')) props = props.replace('<p:presentationPr ', '<p:presentationPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" ');
  zip.file('ppt/presProps.xml', props);
  fs.writeFileSync(file, await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' }));
  const total = plan.reduce((t, p) => t + (p.afterSec || 0), 0);
  return { slides: files.length, total };
}

const mmss = s => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;
module.exports = { applyTransitions, mmss };
