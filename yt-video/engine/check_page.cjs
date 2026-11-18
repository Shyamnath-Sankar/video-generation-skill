#!/usr/bin/env node
/* check_page.cjs: catch problems in a Short's HTML page BEFORE spending time on a render.

   node check_page.cjs page.html [--timeline timeline.json] [--json report.json] [--w 1080 --h 1920] [--times 0.5,2,4]

   Checks (FAIL stops the pipeline, WARN is for you to look at):
   - page loads with no JS errors / missing files, window.VIDEO + window.seek exist, size is 1080x1920
   - #stage sits at 0,0 and is exactly w x h in ?render mode
   - every declared font loads (no silent fallback)
   - source has no nondeterminism: Math.random, Date.now, performance.now, CSS animations/transitions, timers
     (code between PREVIEW-START and PREVIEW-END markers is ignored; that block only runs outside ?render)
   - seek(t) is a pure function of t: the same t gives identical pixels in any order
   - at sample times: text inside the frame, inside the Shorts safe zone, big enough for a phone, not overlapping
*/
const { chromium } = require('playwright');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const args = process.argv.slice(2);
const opt = {}; const pos = [];
for (let i = 0; i < args.length; i++) {
  if (args[i].startsWith('--')) { const k = args[i].slice(2); const v = args[i + 1]; if (v === undefined || v.startsWith('--')) opt[k] = true; else { opt[k] = v; i++; } }
  else pos.push(args[i]);
}
const html = pos[0];
if (!html) { console.log('usage: node check_page.cjs page.html [--timeline timeline.json] [--json report.json]'); process.exit(2); }
// format profile (engine/formats.json) comes from the timeline; --w/--h only for pages without one
const TL_PATH = opt.timeline || path.join(path.dirname(html), 'timeline.json');
const TLD = fs.existsSync(TL_PATH) ? JSON.parse(fs.readFileSync(TL_PATH, 'utf8')) : null;
const FORMATS = JSON.parse(fs.readFileSync(path.join(__dirname, 'formats.json'), 'utf8'));
const F = (TLD && TLD.formatInfo) || (opt.format ? FORMATS[opt.format] : FORMATS.short);
const FMT = (TLD && TLD.format) || opt.format || 'short';
const W = +(opt.w || F.w), H = +(opt.h || F.h);
// short: the Shorts UI covers top/bottom/right; long: title-safe margins and the player controls at the bottom
const SAFE = F.safe;
const MIN_TEXT_PX = +(opt['min-text'] || F.min_text_px || 34);
const PAGE = path.basename(html);

const results = []; // {level:'FAIL'|'WARN'|'OK', check, detail}
const add = (level, check, detail = '') => results.push({ level, check, detail });

