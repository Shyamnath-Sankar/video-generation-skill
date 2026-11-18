#!/usr/bin/env python3
"""Mix the Short's soundtrack: narration + (optional) music + (optional) sound effects -> out/mix.wav

usage: mix_audio.py <project_dir> [--music out/music.wav] [--lufs -14] [--tp -1.5] [--bed -9] [--duck 9] [--sfx-db 0]

Priority is voice > sfx > music:
- every narration clip is placed at its scene's voiceStart (timeline.json), high-passed and levelled
- music (only if timeline music.enabled and the file exists) sits --bed dB under the voice and ducks a further
  --duck dB while anyone is speaking (smooth 40 ms attack / 350 ms release)
- sound effects (assets/sfx, CC0) land on the timeline cues, levelled relative to the voice
- the result is loudness-normalised in two passes to --lufs integrated (YouTube plays Shorts at about -14 LUFS)
  with true peak under --tp dBTP, 48 kHz stereo, exactly as long as the video
Writes out/mix.wav and out/mix_report.json. Measure the final MP4 again with verify_video.py.
"""
import argparse, json, math, pathlib, re, subprocess, sys, tempfile
import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
SKILL = pathlib.Path(__file__).resolve().parent.parent
SFX_DIR = SKILL / "assets" / "sfx"
SFX_REL_DB = {"whoosh": -11, "pop": -10, "click": -12, "tick": -15, "impact": -7, "riser": -13}


def decode(path, ch):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", str(ch), "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"cannot decode {path}: {r.stderr.decode()[-300:]}")
    x = np.frombuffer(r.stdout, dtype="<f4").copy()   # float32: long videos stay in memory
    return x.reshape(-1, ch).T


def db(x):
    return 20 * math.log10(max(float(x), 1e-12))


def active_rms(x, floor_db=-45):
    """RMS over the frames that are not silence (speech level, not diluted by pauses)"""
    hop = SR // 100
    if x.size < hop:
        return 0.0
    f = x[: x.size // hop * hop].reshape(-1, hop)
    r = np.sqrt((f ** 2).mean(axis=1))
    keep = r[r > 10 ** (floor_db / 20)]
    return float(np.sqrt((keep ** 2).mean())) if keep.size else 0.0


def smooth_env(active, attack, release):
    """one-pole attack/release smoothing of a 0/1 activity curve sampled every 10 ms"""
    out = np.zeros_like(active, dtype=float); v = 0.0
    a = 1 - math.exp(-0.01 / attack); r = 1 - math.exp(-0.01 / release)
    for i, x in enumerate(active):
        v += (x - v) * (a if x > v else r); out[i] = v
    return out


def loudnorm(src, dst, lufs, tp, dur):
    """two-pass loudnorm. A gentle peak limiter runs first, so linear gain can reach the target without the
    true-peak ceiling holding it back (sfx impacts, plosives); if linear still misses, fall back to dynamic."""
    lim = str(pathlib.Path(src).with_name("pre_lim.wav"))
    I0, _ = measure(src)
    gain = (lufs - I0) if I0 is not None else 0.0
    # limit peaks to where they will land at (tp - 0.5) dBTP after the gain loudnorm will apply
    limit = min(1.0, max(0.0625, 10 ** ((tp - 0.5 - gain) / 20)))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", f"alimiter=limit={limit:.4f}:attack=2:release=80:level=0:asc=1",
                    "-c:a", "pcm_f32le", lim], check=True)
    src = lim
    meas, res = _loudnorm(src, dst, lufs, tp, dur, True)
    I, _ = measure(dst)
    if I is not None and abs(I - lufs) > 0.7:
        meas, res = _loudnorm(src, dst, lufs, tp, dur, False)
        res["fallback"] = "dynamic"
    return meas, res


def _loudnorm(src, dst, lufs, tp, dur, linear):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-af", f"loudnorm=I={lufs}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        raise SystemExit("loudnorm measurement failed:\n" + r.stderr[-800:])
    meas = json.loads(m.group(0))
    af = (f"loudnorm=I={lufs}:TP={tp}:LRA=11:measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:"
          f"measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}:linear={'true' if linear else 'false'}:print_format=json")
    r2 = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", src, "-af", af + f",aresample={SR},apad", "-t", f"{dur:.4f}",
                         "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", dst], capture_output=True, text=True)
    if r2.returncode != 0:
        raise SystemExit("loudnorm pass 2 failed:\n" + r2.stderr[-800:])
    m2 = re.search(r"\{[^{}]*\"normalization_type\"[^{}]*\}", r2.stderr, re.S)
    return meas, (json.loads(m2.group(0)) if m2 else {})


