# video-generation-skill

The `yt-video` skill used by my daily explainer video pipeline: HTML pages animated by `seek(t)`, narrated scene by scene, rendered to MP4 with Playwright + ffmpeg, with built-in verification gates.

## Contents

- `yt-video/` - the complete skill: `SKILL.md` and `README.md` inside explain the workflow; includes `reference/`, `scripts/`, `engine/`, `template/`, `styles/`, and bundled `assets/` (fonts and sound effects).

## Source and licenses

- The skill itself was made by me (Shyamnath Sankar) with Claude.
- Bundled third-party assets keep their own licenses, included in the tree:
  - Fonts: SIL OFL 1.1 (`yt-video/assets/fonts/OFL-*.txt`), KaTeX fonts (`yt-video/assets/fonts/LICENSE-KaTeX.txt`) - see `yt-video/assets/fonts/LICENSES.md`
  - Sound effects: CC0 - see `yt-video/assets/sfx/LICENSES.md`
  - Rendering approach adapted from Bart's motion-graphics skills (MIT) - see `yt-video/NOTICE.md`
- Style presets are inspired by well-known explainer channels (3Blue1Brown, Kurzgesagt, Vox and others). They contain no logos, characters or assets from those creators and imply no affiliation.
