# hype-captions: big-caption creator style

Maximum retention: the words *are* the visual. Huge uppercase captions, one or two words at a time, punchy zooms.

## Look
- Black background with a heavy vignette and grain.
- Captions: `box` mode, Anton uppercase 110 px, white with a black outline, the active word in a yellow `#FFE600` box tilted −2°. Centre ~y 1240.
- Secondary accent per moment: green `#22FF66` for "yes/money/good", red `#FF2D55` for "no/bad", cyan `#00C2FF` for neutral highlights.
- Supporting visuals are simple and big above the captions: an icon, a number, a one-word label, a progress bar.

## Motion
- `punch` transitions: hard cut with a zoom settle; occasional "camera shake" on emphasis words (seeded noise offset 4–8 px for 0.2 s).
- Every emphasised word gets a punch (scale 1.12 → 1) and optionally a pop sound via `sfx_at`.
- Scenes 2–4 s; keep total under 40 s.

## Don't
- Copy a specific creator's caption preset, face or catchphrases. Emoji spam. Claims of income/results the user can't back up.
