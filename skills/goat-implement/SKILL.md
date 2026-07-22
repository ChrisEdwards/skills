---
name: goat-implement
description: Take a bead or Jira ticket from claimed to a reviewed draft PR — implement test-first, then loop a fresh multi-model review against a reused fixer until the findings are clean.
disable-model-invocation: true
---

# GOAT Implement

Turn one tracked issue into a draft PR that has already survived review. This skill does the whole arc: read the issue, claim it, branch, implement test-first, open a draft PR, then run a review→fix loop where a fresh reviewer each round hands findings to a persistent fixer, until nothing MEDIUM or worse remains.

It runs autonomously. The one exception: **repo conventions win.** Wherever the target repo's own instructions (CLAUDE.md, AGENTS.md, pr-tools skills) say to ask a human — which branch to base off, whether to close a bead — honor that gate instead of deciding alone.

## Prerequisites

- A tracker for the issue: `br` for beads, the Atlassian MCP for Jira, `gh` for GitHub issues. Use whichever the issue lives in; degrade gracefully when one is absent.
- The **orca** skills (`orca-spawn`, `orca-watch`, `orca-msg`) for driving workers, and `codex` + `cmux` on PATH for the fixer.
- The `goat-review-pr` skill for the review leg. `/tdd` is used when present.

## Input

The argument is a bead id and/or a Jira key. If both exist for the same work, read both. If none was given, ask for one.

## Workflow

Track the steps with TodoWrite. Don't stop early — the value is a clean reviewed PR.

### 1. Read the issue

Read the bead in full (`br show`) and follow every reference outward: a Jira key in the title or `external-ref` (fetch via the Atlassian MCP), a `Fixes #123` link, a plain URL. Read both the bead and the Jira ticket when both exist. Distill everything into one compact context block: goal, acceptance criteria, explicit out-of-scope, and any existing design/plan. Never invent ticket content you couldn't fetch — note what was unreachable and continue.

### 2. Plan gate

- **Issue is well-specified** (carries a plan, or the implementation detail is clear) → proceed.
- **No plan, but a simple change** → proceed.
- **No plan and the change is complex** → stop. Tell the user this needs planning first and suggest a planning skill (e.g. `goat-triage`). Do not wing a large change.

### 3. Claim and branch

Read the repo's own conventions before touching the tracker or git, and let them override everything in this step. With no repo guidance, use these defaults:

- Set the issue in progress (bead → `in_progress`; Jira → In Progress, assigned to the current user).
- Create the branch. Prefer the repo's pr-tools skills if present, and stack the branch when the repo signals a stacked base (e.g. a `stacked-branch` label); otherwise branch off the default branch. Name it from the Jira key plus a kebab-case slug (e.g. `aiml-1145-add-test-skill`).

### 4. Implement

Implement to the plan (or the issue). Use `/tdd` when it exists — cover the real cases, not just the happy path. Run the repo's own verify/test command (find it in the repo docs or Makefile) and get it green before moving on.

### 5. Commit and open a draft PR

Commit with a conventional-commits message: the subject carries the issue id(s) — both the bead id and the Jira key when both exist — and the body says **what changed and why**, so the history explains the reasoning, not just the diff. Push, and open a **draft** PR (via pr-tools if present).

### 6. Review → fix loop

At most **3 rounds**. Stop as soon as a review turns up nothing rated MEDIUM, HIGH, or CRITICAL. Review and fix run one after the other — never at the same time, since the workers share the same working tree.

Each round:

1. **Review.** Spawn a **fresh Claude worker** (`orca-spawn`, then `orca-watch` for its turn-end) to run `goat-review-pr` on the PR, briefed to **return the consolidated findings rather than post a GitHub review**. Read its full response.
2. **Judge.** Count the confirmed MEDIUM+ findings. None → close the reviewer surface and leave the loop.
3. **Fix.** Hand the findings to the **fixer** — a single **Codex worker** spawned in round one and reused every round after via `orca-msg`. It applies the fixes, re-runs the repo's verify command, commits (conventional message, same issue ids), and pushes.
4. **Close the reviewer** surface; the next round spawns a new one.

Close the fixer surface when the loop ends. Orca has no close wrapper — close a surface with the raw cmux seam (`orca-cmux.sh close --surface <uuid>`).

### 7. Wrap up and exit

- Update the issue (bead and/or Jira) with a short note on what was done and the PR link.
- Per the repo's convention (honoring any "ask first" gate): close the bead and mark the Jira ticket In Review.
- Report the PR URL, the rounds run, and any findings deliberately left (LOW, or unresolved at the round cap). Then exit.

## When things go wrong

- **Issue unreadable / wrong id** → report it and stop; the id is likely wrong.
- **A linked ticket won't fetch** → note it, continue on what you have.
- **orca / codex / cmux missing** → tell the user what to install and stop before the loop; there's no single-worker fallback for the review leg.
- **A worker dies or stalls** → relay its surface UUID so the user can flip to its tab. Don't retry blindly or tear the tab down.
- **Round cap hit with findings still open** → stop the loop, leave the PR in draft, and list what remains in the wrap-up.
