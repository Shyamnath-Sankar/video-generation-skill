#!/usr/bin/env python3
"""Bring one narration clip from OmniVoice (or any TTS / recording) into the project, cleaned and checked.

usage: import_voice.py <src_audio> <project_dir> <scene_id> [--text "the line"] [--keep-silence] [--pad 0.06]

- converts to 48 kHz mono 16-bit WAV at <project>/voice/<scene_id>.wav
- trims leading/trailing silence (keeps --pad seconds) so scene timing is tight
- FAILS if the clip is empty, silent, clipped or absurdly long/short for its text, which is how
  TTS glitches (skipped words, rambling, repeated phrases) usually show up
Prints JSON with duration, peak, rms and words/second.
"""
import argparse, json, math, pathlib, re, subprocess, sys, wave
import numpy as np

SR = 48000


def decode(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"FAIL cannot decode {path}: {r.stderr.decode()[-300:]}")
    return np.frombuffer(r.stdout, dtype="<f4").astype(np.float64)


def write(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("project"); ap.add_argument("scene")
    ap.add_argument("--text", default=None, help="the line that was spoken (enables the words/second sanity check)")
    ap.add_argument("--keep-silence", action="store_true"); ap.add_argument("--pad", type=float, default=0.06)
    ap.add_argument("--threshold-db", type=float, default=-42)
    A = ap.parse_args()
    x = decode(A.src)
    problems, notes = [], []
    if len(x) < SR * 0.2:
        problems.append(f"clip is only {len(x) / SR:.2f}s long")
    # trim silence using a 10 ms RMS envelope
    hop = SR // 100
    frames = x[: len(x) // hop * hop].reshape(-1, hop) if len(x) >= hop else x.reshape(1, -1)
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    voiced = np.where(db > A.threshold_db)[0]
    if voiced.size == 0:
        problems.append(f"no audio above {A.threshold_db} dBFS: the clip is silent")
        y = x
    elif A.keep_silence:
        y = x
    else:
        pad = int(A.pad * SR)
        a = max(0, voiced[0] * hop - pad); b = min(len(x), (voiced[-1] + 1) * hop + pad)
        y = x[a:b].copy()
        fade = min(len(y) // 4, int(0.008 * SR))
        if fade > 0:
            y[:fade] *= np.linspace(0, 1, fade); y[-fade:] *= np.linspace(1, 0, fade)
        trimmed = (len(x) - len(y)) / SR
        if trimmed > 0.05:
            notes.append(f"trimmed {trimmed:.2f}s of silence")
    peak = float(np.abs(y).max()) if len(y) else 0.0
    clip_frac = float((np.abs(y) > 0.999).mean()) if len(y) else 0.0
    if clip_frac > 0.001:
        problems.append(f"{clip_frac * 100:.2f}% of samples are clipped; regenerate or lower the TTS output gain")
    if peak < 0.03 and voiced.size:
        notes.append("very quiet clip; the mix normalises it, but check it is not mostly noise")
    # long internal silences usually mean the model paused oddly or skipped
    if voiced.size:
        gaps = np.diff(voiced) * hop / SR
        if gaps.size and gaps.max() > 1.2:
            notes.append(f"contains a {gaps.max():.1f}s pause; listen for a skipped phrase")
    dur = len(y) / SR
    wps = None
    if A.text:
        words = [w for w in re.sub(r"\[[^\]]+\]", " ", A.text).split() if re.search(r"\w", w)]
        if words and dur > 0:
            wps = len(words) / dur
            if wps > 5.0:
                problems.append(f"{len(words)} words in {dur:.2f}s ({wps:.1f}/s): too fast, words were probably skipped")
            elif wps < 1.3:
                problems.append(f"{len(words)} words in {dur:.2f}s ({wps:.1f}/s): too slow, the model probably rambled or repeated")
    out = pathlib.Path(A.project) / "voice" / f"{A.scene}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not problems:
        write(out, y)
        stale = out.with_suffix(".words.json")
        if stale.exists():
            stale.unlink(); notes.append("removed stale word timings; re-run align_words.py if you use it")
    rep = {"scene": A.scene, "file": str(out) if not problems else None, "duration": round(dur, 3), "peak_dbfs": round(20 * math.log10(max(peak, 1e-9)), 1),
           "words_per_sec": round(wps, 2) if wps else None, "ok": not problems, "problems": problems, "notes": notes}
    print(json.dumps(rep, indent=1))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
