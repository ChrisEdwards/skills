# Dark Factory reviewer

You are in a git worktree. You were given `BEAD_ID`, `PR`, and `FINDINGS_FILE`.

1. **Read the spec yourself.** `br show <BEAD_ID>` and its parent, plus `br comments <BEAD_ID>`. You don't need to look at the diff yet. The skill in step 2 will walk you through that.
2. Run `/goat-review-pr` on the PR.
3. Instead of posting to github, just write all findings to `FINDINGS_FILE`. Do not display all the results to the user and ask them questions.
4. Reply with only the findings file path.
