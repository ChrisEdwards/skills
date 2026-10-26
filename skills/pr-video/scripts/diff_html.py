# /// script
# requires-python = ">=3.11"
# dependencies = ["pygments>=2.18"]
# ///
"""Turn one file's unified diff into a syntax-highlighted HTML fragment for a slide.

Usage:
  uv run diff_html.py PATCH [--hunks 1,3] [--new-lines 40-72] [--style friendly] > frag.html
  git diff main...HEAD -- path/to/file.py | uv run diff_html.py - --new-lines 120-150

PATCH is a single-file `git diff` (or "-" for stdin). The lexer comes from the file
name in the `+++` header. Old and new sides are highlighted as whole texts, then split
back into lines, so multi-line strings and docstrings colour correctly.

--source FILE is the file's new-side text. For Python it names the class and function a
fragment starts inside (from `ast`) when their signature lines are not shown, as a
breadcrumb in the file bar, like GitHub's hunk header. Other languages fall back to git's
hunk header text, and only when the fragment starts at the top of its hunk.
--hunks keeps only the listed hunks (1-based). Prose files (.md/.rst/.txt) wrap long lines, --wrap forces it for others.
--new-lines keeps rows whose new-side
line number is in range, plus deletions sitting inside it. Aim for 25 rows or fewer.
The fragment carries its own <style> and a fit script that shrinks the code font
until the diff fits; a red outline means it still overflows at 17px (the smallest size that reads in a video), so cut lines.
Place it inside a slide built on assets/slide.css.
Open the slide as NN.html#hl=116-120,130 to highlight those new-side lines and dim the
rest; shoot.py does this for the [[...]] markers in the script.
"""

import argparse
import ast
import html
import re
import sys
from pathlib import Path

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)$")


def lex_lines(text: list[str], lexer: object, formatter: HtmlFormatter) -> list[str]:
    if not text:
        return []
    out = highlight("\n".join(text) + "\n", lexer, formatter).split("\n")
    return out[: len(text)]


Scope = tuple[tuple[str, str], ...]  # (keyword, name) pairs, outermost first


def python_scopes(source: str) -> list[tuple[int, int, str, str]]:
    """(signature line, end line, keyword, name) for every class and function."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    kinds = {ast.ClassDef: "class", ast.FunctionDef: "def", ast.AsyncFunctionDef: "async def"}
    return [(n.lineno, n.end_lineno or n.lineno, kinds[type(n)], n.name)
            for n in ast.walk(tree) if type(n) in kinds]


def scope_at(scopes: list[tuple[int, int, str, str]], line: int) -> Scope:
    """The classes and functions around `line` whose signature is above it, so off screen."""
    inside = sorted((s for s in scopes if s[0] < line <= s[1]), key=lambda s: s[0])
    return tuple((kw, name) for _, _, kw, name in inside)


def git_scope(ctx: str) -> Scope:
    """git's hunk header text, such as `class Foo:` or `def bar(x):`, as a one-step scope."""
    m = re.match(r"\s*((?:async\s+)?(?:def|class|function|func|fn|fun|struct|impl|interface|module|sub))\s+([\w$.:<>]+)", ctx)
    return ((m[1], m[2]),) if m else ()


def scope_html(scope: Scope) -> str:
    parts = [f'<span class="where-kw">{html.escape(kw)}</span> <span class="where-nm">{html.escape(name)}'
             f'{"" if kw == "class" else "()"}</span>' for kw, name in scope]
    return '<span class="where-sep"> › </span>'.join(parts)


