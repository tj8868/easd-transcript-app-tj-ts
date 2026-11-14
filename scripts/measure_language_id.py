#!/usr/bin/env python3
"""
Phase 2 measurement for Bangla/English switching (docs/designs/bilingual_local_transcription.md).
Developer tool; the app never imports it. Run each step alone on 8 GB PCs (one model at a time).

  1. Cut an excerpt and list its speech stretches for a person to label:
       .venv/bin/python scripts/measure_language_id.py stretches <recording> --start 12:00 --end 20:00 --out labels.csv
     -> labels.csv (+ labels.wav, the excerpt). Fill the `lang` column with bn, en or mixed while
        listening (orig_time is the position in the original recording). Leave a row blank to skip it.

  2. Score the three detectors (whisper-bengaliai, tiny, base) on the labelled stretches:
       .venv/bin/python scripts/measure_language_id.py score labels.csv
     -> accuracy per detector and English threshold, errors each way, accuracy by stretch length,
        detector speed; saved to labels.score.json. tiny/base are downloaded once into models/.

  3. Transcribe the excerpt with switching off and on, and check goals G1, G2 and G4:
       .venv/bin/python scripts/measure_language_id.py compare labels.csv --detector tiny
     -> labels.off.txt / labels.on.txt and a pass/fail line per criterion (labels.compare.json).
        Downloads small.en once into models/ if missing.
"""
import argparse
import csv
import gc
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

THRESHOLDS = (0.5, 0.6, 0.7, 0.8)
BUCKETS = ((0, 1, "<1s"), (1, 2, "1-2s"), (2, 4, "2-4s"), (4, 1e9, ">4s"))


def parse_time(text):
    secs = 0.0
    for part in str(text).strip().split(":"):
        secs = secs * 60 + float(part)
    return secs


def fmt(secs):
    secs = int(round(secs))
    return f"{secs // 3600:d}:{secs // 60 % 60:02d}:{secs % 60:02d}" if secs >= 3600 else f"{secs // 60:02d}:{secs % 60:02d}"


def stem(csv_path):
    return os.path.splitext(csv_path)[0]


def read_labels(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)]
    for r in rows:
        r["start_sec"], r["end_sec"] = float(r["start_sec"]), float(r["end_sec"])
        r["lang"] = (r.get("lang") or "").strip().lower()
    return rows


# ----------------------------------------------------------------------------- 1. stretches
def cmd_stretches(args):
    import faster_whisper
    import local_whisper_engine as lwe
    start, end = parse_time(args.start), parse_time(args.end)
    full_wav = lwe.convert_to_wav_pcm16k(args.audio, input_hint=os.path.splitext(args.audio)[1].lstrip(".") or "mp3")
    excerpt = stem(args.out) + ".wav"
    try:
        if not lwe.slice_wav_pcm16k(full_wav, start, end - start, excerpt):
            sys.exit("could not cut the excerpt (check --start/--end)")
    finally:
        if full_wav != args.audio and os.path.exists(full_wav):
            os.remove(full_wav)
    audio = faster_whisper.decode_audio(excerpt)
    stretches = lwe._split_speech_stretches(audio)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["start_sec", "end_sec", "duration", "orig_time", "lang"])
        for s, e in stretches:
            w.writerow([f"{s:.2f}", f"{e:.2f}", f"{e - s:.1f}", fmt(start + s), ""])
    with open(stem(args.out) + ".meta.json", "w", encoding="utf-8") as f:
        json.dump({"source": os.path.abspath(args.audio), "start_sec": start, "end_sec": end}, f)
    print(f"{len(stretches)} stretches -> {args.out} (excerpt: {excerpt}).")
    print("Fill the `lang` column with bn / en / mixed while listening; orig_time is the position in the recording.")


# ----------------------------------------------------------------------------- 2. score
def _load_detector(name):
    import local_whisper_engine as lwe
    if name == "bengaliai":
        return lwe.get_local_whisper_model("bengaliai")
    if not lwe.ensure_aux_model(name):
        raise RuntimeError(f"could not download {name}: {lwe._AUX_DOWNLOAD_FAILED.get(name)}")
    model = lwe._load_aux_model(name)
    if model is None:
        raise RuntimeError(f"could not load {name}")
    return model


def _free_models():
    import local_whisper_engine as lwe
    lwe._LOCAL_MODELS.clear()
    lwe._LOCAL_MODEL = None
    gc.collect()


