---
name: spec-altitude
description: Set the altitude of a spec and its work items for a large multi-step build, so each item fixes what the implementing agent cannot recover from the code and leaves layout to it. Use when writing or reviewing a spec, Ticket Plan, Work Item Plan, or execution tickets for greenfield work or a feature with many dependent steps, or when a wayfinder map's Notes name this skill.
---

A large build lands as many work items over weeks, and the code drifts from any picture drawn before it existed: a file grows and splits, behaviour moves, a library turns out wrong. A plan that pinned layout is now wrong, and the implementing agent either follows it into a bad shape or ignores it and the plan loses authority. A plan that pinned nothing lets the first implementer set every shared contract by accident. **Altitude** is the level a plan writes at to avoid both.

## The altitude test

A sentence in a spec or work item is **at altitude** when it would still be true if the code were arranged differently. Behaviour, invariants, seams, and contracts pass. File names, module layout, function signatures, and private literals fail. What fails belongs to the agent at build time, decided against the code as it then stands.

Use the vocabulary of `codebase-design` (module, interface, seam, adapter) when writing about structure, and the project's `CONTEXT.md` for domain terms.

## Decide

These are above the altitude. Leaving them open is under-specification, and the first implementer sets them by accident.

- **Seams.** Which modules exist, what each owns, which direction dependencies flow, and where adapters swap. Name the interface at a seam only when more than one work item builds against it.
- **Shared contracts.** Anything two work items both touch: names a user sees (commands, labels, settings keys, files read from a user's repository), a record one item writes and another reads, an environment variable several items read. Each is either decided in the spec or **owned** by exactly one work item that defines and documents it before any consumer starts. The owner blocks its consumers.
- **Behaviour and invariants.** What the system does, observable from outside, including failure modes and fail-closed rules.
- **Constraints already decided.** Map decisions, ADRs, and repository standards, by pointer. Restating a standard in every item is duplication that goes stale.
- **Order and blocking** between items.

## Leave open

These are below the altitude. Fixing them is over-specification.

File and module names and layout. Function and class names other than a seam interface. Signatures. Private helpers. A literal used by one item. Library choice unless the map decided it. Test structure. Which existing code to modify.

Guidance may gesture at a shape or pattern, marked as guidance. Carry the standing rule in the spec and in every item: the code as it stands wins, and the pull request records where the plan was left and why.

## Questions a work item answers

Fix the questions, not the headings. Arrange and name sections however reads best, and answer every one of these.

1. Why it exists and which decision it serves. Include any relevant context that would improve decisions during implementation.
2. What it must do, observably.
3. What must hold when it is done, checkable.
4. Which constraints and invariants were decided above it, by pointer.
5. Which contracts it owns for others and which it consumes, naming each owner.
6. What guidance helps, marked as guidance.
7. What it leaves to other items, naming them.

An item is **self-contained** when an agent in a fresh context reads the item, and is able to implement it properly without looking for other information.

## Review before publishing

Check every item both ways before it is created on the tracker, and fix what fails:

- **Below altitude**: names a file, fixes a layout, or pins a literal no other item needs.
- **Unowned contract**: consumes something no item and no spec section defines.
- **Uncheckable**: the done condition cannot be told from not-done.

Create one item per write, never the whole set in one call. When a merged pull request's departure makes a later item's guidance wrong, fix that item before it is picked up.
