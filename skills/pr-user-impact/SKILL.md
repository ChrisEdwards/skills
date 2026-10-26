---
name: pr-user-impact
description: Explain how a PR or branch changes the product's behaviour and user experience, not its code.
disable-model-invocation: true
---

# PR user impact

Explain what a change does to the **product**: what a user, operator, or downstream system now experiences differently. Code is evidence, never the subject. The reader wants impacts, side effects, benefits, and trade-offs.

## Steps

1. **Find the change.** Use the argument (PR number, branch, or range) if given, else the current branch against its base (`gh pr view` for the base, else the default branch). Collect `git log` and `git diff <base>...HEAD --stat`. Done when you know the commit list and every changed file.

2. **Read the language.** Read `CONTEXT.md` / `CONTEXT-MAP.md` / glossaries and use their terms throughout. Done when you can name the domain concepts the change touches.

3. **Reconstruct before and after.** Read the doc, spec, and README diffs first (they state intent), then the source diffs (they state truth). Read tests for the edge cases they pin. For each behaviour, write down old behaviour, new behaviour, and the trigger. Hunt the **second-order effects**: reordered steps, moved error boundaries, changed defaults or fallbacks, new failure paths, things now deleted or overwritten, new records or log entries, decisions the change supersedes. Done when every behavioural diff hunk maps to a before/after pair, and every pure refactor is confirmed to change nothing visible.

4. **Write the explanation.** Sections, adapted to the change:
   - **The problem it fixes**: the user-facing pain, concretely.
   - **How the flow changes**: a side-by-side BEFORE/AFTER text diagram when ordering or flow moved.
   - **What a user sees**: each visible change, in bold lead-ins.
   - **Side effects**: a table of situation → before → after for every behaviour that shifted beyond the headline fix. Flag the ones that cost the user something.
   - **Net effect**: a benefit/cost table, then one or two sentences naming the biggest trade-off and, if obvious, the follow-up that would soften it.

   Prefer concrete scenarios ("a network blip during fetch now…") over abstractions. Name file paths, labels, commands, and messages users actually see. Leave out code, function names, and test counts unless a user would see them.

5. **Check accuracy.** Re-verify each claim in the side-effects table against the source diff. Done when every claim traces to a line in the diff and nothing in the explanation describes the code instead of the product.
