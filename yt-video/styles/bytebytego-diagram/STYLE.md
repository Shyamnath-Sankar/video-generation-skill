# bytebytego-diagram: system-design diagrams (ByteByteGo-inspired)

Clear and structured: a diagram assembles step by step while the voice walks through it.

## Look
- White canvas with a faint dot grid (`background.kind: dots`).
- Boxes: pastel fills (`#E0E7FF`, `#FEF3C7`, `#D1FAE5`, `#FEE2E2`) with a coloured header strip and dark text, radius 16, thin 3 px outline in a darker shade of the fill.
- Arrows: 4 px dark grey with arrowheads; numbered step circles (indigo `#4F46E5` with white numbers) on each arrow.
- Geist 800 for labels, JetBrains Mono for endpoints/protocols.
- Captions: `pop`, dark text, white outline, indigo active word.

## Motion
- `slide` transition between diagrams, but within one diagram nothing cuts: boxes pop in, arrows draw (`K.draw`) on their step number, the numbered circle pops at the arrow's midpoint.
- After the full diagram is built, a highlight (packet or glow ring drawn on canvas) traces the path once from step 1 to the last.

## Recipes
- **"How X works"**: 4–6 numbered steps, vertical flow top→bottom (9:16), each step on its spoken number.
- **Comparison**: two mini-diagrams stacked top/bottom with the difference highlighted.

## Don't
- The ByteByteGo logo or name, copying their exact diagrams. More than ~6 boxes on screen at once.
