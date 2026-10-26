---
name: decision-doc
description: Write a decision document with the user. Criteria first, then options, then a scored matrix. Use when the user asks for a decision doc, must choose between design or technology alternatives, or a wayfinder ticket resolves a decision.
---

A **decision document** records how a choice was made so others can dispute it cell by cell. It is built _with_ the user in four moves, criteria before options, and it is separate from the ADR, which is the short permanent record that points at it. Call the Skill tool for "grilling" to run each move as a round of questions.

Every score in the document is co-owned. The agent proposes, the user marks up. Never present a matrix as settled that the user has not marked up. Markup arrives two ways, in the conversation and as comments on the stored document. Read the store's comments before every revision. Each one is markup.

## Move 1. Frame

- Name the decision as a question. If several questions are on the table, keep them in one document only when they are **coupled**: one question's answer changes another's option set. Otherwise one document each.
- State in one sentence why doing nothing is not an option, or that it is one.
- Fix the **running example**: one concrete scenario every option will be walked through, so scores compare like for like. Make it cross every boundary the decision could meet (repositories, teams, projects, tickets), because criteria are later probed against it.
- Facts about the organisation come from the user, not from the repository the agent is in. What is adopted, who uses which tool, and what the team does today are questions to ask, never inferences.
- Ask where the decision document will live. The reader may have no context, so the document carries a Background section that explains the domain from zero.

Done when the user has agreed the question, the coupling call, the example, and the store.

## Move 2. Criteria

Criteria frame the decision, so they are agreed before any option is named. Each criterion carries:

- an id, a short **slug** (two to four words, `R1. Bedrock, short-lived credential`), and a **tier**: `Must` (hard constraint), `Should` (carries the decision), `Nice` (breaks ties). The id and slug head the criterion and its evaluation row, so the two match by eye,
- the statement, with its **scope** said out loud (within one ticket, across repositories, across projects),
- why it matters to this decision,
- how it is judged: what a 10, a 5, and a 1 look like.

Include a criterion only if it can tell this decision's options apart. Probe each one against every boundary the running example crosses. A criterion that silently stops at a boundary is two criteria.

Lay criteria out as headings, one per criterion, not as a table. A table cell holding three sentences wraps badly, and behind a PR a table row is one source line, so a comment on one criterion lands on the whole row.

Done when every criterion has all six parts and the user has agreed the list and the tiers.

## Move 3. Options

Options are generated together. The agent may add candidates. The user keeps or strikes each.

Each option is a subheading that stands alone, never one dense paragraph. Under it: **what it is** in a sentence plus bullets, a diagram where the shape matters (Mermaid sequence or flow, pseudocode, a file tree, per the "show-me" skill), **the example step by step** as a numbered list (what the human does, what the tool shows, what happens next), and **fixed facts** the reader needs to score it. Check that each option answers _this_ decision's question and not a neighbouring one. An option nobody would argue for is **set aside** with the reason and not scored. An option someone might argue for stays in the matrix even if it is expected to fail a Must.

Done when every kept option has its section and the user has agreed the set.

## Move 4. Evaluate

One matrix per decision. Rows are criteria, columns are options. A cell holds a score out of ten and the full justification, as many bullets as the score needs.

- Must rows are scored like any other. A Must score of 5 or below is a fail: flag the cell and eliminate the option whatever its totals.
- Totals per tier, never one weighted sum. Skip a tier the decision has no criteria in.
- **Loop.** Filling cells surfaces new criteria, options, and variants. Marking up scores splits a criterion whose one score hides two judgements, and can move a criterion between tiers. Scoring can also show the question itself is at the wrong level, in which case reframe the decision. Mark every such change: _added during evaluation_, _split during markup_, _promoted_, _reframed at version N_.
- End with **Reading the result**: which criteria the totals turn on, what one fact would flip them, and a stance or an explicit open question for reviewers. When totals sit within a few points, say the matrix does not pick and name what each option buys instead.

Done when the user has marked up every score and the reading names what the decision turns on.

## Record

- Write the decision document to the agreed store. Status `DRAFT`, an owner, a target date to leave draft, and a one-line version note per revision saying what changed and from whose feedback. The template is in [`TEMPLATE.md`](TEMPLATE.md).
- Revise in place so reviewers' comments survive. Store-specific rules are in [`STORES.md`](STORES.md). Read it before the first revision of a stored document.
- If the choice is hard to reverse, write the ADR in the repo through the "domain-modeling" skill: a paragraph plus a link to the decision document, status `proposed` until reviewed.