def measure(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    tail = r.stderr[r.stderr.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", tail); p = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", tail)
    return (float(i.group(1)) if i and i.group(1) != "-inf" else None, float(p.group(1)) if p and p.group(1) != "-inf" else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("--music", default=None)
    ap.add_argument("--lufs", type=float, default=-14.0); ap.add_argument("--tp", type=float, default=-1.5)
    ap.add_argument("--bed", type=float, default=-9.0, help="music level vs speech level when nobody speaks (dB)")
    ap.add_argument("--duck", type=float, default=9.0, help="extra music reduction under speech (dB)")
    ap.add_argument("--sfx-db", type=float, default=0.0, help="shift all sound effects by this many dB")
    A = ap.parse_args()
    proj = pathlib.Path(A.project); out = proj / "out"; out.mkdir(exist_ok=True)
    tl = json.loads((proj / "timeline.json").read_text())
    dur = tl["duration"]; n = int(round(dur * SR))
    log, warn = [], []

    # ---------------- voice
    voice = np.zeros(n, dtype=np.float32)
    hp = butter(2, 75, "highpass", fs=SR, output="sos")
    placed = 0
    for sc in tl["scenes"]:
        if not sc.get("voice"):
            continue
        x = decode(proj / sc["voice"], 1)[0]
        i = int(round(sc["voiceStart"] * SR))
        if i + x.size > n:
            warn.append(f"voice for '{sc['id']}' runs {(i + x.size - n) / SR:.2f}s past the end; re-run timeline.py")
            x = x[: max(0, n - i)]
        voice[i:i + x.size] += sosfilt(hp, x).astype(np.float32); placed += 1   # high-pass per clip
    missing = [s["id"] for s in tl["scenes"] if not s.get("voice")]
    if missing:
        warn.append("no narration for scenes: " + ", ".join(missing))
    v_rms = active_rms(voice)
    have_voice = v_rms > 1e-4
    target_v = 10 ** (-20 / 20)                 # speech at about -20 dBFS RMS before the final normalise
    if have_voice:
        voice *= target_v / v_rms
        log.append(f"voice: {placed} clip(s), speech level set to -20 dBFS RMS before normalising")
    ref = target_v                               # everything else is levelled against the speech level

    mix = np.zeros((2, n), dtype=np.float32); mix += voice
    # voice activity (10 ms frames) for ducking
    hop = SR // 100
    vf = voice[: n // hop * hop].reshape(-1, hop)
    act = (np.sqrt((vf ** 2).mean(axis=1)) > ref * 10 ** (-24 / 20)).astype(float) if have_voice else np.zeros(n // hop)

    # ---------------- music
    music_on = tl.get("music", {}).get("enabled")
    mpath = pathlib.Path(A.music) if A.music else proj / "out" / "music.wav"
    if music_on and mpath.exists():
        m = decode(mpath, 2)
        if m.shape[1] < n - SR * 0.05:
            warn.append(f"music is {m.shape[1] / SR:.2f}s, video is {dur:.2f}s; padded with silence (re-run make_music.py with the new duration)")
        if m.shape[1] < n:
            m = np.pad(m, ((0, 0), (0, n - m.shape[1])))
        m = m[:, :n]
        m_rms = active_rms(m.mean(axis=0), -60)
        lvl = tl["music"].get("level_db")
        bed_db = A.bed if lvl is None else float(lvl)
        if m_rms > 0:
            m *= ref * 10 ** (bed_db / 20) / m_rms
        if have_voice:
            env = smooth_env(act, 0.04, 0.35)
            g = 10 ** (-A.duck * env / 20)
            for c0 in range(0, n, SR * 60):     # interpolate the gain a minute at a time (memory)
                c1 = min(n, c0 + SR * 60)
                m[:, c0:c1] *= np.interp(np.arange(c0, c1), np.arange(g.size) * hop + hop / 2, g).astype(np.float32)
        mix += m
        log.append(f"music: {mpath.name} at {bed_db:+.0f} dB vs speech, ducking {A.duck:.0f} dB under narration")
    elif music_on:
        warn.append(f"music is enabled but {mpath} does not exist; run make_music first")
    else:
        log.append("music: off")

    # ---------------- sound effects
    cues = tl.get("sfx", {}).get("cues", []) if tl.get("sfx", {}).get("enabled") else []
    cache = {}
    for c in cues:
        kind = c["kind"]
        f = SFX_DIR / f"{kind}.ogg"
        if not f.exists():
            warn.append(f"no sound '{kind}' in assets/sfx (have: {', '.join(p.stem for p in SFX_DIR.glob('*.ogg'))})"); continue
        if kind not in cache:
            s = decode(f, 2)
            pk = max(active_rms(s.mean(axis=0), -50), 1e-6)
            cache[kind] = s / pk
        s = cache[kind] * ref * 10 ** ((SFX_REL_DB.get(kind, -12) + A.sfx_db + (c.get("gain_db") or 0)) / 20)
        i = int(round(c["t"] * SR)); j = min(n, i + s.shape[1])
        if i < n:
            mix[:, i:j] += s[:, : j - i]
    if cues:
        log.append(f"sfx: {len(cues)} cue(s) from assets/sfx (CC0): " + ", ".join(sorted({c['kind'] for c in cues})))

    if not have_voice and not music_on and not cues:
        warn.append("nothing to mix: writing a silent track so the MP4 still has audio")
    # ---------------- normalise + write
    with tempfile.TemporaryDirectory() as td:
        raw = pathlib.Path(td) / "pre.wav"
        peak = np.abs(mix).max()
        if peak > 0.98:                           # keep the float->16 bit pre-master from clipping before loudnorm
            mix *= 0.98 / peak
        pcm = np.clip(mix, -1, 1).T.astype("<f4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "pcm_f32le", str(raw)],
                       input=pcm.tobytes(), check=True)
        dst = out / "mix.wav"
        if have_voice or music_on or cues:
            meas, res = loudnorm(str(raw), str(dst), A.lufs, A.tp, dur)
        else:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-c:a", "pcm_s16le", str(dst)], check=True)
            meas, res = {}, {}
    I, P = measure(dst)
    rep = {"file": str(dst), "duration": dur, "integrated_lufs": I, "true_peak_dbtp": P, "target_lufs": A.lufs, "target_tp": A.tp,
           "normalization": res.get("normalization_type"), "log": log, "warnings": warn}
    (out / "mix_report.json").write_text(json.dumps(rep, indent=1))
    for l in log: print("      " + l)
    for w in warn: print("WARN  " + w)
    ok = I is None or (abs(I - A.lufs) <= 1.0 and (P is None or P <= A.tp + 0.6))
    print(f"{'OK  ' if ok else 'WARN'}  mix -> {dst}  {I if I is not None else '-inf'} LUFS, true peak {P} dBTP (target {A.lufs}, {A.tp})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
