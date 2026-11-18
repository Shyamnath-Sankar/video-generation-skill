# 3b1b-math: visual math explainer (3Blue1Brown-inspired)

Calm, precise, curious. The math *moves* so the viewer sees why it's true. Built in the spirit of Manim, the open-source library 3Blue1Brown's videos are made with. Working demo: `demo/` (odd numbers sum to squares), builds as a Short and as 16:9 (the native format of this kind of video: geometry left, algebra in a right column).

## Look
- **Canvas** `#121417`, flat, no grain, no vignette. Lots of negative space.
- **Colour has meaning**: blue `#58C4DD`, yellow `#F7D96F`, green `#83C167`, red `#FC6255`, teal `#5CD0B3`, brown `#9C7A5B`. One colour = one quantity, everywhere (the term "3" and its 3 tiles are both yellow). White `#ECECEC` for neutral text.
- **Type**: Computer-Modern look via KaTeX fonts: `KaTeX_Main` for text and numbers, `KaTeX_Math` (italic) for variables. Equations in SVG `<text>` with a thin same-colour stroke. Sizes: equations 100–130 px when they are the subject, 60–80 px as labels.
- **Shapes**: thin-stroked geometry (4–7 px), fills at ~70% opacity with the same-colour stroke, rounded tiles (rx 10), number planes/axes (`K.plane`), curly braces with labels.
- **Captions**: `minimal` mode, serif, 56 px, unspoken words dimmed. Quiet; the math is the star.

## Motion
- Ease: Manim's `smooth` (`K.smooth`), ~0.8–1.2 s per action. **No overshoot, no bounce, no blur.**
- Vocabulary: **Write** text (`K.write`, staggered term by term), **Create** strokes (`K.draw`), **Transform** persistent objects to new positions/sizes instead of cutting, **Indicate** with a brief scale + colour lift (`K.thereAndBack`), **FadeIn/FadeOut** with a slight shift.
- One persistent world: the equation from the hook *becomes* the label in the next scene. Scene transition `fade-transform` only when the subject really changes.
- Something is always being drawn; avoid static holds over 2 s (draw a brace, highlight a term).

## Recipes
- **Visual proof**: show the claim as an equation with a yellow `?` → build the geometry term by term on spoken numbers → outline + labels on the key word → swap `?` for the answer.
- **Function / graph**: `K.plane` grid (blue lines at 55% opacity, white axes) → `K.draw` the curve → a dot rides the curve (`path.getPointAtLength`) with a value label.
- **Generalise**: end on the general formula written under the specific example; variable in yellow.

## Don't
- Pi-creature characters or any 3Blue1Brown branding, intro or logo.
- Gradients, glows, emoji, stock icons, bouncing.
- Music louder than a whisper: if the user wants music, `chill` at `level_db: -14`.
