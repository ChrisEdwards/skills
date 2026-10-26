"""Check a script's [[...]] highlight markers against the built slides, before narrating or shooting.

Usage: python3 check_markers.py SCRIPT.md WORKDIR

Reports, per slide:
- COUNT   the script's `## ` headings and slides/NN.html disagree in number
- BAD     a malformed marker
- MISSING marked lines no diff on that slide shows (a partial miss too, which the red
          outline in the video frames does not catch)
- NODIFF  a marker on a slide with no diff
- UNMARKED  a code slide whose narration has no marker (a warning: narrate the lines)
Prints MARKERS_OK when there are no errors. Static and instant, so run it after every
script or fragment change instead of reading highlight contact sheets.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from narrate import MARK, SPEC, slides  # noqa: E402

AT = re.compile(r'data-at="(\d+)"')


def lines(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out.extend(range(int(a), int(b or a) + 1))
    return out


def main() -> None:
    script, work = Path(sys.argv[1]), Path(sys.argv[2])
    deck = slides(script.read_text())
    pages = sorted((work / "slides").glob("[0-9][0-9].html"))
    errors = 0
    if len(pages) != len(deck):
        print(f"COUNT script has {len(deck)} headings, {len(pages)} slides built")
        errors += 1
    for n, (title, paras) in enumerate(deck, 1):
        page = work / "slides" / f"{n:02d}.html"
        shown = {int(x) for x in AT.findall(page.read_text())} if page.exists() else set()
        specs = [m.replace(" ", "") for p in paras for m in MARK.findall(p)]
        specs = [s for s in specs if s]
        if shown and not specs:
            print(f"UNMARKED {n:02d} {title}")
        for spec in specs:
            if not SPEC.fullmatch(spec):
                print(f"BAD {n:02d} {title}: [[{spec}]]")
                errors += 1
            elif not shown:
                print(f"NODIFF {n:02d} {title}: [[{spec}]]")
                errors += 1
            elif missing := [x for x in lines(spec) if x not in shown]:
                print(f"MISSING {n:02d} {title}: [[{spec}]] lines {missing[0]}..{missing[-1]} "
                      f"({len(missing)}) not shown, diff shows {min(shown)}-{max(shown)}")
                errors += 1
    print("MARKERS_OK" if not errors else f"MARKER_ERRORS {errors}")


if __name__ == "__main__":
    main()