(async () => {
  const src = fs.readFileSync(html, 'utf8');
  // ---- static scan ----
  const scanned = src.replace(/PREVIEW-START[\s\S]*?PREVIEW-END/g, '');
  const rules = [
    [/Math\.random\s*\(/, 'FAIL', 'Math.random() makes frames unrepeatable; use the seeded rng()'],
    [/Date\.now\s*\(|new Date\s*\(|performance\.now\s*\(/, 'FAIL', 'wall-clock time inside the render path; everything must come from t'],
    [/@keyframes|animation\s*:|animation-name\s*:/, 'FAIL', 'CSS animations run on real time, not on seek(t)'],
    [/transition\s*:(?!\s*none)/, 'WARN', 'CSS transition found; styles set in seek(t) must apply instantly'],
    [/setTimeout\s*\(|setInterval\s*\(/, 'WARN', 'timers found outside the PREVIEW block'],
    [/requestAnimationFrame\s*\(/, 'WARN', 'requestAnimationFrame outside the PREVIEW block'],
  ];
  for (const [re, level, msg] of rules) {
    const m = scanned.match(re);
    if (m) {
      const line = scanned.slice(0, m.index).split('\n').length;
      add(level, 'determinism (source)', `${msg} (near line ${line}: "${m[0]}")`);
    }
  }
  if (/will-change/.test(scanned)) add('WARN', 'source', 'will-change on scaled elements renders text blurry');

  // ---- load ----
  const browser = await chromium.launch({ args: ['--allow-file-access-from-files', '--font-render-hinting=none'] });
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const errors = [], consoleErr = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') consoleErr.push(m.text()); });
  page.on('requestfailed', r => errors.push('missing file: ' + r.url()));
  await page.goto(pathToFileURL(path.resolve(html)).href + '?render');
  try {
    await page.waitForFunction(() => window.VIDEO && typeof window.seek === 'function', null, { timeout: 15000 });
  } catch {
    add('FAIL', 'page contract', 'window.VIDEO and window.seek(t) were not defined within 15s');
    return finish(browser);
  }
  await page.evaluate(() => (window.READY && window.READY.then) ? window.READY : null);
  const V = await page.evaluate(() => ({ ...window.VIDEO }));
  if (V.w !== W || V.h !== H) add('FAIL', 'size', `VIDEO is ${V.w}x${V.h}, expected ${W}x${H} for format '${FMT}' (${F.aspect})`);
  else add('OK', 'size', `${V.w}x${V.h} (${FMT}, ${F.aspect}${F.scale > 1 ? ', captured at ' + F.scale + 'x' : ''})`);
  if (!(V.duration > 0)) add('FAIL', 'duration', 'VIDEO.duration missing or 0');
  else if (V.duration > F.max_duration) add('FAIL', 'duration', `${V.duration.toFixed(2)}s is over the ${F.max_duration}s limit for '${FMT}'`);
  else if (F.soft_duration && V.duration > F.soft_duration) add('WARN', 'duration', `${V.duration.toFixed(2)}s; allowed (max ${F.max_duration}s) but under ${F.soft_duration}s usually performs better`);
  else add('OK', 'duration', `${V.duration.toFixed(2)}s`);
  if (V.fps && ![24, 25, 30, 50, 60].includes(+V.fps)) add('WARN', 'fps', `VIDEO.fps ${V.fps} is unusual; use 30 or 60`);

  const stage = await page.evaluate(() => { const s = document.getElementById('stage'); if (!s) return null; const r = s.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });
  if (!stage) add('WARN', 'stage', 'no #stage element; the screenshot is the whole viewport');
  else if (Math.abs(stage.x) > 0.5 || Math.abs(stage.y) > 0.5 || Math.abs(stage.w - W) > 0.5 || Math.abs(stage.h - H) > 0.5)
    add('FAIL', 'stage', `#stage is at ${stage.x},${stage.y} size ${stage.w}x${stage.h} in ?render mode; must be 0,0 ${W}x${H}`);
  else add('OK', 'stage', 'positioned at 0,0, full frame');

  const fonts = await page.evaluate(async () => {
    await Promise.all([...document.fonts].map(f => f.load().catch(() => {})));
    await document.fonts.ready;
    return [...document.fonts].map(f => ({ family: f.family.replace(/["']/g, ''), status: f.status }));
  });
  const badFonts = fonts.filter(f => f.status !== 'loaded');
  if (badFonts.length) add('FAIL', 'fonts', 'not loaded: ' + [...new Set(badFonts.map(f => f.family))].join(', '));
  else add('OK', 'fonts', fonts.length ? [...new Set(fonts.map(f => f.family))].join(', ') : 'no @font-face declared');

  // ---- sample times ----
  let times = [];
  if (opt.times) times = String(opt.times).split(',').map(Number);
  else {
    const tl = TLD;
    if (tl && tl.scenes) {
      // only the scenes this page draws (long-form projects split chapters into pages)
      const mine = tl.scenes.filter(s => (s.page || 'index.html') === PAGE);
      if (!mine.length) add('WARN', 'page', `no scene in timeline.json uses page ${PAGE}`);
      const many = mine.length > 24;   // long videos: sample a subset of scenes, every scene's settle time
      for (const s of mine) {
        if (many) { times.push(+Math.min(s.end - 0.05, s.start + 0.9).toFixed(3)); continue; }
        const settle = Math.min(s.end - 0.05, s.start + 0.9);
        times.push(+settle.toFixed(3), +((s.start + s.end) / 2).toFixed(3), +Math.max(s.start, s.end - 0.25).toFixed(3));
      }
    } else for (let i = 0; i < 8; i++) times.push(+((V.duration * (i + 0.5)) / 8).toFixed(3));
  }
  times = [...new Set(times)].filter(t => t >= 0 && t <= V.duration).sort((a, b) => a - b);

  // ---- determinism: same t, same pixels, in any order ----
  const shotAt = async t => { await page.evaluate(t => window.seek(t), t); return page.screenshot({ type: 'png' }); };
  const sha = b => crypto.createHash('sha1').update(b).digest('hex');
  // pixels that differ by more than a few levels (rasteriser noise of 1-2 levels on anti-aliased edges is ignored)
  const pixelDiff = (a, b) => page.evaluate(async ([a, b]) => {
    const load = s => new Promise(r => { const i = new Image(); i.onload = () => r(i); i.src = 'data:image/png;base64,' + s; });
    const [A, B] = await Promise.all([load(a), load(b)]);
    const cv = document.createElement('canvas'); cv.width = A.width; cv.height = A.height; const g = cv.getContext('2d');
    g.drawImage(A, 0, 0); const da = g.getImageData(0, 0, A.width, A.height).data;
    g.clearRect(0, 0, A.width, A.height); g.drawImage(B, 0, 0); const db = g.getImageData(0, 0, A.width, A.height).data;
    let n = 0; for (let i = 0; i < da.length; i += 4) if (Math.max(Math.abs(da[i] - db[i]), Math.abs(da[i + 1] - db[i + 1]), Math.abs(da[i + 2] - db[i + 2])) > 6) n++;
    return n;
  }, [a.toString('base64'), b.toString('base64')]);
  const probeT = times.slice(0, 6);
  const first = {};
  for (const t of probeT) first[t] = await shotAt(t);
  const mism = [];
  for (const t of [...probeT].reverse()) {
    const again = await shotAt(t);
    if (sha(again) !== sha(first[t])) { const n = await pixelDiff(first[t], again); if (n > 40) mism.push(`${t}s (${n} px)`); }
  }
  if (mism.length) add('FAIL', 'determinism (pixels)', `seek(t) drew different pixels for the same t at ${mism.join(', ')}; something depends on the previous frame or the clock`);
  else add('OK', 'determinism (pixels)', `${probeT.length} times re-seeked out of order, identical`);

  // ---- layout at sample times ----
  const layoutIssues = { clipped: [], unsafe: [], small: [], overlap: [] };
  let capSeen = 0;
  const capMode = await page.evaluate(() => (window.TIMELINE && window.TIMELINE.captions && window.TIMELINE.captions.burn === false) ? 'off' :
    ((window.STYLE && window.STYLE.captions && window.STYLE.captions.mode) || (document.getElementById('captions') ? 'pop' : 'off')));
  for (const t of times) {
    const boxes = await page.evaluate(t => {
      window.seek(t);
      const out = [];
      const stage = document.getElementById('stage') || document.body;
      const walker = document.createTreeWalker(stage, NodeFilter.SHOW_ELEMENT);
      const effOpacity = el => { let o = 1; for (let e = el; e && e !== document.documentElement; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return 0; o *= +cs.opacity; } return o; };
      const flag = (el, attr) => { for (let e = el; e; e = e.parentElement) if (e.hasAttribute && e.hasAttribute(attr)) return true; return false; };
      let n = 0;
      while (walker.nextNode()) {
        const el = walker.currentNode;
        const own = [...el.childNodes].filter(c => c.nodeType === 3).map(c => c.textContent).join('').trim();
        if (!own) continue;
        const o = effOpacity(el); if (o < 0.15) continue;
        const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) continue;
        const cs = getComputedStyle(el);
        const scale = el.offsetHeight > 0 ? r.height / el.offsetHeight : 1;
        const id = el.id ? '#' + el.id : (el.className && typeof el.className === 'string' ? el.tagName.toLowerCase() + '.' + el.className.split(' ')[0] : el.tagName.toLowerCase()) + `[${n}]`;
        n++;
        out.push({ id, text: own.slice(0, 40), x: r.x, y: r.y, w: r.width, h: r.height, px: parseFloat(cs.fontSize) * scale,
                   ignoreSafe: flag(el, 'data-safe-ignore'), offscreenOk: flag(el, 'data-offscreen-ok'), caption: flag(el, 'data-caption') });
      }
      return out;
    }, t);
    const content = await page.evaluate(() => {   // anything visible besides the background layers?
      const stage = document.getElementById('stage') || document.body; let n = 0;
      const effOpacity = el => { let o = 1; for (let e = el; e && e !== document.documentElement; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return 0; o *= +cs.opacity; } return o; };
      for (const el of stage.querySelectorAll('*')) {
        if (['bg', 'grain', 'safe'].includes(el.id) || el.closest('#safe')) continue;
        if (el.children.length && !['svg'].includes(el.tagName.toLowerCase())) { const own = [...el.childNodes].some(c => c.nodeType === 3 && c.textContent.trim()); const cs = getComputedStyle(el); if (!own && cs.backgroundColor === 'rgba(0, 0, 0, 0)' && cs.borderStyle === 'none') continue; }
        const r = el.getBoundingClientRect(); if (r.width * r.height < 400 || r.right < 0 || r.bottom < 0 || r.left > innerWidth || r.top > innerHeight) continue;
        if (effOpacity(el) > 0.15) n++;
      }
      return n;
    });
    if (!content) layoutIssues.empty = (layoutIssues.empty || []).concat(t.toFixed(2) + 's');
    if (boxes.some(b => b.caption)) capSeen++;
    for (const b of boxes) {
      const tag = `${t.toFixed(2)}s ${b.id} "${b.text}"`;
      if (!b.offscreenOk && (b.x < -2 || b.y < -2 || b.x + b.w > W + 2 || b.y + b.h > H + 2)) layoutIssues.clipped.push(tag);
      else if (!b.ignoreSafe && (b.x < SAFE.left - 2 || b.x + b.w > SAFE.right + 2 || b.y < SAFE.top - 2 || b.y + b.h > SAFE.bottom + 2))
        layoutIssues.unsafe.push(`${tag} box ${Math.round(b.x)},${Math.round(b.y)} ${Math.round(b.w)}x${Math.round(b.h)}${b.caption ? ' (CAPTION)' : ''}`);
      if (b.px < MIN_TEXT_PX && !b.ignoreSafe) layoutIssues.small.push(`${tag} ${b.px.toFixed(0)}px`);
    }
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], c = boxes[j];
      const ix = Math.max(0, Math.min(a.x + a.w, c.x + c.w) - Math.max(a.x, c.x));
      const iy = Math.max(0, Math.min(a.y + a.h, c.y + c.h) - Math.max(a.y, c.y));
      const inter = ix * iy, small = Math.min(a.w * a.h, c.w * c.h);
      const nested = (ix >= Math.min(a.w, c.w) - 1 && iy >= Math.min(a.h, c.h) - 1); // child text inside its parent
      if (small > 0 && inter / small > 0.2 && !nested && !(a.ignoreSafe || c.ignoreSafe)) layoutIssues.overlap.push(`${t.toFixed(2)}s "${a.text}" x "${c.text}"`);
    }
  }
  if (layoutIssues.empty) add('FAIL', 'visible content', 'nothing visible on screen at ' + layoutIssues.empty.join(', ') + ' (scenes hidden? check display/opacity)');
  else add('OK', 'visible content', 'something on screen at every sample time');
  const cap = (arr, n = 8) => arr.slice(0, n).join('\n      ') + (arr.length > n ? `\n      ... +${arr.length - n} more` : '');
  if (layoutIssues.clipped.length) add('FAIL', 'text inside frame', 'text cut off by the frame edge:\n      ' + cap(layoutIssues.clipped));
  else add('OK', 'text inside frame', `${times.length} sample times`);
  if (capMode !== 'off') {
    if (!capSeen) add('FAIL', 'captions', `caption mode is '${capMode}' but no caption was visible at any sample time (most Shorts are watched muted)`);
    else add('OK', 'captions', `visible at ${capSeen}/${times.length} sample times`);
  }
  const capUnsafe = layoutIssues.unsafe.filter(s => s.includes('(CAPTION)'));
  if (capUnsafe.length) add('FAIL', 'captions in safe zone', 'captions outside the safe zone (covered by player/Shorts UI):\n      ' + cap(capUnsafe));
  const otherUnsafe = layoutIssues.unsafe.filter(s => !s.includes('(CAPTION)'));
  if (otherUnsafe.length) add('WARN', 'safe zone', `text outside x ${SAFE.left}-${SAFE.right}, y ${SAFE.top}-${SAFE.bottom} (covered by the UI / title-safe); add data-safe-ignore if decorative:\n      ` + cap(otherUnsafe));
  else add('OK', 'safe zone', 'all text inside');
  if (layoutIssues.small.length) add('WARN', 'text size', `text under ${MIN_TEXT_PX}px is hard to read (phones, TVs):\n      ` + cap(layoutIssues.small));
  if (layoutIssues.overlap.length) add('WARN', 'overlap', 'text boxes overlap (check the stills):\n      ' + cap(layoutIssues.overlap));

  if (errors.length) add('FAIL', 'page errors', [...new Set(errors)].join('\n      '));
  if (consoleErr.length) add('WARN', 'console errors', [...new Set(consoleErr)].slice(0, 6).join('\n      '));
  return finish(browser);
})().catch(e => { console.error(e); process.exit(1); });

async function finish(browser) {
  await browser.close();
  const fails = results.filter(r => r.level === 'FAIL').length, warns = results.filter(r => r.level === 'WARN').length;
  for (const r of results) console.log(`${r.level.padEnd(4)}  ${r.check}${r.detail ? ': ' + r.detail : ''}`);
  console.log(`\n${fails ? 'PAGE CHECK FAILED' : 'PAGE CHECK PASSED'}  (${fails} fail, ${warns} warn)`);
  if (opt.json) fs.writeFileSync(opt.json, JSON.stringify({ pass: !fails, fails, warns, results }, null, 2));
  process.exit(fails ? 1 : 0);
}
