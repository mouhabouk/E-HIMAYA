// BPMN 2.0 files and pictures of the e-Himaya processes (review point 11, phase 4).
//   node build.js <out-dir>      writes <file>.bpmn (opens in Camunda Modeler, bpmn.io, Bizagi…) and <file>.png
// The pictures are drawn by bpmn-js (the bpmn.io viewer) in the pre-installed Chromium, so they use the standard notation.
const fs = require('fs');
const path = require('path');
const processes = require('./processes.js');

const COL = 175; let LANE = 150; const X0 = 70, Y0 = 20, LABEL = 30;
const SIZE = { start: [36, 36], end: [36, 36], timer: [36, 36], message: [36, 36], gateway: [50, 50], task: [130, 84], service: [130, 84] };
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');

function layout(p) {
  const cols = Math.max(...p.nodes.map(n => n[3])) + 1;
  const width = LABEL + X0 + cols * COL;
  const nodes = {};
  for (const [id, kind, lane, col, name, dy = 0] of p.nodes) {
    const [w, h] = SIZE[kind];
    const cx = LABEL + X0 + col * COL + COL / 2 - 40, cy = Y0 + lane * LANE + LANE / 2 + dy;
    nodes[id] = { id, kind, lane, col, name, w, h, x: Math.round(cx - w / 2), y: Math.round(cy - h / 2), cx, cy };
  }
  return { cols, width, height: p.lanes.length * LANE, nodes };
}

function waypoints(a, b, L) {
  if (b.col > a.col) {
    const sx = a.x + a.w, tx = b.x;
    if (Math.abs(a.cy - b.cy) < 1) return [[sx, a.cy], [tx, b.cy]];
    if (a.kind === 'gateway') return [[a.cx, b.cy < a.cy ? a.y : a.y + a.h], [a.cx, b.cy], [tx, b.cy]];
    const mx = b.col - a.col > 1 ? tx - 28 : Math.round((sx + tx) / 2);
    return [[sx, a.cy], [mx, a.cy], [mx, b.cy], [tx, b.cy]];
  }
  // A loop back: under both nodes, inside the lowest of their lanes.
  const yb = Y0 + (Math.max(a.lane, b.lane) + 1) * LANE - 14;
  return [[a.cx, a.y + a.h], [a.cx, yb], [b.cx, yb], [b.cx, b.y + b.h]];
}

function xml(p) {
  LANE = p.laneHeight || 150;
  const L = layout(p);
  const tag = { start: 'startEvent', end: 'endEvent', task: 'userTask', service: 'serviceTask', gateway: 'exclusiveGateway',
    timer: 'intermediateCatchEvent', message: 'intermediateThrowEvent' };
  const inc = {}, out = {};
  p.flows.forEach(([a, b], i) => { (out[a] ||= []).push(`flow${i}`); (inc[b] ||= []).push(`flow${i}`); });
  const proc = [], di = [];
  proc.push(`<bpmn:laneSet id="ls_${p.id}">`);
  p.lanes.forEach((ln, li) => {
    proc.push(`<bpmn:lane id="lane${li}" name="${esc(ln)}">`);
    Object.values(L.nodes).filter(n => n.lane === li).forEach(n => proc.push(`<bpmn:flowNodeRef>${n.id}</bpmn:flowNodeRef>`));
    proc.push('</bpmn:lane>');
    di.push(`<bpmndi:BPMNShape id="lane${li}_di" bpmnElement="lane${li}" isHorizontal="true"><dc:Bounds x="${LABEL}" y="${Y0 + li * LANE}" width="${L.width - LABEL}" height="${LANE}"/></bpmndi:BPMNShape>`);
  });
  proc.push('</bpmn:laneSet>');
  for (const n of Object.values(L.nodes)) {
    const io = (inc[n.id] || []).map(f => `<bpmn:incoming>${f}</bpmn:incoming>`).join('') + (out[n.id] || []).map(f => `<bpmn:outgoing>${f}</bpmn:outgoing>`).join('');
    const def = n.kind === 'timer' ? `<bpmn:timerEventDefinition id="td_${n.id}"/>` : n.kind === 'message' ? `<bpmn:messageEventDefinition id="md_${n.id}"/>` : '';
    proc.push(`<bpmn:${tag[n.kind]} id="${n.id}" name="${esc(n.name)}">${io}${def}</bpmn:${tag[n.kind]}>`);
    const lbl = ['task', 'service'].includes(n.kind) ? '' : `<bpmndi:BPMNLabel><dc:Bounds x="${n.cx - 60}" y="${n.y + n.h + 4}" width="120" height="40"/></bpmndi:BPMNLabel>`;
    di.push(`<bpmndi:BPMNShape id="${n.id}_di" bpmnElement="${n.id}"${n.kind === 'gateway' ? ' isMarkerVisible="true"' : ''}><dc:Bounds x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}"/>${lbl}</bpmndi:BPMNShape>`);
  }
  p.flows.forEach(([a, b, name], i) => {
    proc.push(`<bpmn:sequenceFlow id="flow${i}" sourceRef="${a}" targetRef="${b}"${name ? ` name="${esc(name)}"` : ''}/>`);
    const w = waypoints(L.nodes[a], L.nodes[b], L);
    const lx = w.length === 2 ? w[0][0] + 8 : w.length === 3 ? w[1][0] + 12 : w[1][0] + 6;
    const ly = w.length === 2 ? w[0][1] - 20 : w.length === 3 ? w[1][1] - 20 : Math.round((w[0][1] + w[1][1]) / 2) - 7;
    const lbl = name ? `<bpmndi:BPMNLabel><dc:Bounds x="${lx}" y="${ly}" width="40" height="14"/></bpmndi:BPMNLabel>` : '';
    di.push(`<bpmndi:BPMNEdge id="flow${i}_di" bpmnElement="flow${i}">${w.map(([x, y]) => `<di:waypoint x="${Math.round(x)}" y="${Math.round(y)}"/>`).join('')}${lbl}</bpmndi:BPMNEdge>`);
  });
  return `<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="defs_${p.id}" targetNamespace="https://e-himaya.tn/bpmn" exporter="e-Himaya docs/deliverables/bpmn" exporterVersion="1.0">
<bpmn:collaboration id="collab_${p.id}"><bpmn:participant id="pool_${p.id}" name="${esc('ء-حماية: ' + p.title)}" processRef="${p.id}"/></bpmn:collaboration>
<bpmn:process id="${p.id}" name="${esc(p.title)}" isExecutable="false">
${proc.join('\n')}
</bpmn:process>
<bpmndi:BPMNDiagram id="dia_${p.id}"><bpmndi:BPMNPlane id="plane_${p.id}" bpmnElement="collab_${p.id}">
<bpmndi:BPMNShape id="pool_${p.id}_di" bpmnElement="pool_${p.id}" isHorizontal="true"><dc:Bounds x="0" y="${Y0}" width="${L.width}" height="${L.height}"/></bpmndi:BPMNShape>
${di.join('\n')}
</bpmndi:BPMNPlane></bpmndi:BPMNDiagram>
</bpmn:definitions>
`;
}

