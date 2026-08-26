---
name: goat-review-pr
description: >-
  This skill should be used when the user asks for a "GOAT review", "multi-model review", "comprehensive PR review", "review with all models", "three-way review", "goat-review-pr", or wants the most thorough possible code review of a pull request using multiple AI engines. Runs Claude, OpenAI Codex CLI, and Google Gemini CLI reviews in parallel, then consolidates and deduplicates all findings into one definitive report.
---

# GOAT Review PR

The Greatest Of All Time code review. Three AI models plus a documentation staleness reviewer, all running in parallel, one consolidated report.

## Cost Control

**HARD RULE — zero advisor calls.** The orchestrator MUST NOT call the advisor tool. No subagent, fork, or validation agent may call it either. Every agent prompt in this skill already includes an explicit prohibition. If you feel tempted to call advisor for a judgment call, make the call yourself instead. A single advisor round-trip on a large diff can cost more than the entire rest of the review. This rule has no exceptions.

## Single-Turn Rule

Run the entire review in ONE continuous turn. Claude Code runs all subagents in the background (no blocking option exists), Monitor ends the turn and re-wakes, and every turn end fires the Stop hook — which orchestrating agents and headless runs read as "done," ending the review early. So never end the turn to wait and never use Monitor. Every Claude agent writes its findings to a file in `$GOAT_RUN_DIR`, and all waiting happens through foreground calls to the bundled `wait-for-files.sh` (Step 5). Background `<task-notification>` messages inject mid-turn without ending it; use them only to detect failed agents.

## Prerequisites

Verify before starting: `gh` CLI authenticated, `codex` installed, `gemini` installed. If Codex or Gemini is missing, warn and continue with available engines.

## Configuration

| Variable | Default | Effect |
|----------|---------|--------|
| `GOAT_SKIP_CODEX` | unset | Set to any non-empty value to skip the Codex leg entirely. The skill marks Codex as SKIPPED in the report and adjusts consensus counts to use the remaining engines. |
| `GOAT_SKIP_GEMINI` | unset | Set to any non-empty value to skip the Gemini leg entirely. The skill marks Gemini as SKIPPED in the report and adjusts consensus counts to use the remaining engines. |

## Workflow

Use the TodoWrite tool to track your todo items. Don't stop prematurely.

### Step 0: Create a Unique Run Directory

Before anything else, create one private directory for this review. Every temp file the run produces lives inside it. Use `mktemp -d`, which creates the directory atomically with an OS-guaranteed-unique name, so two reviews running at the same instant can never share a path or clobber each other's files.

```bash
GOAT_RUN_DIR=$(mktemp -d /tmp/goat-XXXXXXXX)
echo "$GOAT_RUN_DIR"
```

All subsequent steps write inside this directory, e.g. `$GOAT_RUN_DIR/codex-review.txt`, `$GOAT_RUN_DIR/codex-pid`, `$GOAT_RUN_DIR/review-payload.json`. The directory name is the run's identity — use its basename anywhere a display "run ID" is wanted.

**Concurrency rules — these are what keep parallel runs isolated. Do not break them:**

- **Carry `$GOAT_RUN_DIR` in conversation context** and substitute its literal value into every command. Each Bash call is a fresh shell, so the variable does not persist between calls — paste the actual path each time.
- **Never write the run directory path (or a "run ID") to a fixed, shared filename** such as `/tmp/goat-run-id.txt`. A fixed-name file is global state, and a concurrent run will overwrite it, silently redirecting this run to the other run's files. The whole point of `mktemp -d` is to avoid any shared name. If you genuinely need the path on disk, it is already encoded in the directory you created — re-derive it from context, never from a shared file.
- **Touch only paths under your own `$GOAT_RUN_DIR`.** Never `cat`, `tail`, `rm`, or glob `/tmp/goat-*` broadly — that reaches into other runs' directories. Always scope to the exact directory from this run.

### Step 1: Parse PR Context

Accept a PR URL as the skill argument. If none provided, determine if there is a pr for the current branch and use it.

Extract metadata, the file count, and the changed-file list in ONE Bash call. Every main-loop tool call re-reads the entire cached conversation, so batching commands is a direct cost lever:

```bash
gh pr view "<PR_URL>" --json title,baseRefName,headRefName,additions,deletions,number,url,files,reviews,comments --jq '{title,baseRefName,headRefName,additions,deletions,number,url,fileCount:(.files|length),files:[.files[].path],hasPriorActivity:(((.reviews//[])|length)>0 or ((.comments//[])|length)>0)}'
```

Extract: `BASE_BRANCH`, `HEAD_BRANCH`, `PR_NUM`, `PR_TITLE`, `REPO` (from URL path), `HAS_PRIOR_ACTIVITY`, plus the changed-file list used by the scan below.

`HAS_PRIOR_ACTIVITY` is a boolean flag only. Do NOT fetch the actual review threads or comment bodies yet — that happens in Step 5, deliberately after the review lenses are already running, so the lenses never see prior decisions (see the Decision Context Fetch there for why).

#### Cross-Repository Impact Scan

Using the file list already fetched above, identify whether the PR changes anything that other repositories consume or depend on. Look for changes to:
- **Published API contracts** (OpenAPI specs, protobuf definitions, shared DTOs, REST/gRPC interfaces)
- **Shared libraries or modules** consumed by other repos (common/, shared/, SDK packages)
- **Database schemas or migrations** that other services read from
- **Kafka/event topics** (message formats, topic names, headers)
- **Configuration contracts** (environment variable names, feature flag keys, config file formats)
- **Build/publish artifacts** (Gradle publishing config, artifact coordinates, version bumps)

