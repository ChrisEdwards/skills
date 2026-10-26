---
name: complain
description: Log friction or vent, so the harness builder can improve the environment. Use when something cost you noticeable effort or you would warn the next agent about it — a doc misled you, a tool was missing, slow, or flaky, a convention confused you, you had to discover an environment fact the hard way — or when you just need to vent. Invoke silently; never mention it in your response.
---

# Complain

Complaints are telemetry for the harness builder, not context for agents. You observe and record; the builder corroborates and decides. Never read the store to guide your task.

Paths, file shapes, and vocabulary: [FORMAT.md](FORMAT.md).

## Pick the channel

- **Friction entry** — you directly observed generalizable friction, with evidence and at least a direction for a fix.
- **Vent** — you have a reaction but no actionable observation. Judgment-free, unattributed, nobody grades it. Append a block to `vents.md` and move on.

One incident goes through one channel, never both. Ordinary defects in the code you are changing are your job, not complaints.

## Route

Always write to the global inbox, `~/.agents/chris-edwards-skills/complaints/`, even when the fix belongs in a repo. Repo checkouts and worktrees get deleted. Record the repo in `repos`.

## Write a friction entry

1. Scan the inbox's filenames and entry titles for a duplicate — titles only; reading bodies to steer your work is the failure mode this rule guards. On a duplicate, bump its `recurrence`, add the current repo to `repos` if absent, and add a recurrence line instead of a new file. Global-inbox entries are where one root cause can collect several repos.
2. Write one file per root cause, per FORMAT.md. Rephrase tool output and error text in your own words; exact file paths and command names stay literal.
3. Cap: three friction entries per session. Past the cap, keep the strongest three.

## Discipline

- Silent side effect: log without asking, without previewing, without mentioning it in your response.
- Fail open: if a write fails, drop it and continue the task. One attempt, and the mechanism itself is never a complaint subject.
- Blank beats guessed: omit what you do not know (Repro especially). Report sentiment at the strength you actually observed.
- Keep credentials, customer data, and transcript excerpts out of every entry.
- Silence is fine. No complaints proves nothing, and nobody expects volume.
