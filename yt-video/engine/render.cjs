#!/usr/bin/env node
/* render.cjs: turn a seek(t) page into a silent 9:16 H.264 MP4 (or a contact sheet of stills).

   Video:   node render.cjs page.html out.mp4 [--fps 30] [--sub 4] [--workers 2] [--crf 16] [--from 0] [--to 5] [--ff 0 --tf 150] [--scale 2] [--png]
   Stills:  node render.cjs page.html sheet.png --stills 0.5,1.2,3 [--safe] [--cols 3] [--width 360]

   --sub N   motion blur: N sub-frames spread over a 180-degree shutter, averaged (1 = off, use for drafts)
   --ff/--tf exact frame range [ff, tf) (used by chunked renders; overrides --from/--to)
   --scale N capture at N x the page size (long-4k: a 1920x1080 page -> 3840x2160 video)
   --png     lossless frame capture (slower; default is JPEG q95, visually identical after H.264)
   --safe    draw the Shorts safe-zone overlay on the stills (adds ?safe to the page URL)

   Needs: playwright (NODE_PATH pointing at a node_modules that has it) and ffmpeg on PATH.
   Adapted from Bart's motion-graphics render.mjs (MIT, github.com/Barty-Bart/motion-graphics). */
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { pathToFileURL } = require('url');

function parseArgs(argv) {
  const pos = [], opt = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const k = a.slice(2);
      const v = argv[i + 1];
      if (v === undefined || v.startsWith('--')) opt[k] = true; else { opt[k] = v; i++; }
    } else pos.push(a);
  }
  return { pos, opt };
}
const { pos, opt } = parseArgs(process.argv.slice(2));
const [html, out] = pos;
if (!html || !out) {
  console.log('usage: node render.cjs page.html out.mp4 [--fps 30] [--sub 4] [--workers 2] [--crf 16] [--from s] [--to s]\n' +
              '       node render.cjs page.html sheet.png --stills 0.5,1.2,3 [--safe] [--cols 3] [--width 360]');
  process.exit(2);
}
const run = (args, quiet = false) => new Promise((res, rej) => {
  const p = spawn('ffmpeg', args, { stdio: quiet ? 'ignore' : ['ignore', 'inherit', 'inherit'] });
  p.on('close', c => (c ? rej(new Error('ffmpeg exited ' + c)) : res()));
});
const query = ['render', opt.safe ? 'safe' : null].filter(Boolean).join('&');
const url = pathToFileURL(path.resolve(html)).href + '?' + query;