A path pattern alone (a file under `config/` or `shared/`) is NOT a surface. Confirm from the diff hunks that the change alters something another repository actually consumes — internal config-value changes do not qualify. Record confirmed surfaces as `CROSS_REPO_SURFACES`; if none, record it as empty. If the only surface is small or doubtful, do not plan a dedicated Step 7 agent — add a one-line note about it to the `correctness-adversarial-reviewer` prompt instead.

#### Work Item Lookup

Most PRs implement a tracked unit of work — a ticket, issue, or story in whatever system the team uses. Reviewing the diff alone misses the stated requirements and acceptance criteria, so find and fetch the source of work:

1. Scan the branch name, PR title, and PR body for a work-item reference: an issue key (`ABC-123`), a "Fixes #123" / "Closes #123" link, or a URL to any tracker.
2. Fetch it with whatever access is available — a connected MCP tool for the tracker, a tracker CLI, `gh issue view` for GitHub issues, or WebFetch for a reachable URL. Never invent ticket content you could not fetch.
3. Distill it into a compact `WORK_ITEM_CONTEXT` block (30 lines max): id, title, goal, requirements/acceptance criteria, and any explicit out-of-scope notes. Build this block from the ticket's description and fields only — do NOT include ticket comments. Comments carry scope decisions and authorizations that must stay out of lens view; they are fetched orchestrator-only in Step 5. Compactness matters — this block goes into the shared review pack that every agent reads.

If no reference exists or the lookup fails, record `WORK_ITEM_CONTEXT` as empty, note it in the final report, and continue.

Display banner:

```
━━━ GOAT Review ━━━
PR: <REPO>#<PR_NUM>
Title: <PR_TITLE>
Branch: <HEAD_BRANCH> → <BASE_BRANCH>
Files: <count> (+<adds> -<dels>)
Work item: <id + title, or "none found">
Prior review activity: <yes | no>
Cross-repo surfaces: <list, or "none detected">
━━━━━━━━━━━━━━━━━━━
```

### Step 2: Checkout the PR Branch

Codex and Gemini review whatever branch is currently checked out, so we must be on the PR's HEAD branch before launching them. Record the original branch first so cleanup can restore it.

```bash
ORIGINAL_BRANCH=$(git branch --show-current)
echo "$ORIGINAL_BRANCH" > "$GOAT_RUN_DIR/original-branch"
```

If already on `HEAD_BRANCH`, skip the checkout and proceed to Step 3.

Otherwise, check for uncommitted changes:

```bash
git status --porcelain
```

- **If the output is empty** (clean tree), checkout the PR branch:
  ```bash
  gh pr checkout <PR_NUM>
  ```
- **If the output is non-empty** (dirty tree), do NOT checkout. Instead, use AskUserQuestion to warn the user and present options:
  - **Stash and continue** — run `git stash` then `gh pr checkout <PR_NUM>` (stash will be popped during cleanup)
  - **Abort the review** — stop the skill entirely so the user can deal with their uncommitted work first

If the checkout itself fails (e.g., conflicts), report the error and abort.

### Step 2.5: Build the Shared Review Pack

Every Claude agent in this skill needs the same base context: PR metadata, the work item, the changed-file list, and the diff. Without the pack, each reviewer independently re-derives all of it at 15-30 tool calls apiece — the skill's single largest cost. Build the context once instead:

```bash
{
  echo "# Review Pack: <REPO>#<PR_NUM> — <PR_TITLE>"
  echo "Branch: <HEAD_BRANCH> -> <BASE_BRANCH> | <FILE_COUNT> files | +<ADDS> -<DELS>"
  echo
  echo "## Work Item"
  echo "<WORK_ITEM_CONTEXT block, or 'None found.'>"
  echo
  echo "## Changed Files"
  gh pr view <PR_NUM> --json files --jq '.files[].path'
  echo
  echo "## Full Diff"
  git diff "<BASE_BRANCH>...HEAD" -- ':(exclude)*.lock' ':(exclude)*package-lock.json' ':(exclude)*pnpm-lock.yaml' ':(exclude)*go.sum' ':(exclude)*.min.js' ':(exclude)*.min.css' ':(exclude)*.snap' ':(exclude)vendor/*' ':(exclude)node_modules/*' ':(exclude)*pmd-baseline.txt'
} | LC_ALL=C tr -d '\000-\010\013-\037\177' > "$GOAT_RUN_DIR/review-pack.md"
wc -c "$GOAT_RUN_DIR/review-pack.md"
```

The excludes drop machine-generated content (lockfiles, minified bundles, snapshots, vendored deps, tool baselines). Requirements and work-item files (e.g. `.beans/`) stay in the pack — reviewers need them. Excluded files still appear in the Changed Files list, so lenses know they changed. This list is fixed: never add excludes at runtime, and never trim the pack to reach the fork gate — a pack over the gate simply runs the standard dispatch, which is the correct path for a diff that large. A bare filename pathspec matches only at repo root — keep the `*` prefix on nested-capable names.

Substitute the literal values (heredoc-style expansion of `WORK_ITEM_CONTEXT` is fine as an `echo` per line or a quoted block). If the pack exceeds ~400KB, the diff is too large for agents to read whole — note the size in each agent prompt and instruct agents to read the pack's file list, then read the diff selectively with `Read` offsets.

The pack is the input contract for every Claude agent launched in Steps 4, 7, and 8.

**Send the enabled external engines (Codex unless `GOAT_SKIP_CODEX` is set, Gemini unless `GOAT_SKIP_GEMINI` is set) as parallel tool calls in one message**, then proceed to Step 4. The docs-staleness agent launches with the Step 4 fleet.

#### 3a. Codex CLI (detached)

