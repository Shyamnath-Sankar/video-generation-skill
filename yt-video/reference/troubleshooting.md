# Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `playwright not found` | `bash $SKILL/scripts/setup.sh`, or set `SHORTS_NODE_PATH` to a `node_modules` that has playwright |
| Chromium fails to launch on Linux | `npx playwright install-deps chromium` (needs sudo) |
| `fonts did not load` | the style's font files aren't in `assets/fonts`: `short.py style <proj> <style>` copies them again |
| Text sits in the wrong place only in the render | text measured before fonts loaded → `window.READY = K.ready.then(layout)` |
| An element measures 0 wide | it was `display:none` when measured; hide with `visibility` or measure in `layout()` with it shown |
| A scene never appears | `.scene` is `display:none` in CSS; `K.runScenes` sets `display:block` — make sure the section id is `sc-<scene id>` |
| Cue lands on the wrong word | `K.cue` prefix-matches the first word starting with your text; use the full word or `nth`; check `timeline.json` words |
| Captions too fast / too many words | lower `captions.maxWords` / `maxChars` in `style.json`, re-apply the style |
| Narration and visuals drift apart | voice regenerated after the timeline → `short.py timeline` again (build does it) |
| `import_voice` rejects a take | silence, clipping, or wrong words/s: regenerate it (different seed / more steps); check the text has punctuation |
| OmniVoice tool not found | MCP server not connected to this session; ask the user to start it and enable it; continue on estimated timings meanwhile |
| Music cuts off before the end | music older than the timeline: `short.py music <proj> --force` |
| True peak FAIL | `mix_audio.py <proj> --tp -2` then `mux` |
| Render very slow | drafts: `--draft` (no motion blur); finals: raise `--workers` to the core count; avoid big CSS blurs and box-shadows |
| `ffmpeg failed on segment` | out of disk, or ffmpeg without libx264 (`short.py doctor`) |
| Colours look washed out on a phone | keep the BT.709 tags the renderer writes; don't re-encode with other tools |
| Uploaded as a regular video, not a Short | longer than 180 s, or not vertical; `verify` checks both |
| Wrong aspect in a long-form project | `script.json` → `"format": "long"`, then `timeline` (the page reads its size from the timeline) |
| Layout broken in one format | a position hard-coded in CSS: move it into the `K.layout({short, long})` table |
| Long render restarted from zero | timeline changed (new voice shifts every later scene); otherwise chunks are reused. `--fresh` forces a full re-render |
| A chunk fails | its error is printed with the page and frame range; render that range with `--from/--to` to iterate |
| Chapters not shown on YouTube | first must be 0:00, at least 3, each ≥ 10 s; `verify` reports which rule fails |
| 4K render too slow | draft in 1080p (`--draft` does this), final 4K in the background; or use `long` |
