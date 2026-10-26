---
name: grill-complexity
description: Show the complexity each option in a grilling question adds, and what it buys. Use every time the grilling, grill-me, or grill-with-docs skill runs, alongside grill-explanations, or when the user weighs design options.
---

# Make the cost of every option visible

A choice that sounds careful often adds machinery that proves little. The user can only weigh that if you show it. Before writing a question, trace each option through the code and docs as they stand.

For each option, say:

- **What it adds.** New types, states, outcomes, fields, vendor calls, files, and tests. Name every place a new concept must be threaded through, and count them ("a fourth outcome touches the enum, labels, comments, Run Log, progress panel, Evidence and Re-run briefing, seven places").
- **What it buys.** The failure it prevents, how likely that failure is, and who would catch it anyway. If a person reviews the result regardless, say so.
- **Whether it can deliver.** A check that only approximates the truth (a commit that mentions a key, a heuristic, an Agent's own claim) is not proof. Say what it would accept wrongly and what it would reject wrongly, with a concrete example from this repository when you can find one.
- **Who pays, and when.** One-time cost to build, against the ongoing cost to every reader and every later change.
- **How reversible it is.** Easy to add later, or hard to remove once other code depends on it.

Then:

- Name the simplest option that meets the real need, even if nobody proposed it. "Don't build it" and "hand it to a person" are options.
- When two options behave the same for the user, say so plainly, and favour the one with fewer concepts.
- Recommend in one or two sentences, weighing complexity against what it buys.

Grep and read before you claim a count or an example. A cost you guessed is as misleading as one you hid.