async function render(files, outDir) {
  const { chromium } = require('playwright');
  const viewer = require.resolve('bpmn-js/dist/bpmn-viewer.production.min.js');
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 2, viewport: { width: 2800, height: 1200 } });
  await page.setContent(`<html><head><style>
    body{margin:0;background:#fff} #c{width:2800px;height:1200px}
    .djs-label, .djs-element text{font-family:'IBM Plex Sans Arabic',sans-serif !important}
  </style></head><body><div id="c"></div></body></html>`);
  await page.addScriptTag({ path: viewer });
  for (const f of files) {
    const x = fs.readFileSync(path.join(outDir, `${f}.bpmn`), 'utf8');
    const box = await page.evaluate(async src => {
      document.getElementById('c').innerHTML = '';
      const v = new window.BpmnJS({ container: '#c' });
      await v.importXML(src);
      const canvas = v.get('canvas');
      canvas.zoom(1, { x: 0, y: 0 });
      canvas.viewbox({ x: -10, y: 0, width: 2800, height: 1200 });
      // Lane and node colours of the design system: navy lines, tinted lanes, red end, green start.
      document.querySelectorAll('.djs-element[data-element-id^="lane"] .djs-visual rect').forEach((r, i) => r.style.fill = i % 2 ? '#F3F5FA' : '#FFFFFF');
      const set = (sel, fill, stroke) => document.querySelectorAll(sel).forEach(e => { const s = e.querySelector('.djs-visual > circle, .djs-visual > rect, .djs-visual > polygon'); if (s) { s.style.fill = fill; s.style.stroke = stroke; } });
      const reg = v.get('elementRegistry');
      reg.getAll().forEach(el => {
        const g = reg.getGraphics(el); const s = g && g.querySelector('.djs-visual > circle, .djs-visual > rect, .djs-visual > polygon');
        if (!s) return;
        const t = el.type;
        if (t === 'bpmn:StartEvent') { s.style.fill = '#E6F4EA'; s.style.stroke = '#188038'; }
        else if (t === 'bpmn:EndEvent') { s.style.fill = '#FDE8E8'; s.style.stroke = '#D7141A'; }
        else if (t === 'bpmn:UserTask') { s.style.fill = '#E8EDFA'; s.style.stroke = '#1F3FA0'; }
        else if (t === 'bpmn:ServiceTask') { s.style.fill = '#E0F3EF'; s.style.stroke = '#00806A'; }
        else if (t === 'bpmn:ExclusiveGateway') { s.style.fill = '#FFF3D6'; s.style.stroke = '#C25E00'; }
        else if (t.startsWith('bpmn:Intermediate')) { s.style.fill = '#FFF3D6'; s.style.stroke = '#C25E00'; }
      });
      const b = canvas.getActiveLayer().getBBox();
      return { w: b.width, h: b.height };
    }, x);
    await page.screenshot({ path: path.join(outDir, `${f}.png`), clip: { x: 0, y: 0, width: Math.ceil(box.w + 30), height: Math.ceil(box.h + 30) } });
    console.log('drawn', f, Math.round(box.w), 'x', Math.round(box.h));
  }
  await browser.close();
}

(async () => {
  const outDir = process.argv[2] || 'out';
  fs.mkdirSync(outDir, { recursive: true });
  for (const p of processes) fs.writeFileSync(path.join(outDir, `${p.file}.bpmn`), xml(p));
  await render(processes.map(p => p.file), outDir);
})();
