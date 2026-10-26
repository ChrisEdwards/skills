---
name: pr-video
description: Make a narrated video tutorial (MP4, slides plus voiceover) that explains a pull request in plain English and walks through its literal code diffs. Use when the user asks for a video, screencast, or voiceover walkthrough of a PR, branch, or code change.
compatibility: Requires the speak skill installed beside it and set up, plus ffmpeg, uv, git, and Google Chrome. Same platform limits as speak (macOS on Apple Silicon).
---

# PR video

Slides plus one calm voice, explaining a PR so the viewer finishes it understanding what changed, why each choice was made, and what to review. Two halves: a plain-English **story** (problem, scope, picture, rules, map) and a **code walk** that follows execution through each use case over the real diff hunks, syntax highlighted. The viewer must always know where they are in the flow, how they got there, and what comes next.

`SKILL_DIR` below is the absolute path of the directory containing this SKILL.md (the harness reports it when it loads the skill). Substitute its literal value. Scripts live in `$SKILL_DIR/scripts/`, the slide stylesheet in `$SKILL_DIR/assets/slide.css`. Work in `/tmp/pr-video-<slug>/` with a `slides/` folder holding `slide.css`, `NN.html`, and `NN.png`.

## 0. Before first use

Check these before doing any research. If one fails, tell the user exactly what is missing and how to fix it, and stop.

1. **Output folder.** Read the `pr-video output folder` line in `~/.agents/chris-edwards-skills/config.md`. Missing file or line: ask the user to run `/setup-chris-edwards-skills`.
2. **Speech.** `test -x ~/.local/share/agent-tts/venv/bin/python && test -f $SKILL_DIR/../speak/scripts/server.py`. The first fails: point to the speak skill's `references/SETUP.md`. The second fails: the speak skill from this pack must be installed beside this one.
3. **Tools.** `command -v ffmpeg ffprobe uv git`. Fix with `brew install ffmpeg uv git`. The slide scripts fetch Pillow and Pygments through `uv run` on first use.
4. **Chrome.** `test -x "${CHROME_PATH:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"`. Install Google Chrome, or set `CHROME_PATH` to another Chrome or Chromium binary.

## 1. Research

Read the PR body, the full diff (`git diff <base>...HEAD`), every changed source file, the spec or ticket it implements, and the repo's `CONTEXT.md` files. Find the **use cases**: each entry point a caller hits (a command, an endpoint, a job) and, for each, the call path through the changed code. Done when every claim the script will make traces to something you read, you know the *why* behind each choice, you can trace each use case's execution path stop by stop with the file for each stop, and every domain term matches the repo's own vocabulary. Check names and lists against the source, never memory: a paraphrased list (say, the names of pipeline stages) is the first thing to come out wrong. Claims resting on general knowledge go in the script's reader note.

## 2. Plan the slides

One slide per idea, 15 to 35 slides. Order:

1. **The problem.** The world before this PR, in the viewer's terms, and why it matters now.
2. **Purpose and scope.** What the PR does, what it deliberately leaves out, and what later work builds on it. Use `.scope` (in, out, next).
3. **The picture.** One diagram of the flow, drawn as numbered **stops** along each use case's execution path (inline SVG in `.diagram`). Generate it from one function that takes the current stop, so every later view of it has identical geometry.
4. **The rules.** Two to four named principles the choices share, so later slides can say "that is rule two."
5. **The map.** The tour plan. Each use case, then its stops in execution order, each stop with its file(s) and one line on what happens there. Off-path material (shared types, tests, config) is its own last stop. The viewer should be able to predict the rest of the video from this slide.
6. **The code walk, per use case, in execution order.** For each stop:
   - A **you-are-here slide**. The picture with finished stops dimmed, the current stop highlighted, and the next stop marked. A caption says what came before, what this stop does, and what it hands to the next stop. Eyebrow shows `use case · stop N of M`.
   - Its **code slides**. One per meaningful hunk, eyebrow `stop N · file`. Each shows a literal diff from `diff_html.py`, 25 rows or fewer, with one to three side notes in `.code-row` that point at line numbers.
   - Introduce a type or helper at the stop where execution first meets it, not up front.
   After the last stop, show the picture fully lit and recap the path in one breath.
