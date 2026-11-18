#!/usr/bin/env python3
"""Build the Short's timeline from script.json + the narration clips.

usage: timeline.py <project_dir>

Reads   script.json, style.json, voice/<scene-id>.wav (optional), voice/<scene-id>.words.json (optional)
Writes  timeline.json (for scripts) and timeline.js (window.TIMELINE, for the page)

Voice drives time: each scene lasts as long as its narration plus a short gap (never less than its `min`).
Without a voice file the scene length is estimated from the word count, so you can draft visuals first.
Word times come from voice/<id>.words.json when align_words.py made one, otherwise they are estimated
by spreading syllables over the clip (good to about +-0.15s; fine for captions, use cues on stressed words).
"""
import json, math, pathlib, re, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
FORMATS = json.loads((HERE.parent / "engine" / "formats.json").read_text())

TAG = re.compile(r"\[[^\]]+\]")          # OmniVoice non-verbal tags like [laughter]; spoken, never captioned
ID_OK = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
TRANSITION_SFX = {"push": "whoosh", "slide": "whoosh", "punch": "whoosh", "pop": "pop", "drift": None, "fade-transform": None}


def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise SystemExit(f"cannot read duration of {path}: {r.stderr.strip()}")


def syllables(word):
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 1 if re.search(r"\d", word) else 0.5
    n = len(re.findall(r"[aeiouy]+", w))
    if w.endswith("e") and n > 1 and not w.endswith(("le", "ee")):
        n -= 1
    return max(1, n)


def tokens(text):
    """display words of a line, with tags removed but remembered as pauses"""
    out = []
    for raw in text.split():
        if TAG.fullmatch(raw):
            if out:
                out[-1]["pause"] += 2.0
            continue
        w = TAG.sub("", raw).strip()
        if not w:
            continue
        pause = 1.6 if re.search(r"[.!?…]$", w) else 0.9 if re.search(r"[,;:—–-]$", w) else 0.0
        out.append({"w": w, "weight": syllables(w) + (1.5 if re.search(r"\d", w) and len(w) > 2 else 0), "pause": pause})
    return out


def spread(toks, t0, t1):
    """estimate word start/end over [t0, t1] proportional to syllables, with pauses after punctuation"""
    if not toks:
        return []
    total = sum(t["weight"] + t["pause"] for t in toks) - toks[-1]["pause"]
    unit = max(1e-6, (t1 - t0)) / max(total, 1e-6)
    out, t = [], t0
    for i, tk in enumerate(toks):
        e = t + tk["weight"] * unit
        out.append({"w": tk["w"], "s": round(t, 3), "e": round(e, 3)})
        t = e + (tk["pause"] * unit if i < len(toks) - 1 else 0)
    return out


def map_caption(caption, spoken_words, t0, t1):
    """caption text that differs from the spoken text ("20%" for "twenty percent"): spread over the same span"""
    toks = tokens(caption)
    if spoken_words and len(toks) == len(spoken_words):
        return [{"w": tk["w"], "s": w["s"], "e": w["e"]} for tk, w in zip(toks, spoken_words)]
    return spread(toks, t0, t1)


def ts(t):
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_srt(project, scenes, max_chars=42, max_dur=6.0):
    """out/captions.srt from caption word times: upload it to YouTube as subtitles (both formats)"""
    cues, cur = [], []
    for sc in scenes:
        for w in sc["caps"]:
            text = " ".join(x["w"] for x in cur + [w])
            if cur and (len(text) > max_chars or w["e"] - cur[0]["s"] > max_dur):
                cues.append(cur); cur = []
            cur.append(w)
            if re.search(r"[.!?]$", w["w"]):
                cues.append(cur); cur = []
        if cur:
            cues.append(cur); cur = []
    out = project / "out"; out.mkdir(exist_ok=True)
    lines = []
    for i, c in enumerate(cues, 1):
        lines += [str(i), f"{srt_time(c[0]['s'])} --> {srt_time(c[-1]['e'] + 0.15)}", " ".join(x["w"] for x in c), ""]
    (out / "captions.srt").write_text("\n".join(lines))


