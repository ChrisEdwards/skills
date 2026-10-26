# Setting up atts

The speak skill shells out to `atts`, a small local text-to-speech tool bundled in [`scripts/`](../scripts/). It runs from the skill folder, so the only thing to install is its Python environment. It runs Kyutai's Pocket TTS (100M parameters, MIT license) on Apple's MLX framework, entirely offline after the first model download.

## Requirements

- A Mac with Apple Silicon (M1 or later). MLX does not run on Intel Macs, and atts has not been tested anywhere else.
- [uv](https://docs.astral.sh/uv/) and Python 3.12. uv can fetch Python itself if it is missing.
- `ffmpeg`, for `ffplay` playback and speed control: `brew install ffmpeg`.
- About 1 GB of disk: roughly 410 MB for the Python environment and 460 MB for the model.

## Install

Create the Python environment `atts` expects at `~/.local/share/agent-tts/venv`:

```bash
mkdir -p ~/.local/share/agent-tts
uv venv --python 3.12 ~/.local/share/agent-tts/venv
uv pip install --python ~/.local/share/agent-tts/venv/bin/python \
  mlx-audio sentencepiece soundfile requests
```

Then try it from the speak skill's folder:

```bash
scripts/atts "Setup is done."
```

To use `atts` from any shell too, symlink it onto your `PATH`. Keep it a symlink, not a copy, so it always runs the skill's current code:

```bash
ln -s "$PWD/scripts/atts" ~/.local/bin/atts
```

The first call takes a while. It starts the server and downloads the model from Hugging Face (`mlx-community/pocket-tts`, plus a small tokenizer from `kyutai/pocket-tts-without-voice-cloning`) into `~/.cache/huggingface/`. No Hugging Face account or token is needed. Later calls start speaking in about 150 to 250 ms.

## How it runs

- `atts` checks `http://127.0.0.1:7711/health`. If nothing answers, it starts `scripts/server.py` in the background and waits up to 30 seconds for it.
- The server keeps the model in memory and streams audio as it is generated, so it stays running until you stop it or reboot. There is no login item.
- `normalize.py` rewrites text before speaking it: it strips markdown and code, spells out acronyms and ticket keys, shortens file paths, and expands units. Every rule fixes a misreading observed on this model. Add your own acronyms to `ACRONYMS` in `scripts/normalize.py`.

## Commands

| Command | Does |
|---|---|
| `scripts/atts "text"` or `echo text \| scripts/atts` | Speak |
| `scripts/atts --voice jean "text"` | Pick a voice: alba (default), azelma, cosette, eponine, fantine, javert, jean, marius |
| `scripts/atts --seed 42 "text"` | A different take. Default 99. `-1` gives a fresh take every time. |
| `scripts/atts --temp 0.4 "text"` | Steadier delivery. Default 0.7. |
| `scripts/atts --speed 1.25 "text"` | Faster, pitch preserved. Default 1.1. Range 0.5 to 3.0. |
| `scripts/atts --dry "text"` | Print the normalised text without speaking |
| `scripts/atts --status` / `--log` / `--stop` | Check, read the log, or stop the server |

Defaults can also be set with `AGENT_TTS_VOICE`, `AGENT_TTS_SEED`, `AGENT_TTS_TEMP`, `AGENT_TTS_SPEED`, `AGENT_TTS_PORT`, and `AGENT_TTS_MODEL`.

## Troubleshooting

- **`atts: server failed to start`**: run `atts --log`. A missing Python package shows up there. Install it with `uv pip install --python ~/.local/share/agent-tts/venv/bin/python <package>`, not plain `pip`, because uv environments have no pip.
- **The model download fails with a certificate error**: a corporate proxy that intercepts TLS is the usual cause. Point the venv at your company's CA bundle, or update `certifi` in the venv.
- **No sound**: check that `ffplay` is on your `PATH` and your output device is not muted. `atts --dry "text"` confirms the text side works on its own.
- **Port 7711 is taken**: set `AGENT_TTS_PORT` to another port.
