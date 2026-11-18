# Music and sound

## Music: only when the user asks
`script.json` → `"music": {"enabled": false}` is the default. Set it to `true` only when the user asked for music (or approved your suggestion to add it). Never slip it in.

When on, `make_music.py` synthesises the track in code (oscillators, Karplus-Strong plucks, filtered seeded noise, a Schroeder reverb): no samples, no licences, no Content ID claims, and it is exactly as long as the video.

| Mood | BPM | Feel | Good for |
|---|---|---|---|
| `upbeat` | 116 | bright pop/house, offbeat bass, plucked arps | general explainers, editorial |
| `chill` | 84 | electric piano, soft drums | calm math/science (3b1b), diagrams |
| `lofi` | 78 | swung drums, dusty keys, vinyl crackle | study/tips, cosy topics |
| `cinematic` | 90 | wide pads, ostinato, toms | documentary, flat-science |
| `tech` | 128 | minimal techno, filtered saw arp | dev news (Fireship-like) |
| `hype` | 140 | trap: 808s, hat rolls, half-time snare | hype captions |
| `corporate` | 104 | clean, optimistic | product/tutorial |

Options in `script.json` → `music`: `mood`, `bpm`, `key` (e.g. `"A"`), `seed` (another seed = a different variation), `risers` (noise riser into accented scenes), `snap` (default true: scene changes move onto half-beats so cuts hit the groove), `level_db` (bed level vs speech, default −9).

`"accent": true` on a scene adds a crash + sub drop on its first frame (and an impact sfx).
The page can pulse with the beat: `K.pulse(t)` is 1 on each beat and decays (`scale(1 + 0.03 * K.pulse(t))`).

```bash
python3 $SKILL/scripts/short.py music <proj>          # regenerates only when the parameters changed
python3 $SKILL/scripts/make_music.py --list           # moods
python3 $SKILL/scripts/make_music.py --out x.wav --duration 30 --mood lofi --seed 3   # standalone
```
If the user brings their own track instead: put it at `out/music.wav` (it is used as-is, trimmed/padded to length); confirm they have the rights; turn `snap` off unless you set `bpm` to the track's tempo.

## Sound effects
Six CC0 sounds ship in `assets/sfx` (whoosh, pop, click, tick, impact, riser), from the default kit of Bart's `sound-effects` skill (Freesound / Kenney authors, see `assets/sfx/LICENSES.md`).
- `timeline.py` adds one cue per scene change from the style's transition (`push/slide/punch` → whoosh, `pop` → pop, `fade-transform/drift` → none), an impact on `accent` scenes, plus any `sfx_at` word cues. Whooshes start 2 frames early.
- Turn them off with `"sfx": {"enabled": false}`, or per scene `"sfx": "none"`.
- Don't stack more than one effect per second; the voice must stay on top.

## The mix (`mix_audio.py`)
Priority **voice > sfx > music**.
- Voice: high-passed at 75 Hz, levelled to a common speech level, each clip on its `voiceStart`.
- Music: bed at −9 dB vs speech, ducks a further 9 dB while anyone speaks (40 ms attack, 350 ms release). Tune with `--bed`/`--duck`.
- SFX: levelled relative to speech (impact −7 dB, whoosh −11, pop −10, click −12, tick −15, riser −13), shift all with `--sfx-db`.
- Master: two-pass `loudnorm` to **−14 LUFS integrated, true peak ≤ −1.5 dBTP**, 48 kHz stereo, exactly the video's length. YouTube plays Shorts at about −14 LUFS, so this is what the viewer hears, with headroom for the AAC re-encode.
- Report written to `out/mix_report.json`; the final MP4 is measured again by `verify_video.py`.

You can't hear the result. Report the numbers and give the user timestamps to check: the first second, the loudest music moment, the densest sfx moment.
