# Verification: what is checked, why, and how to fix it

Two gates. Both exit non-zero on FAIL, and `short.py build` stops there.

## Gate 1: `check_page.cjs` (before rendering, seconds)
```bash
python3 $SKILL/scripts/short.py check <proj>        # writes out/check.json
```
| Check | FAIL / WARN means | Fix |
|---|---|---|
| page contract | `window.VIDEO`/`window.seek` missing | define both at the end of the script |
| size | VIDEO doesn't match the format (1080×1920 short, 1920×1080 long) | use `K.W`/`K.H` from the timeline |
| stage | `#stage` not at 0,0 or not full size in `?render` | don't scale `#wrap` when `K.RENDER` |
| fonts | a declared font failed to load | font file missing in `assets/fonts` → re-apply the style |
| determinism (source) | `Math.random`, clock, CSS animation, timers found | `K.rng`, pure functions of `t`; move preview-only code inside `PREVIEW-START/END` |
| determinism (pixels) | same `t` drew different pixels after seeking elsewhere (rasteriser noise is ignored) | a value carried between frames: cached state, `+=` on a style, an element shown in one scene and never hidden. Reset everything from `t` |
| visible content | nothing on screen at a sample time | a scene window/transition hides everything, or `display` never set to visible |
| text inside frame | text cut by the frame edge | move it in, or mark deliberate bleed `data-offscreen-ok` |
| captions | caption mode on but no caption ever visible | words missing in timeline (no `say`?), or caption root hidden |
| captions in safe zone (FAIL) / safe zone (WARN) | text under the Shorts UI / outside title-safe | short: x 60–940, y 288–1440; long: x 96–1824, y 54–1026; decorative only: `data-safe-ignore` |
| text size | text under 34 px (short) / 28 px (long) | bigger, or drop it; small labels on scaled-down objects count too |
| overlap | two text boxes overlap | usually a layout bug; check the stills |

Long-form projects with several pages: `check` runs on each page and samples only that page's scenes; `stills` writes one sheet per page.

Then `short.py stills <proj>` and **look**: the checker can't judge taste, hierarchy, or whether a visual matches its word.

## Gate 2: `verify_video.py` (the rendered MP4)
```bash
python3 $SKILL/scripts/short.py verify <proj> --final     # or: verify_video.py file.mp4 --timeline timeline.json --fps 30 --sheet s.png
```
| Check | Requirement | Usual cause of a failure |
|---|---|---|
| container | MP4 with `moov` before `mdat` (faststart) | file not muxed with `-movflags +faststart` |
| resolution | exactly the format's output: 1080×1920, 1920×1080, or 3840×2160 | page size wrong; ffmpeg scale added by hand; wrong `--format` |
| aspect | SAR 1:1, DAR 9:16 or 16:9, no rotation flag | re-encoded from a phone file; filters changing SAR |
| codec / pixel format | H.264, yuv420p | custom ffmpeg flags |
| frame rate | constant, equal to expected | mixed-rate concat; wrong `--fps` |
| frame count | duration × fps (±1) | renderer crashed mid-segment |
| duration | 0 < d ≤ format limit (Shorts 180 s), equals timeline ±1 frame | timeline changed after render → re-render |
| audio | AAC 48 kHz stereo, same length as video ±0.1 s | mix older than the timeline → `short.py mix` then `mux` |
| loudness | −14 ±1.5 LUFS (WARN outside) | re-run `mix` (it normalises) |
| true peak | ≤ −1 dBTP (FAIL above) | `mix --tp -2` |
| hook audio | voice starts within 0.6 s (WARN) | lower `pacing.lead_in`, trim the clip |
| decode | zero decode errors | truncated/corrupt file |
| first frame | content visible at frame 0 (WARN) | start the hook animation before t=0 or show an outline state |
| black frames | no black gap ≥ 0.4 s | scene windows leave a gap; a section shown with nothing in it |
| chapters | (when the timeline has chapters) first at 0:00, ≥ 3, each ≥ 10 s (WARN) | add/merge chapters in `script.json` |
| frozen picture | nothing static ≥ 3 s short / 6 s long (WARN) | add motion: a slow camera drift, a pulse, the next element |
| contact sheet | `out/verify_sheet_<mode>.png`: frame 0 + one frame per scene, Shorts UI zones in red | — look at it |

`--json` writes the full result; `--fast` skips the decode/black/freeze scans (use only while iterating).

## What "done" means
1. `check` PASSED, stills reviewed.
2. `verify` PASSED on `out/final.mp4`, verify sheet reviewed.
3. Delivery note lists the measured LUFS / true peak / duration, illustrative content, and the timestamps to listen to.
