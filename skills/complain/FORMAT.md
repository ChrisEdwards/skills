# Complaint store format

Single source of truth for the complaint store's paths, file shapes, and vocabulary. Writers follow the `complain` skill; the reader is `triage-complaints`.

## Location

- Inbox: `~/.agents/chris-edwards-skills/complaints/`, for every complaint. `repos` names where the fix belongs. No repo inboxes, checkouts and worktrees get deleted.
- Resolved entries live in `resolved/` beneath the inbox.

## Vents: `<inbox>/vents.md`

Append-only free text. One block per vent, separated by `---`. No frontmatter, no attribution, no evidence rules. Triage truncates it after reading.

## Friction entries: `<inbox>/YYYY-MM-DD-<slug>.md`

One file per root cause.

```yaml
---
date: 2026-08-26
type: mistake        # mistake | learning | desire
status: new          # new | retained | resolved
agent: claude-fable-5   # the model or harness name as the writer knows it
tags: [gauntlet, speed]
repos: [my-service]   # repo dir names where seen; [] if outside any repo
recurrence: 0        # times re-hit after first logging
---
```

- `type` carves by remedy. **mistake**: the agent did the wrong thing (remedy is a guardrail). **learning**: it had to discover an environment fact the hard way (remedy is documentation). **desire**: it wished for a tool or context it lacked (remedy is building something).
- `status`. `new`: untriaged. `retained`: triaged but uncorroborated, kept with its evidence. `resolved`: dispositioned and moved to `resolved/`.

Body sections, in order:

```markdown
# <one line, the friction itself>

## Observation
What happened, in the writer's own words.

## Impact
What it cost (time, wrong turns, tokens) and who else it would hit.

## Evidence
Exact paths, commands, quoted doc lines. Facts a triager can chase.

## Repro
Minimal steps. Omit the section when unknown — blank beats guessed.
```

On a duplicate: bump `recurrence` in the existing file, add the current repo to `repos` if absent, and add one line under a `## Recurrences` section (`- 2026-08-27 (<repo>): <one-line note>`). No new file.

Triage appends a final section when it resolves an entry:

```markdown
## Disposition
- 2026-08-30: promoted — <exact change: CLAUDE.md line / skill edit / bead id / check> | wont-fix: <reason> | already-fixed
```
