#!/usr/bin/env bash
#
# wait-for-files.sh — foreground waiter for the GOAT PR review.
#
# Holds the orchestrator's turn open while background agents finish, so the
# whole review runs in one turn and the Stop hook fires once. Runs as a normal
# foreground Bash call (never Monitor, never run_in_background).
#
# Usage:
#   wait-for-files.sh <slice-seconds> <spec>...
#
#   <spec>  A file path (done when it exists), or pid:<N> (done when the
#           process has exited).
#
# Always exits 0. Prints ALL_DONE when every spec is satisfied, or PENDING
# followed by the unsatisfied specs (one per line) when the slice ends first.
# The caller reconciles failures against task notifications, drops dead
# agents from the spec list, and re-runs with the remainder.

set -u

SLICE="${1:-90}"
shift || true

if [[ $# -eq 0 ]]; then
  echo "ALL_DONE"
  exit 0
fi

DEADLINE=$(( $(date +%s) + SLICE ))

while :; do
  PENDING=()
  for SPEC in "$@"; do
    case "$SPEC" in
      pid:*)
        P="${SPEC#pid:}"
        kill -0 "$P" 2>/dev/null && PENDING+=("$SPEC")
        ;;
      *)
        [[ -e "$SPEC" ]] || PENDING+=("$SPEC")
        ;;
    esac
  done

  if [[ ${#PENDING[@]} -eq 0 ]]; then
    echo "ALL_DONE"
    exit 0
  fi

  if [[ $(date +%s) -ge $DEADLINE ]]; then
    echo "PENDING"
    printf '%s\n' "${PENDING[@]}"
    exit 0
  fi

  sleep 5
done
