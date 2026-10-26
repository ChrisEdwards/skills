---
name: setup-chris-edwards-skills
description: Write or update the per-user settings file (~/.agents/chris-edwards-skills/config.md) that the skills in this pack read, such as darkfactory's projects root and where podcast and pr-video save their output. Use for /setup-chris-edwards-skills, or when a skill says this file or a setting in it is missing.
disable-model-invocation: true
---

# Setup Chris Edwards Skills

Settings live in `~/.agents/chris-edwards-skills/config.md`, one `<setting>: <value>` line each. Skills read it at runtime. It is per-user, not per-repo.

## Settings

| Setting | Used by | Meaning | Suggested default |
|---|---|---|---|
| `darkfactory projects root` | darkfactory | Directory holding your repo checkouts. A bead labeled `repo:my-service` maps to `<root>/my-service`. | `~/projects` |
| `podcast output folder` | podcast | Where podcast scripts and MP3s are saved. | `~/Podcasts` |
| `pr-video output folder` | pr-video | Where PR video scripts and MP4s are saved. | `~/Movies/pr-videos` |

## Steps

1. Read the file if it exists. Its values are the current choices. Keep lines for settings not in the table above untouched.
2. Ask only about settings for skills that are installed, meaning their folder sits beside this skill's folder.
3. For each setting, ask the user with your structured-question tool, offering the current value (or the suggested default) as the first option.
4. Validate paths: expand `~` and confirm the directory exists. A missing projects root means a typo, so ask again. A missing output folder is normal on first setup, so offer to create it.
5. Show the final file and write it only after the user confirms. Keep `~` unexpanded in the file so it stays portable.
6. If podcast, pr-video, or speak is installed and `~/.local/share/agent-tts/venv` does not exist, tell the user speech needs a one-time install and point them to the speak skill's `references/SETUP.md`.

## File shape

```
# Settings for the chris-edwards-skills pack. Edit by hand or rerun /setup-chris-edwards-skills.
darkfactory projects root: ~/projects
podcast output folder: ~/Podcasts
pr-video output folder: ~/Movies/pr-videos
```
