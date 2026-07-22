---
name: goat-triage
description: >-
  This skill should be used when the user asks to "goat-triage" a bead/issue, "triage
  and plan a bead", "converge a plan with codex", "multi-model triage", or wants a tracked
  issue turned into a reviewed, converged implementation plan. Reads a bead and any linked
  tracker (Jira, GitHub issue, URL), researches the code to draft an initial plan, spins up
  a Codex worker over cmux to critique it and offer alternatives, converges through back-and-forth,
  then writes the final plan into the bead's design field and marks it ready-for-agent.
---

# GOAT Triage

Turn one tracked issue into a reviewed, converged implementation plan. Claude drafts a plan grounded in the actual code, a Codex worker running in cmux critiques it and offers alternatives, the two converge through real back-and-forth, and the agreed plan lands in the bead's design field with the `ready-for-agent` label.

This is a planning skill, not an implementation skill. It never edits product code. Its only durable writes are the bead's design field and one label.

## Prerequisites

Verify before starting:

- `br` (beads) available and the current directory is inside the target repo.
- `cmux`, `jq`, and `codex` on `PATH`.
- The **orca** plugin skills are installed: `orca:orca-spawn`, `orca:orca-msg`, `orca:orca-watch`. They wrap the cmux seam; this skill drives Codex through them and never types into cmux by hand.
- A tracker connection for any linked ticket, when present. For Jira use the Atlassian MCP tools; for GitHub issues use `gh`; for a plain URL use WebFetch. If a linked ticket cannot be fetched, note it and continue with the bead alone.

If `codex`, `cmux`, or the orca skills are missing, tell the user what to install and stop. There is no single-model fallback — the whole point is the second engine.

## Workflow

Use the TodoWrite tool to track the steps. Do not stop early; the value is in reaching convergence and writing it back.

### Step 0: Create a run directory

Create one private scratch directory for this run. Every temp file lives inside it.

```bash
TMPBASE="${TMPDIR:-/tmp}"; TMPBASE="${TMPBASE%/}"   # strip trailing slash (macOS TMPDIR has one)
TRIAGE_RUN_DIR=$(mktemp -d "$TMPBASE/goat-triage-XXXXXXXX")
echo "$TRIAGE_RUN_DIR"
```

Carry `$TRIAGE_RUN_DIR` in conversation context and paste its literal value into every command (each Bash call is a fresh shell). Touch only paths under your own run directory. Files it will hold: `plan.md`, `codex-brief.md`, `converge-N.md`, `convergence-log.md`, `final-plan.md`.

Also record the repo and bead up front:

```bash
REPO_DIR="$(git rev-parse --show-toplevel)"
echo "$REPO_DIR"
```

The skill argument is the **bead id** (e.g. `mcp-ejr2`). If none was given, ask the user for it.

### Step 1: Read the bead and every linked tracker

Read the bead in full, including its existing design field and metadata:

```bash
br show <bead-id>
```

Capture: summary, evidence, impact, proposed correction, labels, `external-ref`, dependencies (blocks / parent-child), and any existing design content. Never overwrite prior design work blindly; if the design field is already populated, treat it as input and plan to extend or supersede it (and say so in the final plan).

Then follow every reference outward:

- **Jira / external-ref.** If `external-ref` or the title holds a ticket key (e.g. `AIML-1160`), fetch it with the Atlassian MCP `getJiraIssue` tool (for this org, cloudId `https://contrast.atlassian.net`). Pull the description, acceptance criteria, comments, and links.
- **GitHub issues.** `Fixes #123` / `Closes #123` or an issues URL → `gh issue view`.
- **Other beads.** For each dependency, `br show <dep-id>` so the plan respects ordering and stacking.
- **Plain URLs.** Fetch with WebFetch when reachable.

Never invent ticket content you could not fetch. Distill everything into a compact `ISSUE_CONTEXT` block (goal, requirements, acceptance criteria, explicit out-of-scope, dependencies). This block seeds the plan and the Codex brief, so keep it tight.

Display a short banner:

```
━━━ GOAT Triage ━━━
Bead:   <bead-id> — <title>
Ref:    <external-ref / tracker id, or "none">
Repo:   <repo name @ short-sha>
Labels: <labels>
━━━━━━━━━━━━━━━━━━━━
```

### Step 2: Research the code and draft the initial plan

