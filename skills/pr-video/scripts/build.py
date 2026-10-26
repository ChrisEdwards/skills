"""Mux slides/NN.png against WORKDIR/track.wav into one MP4, then verify it.

Usage: python3 build.py WORKDIR OUT.mp4

Slide cuts land on cumulative frame times (rounded once per boundary, so error never
builds up). Audio is encoded once from the single track. Verification prints:
video vs audio duration, long-silence count (should equal slides - 1), and writes
WORKDIR/boundaries.png, one frame from 0.8s into each slide, to Read and confirm order.
With WORKDIR/segments.json, each slide's highlight frames switch at their marker times.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

from shoot import variant

FPS = 30


def probe(path: Path, stream: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries",
                          "stream=duration", "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(out.stdout.strip())


def main() -> None:
    work, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    durations = json.loads((work / "durations.json").read_text())
    pngs = sorted((work / "slides").glob("[0-9][0-9].png"))
    if len(pngs) != len(durations):
        raise SystemExit(f"{len(pngs)} slide PNGs but {len(durations)} narrated slides.")

    seg_file = work / "segments.json"
    segments = json.loads(seg_file.read_text()) if seg_file.exists() else [[[0.0, None]]] * len(durations)
    lines, starts, done, elapsed = [], [], 0, 0.0
    for png, d, segs in zip(pngs, durations, segments):
        starts.append(elapsed)
        for k, (_, spec) in enumerate(segs):
            img = variant(png, spec)
            if not img.exists():
                raise SystemExit(f"Missing {img.name}. Re-run shoot.py after narrate.py.")
            end = round((elapsed + (segs[k + 1][0] if k + 1 < len(segs) else d)) * FPS)
            if end > done:
                lines += [f"file '{img}'", f"duration {(end - done) / FPS:.6f}"]
                done = end
        elapsed += d
    lines.append(lines[-2])  # concat demuxer ignores the last duration otherwise
    (work / "slides.txt").write_text("\n".join(lines) + "\n")

    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", work / "slides.txt", "-i", work / "track.wav", "-map", "0:v", "-map", "1:a",
                    "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-tune", "stillimage",
                    "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-t", f"{elapsed:.3f}",
                    "-movflags", "+faststart", out], check=True)

    v, a = probe(out, "v:0"), probe(out, "a:0")
    sd = subprocess.run(["ffmpeg", "-i", work / "track.wav", "-af", "silencedetect=noise=-45dB:d=1.4",
                         "-f", "null", "-"], capture_output=True, text=True).stderr
    silences = len(re.findall("silence_end", sd))
    frames = []
    for i, s in enumerate(starts):
        f = work / f"b{i:02d}.png"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{s + 0.8:.2f}", "-i", out,
                        "-frames:v", "1", "-vf", "scale=480:-1", f], check=True)
        frames.append(f)
    rows = -(-len(frames) // 4)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "1", "-i", work / "b%02d.png",
                    "-vf", f"tile=4x{rows}:padding=6", "-frames:v", "1", work / "boundaries.png"], check=True)
    for f in work.glob("b[0-9][0-9].png"):
        f.unlink()

    ok = abs(v - a) < 0.1
    print(f"BUILT {out} video={v:.2f}s audio={a:.2f}s {'MATCH' if ok else 'MISMATCH'} "
          f"long_silences={silences} expected={len(durations) - 1}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
