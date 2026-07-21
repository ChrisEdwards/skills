#!/usr/bin/env bash
#
# gemini-review.sh — runs the Gemini leg of the GOAT PR review.
#
# The skill calls this single, reviewed script instead of invoking the gemini
# CLI directly.
#
# Usage:
#   gemini-review.sh <output-file> [prompt]
#
#   <output-file>  Path to write the review (stdout+stderr) to. Required.
#   [prompt]       Prompt to send. Defaults to the /code-review slash command.
#
# Runs synchronously and writes everything to <output-file>; the caller is
# expected to background the invocation (run_in_background: true).
#
# NOTE: headless gemini cannot answer approval prompts. Add the auto-approval
# flag you need to the invocation below (e.g. -y) before relying on this.

set -uo pipefail

OUT="${1:-}"
if [[ -z "$OUT" ]]; then
  echo "usage: gemini-review.sh <output-file> [prompt]" >&2
  exit 2
fi
PROMPT="${2:-/code-review}"

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

exit $status
