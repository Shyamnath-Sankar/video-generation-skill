#!/usr/bin/env python3
"""Verify a rendered Short is correct before anyone uploads it. Exit code 0 = PASS, 1 = FAIL.

usage: verify_video.py video.mp4 [--timeline timeline.json] [--w 1080 --h 1920] [--fps 30]
                       [--no-audio] [--lufs -14] [--sheet sheet.png] [--json report.json] [--fast]

Checks (FAIL = must fix, WARN = look at it):
  container   MP4, moov atom before mdat (faststart, so it starts playing before it fully downloads)
  video       exactly 1080x1920, square pixels, display aspect 9:16, no rotation flag, H.264 High,
              yuv420p 8-bit, constant frame rate = expected fps, frame count = duration x fps, BT.709 tags
  duration    > 0 and within the format's limit (Shorts: <= 180 s), matches timeline.json within one frame
  chapters    long-form: first at 0:00, at least 3, each >= 10 s (YouTube's rules for showing chapters)
  format      --format short|long|long-4k (default: from timeline.json, else short). Sizes and safe zones
              come from engine/formats.json
  audio       AAC, 48 kHz, stereo, as long as the video (+-0.1 s), integrated loudness near the target,
              true peak <= -1 dBTP, not silent, no long silence at the very start
  decode      the whole file decodes with zero errors
  picture     first frame is not black (it is the first thing a scroller sees), no black gaps > 0.4 s,
              no frozen stretches > 3 s (a stuck render or a scene that forgot to animate)
  sheet       optional contact sheet: one frame per scene (from the timeline) with the Shorts safe zone
              drawn on top, so you can check framing by eye
"""
import argparse, json, math, pathlib, re, struct, subprocess, sys

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("video"); ap.add_argument("--timeline"); ap.add_argument("--format"); ap.add_argument("--w", type=int); ap.add_argument("--h", type=int)
ap.add_argument("--fps", type=float, default=None); ap.add_argument("--no-audio", action="store_true")
ap.add_argument("--lufs", type=float, default=-14.0); ap.add_argument("--sheet"); ap.add_argument("--json")
ap.add_argument("--fast", action="store_true", help="skip full decode, black and freeze scans")
A = ap.parse_args()
V = pathlib.Path(A.video)
R = []  # (level, check, detail)


def add(level, check, detail=""):
    R.append((level, check, detail))


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def frac(s):
    try:
        a, b = s.split("/"); return float(a) / float(b) if float(b) else 0.0
    except Exception:
        try: return float(s)
        except Exception: return 0.0


if not V.exists():
    print(f"FAIL  file: {V} does not exist"); sys.exit(1)

# ------------------------------------------------------------------ probe
pr = run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(V)])
if pr.returncode != 0:
    print(f"FAIL  probe: ffprobe cannot read the file: {pr.stderr.strip()[:300]}"); sys.exit(1)
info = json.loads(pr.stdout)
fmt = info.get("format", {})
vs = [s for s in info["streams"] if s["codec_type"] == "video"]
aus = [s for s in info["streams"] if s["codec_type"] == "audio"]
tl = None
tlp = A.timeline or (V.parent.parent / "timeline.json" if (V.parent.parent / "timeline.json").exists() else None)
if tlp and pathlib.Path(tlp).exists():
    tl = json.loads(pathlib.Path(tlp).read_text())
fps_expect = A.fps or (tl["fps"] if tl else None)
FORMATS = json.loads((pathlib.Path(__file__).resolve().parent.parent / "engine" / "formats.json").read_text())
FMT = A.format or (tl.get("format") if tl else None) or "short"
if FMT not in FORMATS:
    print(f"FAIL  format: unknown format {FMT}; one of {', '.join(FORMATS)}"); sys.exit(1)
F = FORMATS[FMT]
A.w = A.w or F["w"] * F["scale"]; A.h = A.h or F["h"] * F["scale"]
ASPECT = F["aspect"]

