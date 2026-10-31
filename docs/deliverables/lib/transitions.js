// Slide transitions and timings written the way PowerPoint writes them, so they show in the Transitions tab and can be
// changed there (effect, duration, "After" time). Morph falls back to a fade in viewers without it (PowerPoint before
// 2019, LibreOffice). Every slide advances on a click or after its time; "Use Timings" is ticked, untick it in the Slide
// Show tab to keep the clicks only.
// Objects named "anim …" get an entrance animation (fade, 0.5 s, one after the other from the end of the transition),
// so the Animations tab and its timing (start, duration, delay) can be changed object by object.
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

async function applyTransitions(file, plan, { useTimings = true } = {}) {
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
    x = x.replace(/<p:timing>[\s\S]*?<\/p:timing>/, '');
    x = x.replace(at, at + transitionXml(plan[k]) + timingXml(x));
    zip.file(f, x);
  }
  // "Use Timings" as asked (Slide Show tab), so the stored times run the show; the presenter can still click.
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

// Entrance fades for the objects named "anim …", in document order: the first starts after the transition, the others
// with it, staggered by stepMs.
function timingXml(x, { durMs = 500, stepMs = 120 } = {}) {
  const shapes = [...x.matchAll(/<p:(sp|pic)>\s*<p:nv(?:Sp|Pic)Pr>\s*<p:cNvPr id="(\d+)" name="anim [^"]*"/g)].map(m => ({ kind: m[1], id: m[2] }));
  if (!shapes.length) return '';
  let n = 4;
  const effects = shapes.map(({ id }, k) => {
    const a = ++n, b = ++n, c = ++n;
    return `<p:par><p:cTn id="${a}" presetID="10" presetClass="entr" presetSubtype="0" fill="hold" grpId="0" nodeType="${k ? 'withEffect' : 'afterEffect'}">` +
      `<p:stCondLst><p:cond delay="${k * stepMs}"/></p:stCondLst><p:childTnLst>` +
      `<p:set><p:cBhvr><p:cTn id="${b}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn><p:tgtEl><p:spTgt spid="${id}"/></p:tgtEl>` +
      `<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>` +
      `<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="${c}" dur="${durMs}"/><p:tgtEl><p:spTgt spid="${id}"/></p:tgtEl></p:cBhvr></p:animEffect>` +
      `</p:childTnLst></p:cTn></p:par>`;
  }).join('');
  const bld = shapes.filter(s => s.kind === 'sp').map(s => `<p:bldP spid="${s.id}" grpId="0" animBg="1"/>`).join('');
  return '<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>' +
    '<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>' +
    '<p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/><p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond></p:stCondLst><p:childTnLst>' +
    `<p:par><p:cTn id="4" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>${effects}</p:childTnLst></p:cTn></p:par>` +
    '</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn>' +
    '<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>' +
    '<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq>' +
    `</p:childTnLst></p:cTn></p:par></p:tnLst><p:bldLst>${bld}</p:bldLst></p:timing>`;
}

const mmss = s => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;
module.exports = { applyTransitions, mmss };
