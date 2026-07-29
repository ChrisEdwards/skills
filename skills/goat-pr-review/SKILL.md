---
name: goat-review-pr
description: >-
  This skill should be used when the user asks for a "GOAT review", "multi-model review",
  "comprehensive PR review", "review with all models", "three-way review", "goat-review-pr",
  or wants the most thorough possible code review of a pull request using multiple AI engines.
  Runs Claude, OpenAI Codex CLI, and Google Gemini CLI reviews in parallel,
  then consolidates and deduplicates all findings into one definitive report.
---

# GOAT Review PR

The Greatest Of All Time code review. Three AI models plus a documentation staleness reviewer, all running in parallel, one consolidated report.

## Prerequisites

Verify before starting: `gh` CLI authenticated, `codex` installed, `gemini` installed. If Codex or Gemini is missing, warn and continue with available engines.

## Workflow

Use the TodoWrite tool to track your todo items. Don't stop prematurely.

### Step 0: Create a Unique Run Directory

Before anything else, create one private directory for this review. Every temp file the run produces lives inside it. Use `mktemp -d`, which creates the directory atomically with an OS-guaranteed-unique name, so two reviews running at the same instant can never share a path or clobber each other's files.

```bash
TMPBASE="${TMPDIR:-/tmp}"; TMPBASE="${TMPBASE%/}"   # strip trailing slash (macOS TMPDIR has one)
GOAT_RUN_DIR=$(mktemp -d "$TMPBASE/goat-XXXXXXXX")
echo "$GOAT_RUN_DIR"
```

All subsequent steps write inside this directory, e.g. `$GOAT_RUN_DIR/codex-review.txt`, `$GOAT_RUN_DIR/codex-pid`, `$GOAT_RUN_DIR/review-payload.json`. The directory name is the run's identity — use its basename anywhere a display "run ID" is wanted.

**Concurrency rules — these are what keep parallel runs isolated. Do not break them:**

- **Carry `$GOAT_RUN_DIR` in conversation context** and substitute its literal value into every command. Each Bash call is a fresh shell, so the variable does not persist between calls — paste the actual path each time.
- **Never write the run directory path (or a "run ID") to a fixed, shared filename** such as `/tmp/goat-run-id.txt`. A fixed-name file is global state, and a concurrent run will overwrite it, silently redirecting this run to the other run's files. The whole point of `mktemp -d` is to avoid any shared name. If you genuinely need the path on disk, it is already encoded in the directory you created — re-derive it from context, never from a shared file.
- **Touch only paths under your own `$GOAT_RUN_DIR`.** Never `cat`, `tail`, `rm`, or glob `/tmp/goat-*` broadly — that reaches into other runs' directories. Always scope to the exact directory from this run.

### Step 1: Parse PR Context

Accept a PR URL as the skill argument. If none provided, determine if there is a pr for the current branch and use it.

Extract metadata, the file count, and the changed-file list in ONE Bash call. Every main-loop tool call re-reads the entire cached conversation, so batching commands is a direct cost lever — measured runs spent several dollars purely on cache reads from tiny sequential Bash steps:

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

