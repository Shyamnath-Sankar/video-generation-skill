# Long-form 16:9 videos

Same pipeline as Shorts: `script.json` → OmniVoice per scene → timeline → HTML pages → render → mix → verify. What changes is the format profile, the structure, and the tooling that keeps 5–20 minute videos practical.

## Formats (`script.json` → `"format"`, or `short.py init --format`)
| Format | Page size | Output | Use |
|---|---|---|---|
| `short` | 1080×1920 | 1080×1920 | YouTube Shorts, ≤ 180 s |
| `long` | 1920×1080 | 1920×1080 | regular YouTube video (default for long-form) |
| `long-4k` | 1920×1080 | 3840×2160 | same page, captured at 2×: crisp 4K text and vectors, ~4× render time. Drafts still render at 1080p |

Profiles live in `engine/formats.json` (sizes, safe zones, caption defaults, limits, check thresholds); every script and `kit.js` read them, so pages never hard-code 1080/1920. A page can serve both formats with a layout table: `const L = K.layout({short: {...}, long: {...}})` + `K.place(...)` (see the template and both style demos).

## Frame and safe zone (16:9)
- **Title-safe**: x 96–1824, y 54–1026 (5% margins). The checker warns outside it.
- The player's controls and progress bar cover the bottom ~120 px when hovered: keep captions and key text above y 1000.
- **End screen**: YouTube end-screen elements (video/subscribe cards) cover large parts of the frame in the last 5–20 s. Plan the last scene as a calm 15–20 s outro with a simple background and the content centred-left, or a recap with nothing critical in the right half.
- Layout bands: kicker/top label y 90–140 · main content y 160–880 · captions (if burned) y ~930.
- Type: headings 72–120 px, body labels 36–56, nothing under 28 px (checked). People watch long-form on TVs and phones held sideways.

## Structure (5–15 min)
| Part | Job |
|---|---|
| Cold open (0–30 s) | The question or the payoff preview. Show, don't introduce yourself. |
| Chapters (2–4 min each) | One idea per chapter; each opens with a title card (kicker + heading) and closes with a one-line recap. |
| Pattern interrupts | Every 30–60 s change something big: a new visual metaphor, a camera move, a diagram reset, a demo. |
| Outro (15–20 s) | Land the idea, then a calm end-screen layout. |

Pacing: 140–160 words per minute (`pacing.wps` 2.5 for estimates), a visible change every few seconds (the verifier flags 6 s+ frozen). Scenes can be longer than in Shorts (5–15 s) with several cues inside.

## Chapters
Put `"chapter": "Title"` on the first scene of each chapter. `timeline.py` writes `out/chapters.txt` (`0:00 Intro`, `1:42 How it works`, …) to paste into the description, and checks YouTube's rules: the first chapter starts at 0:00, at least 3 chapters, each at least 10 s. `verify_video.py` repeats the check.

## One page per chapter
A 10-minute video in one HTML file gets unwieldy. Split it: each scene can name its page (`"page": "ch2-how.html"`); consecutive scenes on the same page form a **segment**. Each page loads the same `timeline.js`, `style.js`, `kit.js` and draws only its own scenes (`K.runScenes({...})` ignores scenes without a section on that page). `short.py check` and `stills` run per page; `render` renders each segment from its page and joins them.
- Cuts between pages are hard cuts on the segment boundary: give each chapter page its own title-card entrance, or end the previous chapter on a frame that matches the next one's first frame.
- Shared components (title card, lower third, diagram helpers) go in your own `common.js` in the project, loaded by every page.

## Rendering long videos
`short.py render` splits each segment into chunks (≤ `--chunk` seconds, default 20), renders them in parallel (`--workers`, default up to 4), caches them in `out/chunks/<mode>/` keyed by the page, the shared files and the frame range, and joins them without re-encoding.
- Re-running after an edit renders only chunks whose inputs changed. Editing one chapter page re-renders that chapter. Changing narration shifts all later times, so everything after it re-renders.
- `--fresh` ignores the cache. `--from/--to` renders a time range to preview one section.
- Rough cost on 2 cores: drafts ~10 frames/s (1 min of video ≈ 3 min), finals with motion blur ~2.5 frames/s (1 min ≈ 12 min), 4K ×4. Tell the user before starting a long final; it can run in the background.

## Captions in long-form
Default `"captions": {"burn": false}`: no burned-in captions, and `out/captions.srt` (always written) is uploaded to YouTube as subtitles. Set `burn: true` for a social-style look; the style's caption look is scaled for 16:9 (smaller, lower, longer lines) unless the style defines `captionsLong`.

## Thumbnail
`short.py thumb <proj> [--t 12.4]` renders a frame to `out/thumbnail.jpg` at 1280×720 (YouTube's size, < 2 MB). Better: build a dedicated `thumbnail.html` (same kit and style; huge 3–5 word title, one striking visual, high contrast) and run `short.py thumb <proj> --page thumbnail.html --t 0`. Thumbnails are not rendered into the video.

## Music for long videos
Only if asked, as always. Past 100 s, `make_music.py` builds the track from an intro bar plus 16-bar loops (variation A/A/B, overlap-added so reverb tails carry), so memory stays flat for any length. Consider `level_db: -14` for narration-heavy videos.

## Delivery note (long-form)
MP4 + `chapters.txt` + `captions.srt` + `thumbnail.jpg`, the verify summary, what is illustrative, and timestamps to spot-check: the cold open, each chapter start, the loudest music moment.