def cmd_score(args):
    import faster_whisper
    import local_whisper_engine as lwe
    rows = [r for r in read_labels(args.labels) if r["lang"] in ("bn", "en")]
    if not rows:
        sys.exit("no rows labelled bn or en in " + args.labels)
    audio = faster_whisper.decode_audio(stem(args.labels) + ".wav")
    total_min = sum(r["end_sec"] - r["start_sec"] for r in rows) / 60
    results = {}
    for name in args.detectors:
        print(f"\n=== detector: {name} ===")
        try:
            det = _load_detector(name)
        except Exception as e:
            print(f"  skipped: {e}")
            continue
        t0 = time.time()
        scored = []
        for r in rows:
            seg = audio[int(r["start_sec"] * 16000):int(r["end_sec"] * 16000)]
            _, p_en = lwe._stretch_language(det, seg)
            scored.append((r["lang"], r["end_sec"] - r["start_sec"], p_en))
        secs = time.time() - t0
        res = {"seconds_per_minute": round(secs / max(total_min, 1e-6), 2), "thresholds": {}}
        for thr in THRESHOLDS:
            judged = [(lang, dur, "en" if p >= thr else "bn") for lang, dur, p in scored if dur >= args.min_lid]
            n = len(judged) or 1
            n_bn = sum(1 for l, _, _ in judged if l == "bn") or 1
            n_en = sum(1 for l, _, _ in judged if l == "en") or 1
            acc = sum(1 for l, _, g in judged if l == g) / n
            bn_as_en = sum(1 for l, _, g in judged if l == "bn" and g == "en")
            en_as_bn = sum(1 for l, _, g in judged if l == "en" and g == "bn")
            buckets = {}
            for lo, hi, label in BUCKETS:
                b = [(l, "en" if p >= thr else "bn") for l, d, p in scored if lo <= d < hi]
                buckets[label] = f"{sum(1 for l, g in b if l == g)}/{len(b)}"
            res["thresholds"][str(thr)] = {
                "accuracy": round(acc, 3), "bangla_tagged_english": bn_as_en,
                "bangla_tagged_english_pct": round(100 * bn_as_en / n_bn, 1),
                "english_tagged_bangla": en_as_bn, "english_tagged_bangla_pct": round(100 * en_as_bn / n_en, 1),
                "by_length": buckets}
            print(f"  threshold {thr}: accuracy {acc:.1%} on {len(judged)} stretches >= {args.min_lid}s | "
                  f"Bangla->English {bn_as_en} ({100 * bn_as_en / n_bn:.1f}%) | English->Bangla {en_as_bn} | "
                  f"by length {buckets}")
        print(f"  speed: {res['seconds_per_minute']} s of CPU per minute of speech")
        results[name] = res
        del det
        _free_models()
    out = stem(args.labels) + ".score.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {out}. Pass criterion: >= 90% accuracy and <= 3% Bangla tagged English at the chosen threshold.")


