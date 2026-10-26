---
name: grill-explanations
description: How to write each question in a grilling session. Use every time the grilling, grill-me, or grill-with-docs skill runs, or the user asks to be grilled.
---

# Explain every grilling question in full

The user has nothing in front of them: not the code, the ticket, its comments, or your research. Each question stands on its own.

- Open with the problem in plain words: what goes wrong or is undecided, and why it matters.
- Quote or summarize every source you cite (comment, spec line, file) and say where it lives, with its date for comments. Never write "the earlier comment" or "as discussed".
- When the question depends on how something works today, walk through it step by step. A numbered list is fine.
- For each option, say concretely what it means and what it costs.
- Say what goes wrong if the question is left as it is.
- The recommendation says what to do and why, in one or two sentences.
- Use the repo's glossary terms, but explain any term the user may not hold in mind.

Terse shorthand ("use the Claim as the liveness test") is a failure. Write what a colleague new to this code would need to decide well. Length is fine. Vagueness is not.

Between rounds, restate settled answers in one line each. The full explanation is for open questions.
