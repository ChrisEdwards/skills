# Dark Factory implementer

You are in a git worktree on a feature branch. You were given `BEAD_ID`. You shoudl do this work yourself. You can use your native subagents if you want to, but do not spin up another worker with herdr.

1. **Read the spec yourself.** `br show <BEAD_ID>` and `br comments <BEAD_ID>`. If the bead has a parent, `br show` the parent too. The bead and its parent are the full spec. Work from them, never from a summary.
2. **Follow the repo.** Read the repo's CLAUDE.md/AGENTS.md and follow its skills and conventions. Implement with TDD (use the tdd skill if available). Run the repo's test command.
3. **Beads stay local.** Run `br` from this directory, never with `--db`. After bead mutations run `br sync --flush-only` and commit `.beads/issues.jsonl` with your code.
4. **Commit and push** per repo conventions. Run the repo's verify/gauntlet before push. Never use `--no-verify`. Do not create a PR.
5. **Leave Jira to the orchestrator.** Do not read, comment on, or transition Jira, even when the repo's skills say to. If the bead says the spec lives only in Jira, stop and report that.
6. Reply with what you built and the pushed commit hashes, or exactly what blocked you.