# ------------------------------------------------------------------ container
if "mp4" not in fmt.get("format_name", "") and "mov" not in fmt.get("format_name", ""):
    add("FAIL", "container", f"format is {fmt.get('format_name')}, expected MP4")
else:
    order = []
    with open(V, "rb") as f:
        pos, size = 0, V.stat().st_size
        while pos < size and len(order) < 50:
            f.seek(pos); hdr = f.read(16)
            if len(hdr) < 8: break
            sz, typ = struct.unpack(">I4s", hdr[:8])
            if sz == 1: sz = struct.unpack(">Q", hdr[8:16])[0]
            elif sz == 0: sz = size - pos
            order.append(typ.decode("latin1"))
            if sz < 8: break
            pos += sz
    if "moov" in order and "mdat" in order and order.index("moov") > order.index("mdat"):
        add("WARN", "faststart", "moov atom is after mdat; re-mux with -movflags +faststart so it streams instantly")
    elif "moov" in order:
        add("OK", "container", f"MP4, faststart ({' '.join(order[:4])})")
    else:
        add("FAIL", "container", "no moov atom found; the file is incomplete")

# ------------------------------------------------------------------ video stream
dur = float(fmt.get("duration", 0) or 0)
if len(vs) != 1:
    add("FAIL", "video stream", f"{len(vs)} video streams, expected 1")
else:
    v = vs[0]
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    if (w, h) != (A.w, A.h):
        add("FAIL", "resolution", f"{w}x{h}, expected {A.w}x{A.h} ({ASPECT}, format '{FMT}')")
    else:
        add("OK", "resolution", f"{w}x{h}")
    sar = v.get("sample_aspect_ratio", "1:1")
    if sar not in ("1:1", "0:1", "N/A"):
        add("FAIL", "pixel aspect", f"SAR {sar}; pixels must be square or players will stretch the frame")
    dar = v.get("display_aspect_ratio")
    if dar and dar not in (ASPECT, "0:1", "N/A"):
        add("FAIL", "display aspect", f"DAR {dar}, expected {ASPECT}")
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd: rot = int(sd["rotation"])
    if v.get("tags", {}).get("rotate"): rot = int(v["tags"]["rotate"])
    if rot:
        add("FAIL", "rotation", f"rotation flag {rot} degrees: some players will turn the video sideways")
    else:
        add("OK", "aspect", f"square pixels, {ASPECT}, no rotation flag")
    codec, prof, pix = v.get("codec_name"), v.get("profile", ""), v.get("pix_fmt")
    if codec != "h264":
        add("WARN" if codec in ("hevc", "vp9", "av1") else "FAIL", "codec", f"{codec}; H.264 is the safest upload codec")
    else:
        add("OK", "codec", f"H.264 {prof}")
    if pix != "yuv420p":
        add("FAIL", "pixel format", f"{pix}; use yuv420p (8-bit 4:2:0) or many phones will not play it")
    rfr, afr = frac(v.get("r_frame_rate", "0")), frac(v.get("avg_frame_rate", "0"))
    fps = rfr or afr
    if fps_expect and abs(fps - fps_expect) > 0.01:
        add("FAIL", "frame rate", f"{fps:.3f} fps, expected {fps_expect}")
    elif afr and abs(rfr - afr) > 0.05:
        add("WARN", "frame rate", f"variable frame rate (r {rfr:.3f} vs avg {afr:.3f}); render at a constant rate")
    else:
        add("OK", "frame rate", f"{fps:g} fps constant")
    if fps not in (24, 25, 30, 50, 60) and abs(fps - 30000 / 1001) > 0.01 and abs(fps - 60000 / 1001) > 0.01:
        add("WARN", "frame rate", f"{fps:.3f} fps is unusual for Shorts; use 30 or 60")
    cnt = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(V)])
    try:
        frames = int(cnt.stdout.strip().split(",")[0])
    except ValueError:
        frames = None
    vdur = float(v.get("duration", dur) or dur)
    if frames and fps:
        exp = round(vdur * fps)
        if abs(frames - exp) > 1:
            add("FAIL", "frame count", f"{frames} frames for {vdur:.3f}s at {fps:g} fps (expected {exp}); frames were dropped or duplicated")
        else:
            add("OK", "frame count", f"{frames} frames")
    tags = (v.get("color_space"), v.get("color_primaries"), v.get("color_transfer"))
    if not all(t == "bt709" for t in tags):
        add("WARN", "colour tags", f"colour space/primaries/transfer = {tags}; tag BT.709 so colours look the same on every device")
    br = int(fmt.get("bit_rate", 0) or 0)
    if br and br < 300_000:
        add("WARN", "bitrate", f"{br / 1e6:.1f} Mb/s is very low for 1080x1920; gradients may band after YouTube re-encodes (render the final with --crf 16 or lower)")
    if V.stat().st_size > 2 * 1024 ** 3:
        add("WARN", "file size", "over 2 GB")

