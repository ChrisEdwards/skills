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

## Prerequisites

- `gh` CLI, authenticated
- `codex` CLI (optional, skipped if missing)
- `gemini` CLI (optional, skipped if missing)

## Configuration

The review skill supports environment variables to skip engines:

- `GOAT_SKIP_CODEX=1` to skip the Codex leg
- `GOAT_SKIP_GEMINI=1` to skip the Gemini leg
