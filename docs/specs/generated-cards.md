# Generated cards

Status: superseded (2026-10-31, generated powers built by docs/specs/registry-lite.md and read by gen-training-arms.md; budgeted generated cards never specced).

Finish with `/spec generated-cards` (interview,
Fits with, tests, build steps) before building. Build after the
learned-play amendment (ground-truth-first pipeline) and
`rules-engine-upgrade` are built. This spec is only about randomized content
for training coverage; engine capabilities live in `rules-engine-upgrade`.

## Outcome

Training content that covers far more of the space of card designs than
official StS does, so the effect net learns what each primitive is worth
instead of memorising the few bundles official cards use, measured by
better results on **held-out official cards**.

Prior art: procedural content generation / domain randomization; the
Procgen benchmark (carded in `docs/research/learned-play-and-generalisation/`,
not verified) reports better generalisation from more generated training
levels.

## Ideas so far

- **Cards and powers together** (owner, 2026-10-24: one training run
  instead of two). Generated cards and generated hook powers both use
  existing primitives, triggers and conditions.
  - Generated powers sample **duration patterns** on purpose, so the net
    sees the same effect as permanent (no removal), this turn only (turn
    end → `RemoveSelf`), used up when it fires (`RemoveSelf` in the
    triggered hook) and wearing down (`ReduceSelf(1)`).
  - Validity rules: no hook whose effects can trigger itself (loops), stack
    caps against runaway growth, the existing turn limit against stalls;
    generated cards may grant generated powers.
- **Depends on `rules-engine-upgrade`** for the runtime registry and the
  full rules model (replacement hooks, counters, static modifiers as
  data). Once that's built, generated powers sample from every kind of
  ability and lifetime in the rules-model map, not only triggered hooks.
- **Power budget, from the owner's knowledge:**
  - Strike and Defend are not the baseline: nearly every StS card is
    stronger than them.
  - What sets how strong a card's effect may be, by impact (owner's
    ranking): **rarity > energy cost > exhaust > upgrade ≈ ethereal**.
  - Rarity plays no part in combat, so it isn't a feature and needs no
    engine support. It only sets how often each budget tier appears in a
    generated deck (commons most, rares least).
  - **Anchor, from the owner:** a common card is worth slightly less than
    two basic cards for its cost. Examples: Iron Wave (5 damage + 5 block
    for 1 ≈ a Strike and a Defend for one energy), Dagger Spray (4 × 2 to
    all), Leap (9 block for 1 ≈ 1.8 Defends). Uncommon and rare budgets
    have no such anchor (their effects are usually unique); fit them, or
    give them a wider band above the common budget.
  - Specific downsides (add a Wound, discard a card, exhaust a card, lose
    Focus…) vary widely in cost.
  - Approach to try: give each card a budget from (rarity, cost, exhaust,
    upgraded, ethereal), fitted to the official in-scope cards with the
    owner's ranking as a constraint (budget must rise in that order of
    importance); give each primitive a price fitted the same way; fill a
    generated card's budget with random primitives, with noise (around
    ±30%) and a few deliberate outliers. Downsides get a wide random price
    rather than a fitted one.
- **Decks mix** official and generated cards (ratio to decide).
- **Experiment:** the effect net trained with vs without generated cards,
  tested on held-out official cards (checks 6, 8, 9 and the bench's
  held-out halves). The id net can't use generated cards (each is a new
  id); it stays the control on official cards only.
- **In the learned-play sweep:** one more switch, "generated cards in
  training on/off".
- **Potential direction (owner, 2026-10-25): vary deck size.** Every deck in
  training and on the bench today is the starter + 5 cards (15 for
  Ironclad), so the net has never seen another size; real runs reach 20-35
  cards, and draw odds and pile sizes change with it. Randomize the number
  of extra cards (for example 3-15) in training, and add bench decks of
  other sizes so the effect can be measured.

## Open questions for the interview

- Budget fitting: ~40 in-scope official cards is little data; add more
  official cards (data only) to fit on?
- Ratio of generated to official cards per deck, and per training round.
- Should generated monsters follow (same idea for the enemy side)?
- How to keep generated cards out of every evaluation set.
