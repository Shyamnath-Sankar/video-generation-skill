---
name: yt-video
description: Make YouTube videos as code, both Shorts (9:16, 1080x1920) and long-form (16:9, 1080p or 4K) - HTML pages animated by seek(t), narrated with OmniVoice (local TTS with voice cloning and voice-design instructions, reached over MCP), optional code-generated music, rendered to MP4 with ffmpeg and verified by script. Includes style presets (3Blue1Brown-like math, KodeKloud-like DevOps, Fireship-like dev news, Kurzgesagt-like flat science, Vox-like documentary, ByteByteGo-like diagrams, hype captions, editorial), chapters, SRT captions and thumbnails for long videos. Use when someone asks for a Short, a reel, a vertical video, a YouTube explainer, an animated or motion-graphics video, or wants a script or topic turned into a narrated video.
---

# YouTube videos from code: Shorts and long-form

You build a video the way a motion designer would, but in code: HTML pages draw any frame from a time value, the narration sets the timing, and scripts render, mix and **prove** the result is valid before anyone uploads it.

```
script.json ──► OmniVoice (MCP) ──► voice/*.wav ──► timeline.py ──► timeline.js ─────────┐
   │ format: short | long | long-4k                                                         ▼
   └─ style preset ─► style.css / style.js ─────────────────────► page(s).html (seek(t), K.layout per format)
                                                                     │ check_page ► stills ► render (cached chunks)
music (only if asked) ─► make_music.py ─┐                            ▼
sound effects (CC0) ─────────────────────┴─► mix_audio.py ─► mix.wav ─► mux ─► final.mp4 ─► verify_video.py
                                          (long-form also: chapters.txt, captions.srt, thumbnail.jpg)
```

`$SKILL` below means this skill's folder. Everything runs through one CLI: `python3 $SKILL/scripts/short.py <command>`.

## Formats
| | `short` | `long` | `long-4k` |
|---|---|---|---|
| Frame | 1080×1920 (9:16) | 1920×1080 (16:9) | page 1920×1080, output 3840×2160 |
| Length | ≤ 180 s (best < 60 s) | any (typ. 5–15 min) | any |
| Safe zone | x 60–940, y 288–1440 (Shorts UI) | x 96–1824, y 54–1026 (title-safe) | same as long |
| Captions | burned in (style look) | `captions.srt` for YouTube; burn-in optional | same as long |
| Extras | — | chapters, one page per chapter, thumbnail 1280×720 | same |

Profiles live in `engine/formats.json`. Pages use `K.W`/`K.H` and a `K.layout({short, long})` table, so one project can be built in either format. **Read `reference/long-form.md` for any 16:9 video.**

## What's in the folder
| Path | What it is |
|---|---|
| `scripts/short.py` | The pipeline CLI: doctor, styles, init, style, kit, timeline, check, stills, thumb, music, mix, render, mux, verify, build |
| `scripts/timeline.py` | Voice durations → scene timings, word cues, captions, sfx cues, beat snapping, page segments, chapters, SRT |
| `scripts/import_voice.py` | Bring an OmniVoice clip in: convert, trim silence, reject broken TTS takes |
| `scripts/make_music.py` | Synthesised background music (7 moods), on the beat grid, any length. **Only when the user asks for music** |
| `scripts/mix_audio.py` | Voice + music (ducked) + sfx → −14 LUFS, true peak ≤ −1.5 dBTP |
| `scripts/verify_video.py` | The correctness gate: size, aspect, codec, fps, frame count, A/V sync, loudness, black/frozen frames, chapters, safe-zone sheet |
| `engine/formats.json` | Format profiles (sizes, safe zones, caption defaults, limits) |
| `engine/render.cjs` | Playwright capture → ffmpeg H.264 (motion blur, frame ranges, 2× capture for 4K), contact sheets |
| `engine/check_page.cjs` | Pre-render checks: page contract, fonts, determinism, safe zone, captions, text size, empty frames |
| `engine/kit.js` | The animation toolkit (springs, cues, captions, transitions, layouts per format, Manim-like draw/write) |
| `template/` | A complete working video (editorial style) that builds in both formats |
| `styles/` | 8 style presets: `style.json` + `STYLE.md`; `3b1b-math` and `kodekloud-devops` have full demos in both formats |
| `assets/` | Fonts (OFL/MIT) and CC0 sound effects |
| `reference/` | Read these when you reach the matching step (table at the end) |

## Workflow

### 0. Set up (first time on a machine)
```bash
bash $SKILL/scripts/setup.sh          # playwright + chromium into ~/.cache/yt-video, numpy/scipy
python3 $SKILL/scripts/short.py doctor
```

### 1. Brief (one round of questions, then work)
Ask in **one** message (AskUserQuestion when available); skip what the user already said:
1. **Format**: Short (9:16) or long-form (16:9, 1080p or 4K). Infer it when obvious ("a Short", "a 10-minute video").
2. **Topic and the one thing** the viewer must remember. A script, article or URL if they have one.
3. **Style**: `short.py styles`. Default `editorial`. Read `styles/<name>/STYLE.md` once chosen.
4. **Voice**: clone (reference clip + its transcript), design ("female, young adult, low pitch, british accent"), or the default. See `reference/voice-omnivoice.md`.
5. **Music**: off unless they ask. If yes: mood (`make_music.py --list`). Never add music they didn't ask for.
6. **Length**: Shorts 20–45 s (max 180). Long-form: their target; plan chapters.