# ----------------------------------------------------------------------------- 3. compare
def _run_once(args):
    """Child process: one transcription, so each run gets its own peak-RSS figure."""
    import resource
    import local_whisper_engine as lwe
    t0 = time.time()
    res = lwe.transcribe_local_audio(args.wav, language=None, mime_type="audio/wav", beam_size=1, code_switch=True)
    print(json.dumps({"status": res.get("status"), "transcript": res.get("raw_transcript", ""),
                      "model": res.get("model"), "wall_sec": round(time.time() - t0, 1),
                      "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}))


def _line_secs(line):
    m = re.match(r"^\[(\d+):(\d{2})(?::(\d{2}))?\]", line)
    if not m:
        return None
    a, b, c = m.groups()
    return int(a) * 3600 + int(b) * 60 + int(c) if c else int(a) * 60 + int(b)


def _lines_in(transcript, s, e):
    return [l for l in transcript.splitlines() if (t := _line_secs(l)) is not None and s - 1 <= t <= e + 1]


def _latin_share(text):
    body = re.sub(r"^\[[^\]]*\]\s*Speaker \d+:\s*", "", text)
    latin = len(re.findall(r"[A-Za-z]", body))
    bengali = len(re.findall(r"[ঀ-৿]", body))
    return latin / (latin + bengali) if latin + bengali else 0.0


def cmd_compare(args):
    import local_whisper_engine as lwe
    os.environ["EASD_CS_DETECTOR"] = args.detector
    if args.threshold is not None:
        os.environ["EASD_CS_EN_THRESHOLD"] = str(args.threshold)
    ready = lwe.ensure_code_switch_models()
    if not all(ready.values()):
        sys.exit(f"switching models could not be downloaded: {ready} {lwe._AUX_DOWNLOAD_FAILED}")
    wav = stem(args.labels) + ".wav"
    runs = {}
    for mode in ("off", "on"):
        env = dict(os.environ, EASD_CODE_SWITCH="1" if mode == "on" else "0")
        print(f"transcribing with switching {mode} ...", flush=True)
        out = subprocess.run([sys.executable, os.path.abspath(__file__), "_run", wav], env=env,
                             capture_output=True, text=True, cwd=ROOT)
        last = [l for l in out.stdout.splitlines() if l.startswith("{")]
        if out.returncode != 0 or not last:
            sys.exit(f"run '{mode}' failed:\n{out.stderr[-2000:]}")
        runs[mode] = json.loads(last[-1])
        with open(f"{stem(args.labels)}.{mode}.txt", "w", encoding="utf-8") as f:
            f.write(runs[mode]["transcript"])
        print(f"  {mode}: {runs[mode]['wall_sec']} s, peak RSS {runs[mode]['peak_rss_mb']} MB, model {runs[mode]['model']}")

    rows = read_labels(args.labels)
    en_rows = [r for r in rows if r["lang"] == "en" and r["end_sec"] - r["start_sec"] >= 2.0]
    en_ok = sum(1 for r in en_rows
                if _latin_share(" ".join(_lines_in(runs["on"]["transcript"], r["start_sec"], r["end_sec"]))) >= 0.7)
    bn_rows = [r for r in rows if r["lang"] == "bn"]
    bn_same = sum(1 for r in bn_rows if _lines_in(runs["on"]["transcript"], r["start_sec"], r["end_sec"])
                  == _lines_in(runs["off"]["transcript"], r["start_sec"], r["end_sec"]))
    g1 = en_ok / len(en_rows) if en_rows else None
    g2 = bn_same / len(bn_rows) if bn_rows else None
    time_ratio = runs["on"]["wall_sec"] / max(runs["off"]["wall_sec"], 1e-6)
    rss_diff = runs["on"]["peak_rss_mb"] - runs["off"]["peak_rss_mb"]
    checks = {
        "G1 English stretches >=2s written in English (>= 80%)": (g1 is not None and g1 >= 0.8, g1),
        "G2 Bangla stretches unchanged (>= 97%)": (g2 is not None and g2 >= 0.97, g2),
        "G4 time with switching <= 1.15x": (time_ratio <= 1.15, round(time_ratio, 2)),
        "G4 extra peak RAM <= 800 MB": (rss_diff <= 800, round(rss_diff)),
    }
    print()
    for name, (ok, val) in checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {val}")
    with open(stem(args.labels) + ".compare.json", "w", encoding="utf-8") as f:
        json.dump({"detector": args.detector, "threshold": os.environ.get("EASD_CS_EN_THRESHOLD", "0.6"),
                   "runs": {k: {x: v for x, v in r.items() if x != "transcript"} for k, r in runs.items()},
                   "checks": {k: {"pass": ok, "value": v} for k, (ok, v) in checks.items()}}, f, indent=2)
    print(f"\nTranscripts: {stem(args.labels)}.off.txt / .on.txt")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stretches")
    s.add_argument("audio")
    s.add_argument("--start", required=True)
    s.add_argument("--end", required=True)
    s.add_argument("--out", required=True)
    s = sub.add_parser("score")
    s.add_argument("labels")
    s.add_argument("--detectors", nargs="+", default=["bengaliai", "tiny", "base"])
    s.add_argument("--min-lid", type=float, default=2.0, dest="min_lid")
    s = sub.add_parser("compare")
    s.add_argument("labels")
    s.add_argument("--detector", required=True, choices=["bengaliai", "tiny", "base"])
    s.add_argument("--threshold", type=float, default=None)
    s = sub.add_parser("_run")
    s.add_argument("wav")
    args = p.parse_args()
    {"stretches": cmd_stretches, "score": cmd_score, "compare": cmd_compare, "_run": _run_once}[args.cmd](args)


if __name__ == "__main__":
    main()