def parse(patch: str) -> tuple[str, list[list[tuple[str, str]]], list[tuple[int, int, str]]]:
    path = "file.txt"
    hunks: list[list[tuple[str, str]]] = []
    heads: list[tuple[int, int, str]] = []
    for line in patch.splitlines():
        if line.startswith("+++ "):
            path = line[4:].removeprefix("b/")
        elif m := HUNK.match(line):
            heads.append((int(m[1]), int(m[2]), m[3].strip()))
            hunks.append([])
        elif hunks and line[:1] in ("+", "-", " ") and not line.startswith(("+++", "---")):
            hunks[-1].append((line[0], line[1:]))
        elif hunks and line == "":
            hunks[-1].append((" ", ""))
    if not hunks:
        raise SystemExit("No hunks found. Pass a single-file unified diff.")
    return path, hunks, heads


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("patch")
    p.add_argument("--hunks")
    p.add_argument("--new-lines")
    p.add_argument("--style", default="friendly")
    p.add_argument("--source", help="the file's new-side text, to name the enclosing scope")
    p.add_argument("--wrap", action="store_true", help="wrap long lines (default for .md/.rst/.txt)")
    a = p.parse_args()
    patch = sys.stdin.read() if a.patch == "-" else Path(a.patch).read_text()
    path, hunks, heads = parse(patch)
    try:
        lexer = get_lexer_for_filename(path, stripnl=False, ensurenl=False)
    except ClassNotFound:
        lexer = TextLexer(stripnl=False, ensurenl=False)
    fmt = HtmlFormatter(nowrap=True, style=a.style)
    wrap = a.wrap or Path(path).suffix in {".md", ".rst", ".txt"}
    keep = {int(h) for h in a.hunks.split(",")} if a.hunks else None
    lo, hi = (int(x) for x in a.new_lines.split("-")) if a.new_lines else (0, 10**9)

    scopes = python_scopes(Path(a.source).read_text()) if a.source and path.endswith((".py", ".pyi")) else None

    def scope_for(at: int, ctx: str, hunk_top: bool) -> Scope:
        if scopes is not None:
            return scope_at(scopes, at)
        return git_scope(ctx) if hunk_top else ()

    rows = []
    head_scope: Scope = ()
    for i, (lines, (old_no, new_no, ctx)) in enumerate(zip(hunks, heads), 1):
        if keep and i not in keep:
            continue
        old_hl = iter(lex_lines([t for k, t in lines if k != "+"], lexer, fmt))
        new_hl = iter(lex_lines([t for k, t in lines if k != "-"], lexer, fmt))
        hunk_rows = []
        cut_above = False  # rows of this hunk dropped above the range, so git's header may be stale
        for kind, _ in lines:
            # The last field is the new-side line a row sits "at", for range filtering and
            # highlighting. A deletion sits at the next new-side line.
            if kind == " ":
                code = next(new_hl); next(old_hl)
                row = ("ctx", old_no, new_no, code, new_no); old_no += 1; new_no += 1
            elif kind == "+":
                row = ("add", "", new_no, next(new_hl), new_no); new_no += 1
            else:
                row = ("del", old_no, "", next(old_hl), new_no); old_no += 1
            if lo <= row[4] <= hi:
                hunk_rows.append(row)
            elif not hunk_rows:
                cut_above = True
        if hunk_rows:
            scope = scope_for(hunk_rows[0][4], ctx, not cut_above)
            if rows:
                rows.append(("gap", "", "", scope_html(scope) or html.escape(ctx), ""))
            else:
                head_scope = scope
            rows.extend(hunk_rows)

    sign = {"ctx": " ", "add": "+", "del": "−", "gap": "⋯"}
    body = "\n".join(
        f'<tr class="{k}" data-at="{at}"><td class="ln">{o}</td><td class="ln">{n}</td>'
        f'<td class="sg">{sign[k]}</td><td class="cd">{c or "&nbsp;"}</td></tr>'
        for k, o, n, c, at in rows
    )
    css = fmt.get_style_defs(".diff .cd")
    print(f"""<style>
.diff {{ border:2px solid var(--border); border-radius:var(--radius); overflow:hidden; background:var(--card); }}
.diff .file {{ font-family:var(--font-mono); font-size:22px; padding:12px 22px; background:var(--muted); color:var(--muted-foreground); border-bottom:2px solid var(--border); display:flex; flex-wrap:wrap; justify-content:space-between; align-items:baseline; gap:4px 28px; }}
.diff .where {{ margin-left:auto; font-size:21px; padding:2px 14px; border-radius:8px; background:var(--card); border:1.5px solid var(--border); white-space:nowrap; }}
.diff .where-kw {{ color:var(--primary); opacity:.75; }}
.diff .where-nm {{ color:var(--foreground); font-weight:700; }}
.diff .where-sep {{ color:var(--muted-foreground); }}
.diff tr.gap .where-kw, .diff tr.gap .where-nm {{ font-style:normal; }}
.diff table {{ border-collapse:collapse; width:100%; font-family:var(--font-mono); font-size:var(--diff-size,23px); line-height:1.5; }}
.diff td {{ padding:0 12px; white-space:pre; vertical-align:top; }}
.diff .ln {{ color:var(--muted-foreground); opacity:.6; text-align:right; width:1%; user-select:none; }}
.diff .sg {{ width:1%; font-weight:700; }}
.diff tr.add {{ background:color-mix(in oklab, var(--success) 11%, transparent); }}
.diff tr.add .sg {{ color:var(--success); }}
.diff tr.del {{ background:color-mix(in oklab, var(--destructive) 11%, transparent); }}
.diff tr.del .sg {{ color:var(--destructive); }}
.diff.wrap table {{ table-layout:fixed; }}
.diff.wrap .ln {{ width:3.4em; }} .diff.wrap .sg {{ width:1.6em; }}
.diff.wrap td.cd {{ white-space:pre-wrap; overflow-wrap:anywhere; }}
.diff tr.gap td {{ background:var(--muted); color:var(--muted-foreground); font-style:italic; }}
.diff.focus tr:not(.hl), .diff.focus-none {{ opacity:.3; }}
.diff tr.hl td:first-child {{ box-shadow:inset 8px 0 var(--accent); }}
.diff tr.hl .ln {{ opacity:1; color:var(--accent); font-weight:700; }}
{css}
</style>
<div class="diff{" wrap" if wrap else ""}"><div class="file"><span>{html.escape(path)}</span>{f'<span class="where">{scope_html(head_scope)}</span>' if head_scope else ""}</div><table>
{body}
</table></div>
<script>
// After layout, shrink all diffs on the slide together until each fits its width and they
// share the content area's height. Every fragment adds this listener, so it runs once.
addEventListener("load", () => {{
  if (window.__diffFit) return;
  window.__diffFit = true;
  const diffs = [...document.querySelectorAll(".diff")];
  const tables = diffs.map(d => d.querySelector("table"));
  const box = diffs[0]?.closest(".content") || document.body;
  const wide = i => tables[i].getBoundingClientRect().right > diffs[i].getBoundingClientRect().right + 1;
  const tall = () => box.scrollHeight > box.clientHeight + 1;
  let size = Math.max(...tables.map(t => parseFloat(getComputedStyle(t).fontSize)));
  while ((tall() || diffs.some((_, i) => wide(i))) && size > 17) {{
    size -= 0.5;
    tables.forEach(t => t.style.fontSize = size + "px");
  }}
  // Still too big at 17px: cut lines from the diff that overflows (or all, if too tall).
  diffs.forEach((d, i) => {{ if (tall() || wide(i)) d.style.outline = "6px solid red"; }});
}});
// "#hl=116-120,130" highlights those new-side lines and dims the rest. Opacity only, so
// layout and fitted font size stay identical across a slide's highlight frames.
addEventListener("load", () => {{
  const spec = new URLSearchParams(location.hash.slice(1)).get("hl");
  if (!spec) return;
  const ranges = spec.split(",").map(r => r.split("-").map(Number)).map(([a, b]) => [a, b ?? a]);
  const diffs = [...document.querySelectorAll(".diff")];
  let hits = 0;
  for (const d of diffs) {{
    const rows = [...d.querySelectorAll("tr[data-at]")].filter(r => r.dataset.at
      && ranges.some(([a, b]) => a <= +r.dataset.at && +r.dataset.at <= b));
    rows.forEach(r => r.classList.add("hl"));
    d.classList.add(rows.length ? "focus" : "focus-none");
    hits += rows.length;
  }}
  // Marker names no shown line. Undim first, or the outline renders pink and shoot.py misses it.
  if (!hits) diffs.forEach(d => {{ d.classList.remove("focus-none"); d.style.outline = "6px solid red"; }});
}});
</script>""")


if __name__ == "__main__":
    main()