7. **Proof.** Tests, numbers, live runs.
8. **Review focus and next steps.**

Done when every changed source file that carries logic has at least one code slide, every code slide is entered from a you-are-here slide, the map and the you-are-here slides agree on stop names and files, and each story slide states one idea.

## 3. Write the script

One markdown file, `## Heading` per slide, in slide order. Front matter (`title`, `date_created`, `document_type: video-script`, `tags`, `sources`), then one reader note paragraph starting with `>` (not spoken). Every other paragraph is spoken.

Plain English is the bar. Write it the way a patient senior colleague explains a change over coffee.

- **Short sentences, one idea each.** Everyday words.
- **Talk to "you."**
- **Explain every term** the first time it appears: name it, then one sentence on what it does. This includes general engineering terms (SDK, schema, enum, callback, mutation testing), not only domain ones.
- **Need, alternatives, choice.** For each decision say what it must do, take the obvious alternatives one at a time and say plainly why each fails, then why the choice works.
- **Concrete stakes** in plain numbers.
- **Spoken lists.** "One. The working folder. Two. The prompt."
- **Code slides narrate the code on screen**, top to bottom, by line number or by what the line says: "Look at line one twenty six. The environment gets two entries." Read identifiers as words ("can use tool", "claude code use bedrock"). When the file bar shows a breadcrumb, say where you are first: "We are inside the run method of Recording Sessions." Say why each line exists, not only what it does.
- **Highlight what you narrate.** Put a marker `[[126]]`, `[[116-120]]`, or `[[116-120,130]]` right before the sentence that talks about those lines. It is not spoken. From that sentence on, the slide lights those lines and dims the rest of the diff, until the next marker, `[[]]` (clear), or the next slide. Numbers are the new-side line numbers in the diff's second column. Deleted lines count as the new line right after them. On a slide with two diffs, a diff with no matching line dims entirely. Mark every sentence that names lines on a code slide. Add markers after the `atts --dry` check, or strip them before it.
- **Unpack every mechanism for a newcomer.** When code calls an external command, library API, or protocol (`git ls-remote`, `json.loads` with a hook, `importlib.resources`), assume the viewer has never used it. Say what it does, what it sends back (show a literal sample output on the slide when it helps, like the `<sha> refs/heads/<branch>` line ls-remote prints), and why this one beats the obvious alternative. Do the same for the PR's own key types and functions. Say what it holds, who fills it, who reads it, and why it is a separate thing.
- **Narrate the transitions.** Each you-are-here slide says where we just were, where we are now, and what we will look at next, in two or three sentences. The first one also says how many stops the tour has.
- **Close with action**, then a one-line sign-off.

Write for the ear. Spell identifiers the way they should sound ("N F R J H dot two", "P L five twenty six", "mut mut"). Check any paragraph with code-like tokens using `$SKILL_DIR/../speak/scripts/atts --dry "<paragraph>"` and reword what comes out garbled. JSON reads fine. Write NUL as "null". Follow any writing rules the user has set. About 150 spoken words per minute; a medium PR runs 15 to 25 minutes.

Save to `<pr-video output folder>/YYYY-MM-DD-<slug>-video.md`.

## 4. Narrate

```bash
python3 $SKILL_DIR/scripts/narrate.py <script.md> /tmp/pr-video-<slug>
```

Run it with `run_in_background` and wait for the completion notification. It sends one or two sentences per TTS request and writes one continuous `track.wav`, `durations.json`, and `segments.json` (when each highlight marker starts). A malformed marker stops it and names the slide. Flags: `--voice` (alba), `--speed` (1.1), `--seed` (99). It takes about as long as the video runs, so build the slides (step 5) while it works.

## 5. Build the slides

