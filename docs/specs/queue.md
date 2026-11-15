# Build queue

Superseded: no longer kept. Work is ordered by lanes (`docs/operating.md`
"Where things live", `docs/backlog.md`, `jobs/lanes.json`); each spec's
state is its line-3 Status line, listed in `docs/INDEX.md`. The list below
is the queue as it last stood.

- [x] docs/specs/learned-play.md · forks · depends on: triggers-and-conditions, eval-bench (built 5d9c3bd) · D4 sweep superseded by curriculum
- [x] docs/specs/exact-solver.md · forks · depends on: none
- [ ] docs/specs/curriculum.md · forks · depends on: exact-solver

Intended order after curriculum (drafts, not queued; each needs `/spec` first):
the rules-engine series in `docs/specs/rules-engine-upgrade.md` (umbrella),
with `warm-start` after its spec 1 (`contract`): contract → warm-start →
amount-expressions → entity-shape → static-modifiers → replacement-hooks →
decision-points → known-top → per-copy-overrides → monster-patterns →
runtime-registry. Then Defect (new entity kind). Agreed 2026-10-26 (owner's ideas list, kept outside this repo).
- [x] docs/specs/contract.md (folded, git 8ff0ca0) · forks · depends on: curriculum (its night ran 2026-10-28) · confirmed 2026-10-29 by the manager · built 2026-10-30 (branch `contract`, 112894a + docs)
- [ ] docs/specs/warm-start.md · forks · depends on: contract · confirmed 2026-10-30 by the manager

Reorder (manager, 2026-10-31): the coverage pilot's held-out
lead rose with training card kinds (4 -> 10 -> 21: -0.074 / -0.039 /
-0.025), so a minimal runtime-registry + generated-cards spec (with new
mechanics in the generator) goes ahead of the fidelity specs (entity-shape,
known-top, per-copy-overrides). It waits behind the data-scaling result,
which decides the round-0 size those runs use. learned-play-results
"Coverage pilot".
- [x] docs/specs/registry-lite.md · forks · depends on: none · confirmed 2026-10-31 by the manager
- [x] docs/specs/rate-features.md · forks · depends on: registry-lite · confirmed 2026-10-31 by the manager
- [x] docs/specs/distill-two-turn.md · forks · depends on: none (rebase on rate-features if it merges first; both edit learn.py) · confirmed 2026-10-31 by the manager
- [ ] docs/specs/card-sets.md · forks · depends on: none (builds before card-upgrades; lane act1-content or any lane free first) · confirmed 2026-11-08 by the owner
- [ ] docs/specs/card-upgrades.md · forks · depends on: card-sets (lane act1-content builds it after M6+M7) · confirmed 2026-11-08 by the owner