### 2. Write the script, then get approval
Read `reference/shorts-design.md` (Shorts) or `reference/long-form.md` (16:9). Write `script.json` (schema in `reference/page-contract.md`): one idea per scene; every scene's `visual` names **which spoken word** each visual change lands on; long-form scenes get `chapter` titles and, for longer videos, a `page` per chapter. Show the user the scene table (id, line, visual, cue words; chapters for long-form) and wait for approval or edits before generating audio. **Never invent facts, numbers, quotes or results**; example values inside UI mockups are fine and get listed as illustrative.

### 3. Create the project
```bash
python3 $SKILL/scripts/short.py init videos/<slug> --style <style> --format short|long|long-4k
```
Copies the template (or the style's `demo/`), `kit.js`, fonts and style tokens. Put your approved `script.json` in place (keep its `format`).

### 4. Narration with OmniVoice (MCP) → `voice/<scene-id>.wav`
Follow `reference/voice-omnivoice.md`: find the OmniVoice MCP tools, generate **one clip per scene** with the same voice settings, then import each:
```bash
python3 $SKILL/scripts/import_voice.py <clip> videos/<slug> <scene-id> --text "<the line>"
```
It fails on silent, clipped, or implausibly fast/slow takes — regenerate those. If OmniVoice is not reachable, say so; you can still build visuals on estimated timings and add the voice later.

### 5. Timeline
```bash
python3 $SKILL/scripts/short.py timeline videos/<slug>
```
Writes `timeline.js` (scene and **word** times, segments, chapters) plus `out/captions.srt` and, with chapters, `out/chapters.txt`. Visuals hit words through `K.cue('scene', 'word')`.

### 6. Build the page(s)
Read `reference/page-contract.md`, `reference/kit-api.md`, `reference/scene-patterns.md` and the style's `STYLE.md`. Give every layout a `K.layout({short, long})` entry when the video might exist in both formats. Every visual change sits on a cue word.

### 7. Check before rendering (cheap, catches most mistakes)
```bash
python3 $SKILL/scripts/short.py check  videos/<slug>      # every page must PASS
python3 $SKILL/scripts/short.py stills videos/<slug>      # out/stills*.png, safe zone in red
```
**Look at the stills yourself.** Fix anything empty, clipped, overlapping, unreadable, off-style, or not matching its word. Frame 0 must already show the hook.

### 8. Music (only if asked) and mix
```bash
python3 $SKILL/scripts/short.py music videos/<slug>       # no-op when music is off
python3 $SKILL/scripts/short.py mix   videos/<slug>
```
See `reference/music-and-sound.md`.

### 9. Draft → review → final
```bash
python3 $SKILL/scripts/short.py build videos/<slug> --draft   # 30 fps, no motion blur, 1080p: fast review copy
python3 $SKILL/scripts/short.py build videos/<slug> --final   # motion blur, crf 16, 4K when long-4k
```
`build` runs timeline → check → music → mix → render → mux → verify and stops at the first failure. Renders are chunked and cached, so a re-build after an edit only redoes what changed. Send the draft first; say how long the final will take before starting it (long-form finals can take a while; run them in the background).

### 10. Verify and deliver
`verify_video.py` runs inside `build`; the MP4 is only done when it prints **VERIFY PASSED**. Open `out/verify_sheet_<mode>.png` (frame 0 + one frame per scene, UI/safe zones in red) and look at it. `reference/verification.md` explains every check.

For long-form also run `short.py thumb videos/<slug>` (or render a dedicated `thumbnail.html`).

Deliver: the MP4, the project folder (`index.html` previews in a browser with the real soundtrack), and a short note: scenes or chapters, what is illustrative, voice settings, music mood (or "no music"), the verify summary (LUFS, true peak, duration); for long-form also `chapters.txt`, `captions.srt` and the thumbnail. **You can't hear**: give the user timestamps to check by ear (the hook, the busiest sfx moment, the loudest music moment, each chapter start).

## Rules that matter most
- `seek(t)` is a pure function of time. No `Math.random`, `Date.now`, CSS animations/transitions or timers in the render path. The checker enforces this.
- Text stays inside the format's safe zone. Never hard-code 1080/1920: use `K.W`, `K.H`, `K.SAFE`, `K.layout`.
- Something meaningful is on screen at frame 0; something moves every 1–2 s (Shorts) or every few seconds (long-form).
- Visual hits land on spoken words (`K.cue`), not on guessed times.
- Music only on request. Sound effects follow the style default (the user can turn them off).
- Styles are *inspired by* the creators named; never use their logos, mascots, characters, intros or names on screen.
- Never say the audio "sounds good" — report the measured numbers and the timestamps to check.

## Reference files
| Read when | File |
|---|---|
| Writing a Short | `reference/shorts-design.md` |
| Anything 16:9 / long-form | `reference/long-form.md` |
| Building pages, script.json schema | `reference/page-contract.md` |
| Using the toolkit | `reference/kit-api.md` |
| Designing scenes | `reference/scene-patterns.md` |
| Picking / making a style | `styles/README.md`, `styles/<name>/STYLE.md` |
| Generating narration | `reference/voice-omnivoice.md` |
| Music and sound effects | `reference/music-and-sound.md` |
| A check failed | `reference/verification.md`, `reference/troubleshooting.md` |