def build(project):
    project = pathlib.Path(project)
    script = json.loads((project / "script.json").read_text())
    style = json.loads((project / "style.json").read_text()) if (project / "style.json").exists() else {}
    fps = int(script.get("fps", 30))
    errors, notes = [], []
    fmt = script.get("format", "short")
    if fmt not in FORMATS:
        errors.append(f"format '{fmt}' unknown; use one of {', '.join(FORMATS)}"); fmt = "short"
    F = FORMATS[fmt]
    w, h = F["w"], F["h"]
    long_form = fmt != "short"
    pace = {"lead_in": 0.12, "gap": 0.22 if not long_form else 0.3, "tail": 0.7 if not long_form else 1.5, "wps": 2.7 if not long_form else 2.5,
            **script.get("pacing", {})}
    burn = script.get("captions", {}).get("burn")
    if burn is None:
        burn = F["captions"]["burn"]

    music = dict(script.get("music") or {})
    music_on = bool(music.get("enabled"))
    if music_on:
        from make_music import MOODS
        mood = music.get("mood") or style.get("music", {}).get("mood") or "upbeat"
        if mood not in MOODS:
            errors.append(f"music.mood '{mood}' unknown; use one of {', '.join(MOODS)}")
            mood = "upbeat"
        style_bpm = style.get("music", {}).get("bpm") if style.get("music", {}).get("mood") == mood else None   # style tempo only for its own mood
        bpm = float(music.get("bpm") or style_bpm or MOODS[mood]["bpm"])
        music = {"enabled": True, "mood": mood, "bpm": bpm, "offset": 0.0, "seed": int(music.get("seed", 7)),
                 "snap": music.get("snap", True), "level_db": music.get("level_db")}
    else:
        music = {"enabled": False}
    sfx_on = script.get("sfx", {}).get("enabled")
    if sfx_on is None:
        sfx_on = style.get("sfx", {}).get("enabled", True)
    style_transition = style.get("transition", "push")

    scenes, seen = [], set()
    t = 0.0
    for i, sc in enumerate(script.get("scenes", [])):
        sid = sc.get("id", "")
        if not ID_OK.match(sid):
            errors.append(f"scene {i}: id '{sid}' must be lowercase letters, digits, - or _ (it becomes a DOM id)")
        if sid in seen:
            errors.append(f"scene id '{sid}' used twice")
        seen.add(sid)
        say = sc.get("say") or sc.get("text") or ""
        if not say.strip():
            errors.append(f"scene '{sid}' has no narration ('say')")
        start = t
        pre = pace["lead_in"] if i == 0 else sc.get("pre", 0.08)
        vfile = project / sc.get("voice_file", f"voice/{sid}.wav")
        toks = tokens(say)
        if vfile.exists():
            vdur = probe_duration(vfile)
            estimated = False
            if toks:
                rate = len(toks) / max(vdur, 1e-3)
                if rate > 5.5 or rate < 1.0:
                    notes.append(f"scene '{sid}': {len(toks)} words in {vdur:.2f}s ({rate:.1f} words/s) looks wrong; "
                                 "listen to it - the TTS may have skipped, repeated or rambled")
        else:
            vdur = max(0.6, len(toks) / pace["wps"] + sum(1 for tk in toks if tk["pause"] > 1) * 0.15)
            estimated = True
        vstart = start + pre
        vend = vstart + vdur
        wfile = vfile.with_suffix(".words.json")
        if not estimated and wfile.exists():
            words = [{"w": x["w"], "s": round(vstart + x["s"], 3), "e": round(vstart + x["e"], 3)} for x in json.loads(wfile.read_text())]
        else:
            words = spread(toks, vstart + 0.03, vend - 0.06)
        end = max(vend + pace["gap"], start + float(sc.get("min", 1.2))) + float(sc.get("hold", 0))
        if music_on and music.get("snap") and i < len(script["scenes"]) - 1:
            half = 60.0 / music["bpm"] / 2
            end = math.ceil((end - 1e-6) / half) * half
        caption = sc.get("caption")
        caps = map_caption(caption, words, words[0]["s"] if words else vstart, words[-1]["e"] if words else vend) if caption else words
        page = sc.get("page", "index.html")
        if not (project / page).exists():
            errors.append(f"scene '{sid}': page '{page}' does not exist")
        scenes.append({"id": sid, "page": page, "chapter": sc.get("chapter"), "start": round(start, 3), "end": round(end, 3), "voiceStart": round(vstart, 3),
                       "voiceEnd": round(vend, 3), "voice": str(vfile.relative_to(project)) if not estimated else None,
                       "estimated": estimated, "say": say, "caption": caption, "words": words, "caps": caps,
                       "accent": bool(sc.get("accent")), "transition": sc.get("transition"), "sfx": sc.get("sfx", "auto"),
                       "sfx_at": sc.get("sfx_at", [])})
        t = end
    if not scenes:
        errors.append("script.json has no scenes")
    else:
        scenes[-1]["end"] = round(scenes[-1]["end"] + pace["tail"], 3)
    duration = math.ceil((scenes[-1]["end"] if scenes else 1) * fps - 1e-6) / fps
    if scenes:
        scenes[-1]["end"] = round(duration, 3)

    # sound-effect cues (mixed by mix_audio.py when sfx is on)
    cues = []
    if sfx_on:
        for i, sc in enumerate(scenes):
            kind = sc["sfx"]
            if kind == "auto":
                kind = TRANSITION_SFX.get(sc["transition"] or style_transition) if i > 0 else None
            if kind and kind != "none":
                lead = 2 / fps if kind in ("whoosh", "riser") else 0
                cues.append({"t": round(max(0, sc["start"] - lead - (1.9 if kind == "riser" else 0)), 3), "kind": kind, "scene": sc["id"]})
            if sc["accent"]:
                cues.append({"t": round(sc["start"], 3), "kind": "impact", "scene": sc["id"]})
            for at in sc["sfx_at"]:
                word = at.get("word")
                hit = next((x for x in sc["words"] if word and re.sub(r"\W", "", x["w"].lower()).startswith(word.lower())), None)
                tt = hit["s"] if hit else sc["start"] + float(at.get("t", 0))
                cues.append({"t": round(tt, 3), "kind": at.get("kind", "pop"), "scene": sc["id"], "gain_db": at.get("gain_db")})
    cues.sort(key=lambda c: c["t"])

    if duration > F["max_duration"]:
        errors.append(f"total {duration:.1f}s is over the {F['max_duration']}s limit for format '{fmt}'"
                      + ("; cut scenes, or use format 'long' for a regular 16:9 video" if fmt == "short" else ""))
    elif F.get("soft_duration") and duration > F["soft_duration"]:
        notes.append(f"total {duration:.1f}s: allowed (max {F['max_duration']}s) but most Shorts that perform well are under {F['soft_duration']}s")

    # segments: consecutive scenes on the same page (each is rendered from that page and concatenated)
    segments = []
    for sc in scenes:
        if segments and segments[-1]["page"] == sc["page"]:
            segments[-1]["end"] = sc["end"]; segments[-1]["scenes"].append(sc["id"])
        else:
            segments.append({"page": sc["page"], "start": sc["start"], "end": sc["end"], "scenes": [sc["id"]]})

    # chapters (YouTube: first at 0:00, at least 3, each at least 10 s)
    chapters = [{"t": sc["start"], "title": sc["chapter"], "scene": sc["id"]} for sc in scenes if sc.get("chapter")]
    if chapters:
        if chapters[0]["t"] > 0.001:
            notes.append("chapters: the first chapter must start at 0:00; add \"chapter\" to the first scene")
        if len(chapters) < 3:
            notes.append(f"chapters: YouTube needs at least 3 chapters to show them ({len(chapters)} given)")
        for a, b in zip(chapters, chapters[1:] + [{"t": duration}]):
            if b["t"] - a["t"] < 10:
                notes.append(f"chapters: '{a['title']}' is {b['t'] - a['t']:.1f}s long; YouTube needs at least 10s per chapter")
        out = project / "out"; out.mkdir(exist_ok=True)
        (out / "chapters.txt").write_text("".join(f"{ts(c['t'])} {c['title']}\n" for c in chapters))
    write_srt(project, scenes)
    est = [s["id"] for s in scenes if s["estimated"]]
    if est:
        notes.append(f"no voice yet for: {', '.join(est)} (timings estimated at {pace['wps']} words/s)")

    tl = {"title": script.get("title", ""), "style": style.get("name"), "format": fmt, "formatInfo": F, "w": w, "h": h, "fps": fps,
          "duration": round(duration, 4), "captions": {"burn": bool(burn)}, "music": music, "sfx": {"enabled": bool(sfx_on), "cues": cues},
          "segments": segments, "chapters": chapters, "scenes": scenes}
    (project / "timeline.json").write_text(json.dumps(tl, indent=1))
    (project / "timeline.js").write_text("/* generated by scripts/timeline.py; do not edit, re-run it */\nwindow.TIMELINE = " + json.dumps(tl) + ";\n")
    print(f"timeline: {fmt} {w * F['scale']}x{h * F['scale']}, {len(scenes)} scenes, {ts(duration)} ({duration:.2f}s) @ {fps} fps, {len(segments)} page segment(s), "
          f"{len(chapters)} chapter(s), captions {'burned in' if burn else 'SRT only'}, music {'on (' + music['mood'] + ', ' + str(music['bpm']) + ' BPM)' if music_on else 'off'}, "
          f"sfx {'on (' + str(len(cues)) + ' cues)' if sfx_on else 'off'}")
    for s in scenes[:40]:
        print(f"  {s['id']:<14} {s['start']:6.2f} -> {s['end']:6.2f}  voice {s['voiceStart']:.2f}-{s['voiceEnd']:.2f}{'  (estimated)' if s['estimated'] else ''}")
    for n in notes:
        print("NOTE  " + n)
    for e in errors:
        print("ERROR " + e)
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(2)
    sys.exit(build(sys.argv[1]))
