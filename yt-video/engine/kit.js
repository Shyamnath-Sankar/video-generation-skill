/* kit.js: the shared toolkit for 9:16 Shorts pages.
   Every style is a pure function of time: seek(t) sets every element for time t. No CSS transitions,
   no timers, no state carried between frames, no Math.random (use K.rng). That is what lets the
   renderer draw any frame in any order, with motion blur.
   Needs window.TIMELINE (timeline.js) and window.STYLE (style.js) loaded first.
   Spring/track helpers adapted from Bart's motion-graphics skills (MIT). */
(function () {
  const K = (window.K = {});
  const TL = (K.TL = window.TIMELINE || { w: 1080, h: 1920, fps: 30, duration: 10, scenes: [] });
  const ST = (K.STYLE = window.STYLE || {});
  K.W = TL.w || 1080; K.H = TL.h || 1920;
  // format profile (engine/formats.json, copied into the timeline): 'short' 9:16, 'long' / 'long-4k' 16:9
  K.FORMAT = TL.format || (K.W > K.H ? 'long' : 'short');
  K.LONG = K.FORMAT !== 'short';
  K.FMT = TL.formatInfo || { safe: K.LONG ? { left: 96, top: 54, right: 1824, bottom: 1026 } : { left: 60, top: 288, right: 940, bottom: 1440 },
    captions: K.LONG ? { burn: false, y: 930, width: 1400, size_scale: 0.82, words_scale: 1.6 } : { burn: true, width: 780, size_scale: 1, words_scale: 1 } };
  K.SAFE = K.FMT.safe;
  // pick the layout table for this format: K.layout({short: {...}, long: {...}})
  K.layout = map => map[K.FORMAT] || (K.LONG ? map.long : map.short) || map.short;
  // place elements once at load from a layout: K.place({id: {left: 80, top: 330, fontSize: 34}, ...}); numbers become px
  const PX = /^(left|top|right|bottom|width|height|fontSize|lineHeight|borderRadius|padding|gap|margin|letterSpacing)$/;
  K.place = obj => { for (const id in obj) { const el = typeof id === 'string' ? document.getElementById(id) : id; if (!el) { console.warn('place: no #' + id); continue; }
    for (const p in obj[id]) { const v = obj[id][p]; if (p.startsWith('attr:')) el.setAttribute(p.slice(5), v); else el.style[p] = (typeof v === 'number' && PX.test(p)) ? v + 'px' : v; } } };
  // red overlay over everything outside the safe zone (shown with ?safe or the preview toggle)
  K.safeOverlay = root => { if (!root) return; const s = K.SAFE; root.innerHTML = '';
    [[0, 0, K.W, s.top], [0, s.bottom, K.W, K.H - s.bottom], [0, s.top, s.left, s.bottom - s.top], [s.right, s.top, K.W - s.right, s.bottom - s.top]]
      .forEach(([x, y, w, h]) => { if (w > 0 && h > 0) { const d = document.createElement('div'); d.style.cssText = `left:${x}px;top:${y}px;width:${w}px;height:${h}px`; root.appendChild(d); } }); };
  K.RENDER = /[?&]render\b/.test(location.search);
  // resolves when every declared font is loaded. Measure text (getComputedTextLength, offsetWidth) only after it:
  //   window.READY = K.ready.then(layout)   (the renderer and checker wait for window.READY)
  K.ready = Promise.all([...document.fonts].map(f => f.load().catch(() => {}))).then(() => document.fonts.ready);

  // ------------------------------------------------------------------ math + easing
  const clamp = (K.clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x)));
  const lerp = (K.lerp = (a, b, u) => a + (b - a) * u);
  K.seg = (t, a, b) => (b <= a ? (t >= b ? 1 : 0) : clamp((t - a) / (b - a)));
  K.eo = x => 1 - Math.pow(1 - clamp(x), 3);                                   // ease-out cubic
  K.ei = x => Math.pow(clamp(x), 3);                                           // ease-in cubic
  K.ease = x => (x = clamp(x), x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2); // in-out cubic
  K.smooth = x => { x = clamp(x); const s = v => 1 / (1 + Math.exp(-v)); const k = 10;   // Manim's "smooth" rate function
    return clamp((s(k * (x - 0.5)) - s(-k / 2)) / (s(k / 2) - s(-k / 2))); };
  K.thereAndBack = x => K.smooth(x < 0.5 ? 2 * x : 2 * (1 - x));
  K.backOut = (x, s = 1.7) => { x = clamp(x) - 1; return x * x * ((s + 1) * x + s) + 1; };
  K.EASE = ST.motion && ST.motion.ease === 'smooth' ? K.smooth : K.ease;   // the style's default ease

  // damped spring step response 0 -> 1. w = speed (8 slow, 14 normal, 22 snappy), z = damping (1 = no overshoot)
  const spring = (K.spring = (t, w = 14, z = 0.82) => {
    if (t <= 0) return 0;
    if (!isFinite(w)) return 1;
    if (z >= 1) return 1 - Math.exp(-w * t) * (1 + w * t);
    const wd = w * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w * t) * (Math.cos(wd * t) + (z * w / wd) * Math.sin(wd * t));
  });
  const SP = (ST.motion && ST.motion.spring) || [14, 0.82];
  K.SPRING = SP;
  // a value that springs to a new target at each key: track(v0, [[t, value, w?, z?], ...]) -> f(t)
  K.track = (v0, keys) => t => { let v = v0, p = v0; for (const [tk, val, w = SP[0], z = SP[1]] of keys) { v += (val - p) * spring(t - tk, w, z); p = val; } return v; };
  // eased keyframes (exact landing, good for cameras): kf([[t0,v0],[t1,v1,easeFn?],...]) -> f(t)
  K.kf = keys => t => {
    if (t <= keys[0][0]) return keys[0][1];
    for (let i = 1; i < keys.length; i++) { const [a, va] = keys[i - 1], [b, vb, e = K.EASE] = keys[i]; if (t <= b) return lerp(va, vb, e((t - a) / (b - a))); }
    return keys[keys.length - 1][1];
  };
  // seeded random (never Math.random): const r = K.rng(7); r() -> [0,1)
  K.rng = s => () => (s = (s + 0x6d2b79f5) | 0, s = Math.imul(s ^ (s >>> 15), 1 | s), s ^= s + Math.imul(s ^ (s >>> 7), 61 | s), ((s ^ (s >>> 14)) >>> 0) / 4294967296);

  // ------------------------------------------------------------------ colour
  const hex = (K.hex = h => { h = h.replace('#', ''); if (h.length === 3) h = h.split('').map(c => c + c).join(''); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)); });
  K.mix = (a, b, u) => { const A = hex(a), B = hex(b); u = clamp(u); return `rgb(${A.map((v, i) => Math.round(lerp(v, B[i], u))).join(',')})`; };
  K.alpha = (a, o) => { const A = hex(a); return `rgba(${A.join(',')},${o})`; };
  // colour that eases to each new key: ctrack('#000', [[t,'#fff'],...], dur)
  K.ctrack = (c0, keys, dur = 0.45) => t => {
    let cur = c0;
    for (const [tk, ck] of keys) { if (t < tk) break; if (t < tk + dur) return K.mix(cur, ck, K.ease((t - tk) / dur)); cur = ck; }
    return cur;
  };
  K.C = Object.assign({ bg: '#0B0B10', bg2: '#16161D', ink: '#FFFFFF', muted: '#9A9AA5', accent: '#FF4F1A', accent2: '#2F47FF', accent3: '#2BD67B', accent4: '#FFD23F', card: '#FFFFFF', line: '#FFFFFF' }, ST.colors || {});

  // ------------------------------------------------------------------ DOM helpers (cached, cheap per frame)
  const ids = {};
  K.$ = id => ids[id] || (ids[id] = document.getElementById(id));
  K.st = (el, props) => { if (typeof el === 'string') el = K.$(el); if (!el) return; const c = el._st || (el._st = {});
    for (const k in props) { const v = props[k]; if (c[k] !== v) { el.style[k] = v; c[k] = v; } } };
  K.text = (el, s) => { if (typeof el === 'string') el = K.$(el); if (el && el._tx !== s) { el.textContent = s; el._tx = s; } };
  K.show = (el, on) => K.st(el, { display: on ? '' : 'none' });
  K.vis = (t, tin, tout, o = {}) => {        // content swap: enter waits din then blurs in over lin; exit blurs out over lout
    const din = o.din ?? 0, lin = o.lin ?? 0.3, lout = o.lout ?? 0.2, bl = o.blur ?? 10;
    const a = tin == null ? 1 : K.eo((t - tin - din) / lin);
    const b = tout == null ? 0 : K.eo((t - tout) / lout);
    return { o: a * (1 - b), blur: (1 - a) * bl + b * bl * 0.6, s: (0.94 + 0.06 * a) * (1 - 0.03 * b), a, b };
  };
  K.apply = (el, v, extra = '') => { if (typeof el === 'string') el = K.$(el); if (!el) return false;
    if (v.o < 0.003) { K.st(el, { display: 'none' }); return false; }
    K.st(el, { display: '', opacity: v.o.toFixed(3), filter: v.blur > 0.1 ? `blur(${v.blur.toFixed(1)}px)` : 'none', transform: `${extra} scale(${v.s.toFixed(4)})` });
    return true; };
  K.typed = (str, t, t0, cps = 22) => str.slice(0, Math.max(0, Math.floor((t - t0) * cps)));
  K.count = (a, b, p, dec = 0) => (lerp(a, b, clamp(p))).toFixed(dec);

  // ------------------------------------------------------------------ timeline: scenes, words, cues
  K.scenes = TL.scenes || [];
  K.scene = id => K.scenes.find(s => s.id === id) || null;
  const norm = w => String(w).toLowerCase().replace(/[^\p{L}\p{N}%]+/gu, '');
  const warned = {};
  // absolute time the narrator starts saying `word` in scene `id` (nth occurrence). Visual hits go here.
  K.cue = (id, word, nth = 0, fallback = 0.3) => {
    const sc = K.scene(id);
    if (!sc) { if (!warned[id]) { console.warn('no scene', id); warned[id] = 1; } return 0; }
    const want = norm(word); let k = 0;
    for (const w of sc.words || []) if (norm(w.w) === want || norm(w.w).startsWith(want)) { if (k++ === nth) return w.s; }
    if (!warned[id + word]) { console.warn(`cue: "${word}" not spoken in scene ${id}; using start+${fallback}s`); warned[id + word] = 1; }
    return (sc.voiceStart ?? sc.start) + fallback;
  };
  K.cueEnd = (id, word, nth = 0) => { const s = K.cue(id, word, nth); const sc = K.scene(id); const w = (sc.words || []).find(x => x.s === s); return w ? w.e : s + 0.3; };
  // beat grid (only when music is on): K.beat(t) -> {n, phase}; K.pulse(t) -> 1 on each beat, decaying
  K.bpm = TL.music && TL.music.enabled ? TL.music.bpm : 0;
  K.beat = t => { if (!K.bpm) return { n: 0, phase: 0 }; const b = (t - (TL.music.offset || 0)) * K.bpm / 60; return { n: Math.floor(b), phase: b - Math.floor(b) }; };
  K.pulse = (t, decay = 7) => (K.bpm ? Math.exp(-decay * K.beat(t).phase * 60 / K.bpm) : 0);

  // ------------------------------------------------------------------ SVG helpers (Manim-like)
  const NS = 'http://www.w3.org/2000/svg';
  K.svg = (tag, attrs = {}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
  K.len = el => el._len || (el._len = el.getTotalLength ? el.getTotalLength() : 0);
  // stroke draws on from 0 -> 1 (Manim "Create")
  K.draw = (el, p) => { const L = K.len(el) + 1; p = clamp(p); K.st(el, { strokeDasharray: `${L} ${L}`, strokeDashoffset: (L * (1 - p)).toFixed(2), visibility: p <= 0 ? 'hidden' : 'visible' }); };
  // outline draws, then fill fades in (Manim "Write"); works on SVG <text> and <path> with a fill
  K.write = (el, p, fillOpacity = 1) => { p = clamp(p); const L = el._wl || (el._wl = 2400);
    K.st(el, { strokeDasharray: `${L} ${L}`, strokeDashoffset: (L * (1 - K.clamp(p / 0.6))).toFixed(1),
      fillOpacity: (fillOpacity * K.seg(p, 0.45, 1)).toFixed(3), strokeOpacity: (1 - K.seg(p, 0.75, 1) * 0.85).toFixed(3), visibility: p <= 0 ? 'hidden' : 'visible' }); };
  // dots flowing along a path (packets on a connector): returns [{x,y,o}]
  K.flow = (path, t, { n = 3, speed = 0.6, t0 = 0 } = {}) => { const L = K.len(path); const out = [];
    for (let i = 0; i < n; i++) { const u = ((t - t0) * speed + i / n) % 1; if (t < t0 || u < 0) continue; const pt = path.getPointAtLength(u * L);
      out.push({ x: pt.x, y: pt.y, o: Math.min(1, u * 8, (1 - u) * 8) }); } return out; };
  // grid of lines (Manim NumberPlane): build once into an <svg> group
  K.plane = (g, { x0 = 0, y0 = 0, w = 1080, h = 1080, step = 90, color = K.C.accent, axis = K.C.ink, width = 2 } = {}) => {
    const lines = [];
    for (let x = x0; x <= x0 + w + 0.1; x += step) lines.push(K.svg('line', { x1: x, y1: y0, x2: x, y2: y0 + h, stroke: color, 'stroke-width': width, 'stroke-opacity': 0.55 }, g));
    for (let y = y0; y <= y0 + h + 0.1; y += step) lines.push(K.svg('line', { x1: x0, y1: y, x2: x0 + w, y2: y, stroke: color, 'stroke-width': width, 'stroke-opacity': 0.55 }, g));
    const ax = K.svg('line', { x1: x0, y1: y0 + h / 2, x2: x0 + w, y2: y0 + h / 2, stroke: axis, 'stroke-width': width * 1.6 }, g);
    const ay = K.svg('line', { x1: x0 + w / 2, y1: y0, x2: x0 + w / 2, y2: y0 + h, stroke: axis, 'stroke-width': width * 1.6 }, g);
    return { lines, axes: [ax, ay], all: lines.concat([ax, ay]) };
  };

  // ------------------------------------------------------------------ background + grain (drawn once, then reused)
  K.background = canvas => {
    if (!canvas) return; canvas.width = K.W; canvas.height = K.H; const g = canvas.getContext('2d');
    const bg = ST.background || {}; const kind = bg.kind || 'flat'; const C = K.C;
    if (kind === 'gradient' || kind === 'sky') {
      const lg = g.createLinearGradient(0, 0, 0, K.H); lg.addColorStop(0, C.bg); lg.addColorStop(1, C.bg2); g.fillStyle = lg; g.fillRect(0, 0, K.W, K.H);
    } else { g.fillStyle = C.bg; g.fillRect(0, 0, K.W, K.H); }
    const r = K.rng(bg.seed || 11);
    if (kind === 'grid' || kind === 'dots') {
      const step = bg.step || 72, ox = (K.W % step) / 2, oy = (K.H % step) / 2;
      g.strokeStyle = g.fillStyle = K.alpha(bg.gridColor || C.ink, bg.gridOpacity ?? 0.06); g.lineWidth = 2;
      if (kind === 'grid') {
        for (let x = ox; x <= K.W; x += step) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, K.H); g.stroke(); }
        for (let y = oy; y <= K.H; y += step) { g.beginPath(); g.moveTo(0, y); g.lineTo(K.W, y); g.stroke(); }
      } else {
        for (let x = ox; x <= K.W; x += step) for (let y = oy; y <= K.H; y += step) { g.beginPath(); g.arc(x, y, 2.5, 0, 6.283); g.fill(); }
      }
    }
    if (kind === 'paper') {   // warm paper fibres
      const img = g.getImageData(0, 0, K.W, K.H), d = img.data;
      for (let i = 0; i < d.length; i += 4) { const n = (r() - 0.5) * 14; d[i] += n; d[i + 1] += n; d[i + 2] += n * 0.8; }
      g.putImageData(img, 0, 0);
    }
    if (kind === 'sky') {     // a few soft blobs (drawn once, no CSS blur)
      for (let i = 0; i < 5; i++) { const x = r() * K.W, y = r() * K.H * 0.8, rad = 220 + r() * 260;
        const rg = g.createRadialGradient(x, y, 0, x, y, rad); rg.addColorStop(0, 'rgba(255,255,255,0.35)'); rg.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = rg; g.fillRect(0, 0, K.W, K.H); }
    }
    const v = bg.vignette ?? 0.3;
    if (v > 0) { const rg = g.createRadialGradient(K.W / 2, K.H * 0.45, K.H * 0.2, K.W / 2, K.H * 0.5, K.H * 0.75);
      rg.addColorStop(0, 'rgba(0,0,0,0)'); rg.addColorStop(1, `rgba(0,0,0,${v})`); g.fillStyle = rg; g.fillRect(0, 0, K.W, K.H); }
  };
  // film grain: a few seeded tiles, cycled at 24 fps. Returns draw(t).
  K.grain = (canvas, amount = (ST.background && ST.background.grain) || 0) => {
    if (!canvas) return () => {};
    if (!amount) { canvas.style.display = 'none'; return () => {}; }
    const tw = Math.round(K.W / 2), th = Math.round(K.H / 2); canvas.width = tw; canvas.height = th; const g = canvas.getContext('2d');
    const tiles = []; const r = K.rng(99);
    for (let k = 0; k < 4; k++) { const img = g.createImageData(tw, th); const d = img.data;
      for (let i = 0; i < d.length; i += 4) { const v = r() * 255; d[i] = d[i + 1] = d[i + 2] = v; d[i + 3] = 255; } tiles.push(img); }
    canvas.style.opacity = amount; let last = -1;
    return t => { const k = Math.floor(t * 24) % tiles.length; if (k !== last) { g.putImageData(tiles[k], 0, 0); last = k; } };
  };

  // ------------------------------------------------------------------ scene transitions (scene-level, per style)
  // Each returns {o, x, y, s, blur} for a scene section at time t. sc.start/sc.end are absolute.
  const TR = (K.TRANSITIONS = {
    // editorial: next scene pushes up from below, old one lifts away with a little blur
    push: (t, sc, first, last) => {
      const i = first ? 1 : spring(t - sc.start + 0.06, 15, 0.86), o = last ? 0 : K.eo((t - sc.end + 0.04) / 0.22);
      return { o: (first ? 1 : K.eo((t - sc.start + 0.06) / 0.2)) * (1 - o), y: (1 - i) * 160 - o * 140, x: 0, s: 1 - o * 0.03, blur: (1 - K.clamp(i * 1.4)) * 6 + o * 8 };
    },
    // 3Blue1Brown-like: calm crossfade with a slight scale, Manim "smooth" timing, never blurry
    'fade-transform': (t, sc, first, last) => {
      const a = first ? 1 : K.smooth((t - sc.start + 0.25) / 0.5), b = last ? 0 : K.smooth((t - sc.end + 0.25) / 0.5);
      return { o: a * (1 - b), x: 0, y: 0, s: 0.97 + 0.03 * a + 0.02 * b, blur: 0 };
    },
    // KodeKloud-like: friendly pop with overshoot, quick fade out
    pop: (t, sc, first, last) => {
      const i = first ? 1 : spring(t - sc.start + 0.04, 16, 0.62), b = last ? 0 : K.eo((t - sc.end + 0.12) / 0.16);
      return { o: (first ? 1 : K.eo((t - sc.start + 0.04) / 0.12)) * (1 - b), x: 0, y: 0, s: (0.86 + 0.14 * i) * (1 + 0.05 * b), blur: 0 };
    },
    // Fireship / hype: hard cut on the boundary, punch-in zoom on the way in
    punch: (t, sc, first, last) => {
      const vis = t >= sc.start && (last || t < sc.end);
      return { o: vis ? 1 : 0, x: 0, y: 0, s: first ? 1 : 1 + 0.1 * (1 - spring(t - sc.start, 22, 0.9)), blur: 0 };
    },
    // Vox / ByteByteGo: horizontal slide like turning a page
    slide: (t, sc, first, last) => {
      const i = first ? 1 : K.ease((t - sc.start + 0.2) / 0.45), b = last ? 0 : K.ease((t - sc.end + 0.2) / 0.45);
      return { o: i > 0 && b < 1 ? 1 : 0, x: (1 - i) * K.W - b * K.W, y: 0, s: 1, blur: 0 };
    },
    // flat-vector science: crossfade with slow parallax drift through the scene
    drift: (t, sc, first, last) => {
      const a = first ? 1 : K.ease((t - sc.start + 0.3) / 0.6), b = last ? 0 : K.ease((t - sc.end + 0.3) / 0.6);
      return { o: a * (1 - b), x: 0, y: 0, s: 1 + 0.04 * K.seg(t, sc.start, sc.end), blur: 0 };
    },
  });
  // Run every scene: show its <section id="sc-ID"> in its window, apply the transition, call its draw fn.
  // fns = { hook: (t, lt, sc, el) => {...}, ... }   lt = t - sc.start
  K.runScenes = (fns, transition = ST.transition || 'push') => {
    const n = K.scenes.length;
    return t => {
      K.scenes.forEach((sc, i) => {
        const el = K.$('sc-' + sc.id); if (!el) return;
        const tr = TR[sc.transition || transition] || TR.push;
        const v = tr(t, sc, i === 0, i === n - 1);
        const inWin = t >= sc.start - 0.7 && t <= sc.end + 0.7;
        if (!inWin || v.o < 0.003) { K.st(el, { display: 'none' }); return; }
        K.st(el, { display: 'block', opacity: v.o.toFixed(3), filter: v.blur > 0.1 ? `blur(${v.blur.toFixed(1)}px)` : 'none',
          transform: `translate(${v.x.toFixed(1)}px,${v.y.toFixed(1)}px) scale(${v.s.toFixed(4)})` });
        if (fns[sc.id]) fns[sc.id](t, t - sc.start, sc, el);
      });
    };
  };

  // ------------------------------------------------------------------ captions
  // Pages of a few words, timed from TIMELINE caption words. Modes: pop | box | minimal | off
  K.captions = (root, o = {}) => {
    const FC = K.FMT.captions || {};
    const cfg = Object.assign({ mode: 'pop', size: 76, y: 1290, maxWords: 3, maxChars: 18, width: FC.width || 780, weight: 850, case: 'none', active: 'accent', color: 'ink', stroke: 'bg' },
      ST.captions || {}, K.LONG ? (ST.captionsLong || {}) : {}, o);
    const burn = TL.captions ? TL.captions.burn !== false : true;
    if (!root || cfg.mode === 'off' || (!burn && !o.force)) { if (root) root.style.display = 'none'; return () => {}; }
    if (cfg.mode === 'minimal') { cfg.maxWords = o.maxWords || (ST.captions && ST.captions.maxWords) || 6; cfg.maxChars = o.maxChars || (ST.captions && ST.captions.maxChars) || 34; }
    if (cfg.mode === 'box') { cfg.maxWords = o.maxWords || (ST.captions && ST.captions.maxWords) || 2; cfg.maxChars = o.maxChars || (ST.captions && ST.captions.maxChars) || 12; }
    if (K.LONG && !(ST.captionsLong && ST.captionsLong.size)) {   // landscape: smaller, lower, wider lines
      cfg.size = Math.round(cfg.size * (FC.size_scale || 0.82)); cfg.y = o.y || FC.y || 930; cfg.width = o.width || FC.width || 1400;
      cfg.maxWords = Math.round(cfg.maxWords * (FC.words_scale || 1.6)); cfg.maxChars = Math.round(cfg.maxChars * (FC.words_scale || 1.6));
    }
    const col = k => (K.C[k] || k);
    const words = []; K.scenes.forEach(sc => (sc.caps || sc.words || []).forEach(w => words.push({ ...w, scene: sc })));
    const pages = []; let cur = null;
    words.forEach((w, i) => {
      const prevEndsSentence = cur && /[.!?…:;]$/.test(cur.words[cur.words.length - 1].w);
      const chars = cur ? cur.words.map(x => x.w).join(' ').length + 1 + w.w.length : 0;
      if (!cur || cur.words.length >= cfg.maxWords || chars > cfg.maxChars || prevEndsSentence || w.scene !== cur.scene || w.s - cur.words[cur.words.length - 1].e > 0.6) {
        cur = { words: [], scene: w.scene }; pages.push(cur);
      }
      cur.words.push(w);
    });
    pages.forEach(p => { p.s = p.words[0].s - 0.04; });
    pages.forEach((p, i) => {
      const next = pages[i + 1];
      const tailEnd = p.words[p.words.length - 1].e + 0.35;
      p.e = next ? Math.min(next.s - 0.04, Math.max(tailEnd, p.words[p.words.length - 1].e + 0.1)) : tailEnd;
      p.e = Math.min(p.e, p.scene.end + 0.05);
      const div = document.createElement('div'); div.className = 'cap-page cap-' + cfg.mode; div.setAttribute('data-caption', '');
      div.style.cssText = `position:absolute;left:${(K.W - cfg.width) / 2}px;width:${cfg.width}px;top:0;text-align:center;display:none;` +
        `font-size:${cfg.size}px;font-weight:${cfg.weight};line-height:1.12;text-transform:${cfg.case === 'upper' ? 'uppercase' : 'none'};`;
      p.spans = p.words.map((w, j) => { const sp = document.createElement('span'); sp.className = 'cap-w'; sp.textContent = w.w; div.appendChild(sp);
        if (j < p.words.length - 1) div.appendChild(document.createTextNode(' ')); return sp; });
      root.appendChild(div); p.el = div;
    });
    let measured = false;
    return t => {
      if (!measured) { pages.forEach(p => { p.el.style.display = ''; p.h = p.el.offsetHeight; p.el.style.display = 'none'; p.el._st = {}; });
        measured = document.fonts.status === 'loaded'; }   // re-measure until the real fonts are in
      pages.forEach(p => {
        const on = t >= p.s && t < p.e;
        if (!on) { K.st(p.el, { display: 'none' }); return; }
        const lt = t - p.s;
        let s = 1, o = 1;
        if (cfg.mode === 'pop') { s = 0.88 + 0.12 * spring(lt, 20, 0.7); o = K.eo(lt / 0.08); }
        if (cfg.mode === 'box') { s = 1.12 - 0.12 * spring(lt, 24, 0.75); }
        if (cfg.mode === 'minimal') { o = K.ease(lt / 0.18) * (1 - K.ease((t - p.e + 0.15) / 0.15)); }
        K.st(p.el, { display: '', opacity: o.toFixed(3), top: (cfg.y - p.h / 2).toFixed(1) + 'px', transform: `scale(${s.toFixed(4)})` });
        p.words.forEach((w, j) => {
          const sp = p.spans[j]; const active = t >= w.s - 0.03 && (j === p.words.length - 1 ? t < p.e : t < p.words[j + 1].s - 0.03);
          const spoken = t >= w.s - 0.03;
          if (cfg.mode === 'pop') {
            const k = spring(t - w.s + 0.03, 22, 0.6);
            K.st(sp, { color: active ? col(cfg.active) : col(cfg.color), display: 'inline-block', transform: active ? `scale(${(1 + 0.08 * Math.min(1, k)).toFixed(3)})` : 'none' });
          } else if (cfg.mode === 'box') {
            K.st(sp, { display: 'inline-block', color: active ? col(cfg.activeText || 'bg') : col(cfg.color), background: active ? col(cfg.active) : 'transparent',
              padding: '0 0.12em', borderRadius: '0.12em', webkitTextStrokeWidth: active ? '0px' : '', transform: active ? `scale(${(1.06 - 0.06 * spring(t - w.s, 26, 0.7)).toFixed(3)}) rotate(-2deg)` : 'none' });
          } else {
            K.st(sp, { color: spoken ? col(cfg.color) : K.alpha(K.C[cfg.color] || '#ffffff', 0.55) });
          }
        });
      });
    };
  };
})();
