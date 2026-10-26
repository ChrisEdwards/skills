---
name: triage-complaints
description: Triage the complaint inbox — corroborate, cluster, and disposition agent-filed friction entries and vents.
disable-model-invocation: true
---

# Triage complaints

Work the complaint inbox into approved fixes. Agents observe; the human decides: nothing an agent wrote becomes environment (CLAUDE.md, skills, tools) without approval here. This is the only path from the store back into agent context.

Paths, file shapes, and vocabulary: [../complain/FORMAT.md](../complain/FORMAT.md).

## Steps

1. **Pick the scope.** Ask the user which entries in `~/.agents/chris-edwards-skills/complaints/` to triage: **repo** (`repos` includes the current repo), **global** (`repos: []`), or **both**. Outside a repo, offer **global** or **all** instead.
2. **Read the inbox.** Load every in-scope entry with status `new` or `retained`, plus `vents.md`. Summarize the vents in two or three lines for color — vents get no dispositions.
3. **Corroborate before grouping.** Check each entry's claims against deterministic evidence: run the command called slow, read the doc called wrong, look for the file called missing. A desire does not prove a tool should exist; a learning does not prove the learned fact is true. Mark each claim corroborated or not.
4. **Cluster and flag recurrence.** Group entries that share a root cause. Any `recurrence` bump, or a cluster repeating after a past promotion, is a triage failure — the fix did not take. Say so explicitly. Union each cluster's `repos`. Two or more repos means the root cause is probably global: a global skill, global CLAUDE.md, the harness, or the machine. Aim the fix there, not at one repo.
5. **Find the sibling class.** Before proposing a fix for one instance, search for other instances governed by the same principle, and match the intervention to the class and its maturity: CLAUDE.md line → routing doc or skill → tool or generator → lint or test → architecture. Removals count as fixes — propose deleting a downstream defense when a better upstream owner makes it redundant.
6. **Propose dispositions, one cluster at a time.** Recommend one of: **promote** (name the exact change — CLAUDE.md edit, skill edit, tool, check, or bead), **wont-fix** (with reason), **retained** (uncorroborated, keep with its evidence), **already-fixed**. Wait for approval per cluster. A single well-evidenced entry is enough to promote; there is no frequency threshold.
7. **Apply approvals.** Promoted, wont-fix, and already-fixed entries: append a `## Disposition` line, set status `resolved`, move the file to `resolved/`. Retained entries: set status `retained`, leave in place. Truncate `vents.md`. In a repo whose convention is beads, create promoted beads through the bead-workflow skill.
8. **Close the loop.** End with a scoreboard: entries triaged, dispositions by kind, repeat clusters, and clusters seen in more than one repo. The repeat-complaint rate is the measure of whether past fixes worked.
