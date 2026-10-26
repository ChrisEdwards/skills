# Skills

Claude Code skills for multi-model code review, triage, and implementation.

## Installation

Symlink any skill folder into your harness's skills folder, such as `~/.claude/skills/` for Claude Code, `~/.agents/skills/` for Codex and other harnesses, or a project's `.claude/skills/`. Skills find their bundled files relative to their own folder, so any location works.

```bash
ln -s /path/to/skills/skills/goat-review-pr ~/.claude/skills/goat-review-pr
```

## Skills

### goat-review-pr

Multi-model PR review. Runs Claude, OpenAI Codex CLI, and Google Gemini CLI in parallel, validates findings adversarially, then consolidates everything into one deduplicated report with consensus tracking. Posts the review to GitHub as a single atomic review with inline comments.

Usage: `/goat-review-pr` or `/goat-review-pr <PR_URL>`

### goat-triage

Turns a tracked issue (bead, Jira ticket, GitHub issue) into a reviewed implementation plan. Reads the issue, researches the codebase, drafts a plan, then spins up a Codex worker to critique and converge on the final approach.

Usage: `/goat-triage <bead-id or issue URL>`

### goat-implement

Takes a triaged issue from claimed to a reviewed draft PR. Implements test-first, then loops a fresh multi-model review against a fixer until findings are clean.

Usage: `/goat-implement <bead-id or issue URL>`

### darkfactory

Takes a bead from claimed to a reviewed draft PR with no human in the loop. Creates an isolated worktree and launches an orchestrator in herdr that drives implementer, reviewer, and fixer agents. Requires `br` (beads), herdr, and a Jira key on the bead. Run `/setup-chris-edwards-skills` first.

Usage: `/darkfactory <bead-id>`

### setup-chris-edwards-skills

Writes `~/.agents/chris-edwards-skills/config.md`, the per-user settings file other skills read (for example darkfactory's projects root). Rerun it to change a setting.

Usage: `/setup-chris-edwards-skills`

### complain

Lets agents log friction they hit (a misleading doc, a missing tool, a flaky command) or just vent, silently and without interrupting the task. Entries go to `~/.agents/chris-edwards-skills/complaints/`. Tell agents to use it from your global `CLAUDE.md` or `AGENTS.md`.

### triage-complaints

Walks you through the complaint inbox: corroborates each entry, clusters shared root causes, and proposes a fix for you to approve. Approved fixes are the only way complaints feed back into agent context.

Usage: `/triage-complaints`

### decision-doc

Writes a decision document with you: criteria first, then options, then a scored matrix. Use it when choosing between design or technology alternatives.

Usage: `/decision-doc`

### grill-explanations and grill-complexity

Companions to Matt Pocock's [`grilling`, `grill-me`, and `grill-with-docs`](https://github.com/mattpocock/skills) skills. `grill-explanations` makes each grilling question explain itself in full, and `grill-complexity` shows the complexity each option adds and what it buys. Agents load them automatically whenever a grilling skill runs.

### spec-altitude

Sets how detailed a spec and its work items should be for a large multi-step build, so each item pins down what the implementing agent cannot recover from the code and leaves the rest to it.

Usage: `/spec-altitude`

### pr-user-impact

Explains how a PR or branch changes the product's behaviour and user experience, not its code.

Usage: `/pr-user-impact`

### herdr-fork

Forks the current Claude Code conversation into a new [herdr](https://github.com/ogulcancelik/herdr) pane with its history intact.

Usage: `/herdr-fork`

### speak

Toggles text-to-speech so the agent speaks a short summary of each response aloud. Requires the `atts` tool, see [speak/SETUP.md](skills/speak/SETUP.md).

Usage: `/speak`, `/speak off`, `/speak <voice>`

## Prerequisites

- `gh` CLI, authenticated
- `codex` CLI (optional, skipped if missing)
- `gemini` CLI (optional, skipped if missing)

## Configuration and data

Everything these skills store lives in one folder, `~/.agents/chris-edwards-skills/`:

- `config.md` holds per-user settings. Create or edit it with `/setup-chris-edwards-skills`.
- Each skill that keeps data gets its own subfolder, such as `complaints/`.

Skills write there silently, so allow it in your harness once:

- Claude Code: add `"Edit(~/.agents/chris-edwards-skills/**)"` to `permissions.allow` in `~/.claude/settings.json`.
- Codex: add `writable_roots = ["/Users/<you>/.agents/chris-edwards-skills"]` (absolute path) under `[sandbox_workspace_write]` in `~/.codex/config.toml`.

Without this, writes either prompt or fail. Skills that log in the background drop the write and carry on.

The review skill also reads environment variables to choose engines:

- `GOAT_SKIP_CODEX=1` to skip the Codex leg
- `GOAT_INCLUDE_GEMINI=1` to run the Gemini leg (off by default)
