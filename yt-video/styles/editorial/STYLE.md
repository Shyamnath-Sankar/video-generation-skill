# editorial: kinetic editorial (default)

Confident and modern: big type, one accent, everything springs onto its word. Derived from Bart's motion-graphics explainers. Working example: `$SKILL/template/`.

## Look
- Near-black gradient `#0E0E12 → #1A1A22`, soft vignette, faint grain (0.05).
- Cream ink `#F4F1EA`, muted `#8D8A84`, **one** accent `#FF4F1A` per scene (blue `#3B5BFF`, green, yellow are secondary, max one extra per scene).
- Geist 900 for hero numbers/words (300–480 px), Geist Mono small caps kickers (`BRAIN FACT · 01`) at top-left of the safe zone.
- Cards/pills in cream with dark text; progress tracks as outlined rounded bars.
- Captions: `pop`, bold, active word in the accent.

## Motion
- Springs with a little overshoot (`[14, 0.82]`), hits land 0.05–0.1 s before the word, blur clears as things land.
- `push` transition: the next scene rises from below, the old one lifts away with a short blur, plus a whoosh.
- Interaction vocabulary: number slam, ring/progress, rows on words, cursor click, toggles, chart bars.

## Don't
- Gradients on UI chrome, glows, emoji, more than two accent colours in a scene, made-up numbers.