Write one file, `WORK/build_slides.py`, on `$SKILL_DIR/scripts/slidekit.py` (its docstring has a complete example). Import it by putting the literal `$SKILL_DIR/scripts` on `sys.path`. `make_frags(repo, base, prefix, [(name, file, "A-B"), ...], WORK)` renders each diff fragment through `diff_html.py` (pass `prefix=""` in a second call for files outside the package, like `pyproject.toml`), names the enclosing class and function in the file bar (`class Foo › def bar()`) whenever the fragment starts below their signatures, and on each gap row between hunks, copies `slide.css`, and flags any fragment `OVER 25` rows or `OUTSIDE_HUNKS`. `Deck(WORK, use_case, STOPS, OFF_PATH, labels=...)` gives `page`, `code`, `code2`, `stack` (any number of diffs beside notes), `wide`, `tour` (the map), `picture`, `here`, and `write(S)`, where `S` maps slide number to HTML. The diagram is laid out for you: up to eight stops in a two-row snake, the off-path stop as a dashed box below, failure labels under their own boxes, and the HERE, NEXT, done, and lit states. Use `extra_svg` with `d.up_arrow(from, to, ...)` for a loop-back and `d.gap_note(x, ...)` for a note between rows. Write only the stops and slide content, never the helpers. Component classes are listed at the top of `assets/slide.css`.

List the hunks before choosing ranges, `python3 $SKILL_DIR/scripts/slidekit.py hunks REPO BASE PATH...`. A fragment shows only rows inside them, so keep ranges, side notes, and narrated lines inside them. A diff on a slide shrinks with any others on it to fit, and a red outline means it is still too big at 17px, so cut the range. Two stacked fragments share about 25 rows. Beside side notes, a diff fits about 95 characters a line. For longer lines use `wide` (full width, one-line notes below, about 16 rows). Sample command output on a side card goes in one `nowrap` code line, shortened with an ellipsis. A stop box holds two file lines of about 28 characters each. Put a third file on the map or the stop's code slides.

The command guard blocks shell loops over variables, recursive deletes, and redirects to a variable path. Keep everything in the one Python file, use literal paths, and make a fresh folder rather than deleting one.

Once the script and slides exist, run `python3 $SKILL_DIR/scripts/check_markers.py <script.md> /tmp/pr-video-<slug>` and fix everything until it prints `MARKERS_OK`. It finds marked lines that no diff on the slide shows, including partial misses, plus a heading count that differs from the slide count. Fixing a fragment range needs no new narration.

Line numbers drift whenever the branch moves. Take every number the script speaks or marks from `cat -n` of the file at the commit you are diffing, after the last code change, never from memory or an earlier run.

## 6. Shoot and inspect

```bash
uv run $SKILL_DIR/scripts/shoot.py /tmp/pr-video-<slug> [NN ... | stale]
```

It also shoots each highlight state as `NN-hl-<lines>.png`, builds labelled `hl-contact-*.png` sheets of them in narration order, and ends with `RED_OUTLINES` listing every frame with a red outline. Passing a slide number that doesn't exist (`99`) rebuilds only the sheets and the report. Shoot after narration finishes, since highlight frames need `segments.json`. Read every `contact-*.png`. With `MARKERS_OK` the highlight frames are mechanical, so read one `hl-contact-*.png` as a spot check, and the rest only for slides you changed by hand. Open a single frame at full size only to diagnose a problem. Done when `MARKERS_OK`, `RED_OUTLINES none` (on a `-hl-` frame a red outline means the marker matched no line shown), and no slide has clipped code, text running off an edge, a lone card stretched into an empty box, a label crossing a diagram line, a you-are-here slide whose highlighted stop differs from its eyebrow, or a slide that disagrees with its narration. Fix, rerun `build_slides.py`, then re-shoot with `shoot.py /tmp/pr-video-<slug> stale`. It shoots every slide whose HTML changed, which catches all the you-are-here slides when you edit the diagram. Listing slide numbers by hand misses them.

## 7. Build and verify

```bash
python3 $SKILL_DIR/scripts/build.py /tmp/pr-video-<slug> <pr-video output folder>/YYYY-MM-DD-<slug>-video.mp4
```

Done when it prints `MATCH`, `long_silences` equals `expected`, and `boundaries.png` (a frame from each slide's opening) shows every slide in order. Then `open` the MP4 and report its path, length, and anything from general knowledge.

## Audio and sync rules

Both came from a broken first video:

- **Short TTS requests.** Whole paragraphs make the voice drift and garble. `narrate.py` chunks at 22 words.
- **One audio track, encoded once.** Rendering an MP3 per slide and joining per-slide MP4 clips adds a small gap or trim at every join, and the cuts compound until the end of a long video is a mess. Slides and highlight frames switch at cumulative times on the single track. Keep it that way when changing anything.
