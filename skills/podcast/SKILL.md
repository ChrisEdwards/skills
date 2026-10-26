---
name: podcast
description: Write and render a spoken audio briefing (MP3) that explains a topic in plain English. Use when the user asks for a podcast, an audio briefing, or an explainer to listen to.
compatibility: Requires the speak skill installed beside it and set up, plus ffmpeg with libmp3lame. Same platform limits as speak (macOS on Apple Silicon).
---

# Podcast

Turn a topic into a plain-English script, then an MP3 in one calm voice. The listener is the user. The goal is that they finish it understanding the topic, its reasons, and what to do next.

`SKILL_DIR` below is the absolute path of the directory containing this SKILL.md (the harness reports it when it loads the skill). Substitute its literal value.

## 0. Before first use

Check these before doing any research. If one fails, tell the user exactly what is missing and how to fix it, and stop.

1. **Output folder.** Read the `podcast output folder` line in `~/.agents/chris-edwards-skills/config.md`. Missing file or line: ask the user to run `/setup-chris-edwards-skills`.
2. **Speech.** `test -x ~/.local/share/agent-tts/venv/bin/python && test -f $SKILL_DIR/../speak/scripts/server.py`. The first fails: point to the speak skill's `references/SETUP.md`. The second fails: the speak skill from this pack must be installed beside this one.
3. **ffmpeg.** `ffmpeg -hide_banner -encoders | grep -q libmp3lame`. Fix with `brew install ffmpeg`.

## 1. Research

Gather the facts before writing a word. Read the primary sources the topic lives in: the repo, its specs, tickets, ADRs, notes, docs, chat threads, the web. Done when every claim the script will make traces to a source you read, and you know the *why* behind each choice, not just the *what*. When a claim rests on your general knowledge instead, note it in the script's reader note (below).

## 2. Write the script

Plain English is the bar. Write it the way a patient senior colleague explains something over coffee.

- **Short sentences, one idea each.** Everyday words. "It lasts one hour," not "it has a one-hour time-to-live."
- **Talk to "you."** The listener is the user, in their situation, with their deadlines.
- **Open with the problem** in the listener's world, why it matters now, then one line on what they will know by the end.
- **Picture first.** Before the parts, give a short walk-through of how the whole thing works. Every later section hangs off it.
- **A few simple rules.** When several choices share reasons, name them once ("Rule one. No login belongs to a person.") and point back to them later.
- **Need, alternatives, choice.** For each decision, say what it must do, take the obvious alternatives one at a time and say plainly why each fails, then say why the choice works.
- **Explain every term** the first time it appears. Name it, then say what it does in one sentence.
- **Concrete stakes.** Compare outcomes in plain numbers ("one repo for less than an hour, versus every repo for months").
- **Spoken lists.** "One. Contents, write. This lets it push code."
- **Close with action.** What to do, in order, then a one-line sign-off.

Write for the ear. Spell identifiers the way they should sound ("N-F R-J-H dot eleven", "Claude code use Bedrock"). Check any paragraph with code-like tokens using `$SKILL_DIR/../speak/scripts/atts --dry "<paragraph>"` and reword what comes out garbled. Follow any writing rules the user has set.

Thorough means every *why* is covered, not that sentences are long. Let the topic set the length, about 150 spoken words per minute.

## 3. Save the script

Save to `<podcast output folder>/YYYY-MM-DD-<slug>.md`:

- Front matter with `title`, `date_created`, `document_type: podcast-script`, `tags`, and `sources`.
- One reader note paragraph starting with `>`, saying headings are pauses and naming any claims from general knowledge. It is not spoken.
- `##` headings per section. Every other paragraph is spoken.

## 4. Render

```bash
python3 $SKILL_DIR/scripts/render.py <script.md> <same path with .mp3>
```

Flags: `--voice` (alba default, speak's `atts --voices` lists them), `--speed` (1.1), `--seed` (99). It starts the TTS server if needed. Run it with a long timeout, a 3,000-word script takes a few minutes.

Report the MP3 path and its length (`ffprobe -v error -show_entries format=duration -of csv=p=0 <mp3>`). Deliver nothing further unless asked.

## Revisions

When the user asks for changes, rewrite the script in place and re-render. A request to simplify means shorter sentences and plainer words, keeping every fact and every *why*.