Every Claude agent in this skill needs the same base context: PR metadata, the work item, the changed-file list, and the diff. Transcript analysis of past runs showed each reviewer independently re-deriving all of it — 15-30 tool calls and 150k-400k cache-write tokens per agent, duplicated across the whole fleet. That duplication was the single largest cost in the skill. Build the context once instead:

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
  git diff "<BASE_BRANCH>...HEAD"
} | LC_ALL=C tr -d '\000-\010\013-\037\177' > "$GOAT_RUN_DIR/review-pack.md"
wc -c "$GOAT_RUN_DIR/review-pack.md"
```

Substitute the literal values (heredoc-style expansion of `WORK_ITEM_CONTEXT` is fine as an `echo` per line or a quoted block). If the pack exceeds ~400KB, the diff is too large for agents to read whole — note the size in each agent prompt and instruct agents to read the pack's file list, then read the diff selectively with `Read` offsets.

The pack is the input contract for every Claude agent launched in Steps 3c, 4, 7, and 8.

**Send Codex, Gemini, and the Docs Staleness agent as three parallel tool calls in one message.** Wait for the tool results to return, then proceed to Step 4.

#### 3a. Codex CLI (detached)

Codex reviews can take 10-15 minutes on large PRs, which exceeds the Bash tool's 10-minute timeout. Launch as a detached process instead:

```bash
codex review --base "<BASE_BRANCH>" 2>&1 | LC_ALL=C tr -d '\000-\010\013-\037\177' > "$GOAT_RUN_DIR/codex-review.txt" & disown
echo $!  > "$GOAT_RUN_DIR/codex-pid"
echo "Codex launched with PID $(cat "$GOAT_RUN_DIR/codex-pid")"
```

Run with `run_in_background: false` (it returns immediately after disown). Do NOT use `timeout:` since the process is detached.

The `tr` filter is mandatory. Raw Codex output contains NUL and other control bytes, and if they enter model context as a tool result, every subsequent API call fails with a 400 error and the session is permanently wedged. The recorded PID belongs to the filter at the end of the pipeline, which exits when Codex does, so the Step 5 monitor works unchanged. If the 20-minute timeout forces a kill, Codex itself dies on its next write.

#### 3b. Gemini CLI (background)

```bash
~/.claude/skills/goat-review-pr/gemini-review.sh "$GOAT_RUN_DIR/gemini-review.txt"
```

Run with `run_in_background: true` and `timeout: 600000` (10 min).

The gemini invocation lives in the bundled `gemini-review.sh` (alongside this skill) rather than inline, so it is a single reviewed artifact. The script takes the output-file path as its first argument and defaults the prompt to `/code-review`. Edit the gemini flags inside the script (e.g. the auto-approval flag headless review needs) rather than here.

#### 3c. Documentation Staleness Reviewer (subagent)

Launch the `docs-staleness-reviewer` custom agent via the Agent tool with `run_in_background: true`, `subagent_type: "docs-staleness-reviewer"`, and `model: "sonnet"` (docs comparison does not need a frontier model). It runs concurrently with the other engines and its results are collected in Step 5.

**Agent prompt** (substitute the variables):

```
Review PR #<PR_NUM> in <REPO> for stale documentation.
Branch: <HEAD_BRANCH> → <BASE_BRANCH>
Read <GOAT_RUN_DIR>/review-pack.md first — it has the changed-file list and full
diff. Do not re-fetch the diff with git or gh.
```

The agent's system prompt already contains the full investigation checklist and output format. Store the agent task ID so you can collect its results in Step 5.

### Step 4: Run Claude Review Agents

**Only after Step 3's tool calls have returned**, launch the Claude review agents. Codex and Gemini are running in the background and will complete while these agents run.

**Check the fork gate first.** Forked lenses (see "Forked Review Lenses" below) are the DEFAULT way to run this step when both feasibility conditions hold — they delivered frontier-model lenses at below-Sonnet-lens cost in measured runs. Run the standard dispatch below only when the gate fails, and report the choice either way.

**Create a TodoWrite item per agent before you start and mark each done only after it has actually run**, then attribute every finding to the agent that produced it.

The roster is deliberately small, and every Claude lens except one must earn its slot from the diff. The original ~20-lens roster was consolidated after measuring 170 posted findings across 29 PRs: the lenses removed produced zero unique MEDIUM+ findings, and half of all posted comments were nitpick/LOW noise. A later disposition study of a posted review found the author declined half of the findings, nearly all from lenses running outside their strength — so the always-on set is now minimal and every other lens is gated on diff content. Do not add extra review agents beyond this roster and its conditionals.

#### Roster Selection

Size the roster to the diff before launching anything:

- **Lite roster** — the diff has fewer than ~50 changed executable lines AND touches no risk domain (auth, payments, data mutations, migrations, external APIs, serialization). Run only the built-in `/review`, plus `project-standards-reviewer` when standards files exist. Codex and Gemini from Step 3 still provide the cross-model check.
- **Full roster** — everything else. Run the core plus every conditional lens whose gate fires.

**Announce the team.** After selecting, print one line per conditional lens that runs, naming the actual reason ("performance: PR changes cache eviction policy"), and one line for each headline lens that was skipped ("security: no security surface in this diff"). The gates stay honest only if the choices are visible.

#### Core (full roster, always run)

1. `correctness-adversarial-reviewer` — logic errors, edge cases, state management bugs, error propagation failures, and intent-vs-implementation mismatches. Also actively constructs failure scenarios: race conditions, malformed input, partial failures, concurrent mutation.

That is the entire always-on Claude core. Codex and Gemini (Step 3) provide the independent cross-model check, and the docs-staleness agent (Step 3c) runs in the background. The built-in `/review` generalist runs only on the lite roster — with the specialists below available, it produces pure overlap.

#### Conditional Lenses

Gate each on diff content, not file paths alone. When a gate is ambiguous, the security lens fails open (run it); every other lens fails closed (skip it).

- Built-in `/security-review` — the diff touches auth/authz, session handling, permission checks, user-input parsing or deserialization, secrets, crypto, queries built from user input, or a network/trust boundary. **Fails open: unsure means run.** Skip only diffs confidently free of security surface (pure refactors, docs, test-only changes).
- `testing-reviewer` — the diff changes test files or test infrastructure, OR changes meaningful runtime behavior (new or changed branches, state mutation, error handling, API behavior) without corresponding test work. In practice this fires on most real PRs; production-file presence alone does not fire it. Hunts coverage gaps, weak assertions, brittle implementation-coupled tests, tautological tests, and coverage gaming.
- `project-standards-reviewer` — locate the repo's standards files first (CLAUDE.md and AGENTS.md at any directory level, linter configs, contributing docs) and pass the path list in the prompt; the agent reads them itself. If the search finds no applicable standards files, skip the lens and disclose the skip in the report. Scope it to exactly two finding types: (a) a violation of a rule actually written in those files, and (b) a regression — the diff removes or degrades something that existed (logging, metrics, error detail, docs, guardrails). Style preferences with no written rule behind them are minor notes at most.
- `maintainability-reviewer` — the diff is structural work: a substantial refactor, new abstractions, file moves, coupling or type-boundary changes, or roughly 200+ changed executable lines. This one lens owns the entire style/structure axis; never add separate clean-code, simplicity, or architecture reviewers. Small behavior-focused diffs skip it — structure opinions on those are noise the author declines.
- `reliability-reviewer` — error handling, retries, circuit breakers, timeouts, health checks, background jobs, async handlers.
- `api-contract-reviewer` — API routes, request/response types, serialization, versioning, exported type signatures.
- `data-migration-reviewer` — migration files, schema changes, backfills, data transformations, deploy-window safety.
- `performance-reviewer` — database queries, loop-heavy data transforms, caching layers, I/O-intensive paths.
- `previous-comments-reviewer` — only when `HAS_PRIOR_ACTIVITY` is true AND the PR has new commits since that feedback. Its sole job is verifying prior feedback actually landed: dropped threads, partial fixes (the author did X but not Y), and fixes reverted by later commits. It never flags suggestions the author declined, self-review notes, or discussions that concluded without a change request — settled items belong to the Step 8 disposition pass, not to re-litigation here. It fetches the threads itself inside its own context, so the other lenses stay blind to them.

#### Agent Input Contract

Every review agent prompt in this step — and the cross-repo (Step 7) and validation (Step 8) agent prompts — must BEGIN with this block (substitute the literal run directory path):

```
Read <GOAT_RUN_DIR>/review-pack.md first. It contains the PR metadata, work item,
changed-file list, and full diff. Do NOT re-fetch the diff with git or gh.
Read source files only when you need context beyond the diff.
```

This replaces per-agent re-derivation of the diff, which past-run transcripts showed was the skill's largest token cost.

#### Work Item Context for Reviewers

The work item block travels inside the review pack, so do not paste it into prompts. If `WORK_ITEM_CONTEXT` from Step 1 is non-empty, add these instructions to the prompts of `correctness-adversarial-reviewer` and `testing-reviewer` (and the built-in `/review` when the lite roster runs):

- `correctness-adversarial-reviewer`: verify the implementation actually satisfies each stated requirement and acceptance criterion. A requirement that is unmet, partially met, or silently reinterpreted is a finding — HIGH if the PR claims to complete the work item. Also flag implemented behavior the work item explicitly ruled out of scope.
- `testing-reviewer`: check that each acceptance criterion has a test exercising it. An untested acceptance criterion is a finding, not a minor note.
- `/review` (lite roster only): use it as intent context when judging whether the change does what it set out to do.

Only those agents get the added instructions — intent context doesn't change the standards or structure reviews.

#### Model Tiering

Only two lenses inherit the session-default frontier model: `correctness-adversarial-reviewer` and the built-in `/security-review` (when its gate selects it). Launch EVERY other Claude agent with `model: "sonnet"` on the Agent tool: the built-in `/review` (lite roster), `testing-reviewer`, `project-standards-reviewer`, `maintainability-reviewer`, all other conditional agents, the docs-staleness agent (Step 3c), the cross-repo agent (Step 7), and all validation agents (Step 8).

This is not optional. Transcript analysis of past runs showed most agents silently inheriting the frontier model, which multiplied cost 2-3x. Codex and Gemini already provide the independent frontier-model cross-check, so the tiered lenses lose little — their job is coverage, not depth.

#### Agent Output Contract

Every agent prompt (including the built-in skills where possible) must end with this output instruction:

```
Report at most 7 findings. For each: severity (CRITICAL/HIGH/MEDIUM), title,
file:line, a one-paragraph issue description, and a one-line suggested fix.
Only report findings you would defend as MEDIUM or higher. Anything below that
bar goes in a "Minor notes" list at the end (one line each, max 5, ordered
most-actionable first so a concrete suggested change never loses its slot to a
naming or phrasing observation). Return only findings and minor notes — no
preamble, no prose report.
```

This keeps consolidation cheap: the orchestrator merges compact structured findings instead of parsing long prose reports. Agent minor notes become LOW findings with verdict SKIP in Step 6.

### Step 5: Collect Background Results

After the Step 4 review agents complete and the Gemini background task finishes, read the Gemini output. Then wait for Codex (which runs as a detached process and may take up to 15 minutes). Also collect the Docs Staleness agent results.

#### Decision Context Fetch (orchestrator-only)

While waiting on Codex, fetch the decision history the lenses were deliberately not shown. Lenses stay blind to prior decisions by design: a lens told "this was already accepted" is primed to under-scrutinize that code, and the acceptance itself might be wrong. Finding problems is the lens's job; filtering by disposition is the orchestrator's. So this context is fetched only now, after every lens is already running, and is never added to the review pack or any lens prompt.

If `HAS_PRIOR_ACTIVITY` is true, fetch the PR threads in one batch:

```bash
gh pr view <PR_NUM> --json reviews,comments
gh api "repos/<REPO>/pulls/<PR_NUM>/comments" --paginate
```

Also fetch the work item's comments using the same tracker access as Step 1, whenever a work item was found — scope changes and authorizations usually land in a late comment, and a review that reads only the ticket description will flag work the team already approved.

Distill a `PRIOR_DECISIONS` block: one line per finding-shaped item the author has already answered (including in self-review) — what was raised, the author's disposition (fixed / accepted tradeoff / declined), and the stated rationale — plus one line, with date, per ticket comment that changes scope or authorizes extra work. This block feeds the Step 8 disposition pass. If there is no prior activity and the work item has no comments, record it as empty.

**Gemini** (should be done by now — read directly):

```bash
cat "$GOAT_RUN_DIR/gemini-review.txt"
```

**Docs Staleness** — the background Agent should be done by now. Its result is returned directly as the agent's response text. If the agent returned `NO_STALE_DOCS_FOUND`, record the docs engine as OK with zero findings. Otherwise, parse its structured findings and add them to the consolidated findings list in Step 6.

**Codex** — use Monitor to wait for the detached process to finish:

```bash
# Monitor: watch for Codex completion (poll every 30s, up to 20 min)
pid=$(cat "$GOAT_RUN_DIR/codex-pid" 2>/dev/null)
if [ -n "$pid" ]; then
  until ! kill -0 "$pid" 2>/dev/null; do sleep 30; done
  echo "Codex review complete"
