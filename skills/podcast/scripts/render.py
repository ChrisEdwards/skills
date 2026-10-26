"""Render a podcast script to MP3 through the speak skill's Pocket TTS server.

Usage: python3 render.py SCRIPT.md OUT.mp3 [--voice alba] [--speed 1.1] [--seed 99]

Spoken text is every paragraph after the front matter. A heading becomes a pause.
A paragraph starting with ">" is a note for the reader and is not spoken.
"""

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

# The TTS server's code ships in the sibling speak skill. Its venv and log are machine data.
SPEAK = Path(__file__).resolve().parents[2] / "speak" / "scripts"
TTS_DATA = Path.home() / ".local/share/agent-tts"
BASE = "http://127.0.0.1:7711"
RATE = 24000


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


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("script", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--voice", default="alba")
    p.add_argument("--speed", type=float, default=1.1)
    p.add_argument("--seed", type=int, default=99)
    a = p.parse_args()

    text = a.script.read_text()
    if text.startswith("---\n"):
        text = text.split("\n---\n", 1)[1]
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]

    ensure_server()
    pcm = a.out.with_suffix(".pcm")
    with open(pcm, "wb") as out:
        for i, block in enumerate(blocks, 1):
            if block.startswith(">"):
                continue
            if block.startswith("#"):
                out.write(silence(1.2))
                continue
            body = json.dumps({"text": block, "voice": a.voice, "normalize": True,
                               "seed": a.seed, "temperature": 0.7}).encode()
            req = urllib.request.Request(f"{BASE}/say", data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as resp:
                out.write(resp.read())
            out.write(silence(0.5))
            print(f"{i}/{len(blocks)}", flush=True)

    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(RATE),
                    "-ac", "1", "-i", pcm, "-af", f"atempo={a.speed}",
                    "-codec:a", "libmp3lame", "-b:a", "64k", a.out], check=True)
    pcm.unlink()
    print(a.out)


if __name__ == "__main__":
    main()
