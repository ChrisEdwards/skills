# Report and Submit (GOAT Review Steps 9-10)

Loaded from SKILL.md Step 9. Follow end to end, then return to Step 11 (Cleanup) in SKILL.md.

### Step 9: Output the Consolidated Report

Produce this exact format:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GOAT REVIEW: <PR_TITLE>
  <REPO>#<PR_NUM> | <FILE_COUNT> files | +<ADDS> -<DELS>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REVIEW SOURCES
  Claude (<one line per agent run>)  .... <status: OK | FAILED>
  Codex  (review)            .... <status: OK | FAILED | SKIPPED>
  Gemini (code-review)       .... <status: OK | FAILED | SKIPPED>
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

  <N>/<N>  engines agree: <count> findings
  2/<N>+ engines agree: <count> findings
  Single engine:       <count> findings

  (where N = number of active engines: 3 when all run, fewer when engines are skipped)

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

**Only findings with verdict FIX or CONSIDER get inline comments.** Findings with verdict SKIP (all LOW/nitpick-grade items, including agent minor notes) are never posted as inline comments. Instead, collect them into one collapsed block at the end of the review body:

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
- **Claude findings** → `Found by: Claude (<agent name>)` — use the specific lens name from the finding's file (e.g., "correctness-adversarial-reviewer", "security-reviewer", "testing-reviewer")
- **Multi-engine findings** → List all engines, e.g., `Found by: Claude (testing-reviewer) + Codex + Gemini (3/3 consensus)`
- **Docs staleness findings** (generated in Step 4) → `Found by: Docs staleness reviewer`
- **Cross-repo impact findings** (generated in Step 7) → `Found by: Cross-repo impact analysis`
- **Prior-feedback follow-up findings** (generated in Step 8's disposition pass) → `Found by: Prior-feedback follow-up`

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