fi
```

Use Monitor tool with `timeout_ms: 1200000` (20 min) and `persistent: false`. Once the monitor fires, read the output.

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

Parse all three outputs and produce ONE definitive report.

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

The agent prompt must begin with the Agent Input Contract block (Step 4), then include the `CROSS_REPO_SURFACES` list and the repo/branch context. Instruct the agent to investigate each surface area for the following categories of cross-repo breakage:

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

Findings corroborated by 2+ **distinct engines** (Claude, Codex, Gemini, docs staleness — engines, not Claude sub-agents; five Claude agents agreeing is still one engine) skip validation and are treated as CONFIRMED. They were found independently by separately trained models, which is stronger evidence than one more Claude pass. But consensus skips technical validation only: it proves the code reads that way, not that the author will act on it. Every finding, consensus included, still goes through the Disposition Pass below.

Single-engine MEDIUM findings also skip validation. Under the per-finding verdict logic they resolve to CONSIDER either way, so validating them spends tokens without changing the report's disposition. LOW findings skip validation as before (SKIP verdicts).

#### Dispatching Validation Agents

Group the single-engine CRITICAL/HIGH findings into batches and dispatch them to parallel subagents (Agent tool with `subagent_type: "Explore"`, `model: "sonnet"`). Each agent prompt must begin with the Agent Input Contract block (Step 4). Use these rules for batching:

- **1-5 findings total** — one validation agent handles all of them
- **6+ findings** — split into 2 agents (roughly equal batches)

Each validation agent receives all the findings in its batch plus the PR context (repo, branch, base branch, PR title). The agent prompt must include:

1. The finding ID, title, file, line, severity, issue description, and which engines flagged it
2. Instructions to investigate each finding using the two-phase approach below
3. This framing, verbatim: "False positives are common. Reject a finding when the cited code does not prove it, when it predates and is unaffected by this diff, when surrounding code already handles it, or when it is an unsupported preference rather than a defect."

#### Two-Phase Validation Per Finding

**Phase 1 — Direct Investigation.** For each finding, the agent should:

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
- Does other code in the same file already do the same thing? Before confirming any "this line is wrong" finding, read the other call sites of the same constructor or method — an established sibling pattern usually means the behavior is intentional, and a review that flags one instance without noticing the convention is wrong in a way the author will point out.
- Does config, a feature flag, or a deployment constraint eliminate the scenario in practice?

The agent should actively try to disprove the finding before confirming it.

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
- Recalculate the consensus counts and overall verdict based on the surviving findings.

#### Disposition Pass (every finding, orchestrator-only)

Technical truth is not the posting bar — whether the author will act is. After validation, check every surviving CRITICAL/HIGH/MEDIUM finding against the `PRIOR_DECISIONS` block from Step 5. This includes multi-engine CONFIRMED findings: consensus proves the code reads that way, not that the author will act. No subagents are needed — everything required is already in context. Three questions:

1. **Already settled?** The finding matches an item the author already answered, including in a self-review round. Suppress it. Re-raising a settled item is allowed only with concrete new evidence the author demonstrably did not consider, and the posted comment must name that evidence, acknowledge the prior decision, and never carry a higher severity than the original round.
2. **Already authorized?** The finding objects to scope, and a ticket comment authorized that scope. Suppress it — this is the review being wrong on the facts, not a judgment call.
3. **Established local pattern?** The finding says a line does the wrong thing, but a sibling call site in the same file deliberately does the same thing and validation did not already catch it. Suppress it, or reframe it as a LOW question about whether the convention is documented.

Suppressed findings are removed from the posted review but stay in the on-screen report under the SUPPRESSED section, one line each with the reason, so the user can audit what the filter removed.

### Step 9: Output the Consolidated Report

Produce this exact format:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GOAT REVIEW: <PR_TITLE>
  <REPO>#<PR_NUM> | <FILE_COUNT> files | +<ADDS> -<DELS>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REVIEW SOURCES
  Claude (<one line per agent run>)  .... <status: OK | FAILED>
  Codex  (review)            .... <status: OK | FAILED>
  Gemini (code-review)       .... <status: OK | FAILED>
  Docs Staleness (reviewer)  .... <status: OK | FAILED | NO STALE DOCS>
  Roster: <full | lite — reason>
  Lenses: <forked | standard — reason>

━━━ SUMMARY ━━━

<2-3 sentence overall assessment. Is this PR safe to merge?
 What's the biggest risk? How many total unique findings?>

━━━ FINDINGS ━━━

CRITICAL (<count>) — Must fix before merge
─────────────────────────────────────────

[C1] <title>
     File: <path>:<line>
     Flagged by: <engines, e.g. "Claude + Codex + Gemini (3/3)">
     Issue: <clear description>
     Fix: <specific actionable suggestion>
     Verdict: FIX

HIGH (<count>) — Strongly recommended
─────────────────────────────────────────

[H1] <title>
     File: <path>:<line>
     Flagged by: <engines>
     Issue: <description>
     Fix: <suggestion>
     Verdict: FIX | CONSIDER

MEDIUM (<count>) — Worth addressing
─────────────────────────────────────────

[M1] <title>
     File: <path>:<line>
     Flagged by: <engines>
     Issue: <description>
     Fix: <suggestion>
     Verdict: FIX | SKIP — <reason>

LOW (<count>) — Optional improvements
─────────────────────────────────────────

[L1] <title>
     File: <path>:<line>
     Flagged by: <engines>
     Issue: <description>
     Verdict: SKIP — <reason>

━━━ SUPPRESSED (disposition pass) ━━━

  <One line per suppressed finding: title — reason
   (settled in prior round | authorized in ticket comment |
   established local pattern). Omit this section when
   nothing was suppressed.>

━━━ DOCS STALENESS ━━━

  <If any docs staleness findings exist, list them here in
   the same finding format as above. If none, print:
   "No stale documentation detected.">

━━━ CONSENSUS ━━━

  3/3+ engines agree: <count> findings
  2/3+ engines agree: <count> findings
  Single engine:      <count> findings

━━━ VERDICT ━━━

  <APPROVE | REQUEST CHANGES | COMMENT>
  <one sentence justification>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### Verdict Logic

- Any CRITICAL findings → **REQUEST CHANGES**
- 3+ HIGH findings → **REQUEST CHANGES**
- 1-2 HIGH findings → **COMMENT** with fix recommendations
- Only MEDIUM/LOW → **APPROVE** with suggestions
- No findings → **APPROVE**

#### Per-Finding Verdict Logic

Each finding gets a FIX, CONSIDER, or SKIP verdict:
- CRITICAL or HIGH severity → **FIX**
- MEDIUM + multi-engine consensus → **FIX**
- MEDIUM + single engine → **CONSIDER**
- LOW + multi-engine consensus → **CONSIDER**
- LOW + single engine → **SKIP** with brief reason

### Step 10: Submit a GitHub PR Review

After displaying the consolidated report, ask the user whether they want to submit a formal GitHub PR review using the AskUserQuestion tool. Present two questions in a single AskUserQuestion call:

**Question 1 — Post review?**

Ask whether to submit the review. Options:

- **Yes, submit review** — proceed with review creation
- **No, skip** — skip to Step 11

If the user declines, skip to Step 11.

**Question 2 — Review disposition**

Ask what disposition to give the review. Pre-select the disposition that matches the verdict from Step 9's Verdict Logic, but let the user override it. Options:

- **Approve** — mark the PR as approved
- **Request Changes** — block the PR until changes are made
- **Comment** — leave feedback without approving or blocking

**Question 3 — Review body**

Ask if the user wants to add any overall comments to the review body. Options:

- **Use generated summary** — use the 2-3 sentence summary from the GOAT report as the review body
- **No body** — submit the review with inline comments only

If the user selects "Other" they can type a custom review body to use instead.

#### Branding

Do NOT use the word "GOAT" in any text posted to GitHub (review body, inline comments, or general comments). "GOAT" is an internal skill name, not a public label. Use "Multi-model review" or "Review" instead when a header is needed. The on-screen report shown in the terminal may use "GOAT" freely since only the user sees it.

#### Building the Review Payload

Get the HEAD commit SHA:

```bash
gh pr view <PR_NUM> --repo <REPO> --json headRefOid --jq '.headRefOid'
```

Build a JSON payload file containing the review body, event, commit ID, and all inline comments. Write it to `$GOAT_RUN_DIR/review-payload.json`:

```json
{
  "commit_id": "<HEAD_SHA>",
  "body": "<review body text, or empty string>",
  "event": "APPROVE | REQUEST_CHANGES | COMMENT",
  "comments": [
    {
      "path": "<file path>",
      "line": <line number>,
      "side": "RIGHT",
      "body": "<comment body>"
    }
  ]
}
```

The `event` field maps from the user's disposition choice: "Approve" → `APPROVE`, "Request Changes" → `REQUEST_CHANGES`, "Comment" → `COMMENT`.

Submit the review as a single atomic API call:

```bash
gh api repos/<REPO>/pulls/<PR_NUM>/reviews \
  --method POST \
  --input "$GOAT_RUN_DIR/review-payload.json"
