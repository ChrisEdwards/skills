# Dark Factory fixer

You are in a git worktree on a feature branch. You were given `BEAD_ID`, `FINDINGS_FILE`, and optionally `ADVICE_FILE`.

You should not need to spin up a subagent using herdr for this.

1. **Read the context yourself.** `br show <BEAD_ID>` and its parent, `br comments <BEAD_ID>`, then read `FINDINGS_FILE` and `ADVICE_FILE`.
2. Fix at your discretion. Do not over-complicate. Skip findings that are wrong or out of scope, and say why.
3. Follow repo conventions. Run `br` from this directory, never with `--db`. If beads changed, `br sync --flush-only` and commit `.beads/issues.jsonl`.
4. Re-run the repo's tests, commit, and push. Never use `--no-verify`.
5. Reply with what you fixed, what you skipped, and why.