(async () => {
  const browser = await chromium.launch({ args: ['--allow-file-access-from-files', '--disable-gpu-vsync', '--font-render-hinting=none'] });
  const pageErrors = [];

  const SCALE = Math.max(1, +(opt.scale || 1));
  async function openPage(V) {
    const page = await browser.newPage({ viewport: V ? { width: V.w, height: V.h } : { width: 1080, height: 1920 }, deviceScaleFactor: V ? SCALE : 1 });
    page.on('pageerror', e => pageErrors.push(e.message));
    page.on('requestfailed', r => pageErrors.push('failed to load ' + r.url()));
    await page.goto(url);
    await page.waitForFunction(() => window.VIDEO && typeof window.seek === 'function', null, { timeout: 30000 });
    // optional async setup (baking simulations, decoding images)
    await page.evaluate(() => (window.READY && typeof window.READY.then === 'function') ? window.READY : null);
    const bad = await page.evaluate(async () => {
      await Promise.all([...document.fonts].map(f => f.load().catch(() => {})));
      await document.fonts.ready;
      return [...document.fonts].filter(f => f.status !== 'loaded').map(f => f.family);
    });
    if (bad.length) {
      const msg = 'fonts did not load (a fallback font would be rendered): ' + [...new Set(bad)].join(', ');
      if (!opt['allow-font-fallback']) { console.error('ERROR: ' + msg); await browser.close(); process.exit(1); }
      console.warn('WARNING: ' + msg);
    }
    return page;
  }

  const probe = await openPage(null);
  const V = await probe.evaluate(() => ({ ...window.VIDEO }));
  await probe.close();
  if (!V.w || !V.h || !V.duration) { console.error('ERROR: window.VIDEO needs w, h and duration'); process.exit(1); }
  const OK_SIZES = ['1080x1920', '1920x1080'];
  if (!OK_SIZES.includes(`${V.w}x${V.h}`)) console.warn(`WARNING: page is ${V.w}x${V.h}; YouTube formats here are 1080x1920 (Shorts) and 1920x1080 (long-form)`);

  const shot = async (page, t, type) => {
    await page.evaluate(t => window.seek(t), t);
    return type === 'png' ? page.screenshot({ type: 'png' }) : page.screenshot({ type: 'jpeg', quality: 95 });
  };

  // ---------- stills / contact sheet ----------
  if (opt.stills) {
    const times = String(opt.stills).split(',').map(Number).filter(x => isFinite(x));
    const page = await openPage(V);
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stills-'));
    try {
      for (let i = 0; i < times.length; i++) {
        fs.writeFileSync(path.join(dir, String(i).padStart(3, '0') + '.png'), await shot(page, times[i], 'png'));
      }
      const cols = Math.min(+(opt.cols || 4), times.length), rows = Math.ceil(times.length / cols);
      const w = +(opt.width || (V.w > V.h ? 480 : 360));
      // label every still with its time so the sheet can be read back against the timeline
      const labels = times.map(t => t.toFixed(2) + 's');
      const inputs = [], filters = [];
      times.forEach((_, i) => {
        inputs.push('-i', path.join(dir, String(i).padStart(3, '0') + '.png'));
        filters.push(opt.nolabel ? `[${i}:v]scale=${w}:-2:flags=lanczos[s${i}]` :
                     `[${i}:v]scale=${w}:-2,drawbox=x=0:y=0:w=${Math.round(w * 0.42)}:h=${Math.round(w * 0.1)}:color=black@0.7:t=fill,` +
                     `drawtext=text='${labels[i]}':x=8:y=6:fontsize=${Math.round(w * 0.065)}:fontcolor=white[s${i}]`);
      });
      const pad = cols * rows - times.length;
      for (let i = 0; i < pad; i++) filters.push(`color=c=gray:s=${w}x${Math.round(w * V.h / V.w / 2) * 2}:d=1[p${i}]`);
      const all = times.map((_, i) => `[s${i}]`).concat(Array.from({ length: pad }, (_, i) => `[p${i}]`)).join('');
      const layout = [];
      const ch = Math.round(w * V.h / V.w / 2) * 2;
      for (let i = 0; i < cols * rows; i++) layout.push(`${(i % cols) * (w + 6)}_${Math.floor(i / cols) * (ch + 6)}`);
      filters.push(`${all}xstack=inputs=${cols * rows}:layout=${layout.join('|')}:fill=gray[out]`);
      if (cols * rows === 1) filters[filters.length - 1] = `[s0]null[out]`;
      await run(['-v', 'error', '-y', ...inputs, '-filter_complex', filters.join(';'), '-map', '[out]', '-frames:v', '1', out]);
    } finally { fs.rmSync(dir, { recursive: true, force: true }); }
    await browser.close();
    if (pageErrors.length) { console.error('page errors:\n' + pageErrors.join('\n')); process.exit(1); }
    console.log('stills ->', out);
    return;
  }

  // ---------- video ----------
  const fps = +(opt.fps || V.fps || 30), sub = Math.max(1, +(opt.sub || 1));
  const workers = Math.max(1, +(opt.workers || Math.min(4, os.cpus().length)));
  const crf = String(opt.crf || 16), type = opt.png ? 'png' : 'jpeg';
  const total = Math.round(V.duration * fps);
  const fromF = opt.ff !== undefined ? Math.max(0, +opt.ff) : Math.max(0, Math.round((+(opt.from || 0)) * fps));
  const toF = Math.min(total, opt.tf !== undefined ? +opt.tf : (opt.to !== undefined ? Math.round(+opt.to * fps) : Infinity));
  const N = toF - fromF;
  if (N <= 0) { console.error('ERROR: nothing to render (check --from/--to and VIDEO.duration)'); process.exit(1); }
  const base = out.replace(/\.mp4$/i, '');
  // sRGB screenshots -> BT.709 limited range, tagged, so players show the colours you designed
  const colour = ['scale=out_color_matrix=bt709:out_range=tv', 'format=yuv420p'];
  const blur = sub > 1 ? [`tmix=frames=${sub}`, `select='eq(mod(n\\,${sub})\\,${sub - 1})'`, `setpts=N/(${fps}*TB)`] : [];
  const vf = [...blur, ...colour].join(',');
  const enc = ['-c:v', 'libx264', '-profile:v', 'high', '-preset', 'medium', '-crf', crf, '-g', String(fps * 2), '-bf', '2',
               '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv'];
  const t0 = Date.now(); let done = 0;
  const per = Math.ceil(N / workers), segs = [];
  if (!opt.quiet) console.log(`rendering ${N} frames @ ${fps} fps (${V.w * SCALE}x${V.h * SCALE}), ${sub} sub-frame(s), ${workers} worker(s) -> ${out}`);
  await Promise.all(Array.from({ length: workers }, async (_, w) => {
    const a = fromF + w * per, b = Math.min(toF, a + per); if (a >= b) return;
    const seg = `${base}_seg${w}.mp4`; segs[w] = seg;
    const page = await openPage(V);
    const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps * sub), '-c:v', type === 'png' ? 'png' : 'mjpeg', '-i', '-',
      '-vf', vf, '-r', String(fps), ...enc, seg], { stdio: ['pipe', 'inherit', 'inherit'] });
    let code = null; const closed = new Promise(r => ff.on('close', c => { code = c; r(); }));
    ff.stdin.on('error', () => {});
    for (let f = a; f < b && code === null; f++) {
      for (let s = 0; s < sub && code === null; s++) {
        const t = (f + (sub > 1 ? (s / sub) * 0.5 : 0)) / fps;   // 180-degree shutter
        const buf = await shot(page, t, type);
        if (!ff.stdin.write(buf)) await Promise.race([new Promise(r => ff.stdin.once('drain', r)), closed]);
      }
      if (!opt.quiet && (++done % 15 === 0 || done === N)) process.stdout.write(`\r  ${done}/${N} frames  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    }
    ff.stdin.end(); await closed; await page.close();
    if (code !== 0) throw new Error(`ffmpeg failed on segment ${w} (exit ${code})`);
  }));
  const list = base + '_segs.txt';
  fs.writeFileSync(list, segs.filter(Boolean).map(s => `file '${path.resolve(s).replace(/'/g, "'\\''")}'`).join('\n'));
  await run(['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', list, '-c', 'copy', '-movflags', '+faststart', out]);
  segs.filter(Boolean).forEach(s => fs.rmSync(s, { force: true })); fs.rmSync(list, { force: true });
  await browser.close();
  console.log(`${opt.quiet ? '' : '\n'}video -> ${out}  (${N} frames, ${((Date.now() - t0) / 1000).toFixed(0)}s)`);
  if (pageErrors.length) { console.error('page errors while rendering:\n' + [...new Set(pageErrors)].join('\n')); process.exit(1); }
})().catch(e => { console.error(e); process.exit(1); });