```

This creates one review with all inline comments attached, rather than posting comments individually. The review appears as a single cohesive unit in the GitHub UI.

#### Comment Body Format

**Only findings with verdict FIX or CONSIDER get inline comments.** Findings with verdict SKIP (all LOW/nitpick-grade items, including agent minor notes) are never posted as inline comments — half of all inline comments in past runs were nitpick/LOW noise. Instead, collect them into one collapsed block at the end of the review body:

```
<details>
<summary>Minor notes (<count>)</summary>

- `path/file.py:42` — <one-line note> *(<attribution>)*
- ...
</details>
```

**Advisory structure and style findings never post inline, regardless of consensus.** A finding whose impact is structural — naming, mutability, duplication, extract-a-class suggestions, code organization — goes into the same collapsed block unless it cites a rule actually written in the repo's standards files (CLAUDE.md, AGENTS.md, linter configs) or a concrete functional defect. Multi-engine agreement does not rescue it: three models sharing a taste preference is still a taste preference, and authors decline this class of inline comment almost every time. Inline MEDIUM comments are reserved for findings with functional consequence — correctness, data integrity, security, performance, missing tests, lost observability.

Each inline comment must clearly explain the issue and attribute the source model(s). Use this format:

```
**[<SEVERITY>]** <title>

<Clear, detailed explanation of the issue — what's wrong and why it matters.>

