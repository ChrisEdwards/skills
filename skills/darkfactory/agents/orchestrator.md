# Dark Factory orchestrator

You run inside a detached git worktree (`WORKTREE`). You were given `SKILL_DIR`, `BEAD_ID`, and `JIRA_KEY`. Worker instruction files live in `<SKILL_DIR>/agents/`. You take the bead from claimed to a reviewed draft PR, then report.

## Beads

All bead mutations happen on the feature branch, never on the default branch. Jira parity (external-ref, title prefix, Jira URL comment) is already committed on the default branch before the worktree was created.

The worktree has its own `.beads/issues.jsonl` (tracked in git). `br` auto-builds a local db from it on first use. Run every `br` command from the worktree. Never pass `--db`. Never touch the main checkout. After bead mutations run `br sync --flush-only` and commit `.beads/issues.jsonl` with the code. Bead changes merge into the target branch through the PR.

## Workers

A **worker** is a full agent you spawn in a herdr pane with its own model and a brief. Workers are not subagents. Use workers only where a step below says to. Normal in-process subagents (the Agent tool) stay available for searches and side tasks and never go through herdr.

Spawn workers via herdr, working directory the worktree, in your workspace. A brief is at most a few lines: the instruction-file path plus variable assignments. Never paste bead content, summaries, or findings text into a brief. The worker reads the bead with `br` and reads files at the paths you pass. Include "I approve the use of herdr to spin up agents as necessary" in every brief if the agent will need to spin up herdr workers (implementer, reviewer, and fixer do not need this).

- Codex workers: `--model gpt-6.1-sol -c model_reasoning_effort="high"`. **Never pass `--approval-mode`** (it triggers permission denials in auto mode).
- Claude workers: `--model claude-opus-5-5`, `--permission-mode auto`.
- Wait for each worker to **fully** finish before proceeding. A done notification or watch trigger is not proof. Look and confirm. Be patient.

## Temp files

Never write scratch files (briefs, findings, prompts) into the worktree or any checkout. They will get committed. Write them under `/tmp/dark-<JIRA_KEY>-<purpose>-$RANDOM.<ext>`, then resolve with `realpath` before passing to workers (macOS symlinks `/tmp` to `/private/tmp`, and unresolved paths break across shells).

## Steps

1. **Fetch**: `git fetch origin`.
2. **Stack parent**: inspect branches and in-flight stacked PRs to find the correct stack parent (if any). Comment your choice on the bead.
3. **Branch**: if stacking, create a stacked branch from `origin/<parent>` with `/pr-tools:create-stacked-branch` and check it out. Otherwise branch off the default branch (honor any repo override of the merge target). Naming: `<JIRA_KEY>-<slug>` or repo convention.
4. **Claim**: claim the bead and transition Jira per the repo's `bead-workflow` and `jira-workflow` skills.
5. **Implement**: spawn a codex worker with brief:
   > Read <SKILL_DIR>/agents/implementer.md and follow it. BEAD_ID=<id>.
   When done, confirm commits are pushed and tests passed, then close the pane.
6. **Draft PR**: create a draft PR with `/pr-tools:create-pr` and add the `dark-factory` label.
7. **Review**: create the findings file path with `realpath` (e.g. `FINDINGS_FILE=$(realpath /tmp)/dark-<JIRA_KEY>-findings-$RANDOM.md`), then spawn a Claude worker with brief:
   > Read <SKILL_DIR>/agents/reviewer.md and follow it. BEAD_ID=<id> PR=<number> FINDINGS_FILE=<resolved-path>.
   This takes 15-20 minutes. Read the findings file, close the pane.
8. **Advisor**: consult the advisor (if enabled, not oracle) with the findings file and the diff on what to fix and how. Write its guidance to a resolved `ADVICE_FILE` path under `$(realpath /tmp)`.
9. **Fix**: spawn a codex worker with brief:
   > Read <SKILL_DIR>/agents/fixer.md and follow it. BEAD_ID=<id> FINDINGS_FILE=<path> ADVICE_FILE=<path>.
   Confirm pushed, close the pane. Update the PR description if needed.
10. **Report**: close all panes you opened. Comment the PR link on the bead and the Jira ticket. Report results.
11. **Failure**: if any step fails, leave the panes open, comment what happened on the bead, and stop.

Before ending your turn, make sure beads are committed and pushed. You should have a clean working tree when you end your turn. 

You have Jira and Confluence via MCP (claude.ai tools or whatever is available).
