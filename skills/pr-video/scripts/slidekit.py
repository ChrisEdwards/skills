"""Shared slide helpers for a PR video's build_slides.py. Plain python3, no dependencies.

In WORK/build_slides.py:

    import sys; sys.path.insert(0, "<SKILL_DIR>/scripts")  # the literal pr-video skill path
    from slidekit import Deck, make_frags
    make_frags(REPO, "main", "packages/x/src/x/", [("cli_call", "adapters/cli.py", "140-147"), ...], WORK)
    d = Deck(WORK, "factory run", STOPS, OFF_PATH, labels={7: ("no push:", "Infrastructure Failure")},
             extra_svg=d_loop)  # optional
    S = {1: d.page("01 · the problem", "Title", "<div class=row>...</div>"), 3: d.page(..., d.picture()),
         6: d.here(1, "before", "now", "next"), 7: d.page("stop 1 · file", "Title", d.code("cli_call", ("lines 1-2", "note")))}
    d.write(S)

STOPS = [(1, "Command", ["adapters/cli.py", "adapters/prompts.py"]), ...] in execution order, at most 8.
OFF_PATH = (9, "Off path", "one mono line naming the files") or None.
Layout: up to 4 stops per row, the second row runs right to left (a snake). The picture's
geometry never changes between calls, so every you-are-here view lines up.

Also a CLI:  python3 slidekit.py hunks REPO BASE PATH...   prints each file's new-side hunk
ranges, so fragment ranges, notes, and markers stay inside them.
"""

import re
import subprocess
import tempfile
import sys
from pathlib import Path

TOOL = Path(__file__).with_name("diff_html.py")
CSS = Path(__file__).parent.parent / "assets" / "slide.css"
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.M)

W, H = 380, 150
X = (20, 440, 860, 1280)
ROW_Y = (40, 330)
PRIMARY, MUTED, DONE, GOOD = "#5b3fd6", "#c9ccd6", "#b5b8c4", "#2f8a4a"
MONO = 'font-family="SF Mono, monospace"'


def hunks(repo: str, base: str, path: str) -> list[tuple[int, int]]:
    diff = subprocess.run(["git", "-C", repo, "diff", f"{base}...HEAD", "--", path],
                          capture_output=True, text=True, check=True).stdout
    return [(int(a), int(a) + int(n or 1) - 1) for a, n in HUNK.findall(diff)]


def make_frags(repo: str, base: str, prefix: str, frags: list[tuple[str, str, str]], work: Path) -> None:
    """Render each (name, path under prefix, "A-B") to WORK/frags/name.html and warn on
    ranges that leave the hunks or exceed 25 rows. Copies slide.css into WORK/slides."""
    out = Path(work) / "frags"
    out.mkdir(parents=True, exist_ok=True)
    (Path(work) / "slides").mkdir(exist_ok=True)
    (Path(work) / "slides" / "slide.css").write_text(CSS.read_text())
    for name, path, lines in frags:
        diff = subprocess.run(["git", "-C", repo, "diff", f"{base}...HEAD", "--", prefix + path],
                              capture_output=True, text=True, check=True).stdout
        # New-side text, so the fragment can name the class and function it starts inside.
        shown = subprocess.run(["git", "-C", repo, "show", f"HEAD:{prefix + path}"],
                               capture_output=True, text=True)
        with tempfile.NamedTemporaryFile("w", suffix=Path(path).suffix) as source:
            source.write(shown.stdout if shown.returncode == 0 else "")
            source.flush()
            frag = subprocess.run(["uv", "run", "-q", str(TOOL), "-", "--new-lines", lines, "--source", source.name],
                                  input=diff, capture_output=True, text=True, check=True).stdout
        (out / f"{name}.html").write_text(frag)
        rows = frag.count("<tr ")
        lo, hi = (int(x) for x in lines.split("-"))
        spans = [(a, b) for a, n in HUNK.findall(diff) for a, b in [(int(a), int(a) + int(n or 1) - 1)]]
        outside = [n for n in range(lo, hi + 1) if not any(a <= n <= b for a, b in spans)]
        warn = (" OVER 25" if rows > 25 else "") + (f" OUTSIDE_HUNKS {outside[0]}-{outside[-1]}" if outside else "")
        print(f"{name} {rows} rows{warn}")


