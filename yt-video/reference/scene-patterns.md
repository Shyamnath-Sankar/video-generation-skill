# Scene patterns

Each pattern: what it's for, how to build it with `kit.js`, and the cue to hang it on. Working examples: `template/index.html` (number slam, ring, dot grid, cursor click), `styles/3b1b-math/demo` (Write/Create/Transform, tile layers), `styles/kodekloud-devops/demo` (terminal, outlined cards, nested boxes, flowing packets, nodes, self-healing).

## Number slam (hooks, stats)
Giant number fills the frame width, lands on the word with a spring from scale 1.6–1.7 and a blur that clears.
```js
const hit = K.cue('hook', 'nine');
const k = K.spring(t - hit + 0.08, 15, 0.7);
K.st('num', { opacity: K.eo((t - hit + 0.08) / 0.12).toFixed(3), transform: `translate(-50%,-50%) scale(${(1.7 - 0.7 * k).toFixed(4)})`,
  filter: k < 0.9 ? `blur(${((1 - k) * 18).toFixed(1)}px)` : 'none' });
```
Frame 0 trick: show the number as an outline (`-webkit-text-stroke`, transparent fill) from the start and fill it on the word.

## Ring / progress / meter
SVG circle with `stroke-dasharray = 2πr`, offset `2πr·(1-p)`, `p` from `K.spring(t - cue, 7, 1)`. Count-up text follows the same `p`. Rotate −90° so it starts at 12 o'clock.

## List that builds (3 reasons, 3 steps)
Rows at fixed y (e.g. 420, 640, 860), each `K.apply(row, K.vis(t, K.cue(id, word), null), 'translateX(...)')`. Number badges pop with `K.spring(…, 16, 0.6)`. Dim earlier rows to 40% when a new one lands so the eye follows the voice.

## Bar chart / comparison
Bars grow from the baseline with `K.spring(t - cue, 10, 0.85)`; stagger 0.08 s. Only label values you can source. Two-option comparison: split the frame vertically (top / bottom halves, not left / right: the right edge is unsafe), winner gets the accent.

## Before → after (split or wipe)
Two layers stacked; a wipe line moves with `K.kf([[c0, 0], [c0 + 0.6, 1, K.ease]])`, clip the top layer with `clip-path: inset(0 0 ${(1-p)*100}% 0)`.

## Terminal / code
Dark card, mono 30–36 px, `K.typed(cmd, t, t0, cps)` + blinking caret (`Math.floor(t * 2.4) % 2`). Start typing before 0 (`t0 = -0.4`) when it is the hook. Highlight one token by wrapping it in a span coloured with the accent on its cue. Keep lines ≤ 34 characters at 34 px.

## Diagram with flow (systems, pipelines)
Outlined cards + SVG connector paths; `K.draw(path, p)` to draw connectors on their cue, `K.flow(path, t, {n:3, speed:0.9})` for packets. Nodes in a vertical stack read best in 9:16 (top → bottom), at most 4–5 boxes on screen.

## Cursor click (CTA, UI demo)
Cursor path with `K.kf` arriving 0.15 s before the word, press = `1 - 0.15 * K.thereAndBack(K.seg(t, cue - 0.1, cue + 0.1))`, the button swaps state on the word, a ring expands from the click point.

## Manim vocabulary (math / science)
- **Write**: `K.write(textEl, (t - t0) / dur)`; for left-to-right writing, split into terms and stagger `t0` by ~0.14 s.
- **Create**: `K.draw(pathEl, K.smooth(K.seg(t, a, b)))`.
- **Transform**: move/scale a persistent group with `K.lerp` + `K.smooth(K.seg(...))`; cross-fade glyph swaps (`?` → `4²`) over 0.6–0.8 s.
- **Indicate**: brief `1 + 0.12 * K.thereAndBack(...)` scale and a colour lift.
- Colour-code consistently: the same colour means the same quantity everywhere (term `3` and its tiles are both yellow).

## Map pin / location
Flat outline map (SVG path you draw or the user supplies), pin drops with a spring on the place name, a ring pulses twice. Never trace copyrighted map artwork.

## Quote / statement card
Big serif (Vox/vox-doc) or heavy sans text, words revealed on their spoken times using caption-like spans; highlighter swipe behind the key phrase: a rect whose width springs on the cue.

## Scene change carriers (when the style isn't `punch`)
- An element from scene A scales up to become scene B's background (flood).
- The key number/word moves to its new position instead of disappearing (Transform).
- A wipe bar in the accent colour crosses the frame on the change.
