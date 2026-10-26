# Decision document template

Section order is fixed. Every section is present even when short. Ids are per decision (`W1`, `R1`, ...) so a cell can name its criterion.

```markdown
Status: DRAFT | REVIEW | DECIDED     Owner: <name>     Leave draft by: <date>
Version N: <what changed, from whose feedback>. One line per revision, newest first.

# <Title: the question in plain words>

## How to read this
Who this is for, what feedback is wanted, where to comment. Reading time.

## Decisions to be made
1. <question> (one per coupled decision)
Why doing nothing is or is not an option.

## Background and context
From zero. What the system is, what this decision has to settle, the facts
that make it hard. Sources.

## Vocabulary
| Term | Meaning |

## The running example
One concrete scenario every option is walked through.

## How this document was built
Criteria first, then options, then evaluation, then the loop. Tier meanings.
Must scored, fail at 5 or below.

# Decision N. <question>

## Criteria
### <Id>. <Slug> (<Tier>)
<The statement, one sentence.>
- **Why it matters.** ...
- **Judged.** 10 ... 5 ... 1 ... Fail at 5 or below (Must only).
Mark additions: *added during evaluation*.

## Options
### <Id>. <Name>
**What it is.** One sentence, then bullets.
<diagram, when the shape matters>
**The example, step by step.** 1. ... 2. ...
**Fixed facts.** ...
### Set aside before scoring
- <option>, <reason>.

## Evaluation
| Criterion | <Option A> | <Option B> | ... |
Row head: **<Id>** <Slug> (<Tier>), matching the criterion heading.
Cell: **score** then bullets of justification. Flag: `Fails Must`.
Rows at the end: Must (Pass / Eliminated), Should total (max), Nice total (max).

## Reading the result
What the totals turn on. What one fact would flip them.
**Stance.** <option> or Open, with the question for reviewers.

# Decisions
- Decision N. <stance or open>, <what it turns on>.
```
