# Revising a stored decision document

Reviewers mark up the stored copy. A revision that loses their comments loses the review. Rules per store.

## Confluence

The API has no partial edit. Every update replaces the whole body. Inline comments survive only if the new body still carries their anchor spans.

1. Fetch the page body in HTML. It is large, so it lands in a file, not in context.
2. Edit the file in place with string or regex replacements. Assert each target matches exactly once. Keep every `<span class="annotation" ...>`, `data-local-id`, `data-colwidth`, and media id untouched.
3. Assert the annotation count is unchanged, then send the whole body back.
4. Read the inline comments afterwards to confirm none went dangling.

Never regenerate the body from memory. That drops every inline comment. Footer comments survive any update. A comment on a passage you rewrite is orphaned either way, so keep the anchored words when you can and tell the user when you cannot.

Cost: the full body passes through the model on the way back, about the page's size in characters per edit. For a long page a small script with an API token that does the replacement outside the model is the fix.

## Google Doc

Same shape as Confluence. Full replacement loses anchored comments. Prefer the document API's targeted edits when available. Otherwise treat as Confluence.

## Repo markdown behind a PR

Edits are commits. Review comments anchor to lines and survive pushes, marked outdated when their line changes. Nothing to preserve by hand. Keep the file under the path the ticket links.

A table row is one source line, so a comment on one matrix cell lands on the whole row. Keep criteria and options out of tables. The matrix stays a table, and the reader names the option in the comment. Mermaid renders on GitHub, so diagrams can be inline.

## Jira description

One field, overwritten whole. Comments are not anchored, so nothing is lost and nothing is preserved. Quote the passage a comment referred to when you answer it.
