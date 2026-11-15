# Fractional amounts and max HP

Status: closed (2026-11-11, built and in use; owner-led, lane act1-content; landed 31907643). As built: docs/extending.md (amounts: the fraction, OwnMaxHp, HealOf).

The Divider idea is kept in the owner's idea list. Built before
`docs/specs/potions.md`, which loads Blood Potion with it.

## Outcome

An amount can scale a state number by a fraction (`base + k/per ×
quantity`, truncated as the game truncates), it can read the user's max HP,
and an effect can heal by an amount. So "heal 20% of your max HP" (Blood
Potion) and its kind are content, not code.

**How it moves the goals.** Act 1 (`decision/act1-finish`): Blood Potion
becomes writable (the potions spec loads it); later heals by a share of max
HP (rest site, Lizard Tail, Fairy in a Bottle) have their amount. Goal 1: a
designer writes "a fifth of your max HP" in the files, and generated content
can use it. Every amount written today resolves exactly as now; golden, the
rules version and every net's input stay as they are.

**Non-goals** (owner, 2026-11-11):
- Amounts fixed when a monster's intent is chosen. Hexaghost's Divider
  (`HP / 12 + 1`, fixed at `setMove`, the engine's `rolled_damage` and
  `divider_damage`) stays as it is. An amount resolves when its effect
  runs, and an intent-time amount is a different timing: it becomes an idea.
- `WinHeal` by an amount.
- New net columns for the new quantity: heals have no net column today by
  design (`py/src/features.rs`, "the 10-29 layout stays"), and no content
  puts max HP in damage yet.
- The heals that need other missing pieces (rest site, Lizard Tail, Fairy in
  a Bottle).
- An `OwnHp` (current HP) quantity: nothing needs it yet.

## Behavior

### The fraction

- `Amount` gains `per` (the bottom of the fraction, at least 1, default 1):
  `base + trunc(k × quantity / per)`, computed in 32 bits, truncated toward
  zero as Java's `(int)` cast does (game parity). With `per` 1 this is
  today's `base + k × quantity`, bit for bit.
- A fraction is kept in lowest terms with its sign on top (`"2/10"` loads as
  1/5), so two equal fractions are one amount.
