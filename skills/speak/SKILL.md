---
name: speak
description: Toggle text-to-speech so Claude speaks responses aloud via Pocket TTS. Use when the user says "speak", "/speak", "talk to me", "speak on", or "speak off". Also responds to "use voice X" to change the active voice.
compatibility: Requires macOS on Apple Silicon, uv, Python 3.12, and ffmpeg. Downloads a ~460 MB model on first use.
---

# Speak Skill

Toggle TTS on or off. When on, every response is spoken aloud via the bundled `scripts/atts` while the full text still prints to screen.

`SKILL_DIR` below is the absolute path of the directory containing this SKILL.md (the harness reports it when it loads the skill). Substitute its literal value.

## Activation

- `/speak` or `/speak on` enables TTS
- `/speak off` disables TTS
- `/speak <voice>` enables TTS with that voice (alba, azelma, cosette, eponine, fantine, javert, jean, marius)

## Behavior when enabled

After writing your text response, run a single background Bash command that speaks a **natural spoken summary** of the response. Follow these rules:

1. Speak the meaning, not the markup. `atts` strips markdown and expands acronyms, paths, ticket keys, units and numbers (as words), but it cannot summarise for you.
2. Keep it concise. Under 3 sentences, speak it nearly verbatim. Longer, summarize the key points in 2-4 spoken sentences.
3. Never speak raw code, stack traces, or command output.
4. Run with `run_in_background: true` so the user isn't blocked.

## Command template

```bash
$SKILL_DIR/scripts/atts --voice $VOICE "spoken text here"
```

## Defaults

- **Voice:** alba
- **Engine:** Pocket TTS 100M (Kyutai, MIT) via mlx-audio, resident server on port 7711
- **Latency:** ~145-225ms to first audio, flat regardless of length
- **Seed 99, temperature 0.7, speed 1.1.** The model samples, so without a fixed seed the same text renders as a different take each run. Seeded output is byte-identical. Seed 99 was picked by ear; **seed 42 was the close runner-up, try `--seed 42` if 99 wears thin.** `--seed -1` gives a fresh take each time, `--temp 0.4` steadies the delivery, `--speed 1.25` goes faster (playback time-stretch, pitch preserved).
- Server auto-starts on first call and stays resident. Normalisation and streaming are automatic.

## State

This is a toggle. When the user says `/speak` or `/speak on`, note that TTS is enabled and speak all subsequent responses until `/speak off`. When they provide a voice name, switch to that voice for all subsequent speech.

## Important

- Always print the full text response first, then speak.
- Escape double quotes in spoken text with backslash.
- Troubleshooting: `scripts/atts --status`, `--log`, `--stop`. `scripts/atts --dry "text"` prints the normalised text without speaking.
- If `atts` reports no Python environment, tell the user and disable, and point them to [references/SETUP.md](references/SETUP.md). The venv and log live in `~/.local/share/agent-tts/`.
