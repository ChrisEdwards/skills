---
name: herdr-fork
description: "Fork the current Claude Code conversation into a new Herdr pane, preserving conversation history. Use when the user asks to fork, clone, or branch the current conversation into Herdr."
---

# herdr-fork

Fork the current Claude Code session into a new Herdr pane. The fork inherits the full conversation history. An optional prompt starts the first turn.

This skill is a thin conversational wrapper over the `herdr` CLI. It does not bundle scripts. All terminal control goes through `herdr` commands as documented in the herdr skill.

## Prerequisites

- `HERDR_ENV=1` (this agent runs inside Herdr)
- `CLAUDE_CODE_SESSION_ID` set in the environment (Claude Code exports this)

Verify both before proceeding. If either is missing, tell the user and stop.

## Inputs

- **prompt** (optional) — text for the fork's first turn
- **name** (optional) — agent name for the fork; default to `fork-claude`
- **direction** (optional) — `right` or `down` for the split; default to `right`

## Procedure

1. **Verify environment:**
   ```bash
   test "$HERDR_ENV" = 1
   echo "$CLAUDE_CODE_SESSION_ID"
   ```
   Both must succeed. If `CLAUDE_CODE_SESSION_ID` is empty, stop with a message.

2. **Split a new pane:**
   ```bash
   herdr pane split --current --direction right --cwd "$PWD" --no-focus
   ```
   Read the pane ID from `.result.pane.pane_id` in the JSON response.

3. **Start the forked Claude agent:**
   ```bash
   herdr agent start <name> --kind claude --pane <pane-id> -- --resume "$CLAUDE_CODE_SESSION_ID" --fork-session --permission-mode auto
   ```
   Use a 60-second timeout if the default is too short:
   ```bash
   --timeout 60000
   ```

4. **Send the prompt (if provided):**
   ```bash
   herdr agent prompt <name> "<prompt text>" --wait
   ```
   Run with `run_in_background: true` since the prompt may take a long time.

## Report back

On success, tell the user:
- The **session ID** that was forked
- The **pane ID** of the new fork
- The **agent name**
- Whether a prompt was sent

Example: "Forked this session into pane `w1:p3` as agent `fork-claude`. The prompt was sent."

## On failure

If `agent start` fails, relay the error and the pane ID so the user can inspect. Do not retry or close the pane.

## Boundaries

- Fire-and-confirm only. Open the fork, confirm readiness, stop.
- No monitoring afterward.
- No Codex support (use orca-fork for that).
- Only fork from the main loop, not from a subagent (the subagent's session ID may differ).