# ------------------------------------------------------------------ duration
if dur <= 0:
    add("FAIL", "duration", "0 s")
elif dur > F["max_duration"]:
    add("FAIL", "duration", f"{dur:.2f}s: over the {F['max_duration']}s limit for '{FMT}'" + (", YouTube will treat it as a regular video" if FMT == "short" else ""))
else:
    soft = F.get("soft_duration")
    add("OK" if not soft or dur <= soft else "WARN", "duration", f"{dur:.2f}s" + ("" if not soft or dur <= soft else f" (allowed up to {F['max_duration']}s; under {soft}s tends to perform better)"))
if tl and tl.get("chapters"):
    ch = tl["chapters"]; probs = []
    if ch[0]["t"] > 0.001: probs.append("first chapter must start at 0:00")
    if len(ch) < 3: probs.append(f"only {len(ch)} chapters (YouTube needs 3+)")
    for a, b in zip(ch, ch[1:] + [{"t": dur}]):
        if b["t"] - a["t"] < 10: probs.append(f"'{a['title']}' is {b['t'] - a['t']:.1f}s (min 10s)")
    if probs: add("WARN", "chapters", "; ".join(probs) + " - YouTube will not show chapters")
    else: add("OK", "chapters", f"{len(ch)} chapters, paste out/chapters.txt into the description")
if tl and dur > 0:
    if abs(dur - tl["duration"]) > 1.5 / (fps_expect or 30):
        add("FAIL", "matches timeline", f"video {dur:.3f}s vs timeline {tl['duration']:.3f}s; re-render after re-running timeline.py")
    else:
        add("OK", "matches timeline", f"{tl['duration']:.3f}s, {len(tl['scenes'])} scenes")

# ------------------------------------------------------------------ audio
if A.no_audio:
    if aus: add("WARN", "audio", "--no-audio given but the file has audio")
elif not aus:
    add("FAIL", "audio", "no audio stream (mux out/mix.wav, or pass --no-audio for a silent draft)")