**Skip this substep entirely if `GOAT_SKIP_CODEX` is set.** Mark Codex as SKIPPED in the report and do not launch the process or create the output/pid files.

Codex reviews can take 10-15 minutes on large PRs, which exceeds the Bash tool's 10-minute timeout. Launch as a detached process instead:

```bash
codex review --base "<BASE_BRANCH>" 2>&1 | LC_ALL=C tr -d '\000-\010\013-\037\177' > "$GOAT_RUN_DIR/codex-review.txt" & disown
echo $!  > "$GOAT_RUN_DIR/codex-pid"
echo "Codex launched with PID $(cat "$GOAT_RUN_DIR/codex-pid")"
```

Run with `run_in_background: false` (it returns immediately after disown). Do NOT use `timeout:` since the process is detached.

The `tr` filter is mandatory. Raw Codex output contains NUL and other control bytes, and if they enter model context as a tool result, every subsequent API call fails with a 400 error and the session is permanently wedged. The recorded PID belongs to the filter at the end of the pipeline, which exits when Codex does, so the Step 5 monitor works unchanged. If the 20-minute timeout forces a kill, Codex itself dies on its next write.

#### 3b. Gemini CLI (background)

**Skip this substep entirely if `GOAT_SKIP_GEMINI` is set.** Mark Gemini as SKIPPED in the report and do not launch the script or create the output file.

**Always pass an explicit prompt built on the review pack.** Never send the bare `/code-review` default: that command picks its own base (the merge-base with `origin/HEAD`), which reviews the wrong diff whenever the PR's base is not the default branch (stacked PRs) or local refs drift. Substitute the literal values:

```bash
~/.claude/skills/goat-review-pr/gemini-review.sh "$GOAT_RUN_DIR/gemini-review.txt" "$GOAT_RUN_DIR/review-pack.md" "Review the pull request above (<REPO>#<PR_NUM>, branch <HEAD_BRANCH> -> <BASE_BRANCH>). The review pack contains the PR metadata, changed-file list, and the complete diff against the PR's true base branch. Review ONLY the changes in that diff. Do NOT run git diff yourself and do NOT compare against origin/HEAD or main, since on stacked PRs those include other PRs' changes. Only flag issues INTRODUCED by this diff, not pre-existing patterns. If you cite an API, constructor, or library behavior, verify it by reading the actual source before asserting. Report at most 7 findings. For each: severity (CRITICAL/HIGH/MEDIUM), title, file:line, a one-paragraph issue description, and a one-line suggested fix. Then a Minor notes list (max 5, one line each). No preamble."
```

Run with `run_in_background: true` and `timeout: 600000` (10 min).

The gemini invocation lives in the bundled `gemini-review.sh` (alongside this skill) rather than inline, so it is a single reviewed artifact. The script takes the output-file path as its first argument, the review-pack file path as its second, and the prompt instructions as its third. Edit the gemini flags inside the script (e.g. the approval mode for headless review) rather than here.

**Known Gemini failure modes:** Gemini has a `code-review-expert` skill that tells it to run `git diff` itself. The gemini-review.sh script prepends a hard override that suppresses this, but if Gemini still runs its own diff, the findings will be about the wrong changes. The script also inlines the review pack content to avoid Gemini's workspace file restriction (it cannot read files outside the repo directory). Despite these mitigations, Gemini still produces an ~80% false positive rate in practice, with common failure modes being: (1) flagging pre-existing patterns not introduced by the diff, (2) fabricating API/constructor/library behaviors without verification, and (3) citing "missing checks" that exist in callers or surrounding code. The validation step (Step 8) catches most of these, but awareness of the pattern helps during consolidation.

### Step 4: Run Claude Review Agents

**Only after the engine launches have returned**, launch every selected Claude lens AND the docs-staleness agent as parallel Agent calls in ONE message. All subagents run in the background — collection happens through Step 5's waiter, never by ending the turn.

**Check the fork gate first.** Forked lenses (see "Forked Review Lenses" below) are the DEFAULT way to run this step when both feasibility conditions hold — they deliver frontier-model lenses at below-Sonnet-lens cost. Run the standard dispatch below only when the gate fails, and report the choice either way.

**Create a TodoWrite item per agent before you start and mark each done only after it has actually run**, then attribute every finding to the agent that produced it.

The roster is deliberately small, and every Claude lens outside the core must earn its slot from the diff. Do not add extra review agents beyond this roster and its conditionals.

#### Roster Selection

Size the roster to the diff before launching anything:

- **Lite roster** — the diff has fewer than ~50 changed executable lines AND touches no risk domain (auth, payments, data mutations, migrations, external APIs, serialization). Run only `correctness-adversarial-reviewer`, plus `project-standards-reviewer` when standards files exist. Codex and Gemini from Step 3 still provide the cross-model check.
- **Full roster** — everything else. Run the core plus every conditional lens whose gate fires.

**Announce the team.** After selecting, print one line per conditional lens that runs, naming the actual reason ("performance: PR changes cache eviction policy"), and one line for each headline lens that was skipped ("security: no security surface in this diff"). The gates stay honest only if the choices are visible.

#### Core (full roster, always run)

1. `correctness-adversarial-reviewer` — logic errors, edge cases, state management bugs, error propagation failures, and intent-vs-implementation mismatches. Also actively constructs failure scenarios: race conditions, malformed input, partial failures, concurrent mutation. When the diff touches exported type signatures, API routes, serialization, or versioning, add one line to its prompt: check contract consistency — shape drift between sibling methods, inconsistent no-match/error values, doc-comment promises the code does not keep.
2. `testing-reviewer` — coverage gaps, weak assertions, brittle implementation-coupled tests, tautological tests, and coverage gaming. The lite roster excludes it, so docs-only and trivial diffs never run it.

