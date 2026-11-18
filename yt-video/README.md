# yt-video skill

Make YouTube videos from code, **Shorts (9:16)** and **long-form (16:9, 1080p or 4K)**: HTML pages animated by `seek(t)`, narrated by your local **OmniVoice** (voice cloning / voice design over MCP), optional code-generated music, rendered to MP4 with ffmpeg and **verified** by script.

## Install
1. Copy this folder to `~/.claude/skills/yt-video` (or your project's `.claude/skills/`).
2. Install the tools once: `bash scripts/setup.sh` (Playwright + Chromium into `~/.cache/yt-video`, numpy/scipy). You also need Node 18+, Python 3.9+ and ffmpeg with libx264.
3. `python3 scripts/short.py doctor` should print `ready`.
4. Connect your OmniVoice MCP server to Claude.

## Use
Ask Claude, for example:
- *"Make a 30-second Short on what a Kubernetes pod is, KodeKloud style, in my cloned voice (here's a clip)."*
- *"Make an 8-minute 3Blue1Brown-style video on why the harmonic series diverges, 4K, with calm music, chapters and a thumbnail."*

It writes the script, asks you to approve it, generates the narration scene by scene, builds the pages, checks stills, renders a draft, then a final, and verifies the MP4.

Manual pipeline:
```bash
python3 scripts/short.py init videos/pod --style kodekloud-devops --format short     # or long / long-4k
# generate voice/<scene>.wav with OmniVoice, then for each: scripts/import_voice.py clip.wav videos/pod <scene> --text "..."
python3 scripts/short.py build videos/pod --draft
python3 scripts/short.py build videos/pod --final     # -> videos/pod/out/final.mp4, VERIFY PASSED
python3 scripts/short.py thumb videos/pod             # long-form thumbnail (1280x720)
```
Open `videos/pod/index.html` in a browser to preview with the real soundtrack and a safe-zone toggle.

## Formats
| Format | Output | Notes |
|---|---|---|
| `short` | 1080×1920 | ≤ 180 s, captions burned in, Shorts UI safe zone |
| `long` | 1920×1080 | chapters → `out/chapters.txt`, `out/captions.srt`, one page per chapter, cached chunk renders |
| `long-4k` | 3840×2160 | same pages captured at 2× |

## Styles
`editorial` (default) · `3b1b-math` · `kodekloud-devops` · `fireship-dev` · `flat-science` · `vox-doc` · `bytebytego-diagram` · `hype-captions`. See `styles/README.md`. `3b1b-math` and `kodekloud-devops` include demos that build in every format.

## Layout
`SKILL.md` (workflow) · `reference/` (Shorts design, long-form, page contract, kit API, scene patterns, OmniVoice, music, verification, troubleshooting) · `scripts/` (pipeline) · `engine/` (formats, renderer, checker, kit.js) · `template/` · `styles/` · `assets/` (fonts, CC0 sfx). Credits in `NOTICE.md`.
