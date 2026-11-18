# Style presets

| Style | Inspired by | Look in one line | Demo (short + long) |
|---|---|---|---|
| `editorial` (default) | Bart's motion-graphics explainers | near-black, cream type, one orange accent, kinetic springs, push transitions | `template/` |
| `3b1b-math` | 3Blue1Brown / Manim | dark canvas, Computer-Modern type, blue-yellow-green-red, Write/Create/Transform, no cuts | `3b1b-math/demo` |
| `kodekloud-devops` | KodeKloud | bright sky background, thick navy outlines, flat cards with hard shadows, terminals, bouncy pops | `kodekloud-devops/demo` |
| `fireship-dev` | Fireship | dark grid, yellow highlight, code on screen, punch-in cuts every 1–2 s, boxed captions | — |
| `flat-science` | Kurzgesagt | deep purple gradients, saturated flat shapes, slow parallax drift, calm captions | — |
| `vox-doc` | Vox explainers | paper texture, serif headlines, highlighter swipes, red marker circles, page slides | — |
| `bytebytego-diagram` | ByteByteGo | white dotted canvas, pastel boxes with coloured headers, numbered arrows | — |
| `hype-captions` | high-retention creator Shorts | black, giant uppercase Anton captions with a yellow box, zoom punches | — |

List them: `python3 $SKILL/scripts/short.py styles`. Apply one: `short.py init <proj> --style <name>` or `short.py style <proj> <name>`.

## What a style controls (`style.json`)
`colors` (CSS vars and `K.C`), `fonts` (display/body/mono/math → `style.css`), `weights`, `captions` (mode `pop`/`box`/`minimal`/`off`, size, y, case, colours, stroke; sizes are for 9:16), optional `captionsLong` (overrides for 16:9; otherwise the 9:16 look is scaled down and moved to y≈930), `transition` (scene change), `background` (kind, grid step, vignette, grain), `motion` (default ease and spring), `music` (default mood/bpm when the user asks for music), `sfx` (default on/off). The look of the *scenes themselves* (shapes, layouts, motion vocabulary) is described in each `STYLE.md`: read it before building.

## The line we don't cross
These presets capture a **visual language** (palette, type, motion, layout habits) so a video *feels* like that kind of explainer. They never copy identity:
- no logos, channel names, mascots or characters (no Pi creatures, no Kurzgesagt birds, no channel intros/outros, no catchphrases)
- no traced artwork, frames or thumbnails from their videos
- nothing that implies the creator made or endorsed the video

If a user asks for "exactly like X", build the style and say in one line that it is inspired by X, without their branding.

## Make a new style
1. Copy the closest `styles/<name>/` to `styles/<new>/`, edit `style.json` (fonts must exist in `scripts/style.py` → `FONT_REGISTRY`; add new OFL woff2 files to `assets/fonts` and the registry).
2. Write `STYLE.md`: look, type, colour roles, motion, scene recipes, do/don't.
3. Test: `short.py init /tmp/s --style <new>`, copy any voice clips in, `timeline`, `check`, `stills`. The checker catches caption sizes and colours that break the safe zone.
4. Optional: a `demo/` with `index.html` + `script.json` that `init` will start from.