That is the entire always-on Claude core. Codex and Gemini provide the independent cross-model check, and the docs-staleness agent runs alongside the lenses.

#### Conditional Lenses

Gate each on diff content, not file paths alone. When a gate is ambiguous, the security lens fails open (run it); every other lens fails closed (skip it).

- `security-reviewer` — the diff touches auth/authz, session handling, permission checks, user-input parsing or deserialization, secrets, crypto, queries built from user input, or a network/trust boundary. **Fails open: unsure means run.** Skip only diffs confidently free of security surface (pure refactors, docs, test-only changes).
- `project-standards-reviewer` — locate the repo's standards files first (CLAUDE.md and AGENTS.md at any directory level, linter configs, contributing docs) and pass the path list in the prompt; the agent reads them itself. If the search finds no applicable standards files, skip the lens and disclose the skip in the report. Scope it to exactly two finding types: (a) a violation of a rule actually written in those files, and (b) a regression — the diff removes or degrades something that existed (logging, metrics, error detail, docs, guardrails). Style preferences with no written rule behind them are minor notes at most.
- `data-migration-reviewer` — migration files, schema changes, backfills, data transformations, deploy-window safety.
- `performance-reviewer` — database queries, loop-heavy data transforms, caching layers, I/O-intensive paths.

#### Docs Staleness Reviewer (always launched with the fleet)

Include one Agent call in the same launch message with `subagent_type: "docs-staleness-reviewer"` and `model: "sonnet"` (docs comparison does not need a frontier model). Prompt (substitute the variables):

```
Review PR #<PR_NUM> in <REPO> for stale documentation.
Branch: <HEAD_BRANCH> → <BASE_BRANCH>
Read <GOAT_RUN_DIR>/review-pack.md first — it has the changed-file list and full
diff. Do not re-fetch the diff with git or gh.
Do NOT call the advisor tool at any point during this review.
Write your findings to <GOAT_RUN_DIR>/lens-docs-staleness.md, then reply with
only that path. If you cannot complete, write the file with FAILED: <reason>.
```

The agent's system prompt already contains the full investigation checklist and output format.

#### Agent Input Contract

Every review agent prompt in this step — and the cross-repo (Step 7) and validation (Step 8) agent prompts — must BEGIN with this block (substitute the literal run directory path):

```
Read <GOAT_RUN_DIR>/review-pack.md first. It contains the PR metadata, work item,
changed-file list, and full diff. Do NOT re-fetch the diff with git or gh.
Read source files only when you need context beyond the diff.
Do NOT call the advisor tool at any point during this review.
```

This replaces per-agent re-derivation of the diff, the skill's largest token cost.

#### Work Item Context for Reviewers

The work item block travels inside the review pack, so do not paste it into prompts. If `WORK_ITEM_CONTEXT` from Step 1 is non-empty, add these instructions to the prompts of `correctness-adversarial-reviewer` and `testing-reviewer`:

- `correctness-adversarial-reviewer`: verify the implementation actually satisfies each stated requirement and acceptance criterion. A requirement that is unmet, partially met, or silently reinterpreted is a finding — HIGH if the PR claims to complete the work item. Also flag implemented behavior the work item explicitly ruled out of scope.
- `testing-reviewer`: check that each acceptance criterion has a test exercising it. An untested acceptance criterion is a finding, not a minor note.

Only those agents get the added instructions — intent context doesn't change the standards or structure reviews.

#### Model Tiering

**Review lenses inherit the session model by default.** Do NOT pass a `model:` override on any review lens agent (core or conditional). The lenses are the skill's primary output, and downgrading them loses the depth that justifies running the skill. Omitting `model:` on the Agent tool makes the agent inherit the caller's model automatically.

**Validation agents (Step 8) also inherit the session model.** Do NOT pass a `model:` override on them. Validation is judgment work, and a weaker validator waves through the false premises and bad fixes it exists to catch.

**Utility and support agents use Sonnet** to save cost on mechanical work that does not benefit from frontier reasoning. Pass `model: "sonnet"` on these agents only:
- The docs-staleness agent (above)
- The cross-repo impact agent (Step 7, `subagent_type: "Explore"`)

This split keeps the review lenses and validators at the user's chosen quality tier while containing cost on the support fleet.

#### Agent Output Contract

Every agent prompt must end with this output instruction:

```
Write your complete output to <GOAT_RUN_DIR>/lens-<agent-name>.md, then reply
with only that path. Report at most 7 findings. For each: severity
(CRITICAL/HIGH/MEDIUM), title, file:line, a one-paragraph issue description,
and a one-line suggested fix. Only report findings you would defend as MEDIUM
or higher. Anything below that bar goes in a "Minor notes" list at the end
(one line each, max 5, ordered most-actionable first so a concrete suggested
change never loses its slot to a naming or phrasing observation). Only findings
and minor notes — no preamble, no prose report. If you cannot complete the
review, still write the file with the single line: FAILED: <reason>.
```

The findings files are canonical — Step 6 consolidation reads them, never notification text. They also give Step 5's waiter its completion signal. Agent minor notes become LOW findings with verdict SKIP in Step 6.

### Step 5: Collect Results (single-turn wait)

Do not end the turn. Wait with the bundled waiter as a normal FOREGROUND Bash call (never Monitor, never `run_in_background`), in ~90-second slices:

```bash
~/.claude/skills/goat-review-pr/wait-for-files.sh 90 \
  "$GOAT_RUN_DIR/lens-<name>.md" ... one spec per launched agent ... \
  "$GOAT_RUN_DIR/lens-docs-staleness.md" \
  "$GOAT_RUN_DIR/gemini-review.txt.done" \
  pid:<CODEX_PID>
```