Do not trust the bead's claims — verify them. The bead's file paths, line numbers, and "only affected X" statements are a starting point, not ground truth. This mirrors how the two engines will treat each other: with mutual skepticism.

- Locate the real code with Grep / Glob / Read (or an `Explore` subagent for a broad sweep). Confirm each claim against the actual files.
- Map the true blast radius. Find **every** consumer, not just the obvious one — other workflows, scripts, Makefile targets, docs, other repos. A miss here is the most common way a plan is wrong.
- Where a mechanic is cheap to test and easy to get wrong, **test it empirically** rather than reasoning about it. (Concrete example from a real run: whether a Docker `.dockerignore` negation re-includes a file, and whether an empty build ARG fails closed — both were settled with throwaway builds, and one overturned a wrong assumption.)

Then write `$TRIAGE_RUN_DIR/plan.md` — the initial plan. Structure it as the design doc it will become:

- **Problem** and **root cause**, grounded in verified file:line references.
- **Proposed changes**, file by file, concrete enough to implement.
- **Blast radius** — a table of every touched/affected site and why.
- **Verification** — how the implementer will prove it works (tests, local runs, empirical checks).
- **Alternatives considered** — at least the obvious competing approach, with the tradeoff.
- **Out of scope** — adjacent problems deliberately left alone.

This is your opening position, not the final answer. Keep it honest about open questions.

### Step 3: Spin up a Codex worker to critique the plan

Write `$TRIAGE_RUN_DIR/codex-brief.md`. The worker starts fresh with no shared history, so the brief must be self-contained. Include:

- The `ISSUE_CONTEXT` block.
- The full initial plan (inline, or say to read `$TRIAGE_RUN_DIR/plan.md`).
- Explicit instructions to be a skeptical senior reviewer: verify **every** claim against the real files rather than trusting the summary, hunt for missing consumers and flaws, propose concrete alternatives, and give a recommended final design with file:line citations.
- A short numbered list of the specific questions you most want answered (missed consumers? correctness traps? better design? scope right?).
- The deliverable instruction: **its final chat response is the answer; do not edit repo files.**

Launch it with the **`orca:orca-spawn`** skill:

- agent: `codex`
- task: a short title like `Triage <bead-id>: critique plan`
- brief-file: `$TRIAGE_RUN_DIR/codex-brief.md`
- cwd: `$REPO_DIR` (so Codex reads the same code)

Record what `orca-spawn` returns: the **surface UUID** and the **after_seq** anchor. You need both. Then follow the worker to its first turn-end with the **`orca:orca-watch`** skill, passing `--after <after_seq>` so a fast worker is never missed.

When `orca-watch` reports `turn_end`, cmux routes the worker's response back to you as a message annotated `[From the agent at surface <uuid>]`, usually pointing at a `/tmp/orca-msg.*/...md` file. **Read it in full** (use Read on the referenced path). That is Codex's critique.

### Step 4: Converge

Convergence is a real dialogue, not a single exchange. Loop until both engines agree on one design with no unresolved substantive objection, or the round cap is hit.

Each round:

1. **Evaluate Codex's critique with the same skepticism it was told to use.** Independently verify its key claims against the repo — do not just accept them. (In a real run this caught confirmations *and* required re-testing a mechanic Codex asserted.) Where a disputed point is empirically testable, test it.
2. **Update your position.** Adopt what survives scrutiny, push back on what does not, and be explicit about which is which.
3. **Reply via `orca:orca-msg`** targeting the worker's surface UUID. Write the message to `$TRIAGE_RUN_DIR/converge-N.md` and send it with `--message-file`. State what you accept, what you reject and why, and a tight list of confirm-or-adjust questions. End every round by asking Codex directly: **"Any remaining blocking concerns? If none, say converged."**
4. **Watch** for the reply with `orca:orca-watch` and read it in full.
5. **Append the round** (both sides, and what changed) to `$TRIAGE_RUN_DIR/convergence-log.md`.

**Convergence is reached** when Codex states it has no remaining blocking concerns and you independently agree the design is correct, complete on blast radius, and right-sized on scope. **Round cap: 4.** If you hit it without converging, stop looping and surface the specific open disagreements to the user rather than forcing a false consensus.

Throughout, surface genuine **alternatives** rather than burying them — if two defensible designs remain, name both with their tradeoffs and pick one with a stated reason. The final plan records the roads not taken.

### Step 5: Assemble the final converged plan

