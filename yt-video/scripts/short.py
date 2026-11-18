#!/usr/bin/env python3
"""short.py: one entry point for the YouTube video pipeline (HTML -> MP4), Shorts (9:16) and long-form (16:9).

  short.py doctor                          check node, ffmpeg, python libs, playwright + chromium
  short.py styles                          list style presets
  short.py init  <proj> [--style NAME] [--format short|long|long-4k]   new project from the template (or the style's demo)
  short.py style <proj> <NAME|style.json>  switch / re-apply a style
  short.py kit   <proj>                    refresh the project's copy of kit.js from the skill
  short.py timeline <proj>                 script.json + voice/*.wav -> timeline.json/.js
  short.py check <proj>                    pre-render page checks (determinism, size, fonts, safe zone)
  short.py stills <proj> [--times a,b] [--no-safe]   contact sheet(s) of frames -> out/stills[-<page>].png
  short.py thumb <proj> [--t 1.2] [--page thumbnail.html]   thumbnail image -> out/thumbnail.(png|jpg)
  short.py music <proj>                    synthesise music -> out/music.wav (ONLY if script.json music.enabled)
  short.py mix <proj>                      voice + music + sfx -> out/mix.wav (-14 LUFS)
  short.py render <proj> [--draft|--final] [--workers N] [--chunk 20] [--fresh]   silent MP4, rendered in cached chunks
  short.py mux <proj> [--draft|--final]    silent MP4 + mix.wav -> out/<draft|final>.mp4
  short.py verify <proj> [--draft|--final] verify the MP4 (exit 1 on failure) + out/verify_sheet.png
  short.py build <proj> [--draft|--final]  timeline -> check -> music? -> mix -> render -> mux -> verify

Drafts: 30 fps, no motion blur (fast, for review). Finals: script fps, 4 sub-frames of motion blur.
Renders are split into chunks per page segment and cached in out/chunks/: re-rendering after an edit only
redoes the chunks whose page, assets or timing changed (what makes 10-minute videos practical).
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, math, os, pathlib, shutil, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
SKILL = HERE.parent
ENGINE = SKILL / "engine"
PY = sys.executable


def sh(cmd, env=None, check=True):
    print("$ " + " ".join(str(c) for c in cmd), flush=True)
    r = subprocess.run([str(c) for c in cmd], env=env)
    if check and r.returncode != 0:
        print(f"\nSTOPPED: step failed (exit {r.returncode}). Fix the problem above and re-run.")
        sys.exit(r.returncode)
    return r.returncode


def node_env():
    env = os.environ.copy()
    cands = [os.environ.get("SHORTS_NODE_PATH"), str(pathlib.Path.cwd() / ".shorts-tools" / "node_modules"),
             str(pathlib.Path.home() / ".cache" / "yt-video" / "node_modules")]
    try:
        cands.append(subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip())
    except FileNotFoundError:
        pass
    for c in cands:
        if c and (pathlib.Path(c) / "playwright").exists():
            env["NODE_PATH"] = c + (os.pathsep + env["NODE_PATH"] if env.get("NODE_PATH") else "")
            return env
    r = subprocess.run(["node", "-e", "require.resolve('playwright')"], capture_output=True, env=env)
    if r.returncode == 0:
        return env
    print("playwright not found. Run:  bash " + str(SKILL / "scripts" / "setup.sh"))
    sys.exit(1)


def proj_path(p):
    p = pathlib.Path(p)
    if not (p / "script.json").exists():
        print(f"{p} is not a Short project (no script.json). Create one with: short.py init {p}")
        sys.exit(1)
    return p


def script_of(p):
    return json.loads((p / "script.json").read_text())


def cmd_doctor(a):
    ok = True
    for tool in ("node", "ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        print(f"{'OK  ' if path else 'FAIL'}  {tool}: {path or 'not found'}"); ok &= bool(path)
    if shutil.which("ffmpeg"):
        enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
        for e in ("libx264", "aac"):
            print(f"{'OK  ' if e in enc else 'FAIL'}  ffmpeg encoder {e}"); ok &= e in enc
        flt = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        for f in ("loudnorm", "ebur128", "drawtext", "xstack", "tmix"):
            print(f"{'OK  ' if f in flt else 'WARN'}  ffmpeg filter {f}")
    for mod in ("numpy", "scipy"):
        r = subprocess.run([PY, "-c", f"import {mod}"], capture_output=True)
        print(f"{'OK  ' if r.returncode == 0 else 'FAIL'}  python {mod}"); ok &= r.returncode == 0
    env = node_env()
    r = subprocess.run(["node", "-e", "const {chromium}=require('playwright');chromium.launch().then(b=>{console.log(b.version());return b.close()}).catch(e=>{console.error(e.message);process.exit(1)})"],
                       capture_output=True, text=True, env=env)
    print(f"{'OK  ' if r.returncode == 0 else 'FAIL'}  playwright chromium {r.stdout.strip() or r.stderr.strip()[:200]}"); ok &= r.returncode == 0
    print("\nready" if ok else "\nfix the FAIL lines (scripts/setup.sh installs playwright + chromium)")
    return 0 if ok else 1


def cmd_init(a):
    p = pathlib.Path(a.proj)
    if (p / "script.json").exists() and not a.force:
        print(f"{p} already has a script.json (use --force to overwrite the template files)"); return 1
    sys.path.insert(0, str(HERE)); import style as st
    s = st.load_style(a.style)
    demo = SKILL / "styles" / s["name"] / "demo"
    src = demo if (demo / "index.html").exists() else SKILL / "template"
    p.mkdir(parents=True, exist_ok=True)
    for d in ("voice", "out", "assets"):
        (p / d).mkdir(exist_ok=True)
    shutil.copy2(src / "index.html", p / "index.html")
    shutil.copy2((src if (src / "script.json").exists() else SKILL / "template") / "script.json", p / "script.json")
    shutil.copy2(ENGINE / "kit.js", p / "kit.js")
    st.apply(p, s)
    sc = json.loads((p / "script.json").read_text()); sc["style"] = s["name"]; sc["format"] = a.format
    if a.format != "short":
        sc.setdefault("captions", {"burn": False})
    (p / "script.json").write_text(json.dumps(sc, indent=2) + "\n")
    print(f"new {a.format} video in {p} (style {s['name']}, from {src.relative_to(SKILL)})")
    print("next: edit script.json, generate voice per scene, then: short.py timeline " + str(p))
    return 0


def cmd_style(a):
    p = proj_path(a.proj)
    sys.path.insert(0, str(HERE)); import style as st
    s = st.apply(p, st.load_style(a.name))
    sc = script_of(p); sc["style"] = s["name"]; (p / "script.json").write_text(json.dumps(sc, indent=2) + "\n")
    print(f"style {s['name']} applied; re-run timeline (sfx defaults may change) and check the stills")
    return 0


def cmd_timeline(a):
    return sh([PY, HERE / "timeline.py", proj_path(a.proj)], check=False)


def pages_of(p):
    tl = json.loads((p / "timeline.json").read_text())
    seen = []
    for sg in tl.get("segments") or [{"page": "index.html"}]:
        if sg["page"] not in seen:
            seen.append(sg["page"])
    return tl, seen


def cmd_check(a):
    p = proj_path(a.proj)
    tl, pages = pages_of(p)
    env, rc = node_env(), 0
    for pg in pages:
        stem = pathlib.Path(pg).stem
        rc |= sh(["node", ENGINE / "check_page.cjs", p / pg, "--timeline", p / "timeline.json", "--json", p / "out" / f"check-{stem}.json"], env=env, check=False)
    return rc


def default_times(tl):
    ts = []
    for s in tl["scenes"]:
        ts += [s["start"] + 0.12, min(s["end"] - 0.05, s["start"] + 0.9), max(s["start"], s["end"] - 0.12)]
    return ",".join(f"{t:.2f}" for t in sorted(set(round(t, 2) for t in ts)))


def cmd_stills(a):
    p = proj_path(a.proj)
    tl, pages = pages_of(p)
    F = tl.get("formatInfo", {}); land = tl.get("w", 1080) > tl.get("h", 1920)
    env, rc = node_env(), 0
    for pg in pages:
        scenes = [s for s in tl["scenes"] if s.get("page", "index.html") == pg]
        if a.times:
            ts = [float(x) for x in a.times.split(",")]
            ts = [t for t in ts if any(s["start"] <= t <= s["end"] for s in scenes)]
            times = ",".join(f"{t:.2f}" for t in ts)
        else:
            sub = {**tl, "scenes": scenes if len(scenes) <= 16 else scenes[:: math.ceil(len(scenes) / 16)]}
            times = default_times(sub) if len(scenes) <= 8 else ",".join(f"{min(s['end'] - 0.05, s['start'] + 0.9):.2f}" for s in sub["scenes"])
        if not times:
            continue
        name = a.out or ("stills.png" if len(pages) == 1 else f"stills-{pathlib.Path(pg).stem}.png")
        cmd = ["node", ENGINE / "render.cjs", p / pg, p / "out" / name, "--stills", times,
               "--cols", str(a.cols or (3 if land else 4)), "--width", str(F.get("stills_width", 480 if land else 360))]
        if not a.no_safe:
            cmd.append("--safe")
        rc |= sh(cmd, env=env, check=False)
    return rc


def cmd_thumb(a):
    p = proj_path(a.proj)
    tl, pages = pages_of(p)
    F = tl.get("formatInfo", {}); tw, th = F.get("thumbnail", [1080, 1920])
    page = a.page or pages[0]
    t = a.t if a.t is not None else (0.0 if a.page else min(tl["scenes"][0]["end"] - 0.05, tl["scenes"][0]["start"] + 1.2))
    land = tw > th
    out = p / "out" / ("thumbnail.jpg" if land else "thumbnail.png")
    tmp = p / "out" / "_thumb.png"
    rc = sh(["node", ENGINE / "render.cjs", p / page, tmp, "--stills", f"{t:.3f}", "--cols", "1", "--width", str(tw), "--nolabel"], env=node_env(), check=False)
    if rc:
        return rc
    rc = sh(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-vf", f"scale={tw}:{th}:flags=lanczos", *(["-q:v", "2"] if land else []), out], check=False)
    tmp.unlink(missing_ok=True)
    if rc == 0:
        kb = out.stat().st_size // 1024
        print(f"thumbnail -> {out} ({tw}x{th}, {kb} KB{', OVER the 2 MB YouTube limit' if kb > 2048 else ''})")
    return rc


def music_params(p, tl):
    m = tl["music"]
    acc = [s["start"] for s in tl["scenes"] if s.get("accent") and s["start"] > 0.3]
    return {"mood": m["mood"], "bpm": m["bpm"], "seed": m.get("seed", 7), "duration": tl["duration"], "accents": acc,
            "key": script_of(p).get("music", {}).get("key"), "risers": bool(script_of(p).get("music", {}).get("risers"))}


def cmd_music(a):
    p = proj_path(a.proj)
    tl = json.loads((p / "timeline.json").read_text())
    if not tl.get("music", {}).get("enabled"):
        print("music is OFF (script.json music.enabled is false). Music is only added when the user asks for it.")
        return 0
    prm = music_params(p, tl)
    stamp = p / "out" / "music.json"
    if not a.force and (p / "out" / "music.wav").exists() and stamp.exists() and json.loads(stamp.read_text()) == prm:
        print("music is up to date"); return 0
    cmd = [PY, HERE / "make_music.py", "--out", p / "out" / "music.wav", "--duration", f"{prm['duration']:.4f}", "--mood", prm["mood"],
           "--bpm", str(prm["bpm"]), "--seed", str(prm["seed"])]
    if prm["accents"]: cmd += ["--accents", ",".join(f"{t:.3f}" for t in prm["accents"])]
    if prm["key"]: cmd += ["--key", prm["key"]]
    if prm["risers"]: cmd.append("--risers")
    rc = sh(cmd, check=False)
    if rc == 0:
        stamp.write_text(json.dumps(prm))
    return rc


def cmd_mix(a):
    p = proj_path(a.proj)
    return sh([PY, HERE / "mix_audio.py", p], check=False)


def mode(a):
    return "final" if getattr(a, "final", False) else "draft"


def file_hash(paths):
    h = hashlib.sha1()
    for f in paths:
        f = pathlib.Path(f)
        if f.is_file():
            h.update(str(f.name).encode()); h.update(f.read_bytes())
    return h.hexdigest()


def count_frames(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    try:
        return int(r.stdout.strip().split(",")[0])
    except ValueError:
        return -1


def cmd_render(a):
    p = proj_path(a.proj)
    sc = script_of(p); m = mode(a)
    tl = json.loads((p / "timeline.json").read_text())
    fps = sc.get("fps", 30) if m == "final" else 30
    sub = a.sub or (4 if m == "final" else 1)
    crf = "16" if m == "final" else "20"
    scale = tl.get("formatInfo", {}).get("scale", 1) if m == "final" else 1   # drafts of 4K videos render at 1080p
    workers = a.workers or max(1, min(4, os.cpu_count() or 2))
    total = round(tl["duration"] * fps)
    segs = tl.get("segments") or [{"page": "index.html", "start": 0, "end": tl["duration"]}]
    # frame ranges per page segment, split into chunks (small enough to use every worker, at most --chunk seconds)
    bounds = [round(sg["start"] * fps) for sg in segs] + [total]
    chunk = max(fps * 2, min(int(a.chunk * fps), math.ceil(total / workers)))
    shared = file_hash([p / "kit.js", p / "style.css", p / "style.js", p / "timeline.js",
                        *sorted(x for x in glob.glob(str(p / "assets" / "**" / "*"), recursive=True))])
    units = []
    for i, sg in enumerate(segs):
        f0, f1 = bounds[i], bounds[i + 1]
        if a.start is not None or a.end is not None:   # partial render (preview a range)
            f0 = max(f0, round((a.start or 0) * fps)); f1 = min(f1, round(a.end * fps) if a.end is not None else f1)
        page_h = file_hash([p / sg["page"]])
        for c0 in range(f0, f1, chunk):
            c1 = min(f1, c0 + chunk)
            key = hashlib.sha1(f"{shared}{page_h}{c0}-{c1}-{fps}-{sub}-{crf}-{scale}".encode()).hexdigest()[:12]
            units.append({"page": sg["page"], "f0": c0, "f1": c1, "file": p / "out" / "chunks" / m / f"{pathlib.Path(sg['page']).stem}-{c0:06d}-{c1:06d}-{key}.mp4"})
    cdir = p / "out" / "chunks" / m
    if a.fresh and cdir.exists():
        shutil.rmtree(cdir)
    cdir.mkdir(parents=True, exist_ok=True)
    todo = [u for u in units if not (u["file"].exists() and count_frames(u["file"]) == u["f1"] - u["f0"])]
    print(f"render {m}: {total} frames @ {fps} fps, {sub} sub-frame(s), {len(units)} chunk(s), {len(units) - len(todo)} cached, {len(todo)} to render, {workers} worker(s)", flush=True)
    env = node_env(); t0 = time.time(); failed = []

    def job(u):
        cmd = ["node", ENGINE / "render.cjs", p / u["page"], u["file"], "--ff", str(u["f0"]), "--tf", str(u["f1"]), "--fps", str(fps), "--sub", str(sub),
               "--crf", crf, "--scale", str(scale), "--workers", "1", "--quiet"]
        r = subprocess.run([str(c) for c in cmd], env=env, capture_output=True, text=True)
        return u, r

    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for k, (u, r) in enumerate(ex.map(job, todo), 1):
            if r.returncode != 0:
                failed.append(u); u["file"].unlink(missing_ok=True)
                print(f"  FAIL chunk {u['page']} frames {u['f0']}-{u['f1']}:\n{(r.stderr or r.stdout).strip()[-800:]}", flush=True)
            else:
                print(f"  [{k}/{len(todo)}] {u['page']} frames {u['f0']}-{u['f1']}  ({time.time() - t0:.0f}s)", flush=True)
    if failed:
        print(f"\nSTOPPED: {len(failed)} chunk(s) failed"); return 1
    keep = {u["file"].name for u in units}
    for f in cdir.glob("*.mp4"):          # drop chunks from older versions
        if f.name not in keep:
            f.unlink()
    lst = cdir / "list.txt"
    lst.write_text("".join(f"file '{u['file'].resolve()}'\n" for u in units))
    out = p / "out" / f"{m}_silent.mp4"
    rc = sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", out], check=False)
    if rc == 0:
        print(f"video -> {out}  ({time.time() - t0:.0f}s)")
    return rc


def cmd_mux(a):
    p = proj_path(a.proj); m = mode(a)
    silent, mix, out = p / "out" / f"{m}_silent.mp4", p / "out" / "mix.wav", p / "out" / f"{m}.mp4"
    if not silent.exists():
        print(f"no {silent.name}; run render first"); return 1
    if not mix.exists():
        print("no out/mix.wav; run mix first"); return 1
    vd = float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0", silent],
                              capture_output=True, text=True).stdout.strip() or 0)
    rc = sh(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", mix, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-af", "apad", "-t", f"{vd:.4f}", "-movflags", "+faststart", out], check=False)
    if rc == 0:
        print(f"muxed -> {out}")
    return rc


def cmd_verify(a):
    p = proj_path(a.proj); m = mode(a)
    v = p / "out" / f"{m}.mp4"
    if a.file: v = pathlib.Path(a.file)
    sc = script_of(p)
    fps = sc.get("fps", 30) if m == "final" else 30
    return sh([PY, HERE / "verify_video.py", v, "--timeline", p / "timeline.json", "--fps", str(fps), "--sheet", p / "out" / f"verify_sheet_{m}.png",
               "--json", p / "out" / f"verify_{m}.json"], check=False)


def cmd_build(a):
    p = proj_path(a.proj)
    steps = [("timeline", cmd_timeline), ("check", cmd_check), ("music", cmd_music), ("mix", cmd_mix), ("render", cmd_render), ("mux", cmd_mux), ("verify", cmd_verify)]
    for name, fn in steps:
        print(f"\n===== {name} =====", flush=True)
        a.force = False; a.sub = getattr(a, "sub", None)
        rc = fn(a)
        if rc:
            print(f"\nBUILD STOPPED at '{name}'. Fix it and re-run (steps are cheap to repeat)."); return rc
    print(f"\nBUILD OK -> {p / 'out' / (mode(a) + '.mp4')}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("doctor"); sp.add_parser("styles")
    x = sp.add_parser("init"); x.add_argument("proj"); x.add_argument("--style", default="editorial"); x.add_argument("--force", action="store_true")
    x.add_argument("--format", default="short", choices=["short", "long", "long-4k"])
    x = sp.add_parser("style"); x.add_argument("proj"); x.add_argument("name")
    x = sp.add_parser("kit"); x.add_argument("proj")
    for n in ("timeline", "check", "mix"):
        sp.add_parser(n).add_argument("proj")
    x = sp.add_parser("music"); x.add_argument("proj"); x.add_argument("--force", action="store_true")
    x = sp.add_parser("stills"); x.add_argument("proj"); x.add_argument("--times"); x.add_argument("--no-safe", action="store_true")
    x.add_argument("--cols", type=int); x.add_argument("--out")
    x = sp.add_parser("thumb"); x.add_argument("proj"); x.add_argument("--t", type=float); x.add_argument("--page")
    for n in ("render", "mux", "verify", "build"):
        x = sp.add_parser(n); x.add_argument("proj"); g = x.add_mutually_exclusive_group(); g.add_argument("--draft", action="store_true"); g.add_argument("--final", action="store_true")
        if n in ("render", "build"):
            x.add_argument("--workers", type=int); x.add_argument("--sub", type=int)
            x.add_argument("--chunk", type=float, default=20.0, help="max seconds per render chunk"); x.add_argument("--fresh", action="store_true", help="ignore cached chunks")
            x.add_argument("--from", dest="start", type=float); x.add_argument("--to", dest="end", type=float)
        if n == "verify":
            x.add_argument("--file")
    a = ap.parse_args()
    if a.cmd == "styles":
        return sh([PY, HERE / "style.py", "--list"], check=False)
    if a.cmd == "kit":
        shutil.copy2(ENGINE / "kit.js", proj_path(a.proj) / "kit.js"); print("kit.js refreshed"); return 0
    if a.cmd == "build":
        a.file = None
    return {"doctor": cmd_doctor, "init": cmd_init, "style": cmd_style, "timeline": cmd_timeline, "check": cmd_check, "stills": cmd_stills,
            "music": cmd_music, "mix": cmd_mix, "render": cmd_render, "thumb": cmd_thumb, "mux": cmd_mux, "verify": cmd_verify, "build": cmd_build}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main() or 0)
