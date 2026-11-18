# video-generation-skill

The `yt-video` skill used by my daily explainer video pipeline: HTML pages animated by `seek(t)`, narrated scene by scene, rendered to MP4 with Playwright + ffmpeg, with built-in verification gates.

## Contents

- `yt-video-skill.zip` - the complete skill, exactly as supplied (workflow, styles, engine, scripts, template, fonts, sound effects). Unzip and see `SKILL.md` and `README.md` inside for usage.

## Source and licenses

- The skill itself was made by me (Shyamnath Sankar) with Claude.
- Bundled third-party assets keep their own licenses, included inside the zip:
  - Fonts: SIL OFL 1.1 (`assets/fonts/OFL-*.txt`), KaTeX fonts under `assets/fonts/LICENSE-KaTeX.txt` - see `assets/fonts/LICENSES.md`
  - Sound effects: CC0 - see `assets/sfx/LICENSES.md`
  - Rendering approach adapted from Bart's motion-graphics skills (MIT) - see `NOTICE.md` inside the zip
- Style presets are inspired by well-known explainer channels (3Blue1Brown, Kurzgesagt, Vox and others). They contain no logos, characters or assets from those creators and imply no affiliation.
