# kit.js API (`window.K`)

Load order in the page: `timeline.js` → `style.js` → `kit.js` → your script.

## Format and layout
| Call | Returns / does |
|---|---|
| `K.W`, `K.H` | page size: 1080×1920 (short) or 1920×1080 (long, long-4k) |
| `K.FORMAT`, `K.LONG` | `'short' / 'long' / 'long-4k'`, and whether it's 16:9 |
| `K.FMT`, `K.SAFE` | the format profile (`engine/formats.json`) and its safe rect `{left, top, right, bottom}` |
| `K.layout({short: {...}, long: {...}})` | the table for this format (`long-4k` falls back to `long`) |
| `K.place({id: {left: 80, top: 330, fontSize: 34, 'attr:d': 'M0 0'}, ...})` | position elements once at load; numbers become px, `attr:` sets attributes |
| `K.safeOverlay(el)` | fills `#safe` with red boxes outside the safe zone (shown with `?safe` or the preview toggle) |

## Time, easing, springs
| Call | Returns / does |
|---|---|
| `K.clamp(x,a=0,b=1)`, `K.lerp(a,b,u)` | basics |
| `K.seg(t,a,b)` | 0→1 progress of t through [a,b] |
| `K.ease` (in-out cubic), `K.eo` (out), `K.ei` (in) | easing on 0..1 |
| `K.smooth` | Manim's "smooth" rate function (3b1b feel) |
| `K.thereAndBack(x)` | 0→1→0 smoothly (press, pulse) |
| `K.backOut(x,s)` | overshoot ease |
| `K.EASE` | the style's default ease |
| `K.spring(dt, w=14, z=0.82)` | closed-form spring 0→1 at `dt` seconds after a trigger. `w` speed (8 slow, 14 normal, 22 snappy), `z` damping (1 = no overshoot, 0.6 = bouncy) |
| `K.SPRING` | the style's `[w, z]` |
| `K.track(v0, [[t, v, w?, z?], ...])` | value that springs to each new target → `f(t)` |
| `K.kf([[t0,v0],[t1,v1,ease?], ...])` | eased keyframes → `f(t)` (exact landings, cameras) |
| `K.rng(seed)` | seeded random generator → `r()` in [0,1) |

## Colour
`K.C` = style colours (`bg bg2 ink muted accent accent2 accent3 accent4 card cardInk line` + style extras). `K.mix(a,b,u)` → rgb string, `K.alpha(hex,o)` → rgba, `K.ctrack(c0, [[t, hex], ...], dur)` → colour that eases to each key.

## DOM (cached setters: cheap to call every frame)
| Call | Does |
|---|---|
| `K.$(id)` | cached `getElementById` |
| `K.st(el|id, {prop: value})` | sets style props only when changed |
| `K.text(el|id, s)` | sets textContent only when changed |
| `K.vis(t, tin, tout, {din, lin, lout, blur})` | enter/exit visibility with blur → `{o, blur, s}` |
| `K.apply(el|id, vis, extraTransform)` | applies a `vis` result (opacity, blur, scale) |
| `K.typed(str, t, t0, cps=22)` | typing substring |
| `K.count(a, b, p, dec)` | count-up string |

## Timeline and cues
| Call | Returns |
|---|---|
| `K.TL` | `window.TIMELINE` (`duration`, `fps`, `scenes`, `music`, `sfx`) |
| `K.scenes`, `K.scene(id)` | scenes: `{id, start, end, voiceStart, voiceEnd, words:[{w,s,e}], caps, accent}` |
| `K.cue(id, word, nth=0)` | absolute time the narrator **starts** that word (prefix match, punctuation/case ignored: `'lshaped'` matches "L-shaped"). Falls back to start+0.3 s with a console warning |
| `K.cueEnd(id, word)` | when that word ends |
| `K.bpm`, `K.beat(t)` → `{n, phase}`, `K.pulse(t, decay)` | beat grid when music is on (pulse = 1 on each beat, decaying) |

Put hits slightly **before** the word (`cue - 0.05…0.1`): a spring needs ~0.1 s to read as "arrived".

## SVG (Manim-like)
| Call | Does |
|---|---|
| `K.svg(tag, attrs, parent)` | create an SVG element |
| `K.draw(path, p)` | stroke draws on 0→1 ("Create") |
| `K.write(textOrPath, p)` | outline draws, then fill fades in ("Write"); stagger several elements for left-to-right writing |
| `K.flow(path, t, {n, speed, t0})` | positions of dots flowing along a path (packets on a connector) |
| `K.plane(group, {x0,y0,w,h,step,color,axis})` | NumberPlane-style grid + axes, built once |

## Frame furniture
| Call | Does |
|---|---|
| `K.background(canvas)` | draws the style background once (`flat`, `gradient`, `sky`, `grid`, `dots`, `paper`, + vignette) |
| `K.grain(canvas)` | seeded film grain, returns `draw(t)` (no-op when the style's grain is 0) |
| `K.captions(root, overrides)` | builds caption pages from timeline words, returns `draw(t)`. Modes: `pop` (bold, active word coloured + scaled), `box` (1–2 words, coloured box on the active word), `minimal` (sentence fragments, spoken words brighten), `off`. Hidden when the timeline says `captions.burn: false` (long-form default). In 16:9 the style's caption look is scaled (smaller, lower, longer lines) unless the style has `captionsLong` |
| `K.runScenes({id: fn}, transition)` | shows each `#sc-<id>` in its window with the style transition and calls `fn(t, lt, sc, el)` (`lt` = t − scene start) |
| `K.TRANSITIONS` | `push`, `fade-transform`, `pop`, `punch`, `slide`, `drift` (add your own: `(t, sc, first, last) => {o, x, y, s, blur}`) |
| `K.ready` | promise: all fonts loaded (use with `window.READY`) |
| `K.RENDER` | true when rendering (`?render`) |

## Minimal page script
```js
const C = K.C;
K.st('stage', { width: K.W + 'px', height: K.H + 'px' }); K.safeOverlay(K.$('safe'));
const L = K.layout({ short: { big: { left: 540, top: 700, fontSize: 420 } }, long: { big: { left: 640, top: 520, fontSize: 460 } } });
K.place(L);
function hook(t, lt, sc) {
  const hit = K.cue('hook', 'nine');
  const k = K.spring(t - hit + 0.08, 15, 0.7);
  K.st('big', { transform: `translate(-50%,-50%) scale(${(1.6 - 0.6 * k).toFixed(4)})`, opacity: K.eo((t - hit + 0.08) / 0.12).toFixed(3) });
}
K.background(K.$('bg'));
const grain = K.grain(K.$('grain')), caps = K.captions(K.$('captions')), scenes = K.runScenes({ hook /*, ... */ });
window.VIDEO = { w: K.W, h: K.H, duration: K.TL.duration, fps: K.TL.fps };
window.seek = t => { t = K.clamp(t, 0, VIDEO.duration); scenes(t); caps(t); grain(t); };
seek(0);
```
