// Pan, zoom and rotate for the SVG pages of the living references (spider web, mind maps), Yamen 2026-11-13.
// The build scripts paste this file into each page. Controls sit at the top of the drawing: + and − zoom,
// the hand switches the drag between moving and turning, ⟲ and ⟳ turn by 15°, ⌂ fits the drawing again.
// A click on a node calls viewer.focus(x, y) to zoom onto it.
function makeViewer(stage, vp, fitBox) {
  const css = document.createElement('style');
  css.textContent = `.vctl{position:absolute;top:12px;inset-inline-end:16px;z-index:4;display:flex;gap:6px;align-items:center;flex-wrap:wrap;
    background:var(--card);border:1px solid var(--line);border-radius:999px;padding:5px 8px;box-shadow:0 6px 20px rgba(0,0,0,.18)}
    .vctl button{width:36px;height:36px;padding:0;border-radius:50%;border:1px solid var(--line);background:transparent;color:var(--ink);font-size:18px;line-height:1;cursor:pointer}
    .vctl button:hover{background:rgba(201,162,74,.18)} .vctl button[aria-pressed=true]{background:#C9A24A;color:#1B1405;border-color:#C9A24A}
    .vctl button:focus-visible{outline:2px solid #C9A24A;outline-offset:2px} .vmode{font-size:12px;color:var(--mute);padding-inline:4px}
    #stage[data-mode=turn]{cursor:alias}
    @media (max-width:720px){.vctl{inset-inline:8px auto;top:8px}.vmode{display:none}}`;
  document.head.appendChild(css);
  const st = {x: 0, y: 0, k: 1, r: 0}, LIM = [.08, 10];
  let mode = 'move', drag = null, anim = null;
  const rad = d => d * Math.PI / 180;
  const apply = () => vp.setAttribute('transform', `translate(${st.x},${st.y}) rotate(${st.r}) scale(${st.k})`);
  // screen point of a drawing point, and the reverse
  const toScreen = (cx, cy, s = st) => { const c = Math.cos(rad(s.r)), n = Math.sin(rad(s.r)); return [s.x + s.k * (cx * c - cy * n), s.y + s.k * (cx * n + cy * c)]; };
  const toDraw = (px, py) => { const c = Math.cos(rad(-st.r)), n = Math.sin(rad(-st.r)), dx = (px - st.x) / st.k, dy = (py - st.y) / st.k; return [dx * c - dy * n, dx * n + dy * c]; };
  function animate(to, ms = 450) {
    cancelAnimationFrame(anim);
    const from = {...st}, t0 = performance.now();
    const step = t => { const p = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - p, 3);
      for (const k in to) st[k] = from[k] + (to[k] - from[k]) * e; apply(); if (p < 1) anim = requestAnimationFrame(step); };
    anim = requestAnimationFrame(step);
  }
  const size = () => [stage.clientWidth, stage.clientHeight];
  function fit(animated = false) {
    const b = fitBox(), [W, H] = size();
    const k = Math.min(W / (b.width + 60), H / (b.height + 60), 1.4);
    const cx = b.x + b.width / 2, cy = b.y + b.height / 2;
    const to = {k, r: 0}; const [sx, sy] = toScreen(cx, cy, {x: 0, y: 0, k, r: 0}); to.x = W / 2 - sx; to.y = H / 2 - sy;
    animated ? animate(to) : (Object.assign(st, to), apply());
  }
  function zoomAt(f, px, py, animated = true) {
    const [W, H] = size(); px ??= W / 2; py ??= H / 2;
    const k = Math.max(LIM[0], Math.min(LIM[1], st.k * f)), [cx, cy] = toDraw(px, py);
    const [sx, sy] = toScreen(cx, cy, {x: 0, y: 0, k, r: st.r});
    const to = {k, x: px - sx, y: py - sy};
    animated ? animate(to, 250) : (Object.assign(st, to), apply());
  }
  function rotateBy(d) {
    const [W, H] = size(), [cx, cy] = toDraw(W / 2, H / 2), r = st.r + d;
    const [sx, sy] = toScreen(cx, cy, {x: 0, y: 0, k: st.k, r});
    animate({r, x: W / 2 - sx, y: H / 2 - sy}, 300);
  }
  function focus(cx, cy, k) {
    const [W, H] = size(); k = Math.max(st.k, k || 1.6);
    const [sx, sy] = toScreen(cx, cy, {x: 0, y: 0, k, r: st.r});
    animate({k, x: W / 2 - sx, y: H / 2 - sy});
  }
  // controls
  const bar = document.createElement('div');
  bar.className = 'vctl'; bar.setAttribute('role', 'toolbar'); bar.setAttribute('aria-label', 'التكبير والتحريك والتدوير');
  bar.innerHTML = `<button type="button" data-a="in" title="تكبير" aria-label="تكبير">+</button>
    <button type="button" data-a="out" title="تصغير" aria-label="تصغير">−</button>
    <button type="button" data-a="hand" title="اليد: تحريك أو تدوير بالسحب" aria-label="اليد: تحريك" aria-pressed="false">✋</button>
    <button type="button" data-a="ccw" title="تدوير يسارا" aria-label="تدوير يسارا">⟲</button>
    <button type="button" data-a="cw" title="تدوير يمينا" aria-label="تدوير يمينا">⟳</button>
    <button type="button" data-a="home" title="ملاءمة واستقامة" aria-label="ملاءمة واستقامة">⌂</button>
    <span class="vmode" aria-live="polite">السحب: تحريك</span>`;
  stage.appendChild(bar);
  const modeLbl = bar.querySelector('.vmode'), hand = bar.querySelector('[data-a=hand]');
  function setMode(m) {
    mode = m; hand.setAttribute('aria-pressed', m === 'turn'); hand.textContent = m === 'turn' ? '🔄' : '✋';
    hand.setAttribute('aria-label', m === 'turn' ? 'اليد: تدوير' : 'اليد: تحريك');
    modeLbl.textContent = m === 'turn' ? 'السحب: تدوير' : 'السحب: تحريك'; stage.dataset.mode = m;
  }
  bar.addEventListener('click', e => {
    const a = e.target.closest('button')?.dataset.a; if (!a) return; e.stopPropagation();
    if (a === 'in') zoomAt(1.35); else if (a === 'out') zoomAt(1 / 1.35);
    else if (a === 'ccw') rotateBy(-15); else if (a === 'cw') rotateBy(15);
    else if (a === 'hand') setMode(mode === 'move' ? 'turn' : 'move'); else if (a === 'home') fit(true);
  });
  bar.addEventListener('pointerdown', e => e.stopPropagation());
  // drag: move, or turn around the middle of the screen
  const rect = () => stage.getBoundingClientRect();
  stage.addEventListener('pointerdown', e => {
    if (e.target.closest('.nd, .node, .vctl')) return;
    const b = rect(); cancelAnimationFrame(anim);
    drag = {x: e.clientX, y: e.clientY, s: {...st}, a0: Math.atan2(e.clientY - b.top - b.height / 2, e.clientX - b.left - b.width / 2), moved: false};
  });
  addEventListener('pointermove', e => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) { drag.moved = true; stage.classList.add('drag'); }
    if (mode === 'move') { st.x = drag.s.x + dx; st.y = drag.s.y + dy; apply(); return; }
    const b = rect(), W = b.width, H = b.height, a = Math.atan2(e.clientY - b.top - H / 2, e.clientX - b.left - W / 2);
    const r = drag.s.r + (a - drag.a0) * 180 / Math.PI;
    Object.assign(st, drag.s); const [cx, cy] = toDraw(W / 2, H / 2); const [sx, sy] = toScreen(cx, cy, {x: 0, y: 0, k: st.k, r});
    st.r = r; st.x = W / 2 - sx; st.y = H / 2 - sy; apply();
  });
  addEventListener('pointerup', () => { if (drag) viewer.moved = drag.moved; drag = null; stage.classList.remove('drag'); });
  stage.addEventListener('wheel', e => { e.preventDefault(); const b = rect(); zoomAt(Math.exp(-e.deltaY * .0015), e.clientX - b.left, e.clientY - b.top, false); }, {passive: false});
  addEventListener('keydown', e => {
    if (e.target.closest && e.target.closest('input, select, textarea')) return;
    if (e.key === '+' || e.key === '=') zoomAt(1.35); else if (e.key === '-') zoomAt(1 / 1.35);
    else if (e.key === '[') rotateBy(-15); else if (e.key === ']') rotateBy(15); else if (e.key === '0') fit(true);
  });
  const viewer = {fit, focus, zoomAt, rotateBy, moved: false, state: st};
  return viewer;
}