Write `$TRIAGE_RUN_DIR/final-plan.md` — the full design that both engines agreed on. It supersedes the Step 2 draft and should stand on its own as an implementation blueprint. Include, at minimum:

- Problem and root cause.
- Design decisions with the **evidence** behind them, including any empirical findings (state what was tested and the result).
- Blast-radius table of every affected site.
- The concrete changes, file by file (real snippets where they remove ambiguity).
- Verification plan.
- Out-of-scope notes.
- A short **review provenance** line: converged with Codex over cmux, at what commit, and what Codex independently verified or caught.

Display a concise summary of the converged plan in the terminal so the user can see the outcome without opening the bead.

### Step 6: Confirm, then write the design field and label

Writing `ready-for-agent` signals autonomous agents to pick the bead up, so confirm before the final write. Use AskUserQuestion:

- **Write plan to design field and mark ready-for-agent** (recommended) — proceed with both writes.
- **Write design field only** — save the plan, skip the label.
- **Neither / let me review first** — stop; leave the plan at `$TRIAGE_RUN_DIR/final-plan.md` and tell the user the path.

On approval:

- **Design field.** Prefer a repo-local helper if it exists (some repos ship `scripts/br-set-design` because the `br` CLI misparses `--` inside markdown):
  ```bash
  if [ -x "$REPO_DIR/scripts/br-set-design" ]; then
    "$REPO_DIR/scripts/br-set-design" <bead-id> "$TRIAGE_RUN_DIR/final-plan.md"
  else
    br update <bead-id> --design "$(cat "$TRIAGE_RUN_DIR/final-plan.md")"
  fi
  ```
- **Label.**
  ```bash
  br label add <bead-id> -l ready-for-agent
  ```
- **Verify** both landed:
  ```bash
  br show <bead-id> | sed -n '1,8p'
  ```

Report the bead id, that the design field is populated, and the labels now on it.

### Step 7: Cleanup

The Codex worker's cmux tab is left open on purpose (orca convention). Tell the user its surface UUID so they can flip to it, continue it with `orca:orca-msg`, or close it. Do not tear the worker down for them.

Remove this run's scratch files, then the directory. The run produces only flat files, so this avoids `rm -rf` (which destructive-command guards block):

```bash
rm -f "$TRIAGE_RUN_DIR"/*
rmdir "$TRIAGE_RUN_DIR"
```

## Convergence principles

- **Mutual skepticism.** Each engine verifies the other's claims against the real code. "Codex said so" is not evidence; the file is.
- **Empiricism over argument.** When a mechanic is cheap to test, test it. A throwaway build or script settles a disputed behavior faster and more reliably than two models reasoning at each other.
- **Blast radius first.** The most common wrong plan is one that fixes the obvious site and misses a second consumer. Enumerate every caller before agreeing.
- **Name the alternatives.** Convergence is not premature agreement. If two designs are defensible, both go on the table with tradeoffs before one is chosen.
- **Right-size the scope.** A converged plan says what it deliberately leaves out, so the implementer does not gold-plate.

## Error handling

| Scenario | Action |
|----------|--------|
| No bead id given | Ask the user for it before doing anything else |
| `br show` fails | Report the error; the bead id is likely wrong. Abort |
| Linked ticket unfetchable | Note it in the plan and continue with the bead alone |
| `codex` / `cmux` / orca skills missing | Tell the user what to install, abort (no single-model fallback) |
| `orca-spawn` returns `status=error` | Relay the error and the surface UUID if present; do not retry blindly |
| Worker response not delivered after `turn_end` | Re-check the routed message; if absent, `orca:orca-msg` the worker asking it to restate its conclusion |
| Round cap (4) hit without convergence | Stop; present the open disagreements to the user, write nothing to the bead |
| Design field already populated | Treat as input; extend or supersede it and say which in the final plan |
| User declines the Step 6 write | Leave the plan file in place and report its path; make no bead changes |

## Important notes

- **This skill never edits product code.** It reads, plans, and writes only the bead's design field and one label.
- **The worker starts blank.** Everything it needs goes in the brief. A thin brief yields a shallow critique.
- **Read worker responses in full.** They often arrive as a file path; use Read on it. Skimming the tail loses the reasoning that makes convergence real.
- **Do not force consensus.** A surfaced disagreement is a better outcome than a plan both engines quietly doubt.
- **Keep the convergence log.** It is the audit trail for how the design was reached and belongs in context when writing the final plan.
