# Narration with OmniVoice (local model over MCP)

OmniVoice (k2-fsa/OmniVoice) is a 0.6B multilingual zero-shot TTS model running on the user's machine and exposed to you through an MCP server. It does three things you use here:

| Mode | What you pass | Use when |
|---|---|---|
| **Voice cloning** | `ref_audio` (a clean 5–15 s clip of the target voice) + `ref_text` (its exact transcript; if omitted the model transcribes it with Whisper, slower and less reliable) | The user wants their own voice or a specific voice they have rights to |
| **Voice design** | `instruct`: comma-separated attributes, e.g. `female, young adult, moderate pitch, american accent` | No reference clip; describe the voice |
| **Default** | text only | Quick drafts |

Other knobs the model supports (names as in OmniVoice's `generate()`; the MCP server may expose some or all): `speed` (>1 faster), `duration` (fixed length in seconds, overrides speed), `num_step` (diffusion steps: 32 quality, 16 faster). Output is 24 kHz audio.

**Instruct attributes** the model understands: gender (`male`, `female`), age (`child`, `teenager`, `young adult`, `middle-aged`, `elderly`), pitch (`very low pitch` … `very high pitch`), style (`whisper`), English accents (`american accent`, `british accent`, …) and Chinese dialects. Keep instructs short and attribute-like; it is not a free-form prompt.

**Non-verbal tags** go inline in the text: `[laughter]`, `[sigh]`, `[surprise-ah]`, `[surprise-oh]`, `[question-en]`, `[confirmation-en]`, `[dissatisfaction-hnn]` and others. `timeline.py` strips them from captions and treats them as pauses. Use at most one per Short; they're a spice.

## 1. Find the tools
The server's tool names are not fixed. Discover them before the first call:
- If tools are deferred: `ToolSearch` with query `omnivoice` (then `tts`, `speech`, `voice` if nothing matches).
- Read each tool's description and parameters. Map them onto: text, ref_audio, ref_text, instruct, speed, num_step/steps, output path.
- Typical shapes: one `generate`/`tts` tool with optional clone/design arguments, or separate `clone_voice`/`design_voice` tools. Some return a file path, some write to a path you give, some return base64. Prefer a path (base64 audio wastes context); if the tool only returns base64, write it to a file with a short script, not by pasting it.
- If no OmniVoice tool exists in the session, tell the user: the MCP server must be running and connected to this app. Offer to continue with estimated timings (the timeline works without voice) and drop the voice in later.

Paths: the MCP server runs on the user's machine. Use absolute paths for `ref_audio` and output files that both you and the server can see (the project's `voice/raw/` folder is a good place).

## 2. Write lines for the ear
- One clip **per scene** (`voice/<scene-id>.wav`): exact timing per scene, and a bad take costs one line, not the whole video.
- Same voice settings for every scene (same `ref_audio`/`ref_text` or the identical `instruct`, same `speed`, same `num_step`). Store them in `script.json` → `voice` so a regenerated line matches.
- Spell for speech in `say`, show for the eye in `caption`: say `"twenty percent"`, caption `"20%"`; say `"kube control"` only if the user prefers that pronunciation, caption `kubectl`.
- End each line with punctuation; the model's prosody needs it. Keep lines 4–14 words.
- Numbers, acronyms and code: write them the way they should be pronounced in `say`.

## 3. Generate, import, check
For each scene:
1. Call the OmniVoice tool with the scene's `say` text and the shared voice settings; save to `voice/raw/<id>.wav` (or wherever the tool writes).
2. Import it:
   ```bash
   python3 $SKILL/scripts/import_voice.py voice/raw/<id>.wav <project> <id> --text "<say text>"
   ```
   This converts to 48 kHz mono, trims silence (keeps 60 ms), and **fails** on: silence, clipping, or a words-per-second rate that means skipped words (> 5/s) or rambling/repetition (< 1.3/s). It also warns on long internal pauses.
3. On failure: regenerate (a different seed if the tool has one, or `num_step` 32), at most 3 tries, then tell the user which line keeps failing and why.

Then `short.py timeline <project>`: every scene now lasts as long as its narration (+ gap), never shorter than `min`.

## 4. Exact word timing (optional)
`timeline.py` estimates word times by spreading syllables over each clip (±0.15 s): fine for captions and for cues on stressed words. For tighter sync, if `faster-whisper` is installed, transcribe each clip with word timestamps and save `voice/<id>.words.json` as `[{"w": "Your", "s": 0.03, "e": 0.21}, …]` (times relative to the clip, after import). The timeline uses it automatically. Re-importing a clip deletes its stale words file.

## 5. Cloning etiquette
Only clone a voice the user owns or has permission to use. If they ask for a celebrity's or another creator's voice, say you can design a similar-sounding voice with attributes instead, and don't clone it.

## 6. Long-form narration
- Still one clip per scene (scenes of 1–3 sentences). A 10-minute video is 60–120 clips: generate them in script order, import each, and keep a list of the ones that failed to retry at the end.
- Voice drift over many clips: always pass the identical clone reference / instruct; if the server supports a saved clone prompt (OmniVoice's `voice_clone_prompt`), create it once and reuse it for every clip.
- Re-recording one line later only shifts the scenes after it; `timeline` + `build` re-render just the affected chunks.

## 7. Pacing defaults that sound natural
- `speed` 1.0–1.1 for explainers, 1.1–1.2 for hype, 0.9–1.0 for calm math/science.
- `pacing.gap` (silence between scenes) 0.2–0.35 s; `lead_in` 0.1–0.15 s so the voice starts almost at frame 0.
- A Short of 30 s holds about 75–85 spoken words; long-form runs at 140–160 words per minute.