else:
    a = aus[0]
    issues = []
    if a.get("codec_name") != "aac": issues.append(f"codec {a.get('codec_name')} (use AAC)")
    if int(a.get("sample_rate", 0)) != 48000: issues.append(f"{a.get('sample_rate')} Hz (use 48000)")
    if int(a.get("channels", 0)) != 2: issues.append(f"{a.get('channels')} channel(s) (use stereo)")
    if issues: add("WARN", "audio format", "; ".join(issues))
    else: add("OK", "audio format", f"AAC 48 kHz stereo {int(a.get('bit_rate', 0) or 0) // 1000} kb/s")
    adur = float(a.get("duration", 0) or 0)
    vdur = float(vs[0].get("duration", dur)) if vs else dur
    if adur and abs(adur - vdur) > 0.1:
        add("FAIL", "A/V length", f"audio {adur:.3f}s vs video {vdur:.3f}s; the end will cut off or hang")
    else:
        add("OK", "A/V length", f"audio {adur:.3f}s, video {vdur:.3f}s")
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(V), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"])
    tail = r.stderr[r.stderr.rfind("Summary:"):]
    mi = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", tail); mp = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", tail)
    I = float(mi.group(1)) if mi and mi.group(1) != "-inf" else None
    P = float(mp.group(1)) if mp and mp.group(1) != "-inf" else None
    if I is None:
        add("FAIL", "loudness", "audio is silent")
    else:
        lvl = "OK" if abs(I - A.lufs) <= 1.5 else "WARN"
        add(lvl, "loudness", f"{I:.1f} LUFS integrated (target {A.lufs:g}; YouTube normalises to about -14)")
        if P is not None and P > -1.0:
            add("FAIL", "true peak", f"{P:.1f} dBTP: will clip after YouTube's AAC encode (keep <= -1)")
        elif P is not None:
            add("OK", "true peak", f"{P:.1f} dBTP")
    sd = run(["ffmpeg", "-hide_banner", "-nostats", "-t", "3", "-i", str(V), "-map", "0:a:0", "-af", "silencedetect=n=-45dB:d=0.4", "-f", "null", "-"])
    m = re.search(r"silence_start: (-?[\d.]+)", sd.stderr)
    e = re.search(r"silence_end: ([\d.]+)", sd.stderr)
    if m and float(m.group(1)) <= 0.05 and e and float(e.group(1)) > 0.6:
        add("WARN", "hook audio", f"first {float(e.group(1)):.2f}s are silent; Shorts viewers swipe in the first second, start talking sooner")

# ------------------------------------------------------------------ decode + picture
if not A.fast:
    d = run(["ffmpeg", "-v", "error", "-i", str(V), "-f", "null", "-"])
    errs = [l for l in d.stderr.splitlines() if l.strip()]
    if errs: add("FAIL", "decode", f"{len(errs)} decode error(s): {errs[0][:160]}")
    else: add("OK", "decode", "whole file decodes cleanly")
    # first frame brightness
    # first frame: share of pixels that stand out from the background (text, shapes)
    sw, shh = (480, 270) if A.w > A.h else (270, 480)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(V), "-frames:v", "1", "-vf", f"scale={sw}:{shh}", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    if len(raw) == sw * shh:
        import numpy as np
        y = np.frombuffer(raw, np.uint8).astype(int)
        cover = float((np.abs(y - np.median(y)) > 28).mean())
        if cover < 0.004:
            add("WARN", "first frame", "frame 0 is nearly empty; the hook must be on screen from the first frame (it is what scrollers judge)")
        else:
            add("OK", "first frame", f"has content ({cover * 100:.1f}% of pixels stand out from the background)")
    bd = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(V), "-vf", "blackdetect=d=0.4:pix_th=0.06:pic_th=0.98", "-an", "-f", "null", "-"])
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)", bd.stderr)
    if blacks:
        add("FAIL", "black frames", "black gap(s): " + ", ".join(f"{float(s):.2f}-{float(e):.2f}s" for s, e, _ in blacks[:5]))
    else:
        add("OK", "black frames", "none")
    fz = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(V), "-vf", f"freezedetect=n=0.0015:d={F['freeze_warn_s']}", "-an", "-f", "null", "-"])
    starts = re.findall(r"freeze_start: ([\d.]+)", fz.stderr); ends = re.findall(r"freeze_end: ([\d.]+)", fz.stderr)
    if starts:
        spans = [f"{float(s):.2f}-{(float(ends[i]) if i < len(ends) else dur):.2f}s" for i, s in enumerate(starts[:5])]
        add("WARN", "frozen picture", f"no motion for {F['freeze_warn_s']}s+ at " + ", ".join(spans) + " (keep something moving: every 1-2 s in Shorts, every few seconds in long-form)")
    else:
        add("OK", "frozen picture", "always moving")