class Deck:
    def __init__(self, work: Path, use_case: str, stops: list, off_path: tuple | None = None,
                 labels: dict[int, tuple[str, str]] | None = None, extra_svg: str = "") -> None:
        self.work, self.use_case, self.stops, self.off_path = Path(work), use_case, stops, off_path
        self.labels, self.extra_svg = labels or {}, extra_svg
        self.total = len(stops) + (1 if off_path else 0)
        self.pos = {n: self._xy(i) for i, (n, _, _) in enumerate(stops)}

    @staticmethod
    def _xy(i: int) -> tuple[int, int]:
        return (X[i], ROW_Y[0]) if i < 4 else (X[3 - (i - 4)], ROW_Y[1])

    # ---- pages ----
    def frag(self, name: str) -> str:
        return (self.work / "frags" / f"{name}.html").read_text()

    def page(self, eyebrow: str, title: str, body: str) -> str:
        return ('<!doctype html><html><head><meta charset="utf-8">'
                '<link rel="stylesheet" href="slide.css"></head><body>'
                f'<div class="slide"><span class="eyebrow">{eyebrow}</span><h1>{title}</h1>'
                f'<div class="content">{body}</div></div></body></html>')

    def notes(self, *cards: tuple[str, str]) -> str:
        inner = "".join(f'<div class="card"><span class="tag p">{t}</span><p>{p}</p></div>' for t, p in cards)
        return f'<div class="col">{inner}</div>'

    def code(self, name: str, *cards: tuple[str, str]) -> str:
        return f'<div class="code-row">{self.frag(name)}{self.notes(*cards)}</div>'

    def code2(self, a: str, b: str, *cards: tuple[str, str]) -> str:
        return self.stack((a, b), *cards)

    def stack(self, names: tuple[str, ...], *cards: tuple[str, str]) -> str:
        """Two or more diffs stacked beside the notes. They share about 25 rows."""
        frags = "".join(self.frag(n) for n in names)
        return f'<div class="code-row"><div class="col" style="flex:2.3">{frags}</div>{self.notes(*cards)}</div>'

    def write(self, slides: dict[int, str]) -> None:
        """Rewrite only changed HTML, so `shoot.py WORK stale` re-shoots exactly what changed."""
        for n, html in slides.items():
            path = self.work / "slides" / f"{n:02d}.html"
            if not path.exists() or path.read_text() != html:
                path.write_text(html)
        print(len(slides), "slides")

    def wide(self, names: tuple[str, ...], *cards: tuple[str, str]) -> str:
        """Full-width diffs for long lines, one-line notes in a row below."""
        row = "".join(f'<div class="card" style="padding:16px 26px"><span class="tag p" style="margin-bottom:6px">{t}</span>'
                      f'<p style="font-size:25px">{p}</p></div>' for t, p in cards)
        return "".join(self.frag(n) for n in names) + f'<div class="row">{row}</div>'

    def tour(self, descs: dict[int, str]) -> str:
        """The map: number, stop, files, one line each. descs keyed by stop number."""
        items = [(n, t, " · ".join(f)) for n, t, f in self.stops]
        if self.off_path:
            items.append((self.off_path[0], self.off_path[1], self.off_path[2]))
        rows = "".join(
            f'<span class="num">{n}</span><b style="font-size:29px">{t}</b><code style="font-size:22px">{f}</code>'
            f'<span style="font-size:26px;color:var(--muted-foreground)">{descs.get(n, "")}</span>' for n, t, f in items)
        return f'<div style="display:grid;grid-template-columns:50px 250px 660px 1fr;gap:12px 26px;align-items:center">{rows}</div>'

    def here(self, n: int, before: str, now: str, nxt: str) -> str:
        title = next((t for s, t, _ in self.stops if s == n), self.off_path[1] if self.off_path else "")
        cards = ('<div class="row">'
                 f'<div class="card"><span class="tag">before</span><p>{before}</p></div>'
                 f'<div class="card p"><span class="tag p">now</span><p>{now}</p></div>'
                 f'<div class="card"><span class="tag">next</span><p>{nxt}</p></div></div>')
        return self.page(f"{self.use_case} · stop {n} of {self.total}", f"Stop {n} · {title}",
                         self.picture(n, max_h=470) + cards)

    # ---- diagram ----
    def _state(self, n: int, current: int | None, lit: bool) -> str:
        if lit:
            return "lit"
        if current is None:
            return "normal"
        return "done" if n < current else "current" if n == current else "next" if n == current + 1 else "future"

    def _box(self, n: int, x: int, y: int, w: int, h: int, title: str, files: list[str], st: str) -> str:
        stroke = {"normal": PRIMARY, "lit": GOOD, "done": DONE, "current": PRIMARY, "next": PRIMARY,
                  "future": MUTED, "offpath": "#888"}[st]
        fill = {"current": "#ece8ff", "lit": "#eef8f0"}.get(st, "white")
        width = 7 if st == "current" else 4
        dash = ' stroke-dasharray="14 10"' if st in ("next", "offpath") else ""
        opacity = ' opacity="0.45"' if st == "done" else ""
        ink = "#999" if st in ("done", "future") else "#222"
        parts = [f'<g{opacity}>',
                 f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{fill}" stroke="{stroke}" stroke-width="{width}"{dash}/>',
                 f'<circle cx="{x + 42}" cy="{y + 42}" r="24" fill="{stroke}"/>',
                 f'<text x="{x + 42}" y="{y + 51}" text-anchor="middle" {MONO} font-size="25" font-weight="700" fill="white">{n}</text>',
                 f'<text x="{x + 82}" y="{y + 54}" font-family="Georgia, serif" font-size="34" fill="{ink}">{title}</text>']
        parts += [f'<text x="{x + 30}" y="{y + 100 + i * 32}" {MONO} font-size="21" fill="#555">{line}</text>'
                  for i, line in enumerate(files)]
        tag = {"next": "NEXT", "current": "HERE"}.get(st)
        if tag:
            parts.append(f'<text x="{x + w - 8}" y="{y - 10}" text-anchor="end" {MONO} font-size="24" font-weight="700" fill="{PRIMARY}">{tag}</text>')
        return "".join(parts) + "</g>"

    @staticmethod
    def arrow(points: str, dashed: bool = False) -> str:
        dash = ' stroke-dasharray="12 9"' if dashed else ""
        return f'<polyline points="{points}" fill="none" stroke="#888" stroke-width="4"{dash} marker-end="url(#a)"/>'

    def up_arrow(self, from_stop: int, to_stop: int, line1: str, line2: str = "") -> str:
        """Dashed loop-back arrow from a second-row stop up to the first-row stop above it,
        labelled in the gap between rows. Pass the result as extra_svg."""
        x = self.pos[from_stop][0] + W // 2
        label = "".join(f'<text x="{x + 18}" y="{y}" {MONO} font-size="21" fill="{PRIMARY}">{t}</text>'
                        for t, y in ((line1, 252), (line2, 278)) if t)
        return self.arrow(f"{x},{ROW_Y[1]} {x},{ROW_Y[0] + H + 6}", dashed=True) + label

    @staticmethod
    def gap_note(x: int, line1: str, line2: str = "") -> str:
        """A grey two-line note in the gap between rows, starting at x."""
        return "".join(f'<text x="{x}" y="{y}" {MONO} font-size="21" fill="#555">{t}</text>'
                       for t, y in ((line1, 252), (line2, 278)) if t)

    def picture(self, current: int | None = None, lit: bool = False, max_h: int = 760) -> str:
        parts = ['<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                 'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#888"/></marker></defs>']
        order = [n for n, _, _ in self.stops]
        for a, b in zip(order, order[1:]):
            (xa, ya), (xb, yb) = self.pos[a], self.pos[b]
            if ya != yb:
                parts.append(self.arrow(f"{xa + W // 2},{ya + H} {xb + W // 2},{yb - 6}"))
            elif xb > xa:
                parts.append(self.arrow(f"{xa + W},{ya + H // 2 + 0} {xb - 6},{yb + H // 2}"))
            else:
                parts.append(self.arrow(f"{xa},{ya + H // 2} {xb + W + 6},{yb + H // 2}"))
        parts.append(self.extra_svg)
        for n, title, files in self.stops:
            x, y = self.pos[n]
            parts.append(self._box(n, x, y, W, H, title, files, self._state(n, current, lit)))
        for n, (a, b) in self.labels.items():
            x, y = self.pos[n]
            parts.append(f'<text x="{x + 10}" y="{y + H + 28}" {MONO} font-size="21" fill="#c0392b">{a}</text>'
                         f'<text x="{x + 10}" y="{y + H + 54}" {MONO} font-size="21" fill="#c0392b">{b}</text>')
        height = 690 if self.off_path or len(self.stops) > 4 else 230
        if self.off_path:
            n, title, line = self.off_path
            st = self._state(n, current, lit)
            st = "offpath" if st in ("normal", "future") else st
            parts.append(self._box(n, 20, 560, 1640, 110, title, [], st))
            # Start the file line after the title (Georgia 34px is about 19px a character).
            parts.append(f'<text x="{max(330, 130 + 19 * len(title))}" y="614" {MONO} font-size="21" fill="#555">{line}</text>')
        svg = (f'<svg viewBox="0 0 1680 {height}" style="max-height:{max_h}px" '
               f'xmlns="http://www.w3.org/2000/svg">{"".join(parts)}</svg>')
        return f'<div class="diagram">{svg}</div>'


if __name__ == "__main__":
    if len(sys.argv) < 5 or sys.argv[1] != "hunks":
        raise SystemExit("usage: python3 slidekit.py hunks REPO BASE PATH...")
    repo, base = sys.argv[2], sys.argv[3]
    for path in sys.argv[4:]:
        print(path, " ".join(f"{a}-{b}" for a, b in hunks(repo, base, path)) or "(no hunks)")
