---
name: setup-chris-edwards-skills
description: Write or update the per-user settings file (~/.agents/chris-edwards-skills.md) that the skills in this pack read, such as darkfactory's projects root. Use for /setup-chris-edwards-skills, or when a skill says this file or a setting in it is missing.
disable-model-invocation: true
---

# Setup Chris Edwards Skills

Settings live in `~/.agents/chris-edwards-skills.md`, one `<setting>: <value>` line each. Skills read it at runtime. It is per-user, not per-repo.

## Settings

| Setting | Used by | Meaning | Suggested default |
|---|---|---|---|
| `darkfactory projects root` | darkfactory | Directory holding your repo checkouts. A bead labeled `repo:my-service` maps to `<root>/my-service`. | `~/projects` |

## Steps

1. Read the file if it exists. Its values are the current choices. Keep lines for settings not in the table above untouched.
2. For each setting, ask the user with your structured-question tool, offering the current value (or the suggested default) as the first option.
3. Validate paths: expand `~` and confirm the directory exists. If not, say so and ask again.
4. Show the final file and write it only after the user confirms. Keep `~` unexpanded in the file so it stays portable.

## File shape

```
# Settings for the chris-edwards-skills pack. Edit by hand or rerun /setup-chris-edwards-skills.
darkfactory projects root: ~/projects
```
