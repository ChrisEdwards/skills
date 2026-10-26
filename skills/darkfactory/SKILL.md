---
name: darkfactory
description: Spin up an autonomous orchestrator that takes a bead from claimed to a reviewed draft PR, with multi-model review and fix loop, all in an isolated worktree.
disable-model-invocation: true
---

# Dark Factory

Bead to reviewed draft PR, autonomously, in an isolated worktree. This skill is the controller only. It preflights the bead, creates the worktree, and launches the orchestrator. The orchestrator and every worker (an agent spawned in a herdr pane, distinct from a normal subagent) read their own instruction file from this skill's `agents/` directory and read the bead themselves with `br`. Never summarize a bead into a prompt. Pass IDs and file paths only.

Multiple instances run in parallel, so all temp paths and workspace names must be unique.

Never `cd`. The controller's working directory stays the main checkout for the whole run. Use `git -C <dir>` for git commands against other checkouts, and a subshell `(cd <dir> && cmd)` if a tool truly requires a cwd.

## Input

The argument is a bead ID (e.g. `nf-abc`). If none given, ask for one.

## Constants

- `PROJECTS_ROOT`: the `darkfactory projects root` line in `~/.agents/chris-edwards-skills/config.md`. If the file or line is missing, stop and tell the user to run `/setup-chris-edwards-skills`.
- `ORCHESTRATOR_MODEL=claude-opus-5-5`
- `SKILL_DIR`: the absolute path of the directory containing this SKILL.md (the harness reports it when it loads the skill). Herdr agents never load this skill, so pass them this path. Never use a fixed install path.

## Preflight

1. In the main checkout: `br show <bead-id>`.
2. The bead **must** have Jira parity already committed on the default branch (Jira key in `external-ref`, title prefixed with the key, Jira URL comment). If missing, stop and tell the user to create the Jira ticket and commit parity before running darkfactory. Do not create Jira tickets or commit bead changes to the default branch from this skill. Parity must exist before the worktree is created so the worktree inherits it.
3. Extract the target repo from the `repo:*` label (e.g. `repo:my-service` means `$PROJECTS_ROOT/my-service`). If no `repo:*` label exists, ask the user.
4. Extract the Jira key (e.g. `PROJ-123`) for naming.

## Launch

1. Create a detached worktree and resolve the real path (macOS symlinks `/tmp` to `/private/tmp`):
   ```
   git -C $PROJECTS_ROOT/<repo> worktree add --detach /tmp/dark-<jira-key>-<repo>-$RANDOM
   WORKTREE=$(realpath /tmp/dark-<jira-key>-<repo>-<the-actual-suffix>)
   ```
   Use `$RANDOM` (not `$$`) for the suffix so the path stays valid across shells. After creation, `realpath` the path and use that resolved value everywhere downstream.
2. Use herdr to spin up a Claude agent in a new workspace named `DARK-<jira-key>-<repo>`, model `--model $ORCHESTRATOR_MODEL`, working directory `$WORKTREE` (the resolved path), `--permission-mode auto`.
3. Send this brief (fill in the values, nothing more):
   > Read <SKILL_DIR>/agents/orchestrator.md and follow it exactly. SKILL_DIR=<SKILL_DIR> BEAD_ID=<bead-id> JIRA_KEY=<jira-key> WORKTREE=<worktree-path>. I approve the use of herdr to spin up agents as necessary.
4. Verify the orchestrator is up and running, then end your turn. It handles everything from here.