# ------------------------------------------------------------------ contact sheet with safe zone
if A.sheet and vs:
    if tl:
        times = [min(dur - 0.05, s["start"] + min(0.9 * (s["end"] - s["start"]), max(0.6, (s["end"] - s["start"]) * 0.6))) for s in tl["scenes"]]
        labels = [s["id"] for s in tl["scenes"]]
    else:
        times = [dur * (i + 0.5) / 8 for i in range(8)]; labels = [f"{t:.1f}s" for t in times]
    times.insert(0, 0.0); labels.insert(0, "frame 0")
    land = A.w > A.h
    if len(times) > 24:   # long videos: frame 0 + an even sample of scenes
        idx = [0] + [1 + round(i * (len(times) - 2) / 22) for i in range(23)]
        times = [times[i] for i in idx]; labels = [labels[i] for i in idx]
    cols = min(3 if land else 4, len(times)); rows = math.ceil(len(times) / cols); tw, th = (480, 270) if land else (360, 640)
    inputs, fl = [], []
    for i, t in enumerate(times):
        inputs += ["-ss", f"{max(0, t):.3f}", "-i", str(V)]
        s = tw / (A.w / F["scale"]); sf = F["safe"]
        top, bot, right, left = round(sf["top"] * s), round(sf["bottom"] * s), round(sf["right"] * s), round(sf["left"] * s)
        fl.append(f"[{i}:v]trim=end_frame=1,scale={tw}:{th},"
                  f"drawbox=x=0:y=0:w={tw}:h={top}:color=red@0.22:t=fill,drawbox=x=0:y={bot}:w={tw}:h={th - bot}:color=red@0.22:t=fill,"
                  f"drawbox=x={right}:y={top}:w={tw - right}:h={bot - top}:color=red@0.22:t=fill,drawbox=x=0:y={top}:w={left}:h={bot - top}:color=red@0.22:t=fill,"
                  f"drawbox=x=0:y={th - 34}:w={tw}:h=34:color=black@0.75:t=fill,"
                  f"drawtext=text='{labels[i]} @ {t:.2f}s':x=8:y={th - 28}:fontsize=20:fontcolor=white[s{i}]")
    pad = cols * rows - len(times)
    for i in range(pad): fl.append(f"color=c=gray:s={tw}x{th}:d=0.04[p{i}]")
    ins = "".join(f"[s{i}]" for i in range(len(times))) + "".join(f"[p{i}]" for i in range(pad))
    lay = "|".join(f"{(i % cols) * (tw + 6)}_{(i // cols) * (th + 6)}" for i in range(cols * rows))
    fl.append(f"{ins}xstack=inputs={cols * rows}:layout={lay}:fill=gray[o]" if cols * rows > 1 else "[s0]null[o]")
    r = run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fl), "-map", "[o]", "-frames:v", "1", A.sheet])
    if r.returncode == 0:
        add("OK", "contact sheet", f"{A.sheet} (red = outside the safe zone)")
    else:
        add("WARN", "contact sheet", "could not build: " + r.stderr.strip()[-200:])

# ------------------------------------------------------------------ report
fails = sum(1 for l, *_ in R if l == "FAIL"); warns = sum(1 for l, *_ in R if l == "WARN")
for l, c, d in R:
    print(f"{l:<4}  {c}{': ' + d if d else ''}")
print(f"\n{'VERIFY FAILED' if fails else 'VERIFY PASSED'}  {V.name}  ({fails} fail, {warns} warn)")
if A.json:
    pathlib.Path(A.json).write_text(json.dumps({"video": str(V), "pass": not fails, "fails": fails, "warns": warns,
                                                "results": [{"level": l, "check": c, "detail": d} for l, c, d in R]}, indent=1))
sys.exit(1 if fails else 0)
