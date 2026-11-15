# Start here

Where the current truth about sts-for-ai lives. This page only points; the
numbers and states it leads to are kept where they're made, so they can't
go stale here. `scripts/docs_index.py --check` (the pre-commit hook) fails
if a link below breaks or a linked fact is retired.

## Current state

- **Facts in force:** the kb store in `claims/`, read with `kb find
  <words>` or `kb get <key>` (the kb skill). A session gets the suspect and
  pinned facts at start. Every number, status and decision that's true now
  is a fact there, citing the doc section it comes from.
- **The product player:** [`product/net`](claims/product/net.json); how a
  player is judged: [`yardstick/protocol`](claims/yardstick/protocol.json),
  [`yardstick/headline-setting`](claims/yardstick/headline-setting.json),
  [`yardstick/headline-control`](claims/yardstick/headline-control.json).
- **Act 1 coverage** (the essential goal): counted from the content files
  (the generated docs/INDEX.md is not in the public copy); the history of each block is in
  [act1-inventory.md](research/act1-inventory.md) (monsters and cards) and
  [act1-relics-potions.md](research/act1-relics-potions.md).
- **What's next and why:** the newest big-picture review (the latest
  `research/big-picture-*.md`) outranks the order
  of [backlog.md](backlog.md); [direction.md](direction.md) outranks both.
- **Every doc:** the folders themselves (the generated index is not in the
  public copy). For how things work now read
  [extending.md](extending.md), [concept.md](concept.md) and kb.

## Goals

- [direction.md](direction.md): goal weights, interests, things to avoid.

## How the system works

- [concept.md](concept.md): the core idea (choose between resulting
  states, judged by what's in them) and where each part lives.
- [extending.md](extending.md): how new content and mechanics enter the
  engine and the net, with the rules each content kind follows.
- [../README.md](../README.md): build, checks, scripts and their flags.

## Logs (history, newest last)

These are append-only. Read a section when a fact or doc cites it; don't
read them for the current state.

- [decisions.md](decisions.md): every design decision with its
  alternatives.
- [research/learned-play-results.md](research/learned-play-results.md):
  results of the training and search experiments.
