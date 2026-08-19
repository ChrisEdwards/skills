#!/usr/bin/env bash
#
# gemini-review.sh — runs the Gemini leg of the GOAT PR review.
#
# The skill calls this single, reviewed script instead of invoking the gemini
# CLI directly.
#
# Usage:
#   gemini-review.sh <output-file> <review-pack-file> [prompt]
#
#   <output-file>      Path to write the review (stdout+stderr) to. Required.
#   <review-pack-file>  Path to the review pack markdown file. Its content is
#                       read and prepended to the prompt. This avoids Gemini's
#                       @ file-reference syntax, which fails when the file is
#                       outside the workspace (e.g. /tmp).
#   [prompt]           Instructions to append after the review pack content.
#                      Defaults to a generic review request.
#
# Runs synchronously and writes everything to <output-file>; the caller is
# expected to background the invocation (run_in_background: true).
#
# NOTE: headless gemini cannot answer approval prompts. Add the auto-approval
# flag you need to the invocation below (e.g. -y) before relying on this.

set -uo pipefail

OUT="${1:-}"
if [[ -z "$OUT" ]]; then
  echo "usage: gemini-review.sh <output-file> <review-pack-file> [prompt]" >&2
  exit 2
fi

PACK_FILE="${2:-}"
if [[ -z "$PACK_FILE" ]]; then
  echo "usage: gemini-review.sh <output-file> <review-pack-file> [prompt]" >&2
  exit 2
fi

if [[ ! -r "$PACK_FILE" ]]; then
  echo "review pack not readable: $PACK_FILE" > "$OUT"
  exit 1
fi

PACK_CONTENT=$(cat "$PACK_FILE")
INSTRUCTIONS="${3:-Review the pull request above. Report at most 7 findings.}"

# Prepend a hard override that suppresses Gemini's built-in code-review-expert
# skill, which otherwise tells Gemini to run git diff and scope its own changes.
# That skill reviews the wrong diff on stacked PRs and in worktree checkouts.
SKILL_OVERRIDE="IMPORTANT: Ignore the code-review-expert skill instructions. Do NOT run git diff, git status, or git log. Do NOT scope your own changes. The complete diff is provided below. Review ONLY what is provided. Do NOT use any tools to read files unless you need additional context about code outside the diff. Begin your review now.

"

PROMPT="${SKILL_OVERRIDE}${PACK_CONTENT}

${INSTRUCTIONS}"

if ! command -v gemini >/dev/null 2>&1; then
  echo "gemini CLI not found on PATH; skipping Gemini review." > "$OUT"
  exit 127
fi

# --skip-trust bypass the workspace-trust prompt for this session
# -o text      clean text output
# -p           run headless with the given prompt
# The tr filter strips NUL and other control bytes. If they reach model
# context as a tool result, the session wedges with 400s on every request.
gemini --skip-trust -y -o text -p "$PROMPT" 2>&1 | LC_ALL=C tr -d '\000-\010\013-\037\177' > "$OUT"
status=$?

if [[ $status -ne 0 ]]; then
  echo "" >> "$OUT"
  echo "gemini exited with status $status" >> "$OUT"
fi

# Completion marker for wait-for-files.sh. $OUT exists (empty) from launch, so
# the waiter needs a file that appears only when Gemini is actually done.
touch "${OUT}.done"

exit $status
