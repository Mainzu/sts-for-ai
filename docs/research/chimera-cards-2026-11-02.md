# Chimera Cards as a reference for mutated cards (2026-11-02)

The owner shared the catalogue of the Slay the Spire mod Chimera Cards,
which puts modifiers on official cards. It is a reference for the
generated character (approach review approach 4, manager.md Next L5):
cards mutated from official parents, in a "near" and a "far" pack. The
two exported sheets are in `data/reference/chimera-cards/` (ignored by
git; third-party content, used for ideas only, in our own terms):
`implemented-cardmods.csv` (about 130 modifiers, 22 of them from
crossover mods) and `suggestions-ideas.csv` (community ideas, with a
status per row). This note is a first pass over the implemented sheet,
not a checked mapping; the generator's spec does the per-modifier
mapping.

## What is useful

- **A boon and a bane per modifier.** Most modifiers trade an upside for
  a downside so the card stays near its parent's strength: "+33% damage,
  Ethereal", "cost -1, Exhaust", "draw 1, -20% damage". That is the
  strength reference the goal-1 benches lacked: a mutated card's parent
  says roughly how strong it should be.
- **Stat-conserving conversions.** Several modifiers turn the stat they
  remove into another effect of the same size ("gain Block equal to the
  damage lost", "apply Poison equal to the damage dealt"). A generator can
  use this shape to keep a mutation's budget constant by construction.
- **Rarity as a tier.** Common modifiers are mostly stat-for-keyword
  trades (a "near" pack); rare ones add conditions or new behaviour (a
  "far" pack). The sheet's own notes ("Balance?", "Needs bane", "too
  strong?") flag where its designers thought the trade was off.
- **Applicability rules.** The Conditions column (damage > 1, is an
  Attack, cost >= 0, the upgrade doesn't change the cost, not
  Ethereal/Exhaust already) is the validity check a generator needs.

## Rough fit with the engine (engine-next atoms)

Of the roughly 108 base-game modifiers:

- **About half need no new atom.** Damage, block or cost changes; the
  Exhaust, Ethereal, Innate and Retain flags; X cost; extra hits or
  random targets (Damage, RandomDamage); Draw; energy or Block next turn
  (a pack power with a turn-start hook); Weak, Vulnerable, Poison,
  Strength, Artifact, Intangible or Thorns (Apply); adding a card
  (AddCard); playing a copy (ReplayCard); growing damage (GrowDamage);
  "only if the enemy intends to attack" (the TargetIntendsAttack
  condition); scaling by Strength (ScaledDamage); a discard choice
  (Pick); "all enemies gain Strength"; whole-card transforms (all numbers
  +x%, swap damage and block), which act on the parent's numbers and need
  nothing from the engine.
- **About a quarter need a new atom.** The ones that recur:
  - conditions on game state: own HP below half, the target is the
    lowest-HP enemy, the last card played was an Attack or a Skill, the
    number of debuffs on a creature;
  - a "when drawn" trigger (draw a card, add a copy, change cost);
  - per-copy cost changes over a combat (cost -1 per play, cost changes
    when taking damage, random cost): the variant slots override damage
    only today;
  - a random discard or exhaust from hand (Pick is a choice);
  - play restrictions ("only if every card in hand is an Attack", "no
    other card can be played while this is in hand");
  - damage that ignores Block; Block equal to the damage dealt.
- **About a fifth are character mechanics we don't model:** orbs,
  stances, Mantra, Scry, Miracle, Foretell, and the crossover characters.
- **About a tenth act outside combat:** gold, permanent damage gains,
  upgrades, max HP on pickup, curses in the deck, elite- or boss-only
  costs.

So a "near" pack can be built from today's atoms. A "far" pack wants
roughly five atoms, all small. Which way goal 1 goes (new combinations
of known atoms, or new atoms) is the owner's open "bundles vs atoms"
decision (approach review, decisions for the owner 1); these five are
the concrete atoms that question would add first.