<If the finding affects multiple code locations, mention them:>
Also affects: `path/to/other_file.py:42`, `path/to/another.py:88`

**Suggested fix:** <specific actionable suggestion>

---
*Found by: <attribution>*
```

#### Attribution Rules

The "Found by" line must identify which model(s) flagged the issue and, for Claude findings, which specific review agent detected it:

- **Codex findings** → `Found by: Codex`
- **Gemini findings** → `Found by: Gemini`
- **Claude findings** → Look at the review output in your context to determine which specific reviewer surfaced the finding:
  - Built-in `/review` → `Found by: Claude (code review)`
  - Built-in `/security-review` → `Found by: Claude (security review)`
  - Named review agents → `Found by: Claude (<agent name>)` — use the specific agent name (e.g., "correctness-adversarial-reviewer", "testing-reviewer", etc.)
- **Multi-engine findings** → List all engines, e.g., `Found by: Claude (testing-reviewer) + Codex + Gemini (3/3 consensus)`
- **Docs staleness findings** (generated in Step 3c) → `Found by: Docs staleness reviewer`
- **Cross-repo impact findings** (generated in Step 7) → `Found by: Cross-repo impact analysis`

#### Line Selection

- Each comment must target a line that exists in the PR diff (the RIGHT side of the diff).
- If a finding references multiple lines, pick the most relevant one for the inline comment and mention the other affected locations in the body.
- If the exact line is not in the diff (e.g., the finding is about a line that wasn't changed), use the nearest changed line in the same file and note the actual line in the comment body.

#### Comment Ordering

Order comments in the JSON array from highest to lowest severity (CRITICAL → HIGH → MEDIUM → LOW). GitHub renders them in diff order regardless, but this keeps the payload organized.

#### Error Handling for Review Submission

If the review API call fails (e.g., a comment targets a line not in the diff), the entire review is rejected. To handle this:

1. Try submitting the full review first.
2. If it fails with a validation error, identify the problematic comment(s) from the error message.
3. Remove the offending comment(s) from the payload and retry.
4. If retries still fail, fall back to posting the review body and event without inline comments, then post individual comments using the single-comment API for any that can be salvaged:
   ```bash
   gh api repos/<REPO>/pulls/<PR_NUM>/comments \
     -f body="<comment body>" \
     -f commit_id="<HEAD_SHA>" \
     -f path="<file path>" \
     -F line=<line number> \
     -f side="RIGHT"
   ```
5. Report which comments were successfully posted and which failed.

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

Claude Code supports `subagent_type: "fork"` on the Agent tool: the subagent inherits the parent conversation, and because its prefix is identical to the parent's, its first request reuses the parent's prompt cache instead of paying fresh cache writes. That makes a fleet of review lenses launched from a shared, diff-loaded context cheaper than fresh agents, even though forks are locked to the session model. Measured back-to-back on the same PR, the forked run cost roughly a quarter less overall, with every lens on the frontier model at less than half the per-lens cost of a fresh frontier-model agent.

**Use this path by default whenever both conditions hold**; otherwise run the standard Step 4 dispatch:

1. The environment supports it: `CLAUDE_CODE_FORK_SUBAGENT=1` is set, and the fork `Agent` calls do not error (on error, fall back to standard Step 4 — loudly, never silently). Fork spawning is still a staged-rollout feature, so treat "not available" as normal, not as a failure.
2. The review pack is under ~50k tokens (the diff joins the main context for the rest of the run).

**Always report which path ran.** At the moment you choose, print one line to the user: `Lenses: forked` or `Lenses: standard — <reason>` (e.g. "fork not supported in this environment", "review pack 82k tokens exceeds 50k limit", "CLAUDE_CODE_FORK_SUBAGENT not set"). Carry the same line into the Step 9 report's REVIEW SOURCES section. The fallback must never be silent — the user is comparing cost between the two paths and needs to know which one produced each run.

How it changes the flow:

- After building the review pack (Step 2.5), Read it into the main conversation so the diff sits in the shared cache prefix.
- Launch ALL review lenses as forks **in a single message** so every fork shares one cached prefix. Interleaving any other tool call between launches splits the cache.
- Launch the forks BEFORE the Step 5 Decision Context Fetch. Forks inherit the entire main conversation, so any prior-decision or ticket-comment content loaded before the launch leaks into every lens and breaks their deliberate blindness. This ordering matters only on the fork path (fresh agents see only their prompt and the pack), but keep it on both paths for uniformity.
- Each fork prompt must begin with hard scoping, because a fork inherits this entire workflow and full tool access:

  ```
  You are a forked review agent. IGNORE the GOAT orchestration workflow in your
  context. Do not run other workflow steps, do not launch agents, do not post
  anything to GitHub. Your only job: <lens description>. The PR diff is already
  in your context. Report findings per the Agent Output Contract, then stop.
  ```

- Model tiering does not apply to forks (they inherit the session model). The docs-staleness agent keeps its custom-agent path — forks cannot carry a custom system prompt.
- **Never fork the Step 8 validation agents.** Validation runs 10-20 minutes after the prefix was cached; the cache has expired by then, and each fork would re-write the full prefix at premium rates. Fresh Sonnet validators are cheaper.

## Error Handling

| Scenario | Action |
|----------|--------|
| `codex` not installed | Warn, skip Codex leg, mark as SKIPPED |
| `gemini` not installed | Warn, skip Gemini leg, mark as SKIPPED |
| `gh` not authenticated | Tell user to run `gh auth login`, abort |
| PR URL invalid | Ask user for correct URL |
| Codex process still running after 20 min | Kill PID, mark as TIMEOUT in report |
| Gemini background task timeout | Mark engine as TIMEOUT in report |
| Empty output file | Mark engine as FAILED, note in report |
| Docs staleness agent fails or times out | Mark as FAILED in report, continue with other engines |
| Only 1 engine succeeds | Produce report with available findings, note reduced consensus |

## Important Notes

- **Sanitize every raw CLI capture.** Any raw CLI output captured to a file must pass through `LC_ALL=C tr -d '\000-\010\013-\037\177'` before any part of it is read into context. Control bytes in a tool result permanently wedge the session (every subsequent API call fails with a 400). This applies to any engine added in the future.
- **Do NOT interrupt the Step 4 review agents.** Once Step 4 starts, let every review agent run to full completion. Background `<task-notification>` messages from Codex/Gemini/docs-staleness will arrive mid-review. Ignore them until the Step 4 agents are done. Collecting background results early (Step 5) breaks the intended parallelism and stalls the review.
- **Do NOT stop after the Step 4 reviews.** The consolidation step is the core value of this skill.
- Docs staleness findings are treated as a distinct category. They appear in the DOCS STALENESS section of the report but also contribute to the overall verdict. HIGH docs staleness findings (stale security/deployment docs) count toward the verdict the same way any other HIGH finding would.
- Findings flagged by multiple engines carry significantly more weight than single-engine findings.
- When in doubt about deduplication, keep findings separate rather than incorrectly merging distinct issues.
- The consolidated report replaces the individual review outputs as the authoritative source.
