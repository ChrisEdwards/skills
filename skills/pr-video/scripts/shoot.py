# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10"]
# ///
"""Screenshot every slides/NN.html to NN.png at 1920x1080, then build contact sheets.

Usage: python3 shoot.py WORKDIR [NN ... | stale]

With slide numbers, re-shoots only those. With `stale`, re-shoots every slide whose HTML is
newer than its PNG (Deck.write leaves unchanged HTML untouched, so this is exactly the slides
a build_slides.py edit changed, including every slide that embeds a changed diagram). Always rebuilds WORKDIR/contact-*.png
(six slides per sheet, labelled) so you can Read them and check layout in one look.
If narrate.py wrote WORKDIR/segments.json, also shoots each highlight frame as
NN-hl-<spec>.png (the page opened with #hl=<spec>), and WORKDIR/hl-contact-*.png sheets of
those frames in narration order.
Ends by listing every frame with a red outline (a diff too big, or a marker matching no
shown line), so you fix those without opening every frame.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

CHROME = os.environ.get("CHROME_PATH", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def variant(png: Path, spec: str | None) -> Path:
    """The frame for one highlight state of a slide. build.py imports this."""
    return png if not spec else png.with_name(f"{png.stem}-hl-{spec.replace(',', '_')}.png")


def shoot(url: str, out: Path) -> None:
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--window-size=1920,1080", "--virtual-time-budget=3000",
                    f"--screenshot={out}", url], check=True, capture_output=True)


def main() -> None:
    work = Path(sys.argv[1]).resolve()
    slides = work / "slides"
    only = set(sys.argv[2:])
    pages = sorted(slides.glob("[0-9][0-9].html"))
    if only == {"stale"}:
        only = {p.stem for p in pages
                if not p.with_suffix(".png").exists() or p.stat().st_mtime > p.with_suffix(".png").stat().st_mtime}
        only = only or {"none"}
    if not pages:
        raise SystemExit(f"No slides/NN.html in {work}")
    seg_file = work / "segments.json"
    segments = json.loads(seg_file.read_text()) if seg_file.exists() else []
    shot = 0
    for n, page in enumerate(pages, 1):
        if only and page.stem not in only:
            continue
        shot += 1
        png = page.with_suffix(".png")
        for old in slides.glob(f"{page.stem}-hl-*.png"):
            old.unlink()
        shoot(page.as_uri(), png)
        for spec in {spec for _, spec in (segments[n - 1] if n <= len(segments) else []) if spec}:
            shoot(f"{page.as_uri()}#hl={spec}", variant(png, spec))
    pngs = sorted(slides.glob("[0-9][0-9].png"))
    # Highlight frames in narration order, so a sheet reads like the video.
    frames = [variant(slides / f"{n:02d}.png", spec) for n, segs in enumerate(segments, 1)
              for _, spec in segs if spec]
    frames = [f for f in dict.fromkeys(frames) if f.exists()]
    for old in [*work.glob("contact-*.png"), *work.glob("hl-contact-*.png")]:
        old.unlink()
    for prefix, group in (("contact", pngs), ("hl-contact", frames)):
        for i in range(0, len(group), 6):
            sheet(group[i:i + 6], work / f"{prefix}-{i // 6 + 1}.png")
    red = [f.name for f in sorted(slides.glob("*.png")) if is_red(f)]
    print(f"SHOT {shot} of {len(pngs)} slides, {len(frames)} highlight frames, contact sheets in {work}")
    print(f"RED_OUTLINES {' '.join(red) if red else 'none'}")


def sheet(pngs: list[Path], out: Path) -> None:
    """Up to six frames, 3x2, each labelled with its file name."""
    from PIL import Image, ImageDraw  # here, so build.py can import variant() without Pillow

    w, h, pad, label = 800, 450, 8, 34
    img = Image.new("RGB", (3 * w + 4 * pad, 2 * (h + label) + 3 * pad), "black")
    draw = ImageDraw.Draw(img)
    for i, png in enumerate(pngs):
        x, y = pad + (i % 3) * (w + pad), pad + (i // 3) * (h + label + pad)
        draw.text((x + 6, y + 4), png.name, fill="white", font_size=26)
        img.paste(Image.open(png).convert("RGB").resize((w, h)), (x, y + label))
    img.save(out)


def is_red(png: Path) -> bool:
    """The fit and highlight scripts outline a problem diff in pure red."""
    from PIL import Image

    px = Image.open(png).convert("RGB").resize((480, 270)).tobytes()
    return sum(1 for i in range(0, len(px), 3) if px[i] > 230 and px[i + 1] < 40 and px[i + 2] < 40) > 20


if __name__ == "__main__":
    main()
