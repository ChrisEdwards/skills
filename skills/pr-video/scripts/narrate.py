"""Render a narration script to ONE continuous WAV plus per-slide durations.

Usage: python3 narrate.py SCRIPT.md WORKDIR [--voice alba] [--speed 1.1] [--seed 99]

SCRIPT.md: optional front matter, then one `## Heading` per slide. Paragraphs under a
heading are spoken. A paragraph starting with ">" is a reader note and is skipped.
Text before the first heading is ignored.

Writes WORKDIR/track.wav and WORKDIR/durations.json (seconds per slide, after tempo).

Highlight markers: `[[116-120]]` or `[[116-120,130]]` anywhere in a paragraph is not
spoken. From the moment the text after it starts, the slide's diff highlights those
new-side lines. `[[]]` clears it. Every slide starts unhighlighted. The timings go to
WORKDIR/segments.json, one list per slide of [seconds into slide, spec or null], which
shoot.py and build.py use to swap highlight frames mid-slide on the same audio track.

Why it works this way (both were real failures):
- Long TTS inputs drift and garble, so every request is one or two sentences.
- Per-slide audio clips joined later gain gaps at each join that compound over a long
  video. So all slides go into one PCM stream, tempo is applied once, and slide
  durations are measured from that same stream.
"""

import argparse
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path

# The TTS server's code ships in the sibling speak skill. Its venv and log are machine data.
SPEAK = Path(__file__).resolve().parents[2] / "speak" / "scripts"
TTS_DATA = Path.home() / ".local/share/agent-tts"
BASE = "http://127.0.0.1:7711"
RATE = 24000  # server returns mono s16le PCM at this rate
MAX_WORDS = 22
GAP_SENTENCE = 0.18
GAP_PARAGRAPH = 0.45
PAD_SLIDE = 0.6  # silence at the start and end of each slide
MARK = re.compile(r"\[\[(.*?)\]\]")
SPEC = re.compile(r"\d+(-\d+)?(,\d+(-\d+)?)*")


def healthy() -> bool:
    try:
        urllib.request.urlopen(f"{BASE}/health", timeout=2)
        return True
    except OSError:
        return False


def ensure_server() -> None:
    if healthy():
        return
    if not (SPEAK / "server.py").exists():
        raise SystemExit(f"The speak skill is not installed beside this one (looked in {SPEAK}).")
    if not (TTS_DATA / "venv/bin/python").exists():
        raise SystemExit(f"No TTS environment at {TTS_DATA / 'venv'}. Follow the speak skill's references/SETUP.md.")
    log = open(TTS_DATA / "server.log", "a")
    subprocess.Popen([TTS_DATA / "venv/bin/python", SPEAK / "server.py"], stdout=log, stderr=log)
    for _ in range(60):
        if healthy():
            return
        time.sleep(0.5)
    raise SystemExit(f"TTS server did not start, see {TTS_DATA / 'server.log'}")


def silence(seconds: float) -> bytes:
    return b"\x00\x00" * int(RATE * seconds)


def chunks(paragraph: str) -> list[str]:
    out: list[str] = []
    for s in re.split(r"(?<=[.?!])\s+", " ".join(paragraph.split())):
        if out and len(out[-1].split()) + len(s.split()) <= MAX_WORDS:
            out[-1] += " " + s
        else:
            out.append(s)
    return out


def say(text: str, a: argparse.Namespace) -> bytes:
    body = json.dumps({"text": text, "voice": a.voice, "normalize": True,
                       "seed": a.seed, "temperature": 0.7}).encode()
    req = urllib.request.Request(f"{BASE}/say", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return resp.read() + silence(GAP_SENTENCE)


def slides(script: str) -> list[tuple[str, list[str]]]:
    if script.startswith("---\n"):
        script = script.split("\n---\n", 1)[1]
    parts = re.split(r"^## (.+)$", script, flags=re.M)[1:]
    result = []
    for title, body in zip(parts[::2], parts[1::2]):
        paras = [p.strip() for p in body.split("\n\n") if p.strip() and not p.strip().startswith(">")]
        result.append((title.strip(), paras))
    if not result:
        raise SystemExit("No `## ` slide headings found.")
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("script", type=Path)
    p.add_argument("workdir", type=Path)
    p.add_argument("--voice", default="alba")
    p.add_argument("--speed", type=float, default=1.1)
    p.add_argument("--seed", type=int, default=99)
    a = p.parse_args()
    a.workdir.mkdir(parents=True, exist_ok=True)

    ensure_server()
    track = bytearray()
    durations, segments = [], []
    for n, (title, paras) in enumerate(slides(a.script.read_text()), 1):
        pcm = bytearray(silence(PAD_SLIDE))
        segs: list[list] = [[0.0, None]]
        for para in paras:
            parts = MARK.split(para)  # text, spec, text, spec, ...
            for i, part in enumerate(parts):
                if i % 2:  # a marker: start a highlight segment at the current audio time
                    spec = part.replace(" ", "") or None
                    if spec and not SPEC.fullmatch(spec):
                        raise SystemExit(f"Slide {n} ({title}): bad highlight marker [[{part}]].")
                    at = len(pcm) / 2 / RATE / a.speed
                    if segs[-1][0] == at:
                        segs[-1][1] = spec
                    elif segs[-1][1] != spec:
                        segs.append([at, spec])
                    continue
                for text in chunks(part):
                    if text:
                        pcm += say(text, a)
            pcm += silence(GAP_PARAGRAPH)
        pcm += silence(PAD_SLIDE)
        if len(pcm) % 2:
            pcm += b"\x00"
        track += pcm
        durations.append(len(pcm) / 2 / RATE / a.speed)
        segments.append(segs)
        print(f"{n:02d} {title} {durations[-1]:.1f}s", flush=True)

    raw = a.workdir / "track.pcm"
    raw.write_bytes(track)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(RATE), "-ac", "1",
                    "-i", raw, "-af", f"atempo={a.speed}", a.workdir / "track.wav"], check=True)
    raw.unlink()
    (a.workdir / "durations.json").write_text(json.dumps(durations))
    (a.workdir / "segments.json").write_text(json.dumps(segments))
    print(f"NARRATION_DONE {sum(durations):.1f}s {len(durations)} slides")


if __name__ == "__main__":
    main()
