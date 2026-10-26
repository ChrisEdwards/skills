# Skills

Claude Code skills for multi-model code review, triage, and implementation.

## Installation

Symlink any skill folder into `~/.claude/skills/` (or a project's `.claude/skills/`) to make it available as a slash command.

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

Writes `~/.agents/chris-edwards-skills.md`, the per-user settings file other skills read (for example darkfactory's projects root). Rerun it to change a setting.

Usage: `/setup-chris-edwards-skills`

## Prerequisites

- `gh` CLI, authenticated
- `codex` CLI (optional, skipped if missing)
- `gemini` CLI (optional, skipped if missing)

## Configuration

Per-user settings live in `~/.agents/chris-edwards-skills.md`. Create or edit it with `/setup-chris-edwards-skills`.

The review skill also reads environment variables to choose engines:

- `GOAT_SKIP_CODEX=1` to skip the Codex leg
- `GOAT_INCLUDE_GEMINI=1` to run the Gemini leg (off by default)