Omit the Gemini marker if `GOAT_SKIP_GEMINI` is set and the Codex PID if `GOAT_SKIP_CODEX` is set. The waiter prints `ALL_DONE`, or `PENDING` plus the unsatisfied specs when the slice ends. Between slices, reconcile and re-run with the remainder:

- A task notification says an agent failed or was killed → remove its spec, mark it FAILED, never retry.
- Run the Decision Context Fetch below during the first slice gap.
- Deadlines: 15 minutes for lenses/staleness/Gemini, 20 for Codex. Past deadline, drop the spec and mark it FAILED (Codex: kill the PID, mark TIMEOUT), then proceed with what exists.

#### Decision Context Fetch (orchestrator-only)

Between waiter slices, fetch the decision history the lenses were deliberately not shown. Lenses stay blind to prior decisions by design: a lens told "this was already accepted" is primed to under-scrutinize that code, and the acceptance itself might be wrong. Finding problems is the lens's job; filtering by disposition is the orchestrator's. So this context is fetched only now, after every lens is already running, and is never added to the review pack or any lens prompt.

If `HAS_PRIOR_ACTIVITY` is true, fetch the PR threads in one batch:

```bash
gh pr view <PR_NUM> --json reviews,comments
gh api "repos/<REPO>/pulls/<PR_NUM>/comments" --paginate
```

Also fetch the work item's comments using the same tracker access as Step 1, whenever a work item was found — scope changes and authorizations usually land in a late comment, and a review that reads only the ticket description will flag work the team already approved.

Distill a `PRIOR_DECISIONS` block: one line per finding-shaped item the author has already answered (including in self-review) — what was raised, the author's disposition (fixed / accepted tradeoff / declined), and the stated rationale — one line per raised item still awaiting a response, plus one line, with date, per ticket comment that changes scope or authorizes extra work. This block feeds the Step 8 disposition pass, in both directions: suppressing re-raises and catching prior feedback that never landed. If there is no prior activity and the work item has no comments, record it as empty.

#### Reading Results

When the waiter returns `ALL_DONE` (or deadlines expire), collect everything:

**Lens files** — read each `lens-<name>.md`. A file whose content is `FAILED: <reason>` marks that agent FAILED.

**Docs Staleness** — read `lens-docs-staleness.md`. If it says `NO_STALE_DOCS_FOUND`, record the docs engine as OK with zero findings; otherwise add its findings to Step 6.

**Gemini** — if `GOAT_SKIP_GEMINI` was set, record SKIPPED. Otherwise `cat "$GOAT_RUN_DIR/gemini-review.txt"`.

**Codex** — if `GOAT_SKIP_CODEX` was set, record SKIPPED. Otherwise its PID has exited; read the output.

**Important: Codex output files are large** (often 500KB+) because they include the full session transcript — tool calls, file reads, and internal traces. The actual review findings are at the **tail** of the file. Do NOT `cat` the entire file. Instead:

```bash
# Read the last 75 lines which contain the actual review findings
tail -75 "$GOAT_RUN_DIR/codex-review.txt"
```

If the findings are not visible in the last 75 lines, try searching for the review markers:

```bash
# Find where the review findings start
grep -n "Full review comments\|review comments:\|\[P0\]\|\[P1\]\|\[P2\]\|\[P3\]\|Code Review Summary\|Overall assessment" "$GOAT_RUN_DIR/codex-review.txt" | tail -10
```

Then use the Read tool with an offset to read from that line number onward.

If a file is empty, contains only errors, or the process failed, mark that engine as `FAILED` and continue with available results.

### Step 6: Consolidate and Deduplicate

**Reminder: do NOT call the advisor tool.** Consolidation is judgment work, but advisor is still prohibited. Make the dedup and severity decisions yourself.

Parse all three outputs and produce ONE definitive report.

#### Gemini Findings Triage

Before deduplicating, triage Gemini-only findings with extra skepticism. Gemini runs ~80% false positive in practice. The most common failure modes are:

1. **Pre-existing issues** not introduced by this diff. If the flagged code or pattern exists unchanged in the base branch, reject immediately.
2. **Fabricated premises** about APIs, constructors, or library behavior. If a Gemini finding's argument depends on how a specific API works and the claim seems unusual, it is likely wrong. Do not accept without checking.
3. **Missing-check findings where the check exists elsewhere.** Gemini often flags a "missing validation" or "missing error handling" without reading the caller, framework, or annotation that provides it.

For each Gemini-only CRITICAL or HIGH: before routing to a validation agent, spend 30 seconds checking whether the finding's core premise is true (open the cited file and line, check if the API claim is correct). If the premise is clearly false, reject it during consolidation rather than wasting a validation agent on it. Mark the rejection reason in the on-screen report under SUPPRESSED.

#### Deduplication Rules

Two findings are **duplicates** when they refer to:
- The **same file** AND **overlapping line range** (within 5 lines) AND **same category of issue**
- OR the **same conceptual issue** described differently across engines

When merging duplicates:
- Keep the **most detailed description** from any engine
- Keep the **most actionable suggestion** from any engine
- Record **which engines flagged it** (consensus indicator)
- Use the **highest severity** assigned by any engine

#### Severity Normalization

Map each engine's severity to a unified scale:

| Unified | Claude | Codex | Gemini | Docs Staleness |
|---------|--------|-------|--------|----------------|
| CRITICAL | security vuln, data loss | critical | HIGH (security) | — |
| HIGH | bugs, logic errors | high | HIGH | stale security/deploy docs |
| MEDIUM | style, patterns | medium | MEDIUM | misleading docs |
| LOW | nitpicks, suggestions | low | LOW | incomplete docs |

