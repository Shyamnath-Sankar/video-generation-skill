# flat-science: flat-vector science (Kurzgesagt-inspired)

Wonder and scale. Saturated flat shapes floating on deep gradients, slow drifting parallax, calm narration.

## Look
- Background gradient `#1B1446 → #3A1F6E` with vignette; stars or particles as small seeded dots.
- Flat shapes, no outlines, rounded geometry; light comes from flat lighter/darker shades of the same hue (no gradients on objects). Palette: amber `#FFB23F`, pink `#FF5D8F`, teal `#3FD0C9`, violet `#7B6CFF`, white.
- Nunito 900 for titles; captions `minimal`, 58 px.

## Motion
- `drift` transition: cross-fade with a slow scale through each scene (parallax feel). Layers at different depths move at different speeds (foreground ×1.6, background ×0.4).
- Gentle springs (`[10, 0.9]`), slow orbits, pulsing glows drawn on canvas once (never CSS blur).
- Scale shifts are the signature: zoom from a cell to a body to a planet across scenes.

## Recipes
- **Sense of scale**: object → zoom out by 10× per scene with a label for each level.
- **Process**: a molecule/creature/planet moves through 3 stages, each stage a colour change on its word.

## Don't
- Bird characters or any recognisable Kurzgesagt character design, the logo, or their outro.
- Hard cuts, harsh colours, cluttered frames.