- `times(n)` (a power's stacks, `Effect::scaled`) multiplies `base` and `k`
  and keeps `per`.

### Files

- `"k"` is a whole number (`"k": 2`, as today) or a string fraction
  `"a/b"` (`"k": "1/5"`, owner). A number with a fraction part (`"k": 0.5`)
  or a bad string (`"1/0"`, `"x"`) is an error naming the entry; today
  `"k": 0.5` loads silently as 0 (a bug this fixes).
- The writer (`amount_json`) writes `"k": "1/5"` when `per` isn't 1, else
  as today, so every file written today is written byte for byte as before.
- An upgrade can edit the top (`amount.k`, as today) or the bottom
  (`amount.per`); the upgrade diff lists both.

### Max HP and the heal

- A new quantity `OwnMaxHp`: the max HP of whoever uses the effect (the
  player, or the monster).
- A new effect `HealOf(Amount)`: heals the user by the amount, as `Heal`
  does (capped at max HP, nothing at 0 HP, `OwnerUnbloodied` on crossing
  back above half). A resolved amount at or below 0 heals nothing.
  `{"HealOf": {"base": 0, "k": "1/5", "of": "OwnMaxHp"}}` is Blood Potion's
  heal (16 at 80 max HP, 15 at 75).
- `HealOf` scales by stacks like `BlockOf`; the bounds count it as a heal
  (`can_heal`); the heuristic gives it nothing, as `Heal`; the net gives it no
  column, as `Heal`. `OwnMaxHp` in a damage expression gets no `expr_q_*`
  column (named limit); in `BlockOf` / `ApplyOf` it flows into their `k`
  columns as any quantity does.
- Both are new elements: `registry::element_names()`, `content/wording.json`
  ("your max HP"; a fraction words as "1/5 of your max HP"), the explorer.

### The net and the heuristic

Every reader that casts `k` to a float reads `k / per` (features'
`damage_from_block`, `strength_mult`, `per_strike`, `expr_k`,
`block_of_k`, `apply_of_k`, `block_per_card`; the heuristic's `k` uses).
The integer products that fold `amount × hits` handle fractions. With
`per` 1 everywhere today, every column is byte-identical.

## Fits with

| Neighbour | Must stay true | Test |
|---|---|---|
| Golden, rules version | byte-identical, unchanged | golden |
| Today's amounts (Body Slam, Heavy Blade, Perfected Strike, Whirlwind, Entrench, Limit Break, Second Wind, Fiend Fire) | resolve as now | `amounts.rs`, `quantity_amounts.rs` |
| Upgrades (Heavy Blade+, Perfected Strike+ edit `amount.k`) | as now | `quantity_amounts.rs`, upgrade tests |
| Files | every content file loads and writes back byte for byte | official-file round-trip tests |
| Net inputs | byte-identical; `series_check` PASS | product-layout pins, `series_check` |
| Bounds | sound with a `HealOf` | new `heal_of_lifts_the_bound` |
| Wording | every element worded | `wording.rs` |
| Search speed | `series_speed` at most 10% slower | job (step 4) |

## When in doubt

Prefer the game's arithmetic (Java's truncation) over tidier rounding, and
an unchanged amount over anything else.

## Scope

May change: `engine/src/effects.rs` (Amount, Quantity, the new effect), the
resolver in `state.rs`, the registry (amount parse and write, element
names), `upgrade.rs`, `bound.rs`, `heuristic.rs` (`k` reads),
`py/src/features.rs` (`k` reads, the new arms with no column),
`content/wording.json`, `scripts/explore.py` (wording), tests, docs,
facts.

Off limits: the codec (amounts are content, not state); `golden.txt`; any
existing net's input; card vectors' width; Hexaghost's Divider; configs,
yardsticks, controls; the gauntlet and run layer; saved packs and data on
disk.

## Decisions taken (owner, 2026-11-11; provisional)

- A fractional `k` goes in its own spec, built before potions.
- Fractions are written `"k": "a/b"`; whole numbers stay plain numbers.
- Game parity wins: truncation toward zero, as Java's `(int)`.
- Amounts resolve when their effect runs; intent-time amounts (Divider) are
  out and kept as an idea.
- No net column for the new quantity or heal now.

## Outside assumptions

- The game computes share-of-max-HP heals as `(int)(maxHealth * f)` with a
  float `f` (Blood Potion: `potency / 100.0f`). Read 2026-11-11 in a
  decompiled copy of the game (GitHub AxorusMT/sts): `BloodPotion.java`
  `(int)(maxHealth * (potency / 100.0F))`, `FairyPotion.java` the same
  with a minimum of 1, `RestOption.java` `(int)(maxHealth * 0.3F)`,
  `LizardTail.java` `maxHealth / 2`. The game's damage and block math uses
  libGDX `MathUtils.floor` instead (`AbstractCard.applyPowers`,
  `DamageInfo.applyPowers`); that path isn't this spec's. No game amount
  uses a negative fraction, so rounding one toward zero is our choice, not
  parity. Exact `trunc(max_hp × a /
  b)` equals the float result for the shares Act 1 uses (1/5; later 3/10,
  1/2) at every max HP 1-999. Checked by `float_parity` in step 3; a max HP
  where they differ is named (and the spec asks before choosing).

## Verification

Written first (step 1, passing on unchanged code): the existing pins
(golden, `amounts.rs`, `quantity_amounts.rs`, the product-layout pins,
official-file round trips) cover today's amounts.

Then:
- `fraction_parse`: `"k": "1/5"` loads as k 1, per 5; `"2/10"` as 1/5;
  `"-1/2"` as k -1, per 2; `"k": 0.5`, `"1/0"`, `"x"` are errors naming the
  entry; `"k": 3` as k 3, per 1; the writer gives `"1/5"` back and today's
  forms unchanged.
- `fraction_resolve`: `base 0, k 1/12` of Block 25 gives 2; `k -1/2` of 5
  gives -2 (toward zero); `times(3)` of 1/5 is 3/5.
- `fraction_upgrade`: an upgrade editing `amount.per` changes the bottom;
  the diff names it.
- `heal_of_max_hp`: `HealOf 1/5 of OwnMaxHp` heals 16 at 80 max HP (from
  40 HP) and 15 at 75; caps at max HP; nothing at 0 HP; fires
  `OwnerUnbloodied` crossing above half; a monster's reads its own max HP.
- `float_parity`: for max HP 1-999 and shares 1/5, 3/10, 1/2,
  `trunc(m × a / b) == (m as f32 × (a as f32 / b as f32)) as i32`.
- `heal_of_lifts_the_bound`: a held `HealOf` card: `can_heal()` true.
- Wording: every element worded; the explorer words "1/5 of your max HP".
- End to end: golden identical, `series_check` PASS, `series_speed` within
  10%.

## Don't guard

Amounts past `i16` after resolving; `per` beyond `i16`; a fraction on
`base`.

## Build steps

1. **Pins** on unchanged code (confirm the existing ones cover today's
   amounts; add a features pin over every official and Act 1 pack card if
   none covers them); decisions into `docs/decisions.md`; the Divider idea
   into the ideas list. Check: pass.
2. **The fraction:** `Amount.per`, parse (`"a/b"`, lowest terms, errors),
   write, `resolve` with truncation in 32 bits, `times`, the upgrade field,
   every `k` reader in features and the heuristic. Check: `fraction_parse`,
   `fraction_resolve`, `fraction_upgrade`, golden, pins byte-identical,
   `series_check` PASS.
3. **Max HP and the heal:** `Quantity::OwnMaxHp`, `Effect::HealOf`, scaled,
   bounds, upgrade names, features (no column), element names, wording, the
   explorer. Check: `heal_of_max_hp`, `float_parity`,
   `heal_of_lifts_the_bound`, wording, pins.
4. **Speed and docs:** `series_speed` job (old: this spec's commit; new:
   step 3's; ~12 min, long run), `docs/extending.md` (amounts), the research
   doc's Blood Potion row, facts. Check: `series_speed` within 10%.

## Build plan

4 steps, forks, Opus. No expected stop point; step 3 asks if `float_parity`
finds a max HP where the game's float differs.