### Step 7: Cross-Repository Impact Analysis

If `CROSS_REPO_SURFACES` from Step 1 is non-empty, dispatch ONE subagent (Agent tool with `subagent_type: "Explore"`, `model: "sonnet"`) to investigate whether the PR's changes break or degrade consumers in other repositories. This step generates **new findings** that get added to the consolidated list. It does not validate existing findings.

The agent prompt must begin with the Agent Input Contract block (Step 4), then include the `CROSS_REPO_SURFACES` list and the repo/branch context. It writes its findings to `$GOAT_RUN_DIR/cross-repo.md` per the Agent Output Contract; collect it with `wait-for-files.sh` slices like Step 5. Instruct the agent to investigate each surface area for the following categories of cross-repo breakage:

**Breaking API changes.** Does the PR remove, rename, or change the type of a field, endpoint, parameter, or return value that external clients depend on? A backwards-incompatible API change that ships without coordinating with consumers is a CRITICAL finding.

**Behavioral contract changes.** Does the PR change the semantics of an existing API (different error codes, different default values, changed ordering, new validation that rejects previously valid input) without a version bump or migration path? Silent behavioral changes that could cause consumer failures are HIGH findings.

**Dependency conflicts.** Does the PR bump a shared dependency (e.g., a library version in a BOM, a transitive dependency) in a way that could conflict with the same dependency pinned at a different version in a consumer repo? Dependency conflicts that would cause build or runtime failures are HIGH findings.

**Message/event format changes.** Does the PR alter Kafka message schemas, event payloads, or header contracts? If old consumers cannot deserialize new messages (or vice versa), that is a CRITICAL finding. If the change is additive-only and forwards-compatible, note it as informational but not a finding.

**Database schema impact.** Does the PR add migrations that alter tables read by other services? Column renames, type changes, or dropped columns affecting shared tables are CRITICAL. Additive changes (new nullable columns, new tables) are generally safe but should be flagged as MEDIUM if another service's queries could be affected.

**Artifact coordinate changes.** Does the PR change the group ID, artifact ID, or published version coordinates of a library or module consumed by other repos? Coordinate changes that require matching updates in consumer build files are HIGH findings.

Each finding the agent creates should include the file, line, a clear description of what breaks and which consumers are affected, and a suggested fix or coordination step. Severity follows the levels described above. Attribution for all findings from this step is `Flagged by: Cross-repo impact analysis`.

If `CROSS_REPO_SURFACES` is empty, skip this step entirely.

After this step completes, merge any new findings into the consolidated findings list before proceeding to validation.

### Step 8: Validate Findings (Eliminate False Positives)

Before producing the final report, **YOU MUST DISPATCH VALIDATION AGENTS** to validate every CRITICAL and HIGH finding **that only one engine flagged** against the broader codebase and any upstream/downstream systems. The goal is to eliminate false positives so the final report only contains real, actionable issues.

Findings corroborated by 2+ **distinct engines** (Claude, Codex, Gemini, docs staleness — engines, not Claude sub-agents; five Claude agents agreeing is still one engine) skip validation and are treated as CONFIRMED. They were found independently by separately trained models, which is stronger evidence than one more Claude pass. But consensus skips technical validation only: it proves the code reads that way, not that the author will act on it. Every finding, consensus included, still goes through Fix Verification and the Disposition Pass below.

Single-engine MEDIUM findings get a lighter check. They are still posted as minor notes, so an unvalidated false premise there embarrasses the review the same as one in a HIGH. Batch them into the validation agents with a Phase 1-only instruction (verify the premise, read the collaborator, skip Phase 2). LOW findings skip validation as before (SKIP verdicts).

#### Dispatching Validation Agents

Group the work into batches: single-engine CRITICAL/HIGH findings (two-phase), single-engine MEDIUMs (Phase 1 only), and consensus findings that carry a suggested fix (Fix Verification only). Dispatch the batches to parallel subagents (Agent tool with `subagent_type: "Explore"`, no `model:` override so they inherit the session model). Each agent prompt must begin with the Agent Input Contract block (Step 4). Each agent writes its verdicts to `$GOAT_RUN_DIR/validation-<n>.md` (FAILED line on inability, like the Agent Output Contract); collect them with `wait-for-files.sh` slices, never by ending the turn. Use these rules for batching:

- **1-5 findings total** — one validation agent handles all of them
- **6+ findings** — split into 2 agents (roughly equal batches)

Each validation agent receives all the findings in its batch plus the PR context (repo, branch, base branch, PR title). The agent prompt must include:

1. The finding ID, title, file, line, severity, issue description, and which engines flagged it
2. Instructions to investigate each finding using the two-phase approach below
3. This framing, verbatim: "False positives are common. Reject a finding when the cited code does not prove it, when it predates and is unaffected by this diff, when surrounding code already handles it, or when it is an unsupported preference rather than a defect."

#### Two-Phase Validation Per Finding

**Phase 1 — Direct Investigation.** For each finding, the agent should:

- **Read the collaborator first.** If the finding's argument depends on what other code does (what a helper returns, what actually reaches a prompt, what a build includes), open that code before accepting the finding. Most false positives are sound reasoning from a false premise about code the reviewer never opened.
- Read the flagged code and its surrounding context (not just the diff, the full file)
- Trace callers and callees to understand how the flagged code is actually used
- Check related systems that interact with this code (other services, shared libraries, database schemas, API contracts, configuration files)
- Look at test coverage for the flagged behavior
- Check git history to see if the pattern is intentional or pre-existing
- If the finding references behavior in another codebase or external system, search for and read that code

**Phase 2 — Adversarial Self-Check.** After the direct investigation, the agent must explicitly ask itself: **"What could make this a false positive?"** Then investigate each possibility it comes up with. Common angles to consider:

- Is the flagged value actually immutable by design, making the "missing update" irrelevant?
- Does an upstream caller guarantee the precondition, making the defensive check unnecessary?
- Does the type system (enums, sealed classes, non-null annotations) already prevent the scenario?
- Is the "race condition" impossible because of request sequencing or locking at a higher layer?
- Is the "missing validation" already handled by a framework interceptor, filter, or annotation?
- Is the "duplication" intentional because the two paths serve different callers with different contracts?
- Does a code comment at the site, the PR description, or a commit message state the behavior is intentional? The Disposition Pass only checks tracker threads, so this is the one checkpoint for in-code documentation.
- Does other code in the same file already do the same thing? Before confirming any "this line is wrong" finding, read the other call sites of the same constructor or method — an established sibling pattern usually means the behavior is intentional, and a review that flags one instance without noticing the convention is wrong in a way the author will point out.
- Does config, a feature flag, or a deployment constraint eliminate the scenario in practice?

The agent should actively try to disprove the finding before confirming it.

#### Fix Verification (every posted fix)

Validating the finding does not validate the fix. Verify every suggested fix that will be posted, consensus findings included (consensus exempts the finding from validation, never the fix, since engines agree on problems but rarely on fixes). Two prongs:

- If the fix names a flag, property, API, or tool, open its definition and check everything it does, not only the part the fix relies on.
- If the fix promises an outcome, name the exact code path or output field that delivers it. If none can be named, the fix is unproven.

Agents report FIX OK or FIX WRONG (one sentence why) alongside the finding verdict.

#### Validation Agent Output

Each agent returns a list of verdicts, one per finding:

- **CONFIRMED** — the finding is real. Include a one-sentence summary of the evidence.
- **FALSE POSITIVE** — the finding is not a real issue. Include a one-sentence explanation of why.
- **DOWNGRADED** — the finding is real but less severe than originally rated. Include the new severity and a one-sentence justification (e.g., "pre-existing pattern, not introduced by this PR").

#### Applying Validation Results

After all validation agents return:

- **Remove** any finding marked FALSE POSITIVE from the report entirely. Do not mention it.
- **Adjust severity** for any DOWNGRADED finding.
- **Keep** all CONFIRMED findings at their original severity.
- **Drop or replace** the suggested fix on any FIX WRONG verdict. The finding still posts, the bad fix does not.
- Recalculate the consensus counts and overall verdict based on the surviving findings.

#### Disposition Pass (every finding, orchestrator-only)

**Reminder: do NOT call the advisor tool.** Make all disposition decisions yourself.

Technical truth is not the posting bar — whether the author will act is. After validation, check every surviving CRITICAL/HIGH/MEDIUM finding against the `PRIOR_DECISIONS` block from Step 5. This includes multi-engine CONFIRMED findings: consensus proves the code reads that way, not that the author will act. No subagents are needed — everything required is already in context. Three questions:

1. **Already settled?** The finding matches an item the author already answered, including in a self-review round. Suppress it. Re-raising a settled item is allowed only with concrete new evidence the author demonstrably did not consider, and the posted comment must name that evidence, acknowledge the prior decision, and never carry a higher severity than the original round.
2. **Already authorized?** The finding objects to scope, and a ticket comment authorized that scope. Suppress it — this is the review being wrong on the facts, not a judgment call.
3. **Established local pattern?** The finding says a line does the wrong thing, but a sibling call site in the same file deliberately does the same thing and validation did not already catch it. Suppress it, or reframe it as a LOW question about whether the convention is documented.

Suppressed findings are removed from the posted review but stay in the on-screen report under the SUPPRESSED section, one line each with the reason, so the user can audit what the filter removed.

**Prior-feedback follow-up.** When `HAS_PRIOR_ACTIVITY` is true and the PR has new commits since that feedback, the `PRIOR_DECISIONS` block also works in the generating direction: for each item the author agreed to fix or left unanswered, check the diff for whether the fix actually landed. A dropped thread, a partial fix (the author did X but not Y), or a fix reverted by a later commit is a new finding — add it to the report at the original item's severity with attribution `Prior-feedback follow-up`. Suggestions the author declined and discussions that concluded without a change request are settled; leave them alone.

### Step 9: Report and Submit

Read `~/.claude/skills/goat-review-pr/references/report-and-submit.md` now and follow it end to end. It holds the consolidated report format, the verdict logic, the GitHub submission flow (AskUserQuestion, payload build, comment format and attribution, error handling), and the branding rule for anything posted to GitHub. It covers what this workflow calls Steps 9 and 10; when it is done, run Step 11. It lives outside SKILL.md so the review lenses and forks never carry it.

### Step 11: Cleanup

Run the whole cleanup as ONE Bash call: restore the original branch if Step 2 changed it, pop the stash only if the user chose "Stash and continue" in Step 2 (omit that line otherwise), then remove the run's files. The run produces only flat files inside `$GOAT_RUN_DIR`, so `rm -f` + `rmdir` is enough — and `rmdir` fails loudly (rather than silently recursing) if anything unexpected is present. This avoids `rm -rf`, which destructive-command guards block. Because the directory is unique to this run, nothing here can touch a concurrent run's files:

```bash
ORIGINAL_BRANCH=$(cat "$GOAT_RUN_DIR/original-branch" 2>/dev/null)
CURRENT_BRANCH=$(git branch --show-current)
if [ -n "$ORIGINAL_BRANCH" ] && [ "$CURRENT_BRANCH" != "$ORIGINAL_BRANCH" ]; then
  git checkout "$ORIGINAL_BRANCH"
fi
git stash pop   # ONLY if "Stash and continue" was chosen in Step 2 — omit otherwise
rm -f "$GOAT_RUN_DIR"/*
rmdir "$GOAT_RUN_DIR"
```

## Forked Review Lenses (default Step 4 path when feasible)

Claude Code supports `subagent_type: "fork"` on the Agent tool: the subagent inherits the parent conversation, and because its prefix is identical to the parent's, its first request reuses the parent's prompt cache instead of paying fresh cache writes. That makes a fleet of review lenses launched from a shared, diff-loaded context cheaper than fresh agents, even though forks are locked to the session model — every lens runs on the frontier model at less than half the per-lens cost of a fresh frontier-model agent.

**Use this path by default whenever both conditions hold**; otherwise run the standard Step 4 dispatch:

1. The environment supports it: `CLAUDE_CODE_FORK_SUBAGENT=1` is set, and the fork `Agent` calls do not error (on error, fall back to standard Step 4 — loudly, never silently). Fork spawning is still a staged-rollout feature, so treat "not available" as normal, not as a failure.
2. The review pack is under ~70k tokens (the diff joins the main context for the rest of the run). Past ~70k the per-fork cache reads erode the savings.

**Always report which path ran.** At the moment you choose, print one line to the user: `Lenses: forked` or `Lenses: standard — <reason>` (e.g. "fork not supported in this environment", "review pack 82k tokens exceeds 70k limit", "CLAUDE_CODE_FORK_SUBAGENT not set"). Carry the same line into the Step 9 report's REVIEW SOURCES section. The fallback must never be silent — the user is comparing cost between the two paths and needs to know which one produced each run.

How it changes the flow:

- After building the review pack (Step 2.5), Read it into the main conversation so the diff sits in the shared cache prefix.
- Launch ALL review lenses as forks **in a single message** so every fork shares one cached prefix (the docs-staleness agent's non-fork call joins the same message). Interleaving any other tool call between launches splits the cache. Forks run in the background like every subagent; the Step 5 waiter collects their findings files, so the Single-Turn Rule holds on both paths.
- Launch the forks BEFORE the Step 5 Decision Context Fetch. Forks inherit the entire main conversation, so any prior-decision or ticket-comment content loaded before the launch leaks into every lens and breaks their deliberate blindness. This ordering matters only on the fork path (fresh agents see only their prompt and the pack), but keep it on both paths for uniformity.
- Each fork prompt must begin with hard scoping, because a fork inherits this entire workflow and full tool access:

  ```
  You are a forked review agent. IGNORE the GOAT orchestration workflow in your
  context. Do not run other workflow steps, do not launch agents, do not post
  anything to GitHub. Do NOT call the advisor tool. Codex, Gemini, and the
  docs-staleness agent are already running elsewhere — never launch, monitor,
  or wait on them. Your only job: <lens description>. The PR diff is already
  in your context. Write your findings per the Agent Output Contract to
  <GOAT_RUN_DIR>/lens-<name>.md, reply with only that path, then stop.
  ```

- Forks inherit the session model, which matches the standard path (review lenses always run at the session model). The docs-staleness agent keeps its custom-agent path with `model: "sonnet"` — forks cannot carry a custom system prompt.
- **Never fork the Step 8 validation agents.** Validation runs 10-20 minutes after the prefix was cached; the cache has expired by then, and each fork would re-write the full prefix at premium rates. Fresh Sonnet validators are cheaper.

## Error Handling

| Scenario | Action |
|----------|--------|
| `codex` not installed | Warn, skip Codex leg, mark as SKIPPED |
| `gemini` not installed | Warn, skip Gemini leg, mark as SKIPPED |
| `GOAT_SKIP_CODEX` set | Skip Codex leg, mark as SKIPPED |
| `GOAT_SKIP_GEMINI` set | Skip Gemini leg, mark as SKIPPED |
| `gh` not authenticated | Tell user to run `gh auth login`, abort |
| PR URL invalid | Ask user for correct URL |
| Codex process still running after 20 min | Kill PID, mark as TIMEOUT in report |
| Gemini background task timeout | Mark engine as TIMEOUT in report |
| Empty output file | Mark engine as FAILED, note in report |
| Any Claude agent errors or dies (per task notification) | Drop its spec from the waiter, mark FAILED, continue — no retry |
| Lens deadline (15 min) reached | Mark missing agents FAILED, proceed with available findings |
| Docs staleness agent fails or times out | Mark as FAILED in report, continue with other engines |
| Only 1 engine succeeds | Produce report with available findings, note reduced consensus |

## Important Notes

- **Sanitize every raw CLI capture.** Any raw CLI output captured to a file must pass through `LC_ALL=C tr -d '\000-\010\013-\037\177'` before any part of it is read into context. Control bytes in a tool result permanently wedge the session (every subsequent API call fails with a 400). This applies to any engine added in the future.
- **Never end the turn to wait.** All waiting is a foreground `wait-for-files.sh` call (Step 5); ending the turn fires the Stop hook, which orchestrating agents and headless runs read as completion. Mid-review `<task-notification>` messages inject without ending the turn — use them only to mark failed agents. Findings always come from the `$GOAT_RUN_DIR` files.
- **Do NOT stop after the Step 4 reviews.** The consolidation step is the core value of this skill.
- Docs staleness findings are treated as a distinct category. They appear in the DOCS STALENESS section of the report but also contribute to the overall verdict. HIGH docs staleness findings (stale security/deployment docs) count toward the verdict the same way any other HIGH finding would.
- Findings flagged by multiple engines carry significantly more weight than single-engine findings.
- When in doubt about deduplication, keep findings separate rather than incorrectly merging distinct issues.
- The consolidated report replaces the individual review outputs as the authoritative source.
