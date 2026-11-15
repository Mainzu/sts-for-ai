# Decisions

Design decisions and assumptions made while building, newest last.

## Step 1: engine core

- **The state holds no RNG.** `CombatState` is pure game information, so
  `Eq`/`Hash` compare only what the player can know, and afterstate
  deduplication works. Randomness comes from an `Rng` passed to `new`,
  `step`, `resolve_chance` and `advance`. The Python `Combat` wrapper (step
  4) will own one. The spec's "seeded RNG inside the state" is met by that
  wrapper.
- **Every pile is a multiset** (`Pile` = a count per `CardId`), not just the
  draw pile. Hand, discard and exhaust order don't matter for in-scope cards,
  and canonical piles make equal states compare equal.
- **Chance via a `Chance` trait.** Monster AI is ordinary code that calls
  `below(n)` / `chance(p)`. Sampling passes an `Rng`; `rng::enumerate` lists
  the exact distribution by replaying every path of calls. One AI function
  serves both, so listed and sampled odds can't drift apart. Draws use a
  dedicated multiset enumerator (hypergeometric), which stops early once
  there are more outcomes than the limit.
- **Events with one possible result don't pause.** Cultist's moves, Jaw
  Worm's first move, and a draw from a pile of one card kind resolve
  immediately. `pending` is set only when the result is really uncertain.
- **Order of a monster turn:** all monsters act, end-of-round ticks run, then
  each monster rolls its next move (one chance node per monster whose roll is
  uncertain), then the player's turn starts with a draw. The real game rolls
  each monster's move right after it acts. This is equivalent while move
  rolls don't depend on anything a later monster's action or the round's end
  changes, which holds for the Act 1 roster.
- **Cards mid-play can pause.** `Stage::PlayingCard { next }` stores the
  next effect index, so a draw inside a card (Shrug It Off) is a chance node
  and play resumes after it. The played card sits outside every pile until it
  finishes, as in the game. Monster moves must not pause (debug-asserted);
  spec'd Act 1 moves are deterministic once chosen.
- **Debuff timing:** Vulnerable, Weak and Frail lose a stack at the end of
  each round, except the round a monster applied them in (the game's
  `justApplied`). Ritual on a monster skips the round it's gained, so
  Cultist hits 6, 9, 12… The skip flag is set only when the power goes from
  0 to positive, matching how the game stacks powers.
- **Damage rounding:** Strength is added, then ×0.75 for Weak and ×1.5 for
  Vulnerable, rounded down once at the end (integer math: ×3/4, ×3/2).
- **Jaw Worm odds** use the game's branch constants (0..99 roll, then
  0.5625 / 0.357 / 0.416 re-rolls). Tests check the exact values and that
  they round to the wiki's 59/41, 56/44, 45/30/25 and 64/36 percentages.
- **Shrug It Off and Wound are in the card table already.** Shrug It Off is
  there to test mid-card chance; it is an in-scope card for step 2 anyway.
- **Burning Blood** heals 6 when the combat is won, capped at max HP.
- **Wiki source:** the fandom wiki now returns HTTP 402 to fetches, so values
  were checked against slaythespire.wiki.gg.
- **Power cards** don't exist yet. Step 2 must decide where a played Power
  goes (in the game it leaves combat and isn't exhausted, so it must not
  trigger exhaust effects). The fuzz's card-conservation invariant will need
  to account for that and for created cards (Wound).

## Step 2: full content

- **Wiki gaps filled from the game's AI rules (A0):** the wiki gives the
  odds but not the re-roll odds when a repeat limit blocks a move. Acid
  Slime (M/L) re-rolls 50/50 (Spit blocked → Tackle/Lick; Tackle blocked →
  Spit/Lick) and 40/60 (Lick blocked → Spit/Tackle). Acid Slime (S): Lick or
  Tackle at random first, then alternates (the wiki lists no rule). Louse
  first moves follow the normal roll. Card costs came from each card's
  wiki.gg page (the Ironclad list page has no costs).
- **Played Power cards leave combat** (no pile). `CombatState.created` and
  `removed` count cards added during combat and Powers played, so the fuzz
  checks `deck + created − removed == cards in piles`.
- **Perfected Strike** counts Strike-named cards in hand, draw and discard
  plus itself; the exhaust pile doesn't count (wiki: exhausting Strikes
  lowers its damage).
- **Curl Up** triggers on the first attack hit that makes the louse lose HP
  without killing it (blocked or lethal hits don't), once. Its block is
  queued after the card's own actions in the game, so it is held in
  `deferred_block` and lands when the card finishes: both Twin Strike hits
  connect before it.
- **Splits:** a slime's intent switches to Split as soon as an attack leaves
  it at or below half max HP (lethal hits don't). On its turn the splitter's
  slot takes its first child and the lowest empty slot takes the second
  (Slime Boss → Spike Slime (L) in its slot, then Acid Slime (L); each large
  → two mediums). Children get the splitter's current HP as max HP, don't act
  that turn, and roll their first move with the other monsters. At most 4
  slots are ever used.
- **Lagavulin** sleeps as three moves (Sleep, Sleep, then a Sleep that drops
  Metallicize and wakes it), so no hidden counter is needed. HP damage while
  asleep switches its intent to Stunned and removes Metallicize; damage
  fully absorbed by block doesn't wake it. Awake: Attack, Attack, Siphon
  Soul.
- **Sentries:** slot 1 (the middle one) starts with Beam, the others with Bolt.
- **Looter's Escape** removes it from combat (`Monster.escaped`); if it was
  the last monster the combat is won (the game ends the fight with rewards).
  Mug and Lunge steal no gold here.
- **Monster Metallicize** adds block after all monsters act, so the block
  holds through the player's turn. Flex's Strength loss happens at the end
  of the player's turn; Ethereal cards in hand are exhausted then too.
- **Artifact** blocks Vulnerable, Weak, Frail and negative Strength or
  Dexterity.
- **Encounters** follow the wiki's Act 1 list, limited to in-scope monsters:
  `exordium_thugs` picks its second monster from Cultist or Looter only
  (Slavers are out of scope); Gremlin Gang, Blue and Red Slaver are left out.
  Per-encounter random choices (louse colours, which slime, bite damage,
  Curl Up) are rolled at setup, not chance nodes. `Encounter::group()` says
  hallway, elite or boss.
- **Angry** (Mad Gremlin) isn't implemented: no in-scope monster has it.
- **Sword Boomerang** resolves hit by hit; each hit is a `RandomTarget`
  chance node while more than one enemy lives.

## Step 3: options, search, agents

- **Options merge by afterstate.** `options(limit)` applies each distinct
  action and merges actions whose resulting state (paused or not) is `Eq`:
  that state fixes the whole outcome distribution. An option is
  `Deterministic` (no event before the next decision), `Chance` (every event
  on the way listed, ≤ `limit` outcomes in total, each at a decision or
  over) or `Divergent` (some event too large: the state paused at the first
  event). EndTurn is classified by the same rule.
- **Search builds, then scores, then backs up.** The tree is built first,
  every leaf goes to the evaluator in one `evaluate(&[CombatState])` call
  (the batching step 5 needs), then values back up: max at decisions,
  probability-weighted mean at chance nodes. Finished combats score exactly
  (`score()`), never through the evaluator. Equal states share a node
  (transposition cache keyed by state and turns left), so root options
  match `options()` one-to-one.
- **Search settings** (`SearchConfig`): `limit` 16, `sample_k` 0, `turns` 1,
  `max_nodes` 50,000 (past it, states become leaves), `seed` for sampling.
  With `sample_k > 0`, large events are sampled k times and searched, and
  EndTurn is searched into while `turns` > 1. With `sample_k` 0, `turns`
  has no effect (EndTurn is always a leaf).
- **Heuristic evaluator** (`heuristic.rs`) reads cards and moves only
  through effect primitives (card type only for Enrage). It estimates deck
  damage/block per turn, kills monsters in the order that minimises damage
  taken (Smith's rule: least effective HP per damage first), counts slime
  splits in effective HP, and turns "damage to come / HP" into a win
  probability that never flattens to 0 (so the search still prefers better
  lines when far behind). A monster's damage per round is averaged over its
  next 4 moves: averaging only the next move made Slime Boss look like 0 or
  35 per round, and fixing that took search from 20% to 38% boss wins.
- **Greedy** simulates each card on a copy (random parts sampled with a
  fixed seed): kill if possible, else block when intents exceed block,
  else most damage per energy, else any card that costs no HP.
- **Runner:** `group_specs(group, n, extra, seed)` gives the eval specs
  (encounters of the group in turn; odd-numbered specs get the starter plus
  `extra` random non-status cards). The combat's random events use the
  spec's seed and the agent gets its own RNG, so every agent meets the same
  combats. `play_many` runs on `std::thread::scope` threads (no rayon).
- **Starter deck vs Slime Boss is unwinnable for every agent here** (0% for
  greedy and search, ~105 boss HP left). Boss gains come from the
  starter + 5 decks (search 76% vs greedy 29% on those).

## Step 4: Python bindings, features, replay

- **Build:** `py/` is a PyO3 0.30 + numpy 0.30 crate (`sts-py`, lib name
  `sts`) built with maturin 1.15 into the project venv `.venv` (Python
  3.13); nothing goes into the global Python. The workspace's
  `default-members` is `engine`, so `cargo test` at the root stays the
  engine suite; the module is tested from Python (`py/tests/test_sts.py`).
  `pyo3/extension-module` is enabled by maturin only (pyproject), not in
  Cargo.toml.
- **`Combat` holds the RNG** (the spec's seeded combat): `Combat(deck,
  encounter, seed)` uses `Rng::new(seed)` exactly as the runner does, so a
  `Combat` and `run()` with the same spec see the same combat. The engine
  state stays RNG-free.
- **Option states don't replay the real future:** states returned by
  `options()` get an RNG derived from (not equal to) the combat's, so
  stepping them can't peek. `clone()` is the exact copy, RNG included.
- **Actions are a small `Action` class** (card name + target slot, or
  EndTurn), hashable and comparable; `Action("Bash", 0)`, `Action()` for
  EndTurn.
- **Feature batch format** (for one evaluator call over many states):
  `player` [B,P], `monsters` [B,5,M], and cards as rows over the whole
  batch, `cards` [N,C] with `card_count`, `card_pile` (index into
  `sts.PILES` = hand, draw, discard, exhaust, playing) and `card_state`
  (index into B). One row per distinct card per pile, with its count, so
  Deep Sets pooling is `index_add` of `row_embedding × count`. No padding.
- **Feature contents:** raw values (no scaling; step 5 normalises). Monster
  slots: alive, HP, max HP, block, can split, escaped, actual intent damage
  (Strength/Weak/Vulnerable applied), powers, intent effect primitives.
  Player: HP, max HP, block, energy, turn, pile sizes, awaiting action,
  won/lost, pending chance event, powers. Cards (`effects`): cost, type
  one-hot, flags, effect primitives (damage single/all/random with hits,
  Body Slam / Heavy Blade / Perfected Strike primitives, block, draw,
  energy, HP loss, added cards by pile with the added card's damage/block/
  unplayable, applied powers by target). Monster identity is not encoded in
  either mode; only cards differ between `effects` and `ids`.
- **Unknown powers (Amendment 1):** every power block (player, monsters,
  and the applied-power dims of cards and intents) is one dim per kind plus
  `unknown`; powers outside `known_powers` add their amount to `unknown`.
  `known_cards` works the same for `ids` (outside → unknown slot) and is
  ignored by `effects`. Names are exact (`"Strike"` doesn't include
  `"Strike+"`).
- **Python evaluators** get one batch dict per search and return one score
  per state (anything `numpy.asarray` turns into floats). An exception or a
  wrong length is raised after the search. Through `run()`, the GIL is
  released and each thread re-attaches to call the evaluator.
- **Engine additions:** `agent::intent_damage(s, slot)` (per-monster part
  of `incoming_damage`), `runner::group_specs_from(.., pool)` (extra cards
  from a given pool, for held-out tests).

## Step 5: value nets, generalisation test

- **Training states:** per self-play game, up to 6 random decision states
  plus, when the kept action's option is divergent (EndTurn, big draws),
  its paused state, because those are what search asks the evaluator to
  score. Finished states are never included (search scores them exactly).
  Every state's target is its game's final score (won × (2 − HP lost / 100),
  HP lost after Burning Blood; Amendment 3).
- **Data:** Search + heuristic, `limit` 16. Train 30,000 games (10,000 per
  group), validation / test (a) / test (b) 3,000 games each, each set with
  its own seeds, so the split is by game. Decks: starter + 5 random cards
  (training pool for train/val/(a); for (b), 5 from the whole pool with at
  least 2 held-out cards, by rejection sampling).
- **Held out:** Twin Strike, Iron Wave, Thunderclap, Pommel Strike,
  Uppercut, base and +. The ids net's `known_cards` is every card name
  except those 10, so held-out cards land in its unknown slot, which it
  never sees active in training (no handicap beyond that).
- **Net:** Deep Sets, shared φ (2×64) per card row × count, summed per
  (state, pile); shared ρ (2×64) per live monster slot, sum + max pooled;
  player MLP (64); head 256 → 128 → 1, output 2·sigmoid. Dead monster slots
  are masked out. Inputs normalised per dimension with train-set mean/std
  (live monster slots only; constant dims get std 1).
- **Training:** Adam 1e-3, weight decay 1e-5, batch 512, ≤ 20 epochs, early
  stop on validation MSE (patience 3), best weights kept. Same seed and
  budget for both nets. Test sets are only used for the final report.
- **Storage:** `data/<set>_<effects|ids>.npz` and
  `models/value_<effects|ids>.pt` (both gitignored, cached; `--retrain`).
  Card rows are stored as float16 (small integers, exact).
- **Inference:** `stsnet.Evaluator(model, norm)` is the search callable;
  during the win-rate runs torch uses 1 intra-op thread per call because 16
  runner threads call it.

## Step 6: the Silent transfer test (Amendment 2)

- **Silent cards are new card kinds appended after every Ironclad one**, so
  the Ironclad card ids (0..53) keep their numbers. Silent's Strike and
  Defend are named `Silent Strike` / `Silent Defend` (card names must be
  unique); their effects equal Ironclad's, and `Silent Strike` counts as a
  Strike. Shiv (4 / 6 damage, 0 cost, exhaust) is a colorless card that is
  never picked for decks.
- **Card classes:** `CardDef.class` is Ironclad, Silent or Colorless.
  `deck_cards()` is now "Ironclad, non-status", the same 48 cards as
  before; `class_cards(class)` gives the Silent pool (15 cards × 2).
- **Characters:** `Character` (Ironclad / Silent) gives starting HP (80 /
  70), the starter deck, the win heal (Burning Blood 6 / none) and extra
  first-turn draw (0 / Ring of the Snake 2: one 7-card draw on turn 1).
  `CombatState` stores it; `CombatState::new` stays the Ironclad
  constructor, `new_as` takes a character. `GameSpec` has a `character`.
- **Silent starter:** 5 Silent Strike, 6 Silent Defend, Neutralize (Survivor
  needs a discard choice; a Defend replaces it, per Amendment 2).
- **New primitives:** `AddCard { pile: Hand }` (Blade Dance, Cloak and
  Dagger; copies past the 10-card hand limit go to the discard pile, as the
  wiki says for Blade Dance) and `RandomApply { power, amount, hits }`
  (Bouncing Flask). `RandomApply` reuses the `RandomTarget` chance event:
  `random_hit` applies the power instead of damage when the card in play is
  resolving a `RandomApply`. AddCard is an existing primitive; the hand is a
  new destination for it, which the base feature layout has no dimension for
  (see below). That is the one place a tier A card goes beyond what Ironclad
  training saw; it stays in tier A, since the card's content (the Shivs'
  damage) still encodes, and the Shivs themselves, once in hand, are plain
  cards built from known primitives.
- **Poison:** a new power. At the start of the monsters' turn (after their
  block is cleared, before any acts) each living monster loses HP equal to
  its Poison, ignoring block, then Poison drops by 1. It runs the same
  reactions as attack HP loss except Curl Up (attacks only): it wakes
  Lagavulin (stunned), a slime pushed to half HP splits that turn, and a
  Fungi Beast killed by it releases Spore Cloud. Artifact blocks it (it is a
  debuff). A monster killed by Poison doesn't act.
- **Heuristic:** Poison still to tick (p + (p−1) + … + 1) comes off a
  monster's effective HP; a card's Poison counts as 2 damage per stack in
  the deck's output. Win heal is per character. Ironclad states score
  exactly as before.
- **Feature layouts:** `Features(layout="base" | "full")`, default "base".
  The base layout is exactly the step 5 encoding (54 card ids, 12 powers, 23
  effect scalars): later card ids go to the ids `unknown` slot, later powers
  (Poison) to `unknown`, and later effect scalars (`add_hand`) are dropped.
  "full" gives everything its own dimension. `RandomApply` encodes in the
  `apply_opponent_<power>` block with amount × hits, in either layout.
  `py/tests/data/golden_ironclad.npz` (96 Ironclad states, both modes,
  captured from the step 5 build before any step 6 change) checks the base
  layout byte for byte. Model meta gains `layout`; `stsnet.features_for`
  treats models without it as "base".
- **Python API:** `Combat(..., hp=None, max_hp=None, character="ironclad")`
  (HP defaults to the character's), `make_specs(..., character=)` (default
  pool: the character's cards), `run(..., hp=None, character=)`,
  `sts.starter_deck(character)`, `sts.class_card_names(character)`,
  `sts.character_names()`, `Combat.character`.
- **Transfer test decks:** tier A = Silent starter + 5 cards from Neutralize,
  Sucker Punch, Leg Sweep, Quick Slash, Backflip, Deflect, Slice, Dagger
  Spray, Blade Dance, Cloak and Dagger (base and +). Tier B = starter + 5
  from tiers A and B with at least 2 Poison cards (Deadly Poison, Poisoned
  Stab, Bouncing Flask, base and +), by rejection sampling. Labels: Search
  + heuristic games, 1,000 per group per tier (seeds 20 / 21), same state
  sampling as step 5. The constant baseline predicts the Ironclad training
  mean, as in check 6. The nets are loaded unchanged; `transfer.py` never
  trains.

## Triggers and conditions (SPEC.md Amendment 4)

- Hook powers are static Rust tables of (trigger, condition, effects) keyed by power kind; the state keeps (power, stacks).
- Nets read cards and hook powers as sets of rows (nested Deep Sets), not flat trigger × effect dimensions.
- Strength, Dexterity, Vulnerable, Weak, Frail and Artifact stay built-in modifiers with a dimension each.
- The game stays step-for-step identical (golden trajectories); old models and the base/full layouts are dropped and the nets retrained.
- Check 9 gates on the value of granting a held-out power, measured against a reference net trained with it known.
- Hook timing (step 2), mapped so the golden trajectories hold: the player's turn end fires first in `end_turn` (LoseStrength, before the hand is discarded); every living monster's turn start fires in slot order after monster block resets and before any monster acts (Poison, as in the game's pre-turn pass); every living monster's turn end fires in slot order after all monsters have acted, before the end-of-round debuff countdown (Metallicize, and Ritual, which moved here from the end-of-round tick; the two only touch their owner, so the order is unchanged). The player's turn start fires after block reset and energy, before the turn's draw (moved after the draw in step 5).
- A power marked `just_applied` fires no hooks until the end-of-round tick clears the mark (Ritual skips the turn a monster gains it). `just_applied` widened to `u32` for the new powers.
- A hook's effect amounts use the stacks the power had when the hook fired. `RemoveSelf` and `ReduceSelf(n)` act on that power. Poison is `ReduceSelf(1), LoseHp(1)`: the stack drops first so that a lethal tick, which ends combat at once, leaves the dying monster one stack lower as before (the other order changes 288 golden games). `LoseHp` on a monster now runs its HP-loss reactions (split, Lagavulin waking, Spore Cloud), as the Poison tick did.
- Combat ends at once after any hook effect that kills the player or the last monster, as with card effects.
- Event hooks (step 3): `CardPlayed` fires when the card leaves the hand, after its energy is paid and before its effects resolve (as Gremlin Nob's Enrage and the game's `onUseCard` top-of-queue actions): the player's `by Owner` hooks first, then each living monster's `by Opponent` hooks in slot order (step 5 moved the player's `by Owner` hooks to after the card). Its conditions see the played card and its chosen target. Enrage's Strength now goes through `apply_power` (positive Strength is never a debuff, so nothing changes).
- `OwnerLostHp` fires only when the owner survives the loss; a monster reaching 0 HP fires `OwnerDied` instead (Spore Cloud), as the game's Curl Up checks for non-lethal damage. The loss's source: `Attack` for unblocked attack damage, `Card` for HP loss the owner causes itself (its cards' and its own powers' `LoseHp`: Bloodletting, Hemokinesis, later Combust, which in the game also triggers Rupture), `Any` for the rest (Poison, whose loss comes from the poisoner). A hook filtering on `Any` sees every source. A monster's own move logic (Lagavulin waking, slimes splitting) runs after its hooks and stays hand-coded.
- A monster's hook `Block` while a card is in play goes to `deferred_block` and lands when the card finishes (Curl Up: the game queues it behind the card's own actions).
- Conditional card effects (step 4): a card's `effects` are its on-play row (CardPlayed by Owner, Always); its `rows` are conditional rows run after it, in order. A row's condition is checked when its first effect is reached (with the played card and its chosen target) and a failed row is skipped whole; `Stage::PlayingCard.next` counts through every row's effects, so a card still resumes after a chance event. A card is targeted if any row's effect targets an opponent or a row's condition looks at the target (Spot Weakness).
- `TargetIntendsAttack`: the target's current intent has a `Damage` or `RolledAttack` effect. `TargetHas(p)`: the target has `p` > 0. Both read the target even if the card's earlier effects just killed it (its intent and powers stay), as the game checks them at play time.
- `cards_played_this_turn` counts plays, the card in play included; it goes up when the card leaves the hand (before `CardPlayed` hooks) and resets at the start of the player's turn. `CardsPlayedThisTurnBelow(n)` holds when fewer than `n` cards were played before the card in play: FTL's card text "If you have played less than 3 (4) cards this turn", which the game checks as `cardsPlayedThisTurn.size() <= 3` with FTL in the list. (The wiki's description says "a maximum of 3 before this one"; the card text wins.)
- `PlainDamage { amount, target }` is non-attack damage (Combust, the game's THORNS type): Strength, Weak and Vulnerable don't apply, block absorbs it, and the HP lost counts as source `Any` (so Curl Up ignores it).
- Held-out cards carry a `held_out` flag: `class_cards()` and `deck_cards()` skip them, `held_out_cards()` lists them (check 9), and the Ironclad fuzz pool adds them. Go for the Eyes and FTL (Defect cards) are held out with class Ironclad, so a check-9 deck can hold them; Spot Weakness and Dropkick join the Ironclad training pool.
- Power cards (step 5): the player's turn start fires after the turn's draw resolves (new transient `Stage::TurnStarted`), the game's `atStartOfTurnPostDraw` timing for Brutality and Demon Form; a hook `Draw` there is a second draw event. No in-scope power uses the game's pre-draw player timing (player Poison would). Golden unchanged.
- Combust is two powers, `Combust` (HP loss: one per Combust played) and `CombustDamage` (the sum of the plays' damage), so Combust + Combust+ loses 2 HP and deals 12 as in the game's CombustPower. The loss fires before the damage (power-kind order, the game's order).
- A player's hook `Block` is raw block (the game's `GainBlockAction`): Dexterity and Frail don't apply (Metallicize, Rage).
- The player's `CardPlayed by Owner` hooks (Rage) run when the card has resolved, not when it leaves the hand. The game queues Rage's block ahead of the card's actions but has already computed the card's damage, so Body Slam doesn't count that block; running after the card gives the same result without a new rule.
- HP the player loses from the card in play (`Card` source) is counted in `card_hp_losses`, and the player's `OwnerLostHp` hooks for it (Rupture) run when the card has resolved, before its `CardPlayed by Owner` hooks: the game computes a card's damage at play time, so Hemokinesis deals 15, not 16, with Rupture (wiki). HP lost from Combust and Brutality fires Rupture at once. The count is cleared if the card ends the combat.
- Innate (Brutality+): at the start of turn 1 the innate cards move from the draw pile to the hand and the opening draw is that many cards smaller (never below 0); the draw stays one chance event over the rest.
- The heuristic reads hook powers through their hooks (`hook_rates`): turn-hook block, one-time block on HP loss, Strength per turn / per opponent Skill / per self-inflicted loss, one-shot Strength changes, countdown loss (Poison), self HP loss, non-attack damage to all and extra draws. Its estimates for states with only the earlier powers are unchanged (12,007 states compared bit-for-bit); for the player's new powers it adds turn block to block per turn, damage to all to damage per turn, extra draws to cards per turn, self HP loss × rounds to damage taken, and growing Strength as two turns' worth.
- Until the row features (step 6), the per-card feature vector and the heuristic count a card's conditional rows as if their conditions held. Non-attack damage gets a new effect scalar, `damage_plain`, after `add_hand` (outside `Layout::BASE`).
- Row features (step 6): a row is a trigger one-hot, a condition one-hot (both with `unknown`), a condition parameter (`CardsPlayedThisTurnBelow`'s n; categorical parameters are part of the condition name, `CardType(Attack)`, `TargetHas(Vulnerable)`), a grant one-hot (`own`, `me`, `opponent`) and the effect vector. A card's rows are its effect rows (trigger `CardPlayed(Owner)`, the row's condition; rows with no effects are skipped), then the hooks of each hook power it applies scaled by the amount (× hits for random applies), marked `me` (applied to its user) or `opponent`: so a card granting a power the net never saw (Demon Form) shows that power's hooks (turn start → +Strength) instead of an opaque id. An entity's rows are its hook powers' hooks × stacks (`own`); a monster's also include the hooks of hook powers its intent applies (Cultist's Incantation grants Ritual, `me`).
- In effects mode hook powers have no power dimension and no apply dimension anywhere (cards, intents); they are rows only. The power block is the modifiers (Strength, Dexterity, Vulnerable, Weak, Frail, Artifact) plus `unknown`. In ids mode every power, hook powers included, is a dimension (amount = stacks) plus `unknown`, and there are no rows.
- The per-card vector keeps its meaning: card properties plus every effect summed, conditional rows included (the rows say when they apply). New effect scalars `remove_self` and `reduce_self` (hook rows only).
- Vocabularies replace the `base`/`full` layouts: `known_cards`, `known_powers`, `known_triggers`, `known_conditions`, `known_effects` (names, in dimension order; `None` = all in engine order), so dims depend only on the lists and a saved net encodes newer content (unknown names → `unknown`, unknown effect scalars dropped). `Features.vocab` returns the lists in use for a net's meta. `layout=` stays as an optional argument and only accepts `"full"`.
- Nets on rows (step 7): nested Deep Sets. A shared ψ (row → 32 → 32) embeds each hook row; the sums go into the owning card's φ input (card vector ++ pooled rows) and into the player's or a monster's input (entity vector ++ pooled rows). Piles, monsters, player and head are as before (~192k parameters). Ids nets get no rows, so their pooled parts are zero.
- Meta vocabularies: the effects net saves the full trigger, condition and effect vocabularies (they are primitives; entries only held-out content uses, such as `TargetHas(DemonForm)`, simply never get a training signal). The ids net saves `known_cards` = the Ironclad training pool + starter + statuses (no check 6 or check 9 held-out card, no Silent card) and `known_powers` = every power but Poison (Silent only), DemonForm and Rage (only check 9's held-out cards grant them; Metallicize stays known through Lagavulin). Meta also records `format` ("rows"), and cached self-play data is keyed by it (`data/<set>_<mode>_rows.npz`).
- Check 9 (step 8): the reference net is the effects net trained with check 6's seeds, sizes and budget on starter + 5 cards from the training pool plus check 9's held-out cards (check 6's held-out cards stay out); its data is cached as `data/train_ref_*`/`val_ref_*`. Test decks draw from the same pool with at least 2 check-9 held-out cards (seed 9, 300 per group); every recorded decision of search + heuristic play where one is playable counts. A card's gain is the best option that plays it (any target; a merged option counts if any of its actions plays it) minus the best option that doesn't, per card name; base and upgraded are pooled under the base name. The gate pools all (decision, card) pairs of Metallicize, Demon Form, Rage and Go for the Eyes. The win table runs on the same specs.
- Check 9 result (2026-10-24, owner's call: recorded as failing): gain MAD vs reference, effects 0.0210 vs ids 0.0257, 18.3% lower against a 20% bar: FAIL. Per card: Demon Form 34.3%, Metallicize 13.0%, Rage 9.5%, Go for the Eyes 5.3% (FTL 9.4%, reported). Diagnosis: two separately trained nets already disagree by ~0.026 (effects) / ~0.030 (ids) in gain on training-pool cards, more than the held-out errors compared, so the pooled gate is dominated by net-to-net noise; Rage and Go for the Eyes (76% of pairs) have small gains that show in the afterstate. A better gate is a later amendment.

## Learned play framing (provisional, research docs/research/learned-play-and-generalisation.md)

- Next training work uses expert iteration lite: value targets are each option's search value mixed with the final outcome; the net predicts a correction on top of the heuristic, with a ranking term over each decision's options; 3–5 rounds of play-and-retrain; gated on play (search + net beats search + heuristic at equal node budget), regret per decision and sibling ranking accuracy.
- First step: measure deeper search (`sample_k` > 0, two turns) with the heuristic, to size the teacher.

## Evaluation bench and learned play (provisional, specs docs/specs/eval-bench.md and learned-play.md)

- Prediction, decision quality (regret and ranking against a cached deeper reference search) and win rate are always reported side by side, split training / held-out; differences count only when 95% intervals don't overlap.
- Bench fights are calibrated to ~50% win rate for search + heuristic.
- Learned-play changes are switches measured by a ladder + leave-one-out sweep, one seed per config overnight, top configs confirmed with 3 seeds and an id-feature control.
- The evaluated agent always uses one-turn search; depth only changes the teacher.

## Evaluation bench as built (2026-10-24)

- Families and halves: each family is starter + 3 role cards + 2 fillers; only role cards differ between train and held-out. Families are Ironclad only; Silent tiers A/B appear as standard-set halves. Standard held-out decks need ≥ 2 check-6 or check-9 held-out cards.
- Calibration: each (family, half, encounter) is calibrated separately (150 cells), bisection on 400 games then 1,600 at the two HPs around 50%; a cell is kept only inside 42–58%. 34 excluded (won at 1 HP, lost at 80 HP, or a jump across the band between adjacent HPs). The fresh-seed check plays 1,600 games per cell (400 was too noisy over 116 cells) on seeds from 50,000,000, disjoint from calibration's 5,000,000+.
- Reference search is capped at the engine's 50,000 nodes (the cap isn't settable from Python and `py/src` was off limits); ~9% of decisions hit it, are flagged `capped`, and an uncapped subset is reported.
- The random-evaluator "50% ± 5" test applies random values to options directly. Search through a random leaf evaluator ranks 0.70–0.74 of contested pairs, the floor for evaluators run through search.
- The "multi-hit into Curl Up" probe was replaced by a second AoE probe: the engine applies Curl Up's block after the card resolves, as the game does, so it doesn't blunt a multi-hit card.
- The aliasing audit finds no two saved decisions with equal features (they come from different games); results include a `shared` count so a 0 reads correctly.
- Baseline (`docs/research/bench-baseline.md`): neither net beats the heuristic on tight fights; effects and ids are indistinguishable there; held-out decisions are easier than train's for every evaluator, so compare gaps between evaluators.

## Learned play as built (provisional)

- Deeper teacher (step 1, switch 5): search + heuristic with 2 turns, sample_k 4, limit 16, the engine's node cap. It has the lowest contested regret and the highest ranking of the sizes measured (train regret 0.023 vs 0.056 one-turn, intervals apart), at about the cost of sample_k 2 and ~100× one-turn search. It doesn't win more tight fights than one-turn search, and the reference it's scored against is also a two-turn sampling search, so its gain is an upper bound (table in `docs/research/learned-play-results.md`). Alternatives: sample_k 2 (similar cost, worse held-out), sample_k 1 (cheaper, no held-out gain and fewer wins). At 2–3 games/s (reproduced after the bench fixes in `2cc01ca`) its data can't be regenerated per config: it is generated once per teacher setting (rounds = 1, as the spec allows), and the sweep (step 7) must size deeper-teacher data, and switch 4 + 5 rounds, to the 40-minute budget.
- Search-value targets (step 3, switch 1): `sts.run(record=True, values=True)` returns each decision's root options and values as the agent's search computed them (the engine's `Agent::last_options`, recorded into `CombatResult::option_values`); registry datasets always store them. With the switch on, the same decisions as switch off are sampled (6 per game); each is labelled lambda * final score + (1 - lambda) * its best option's value, and each root option's outcome states (one for deterministic and divergent options, every listed outcome for chance options; finished combats skipped) are examples labelled lambda * the game's final score + (1 - lambda) * that option's value. Afterstates of options not taken still mix in the played game's score, as the spec's single formula says. Examples rise from ~7 to ~34 per game, so training time per epoch rises ~5x. The heuristic's one-turn search values are well below final scores on full-HP games (first decision: mean 0.98 vs 1.71, MSE 1.0, 300 games), so with the heuristic teacher, switch 1 pulls labels down; not corrected here (switch 2 is the heuristic-correction head). All switches off, `learn.py --config configs/baseline.json` reproduces today's effects net: val MSE 0.0543 vs 0.05432 for `models/value_effects.pt` (run `2026-10-24-baseline-35f3c47`; 30,000 + 3,000 games in 212 s, 8 epochs at ~17 s).
- Heuristic correction (step 4, switch 2): the heuristic's static estimate (`heuristic::estimate`, search's leaf value; already on the 0-2 score scale, the exact score when the combat is over) is added to a batch dict as `heuristic` [B] only on request: `Features.encode(..., heuristic=True)` (registry caches, the bench's static values) and in search batches for a callable whose `wants_heuristic` is true (`stsnet.Evaluator` of a correction net). Default batches are byte-identical (`test_golden_features_unchanged`); it isn't a feature. The correction net outputs heuristic + an unbounded correction from the same head (no sigmoid, no clamp), whose last layer is zero-initialised, so an untrained net matches search + heuristic exactly (option values and picks). The correction learns the gap between the heuristic and the labels (the heuristic's one-turn values run ~0.7 below final scores on full-HP games). Saved models record `correction`; older ones load as plain nets. Registry caches gained a version tag (`v2`) since they now store the estimate.
- Ranking loss (step 4, switch 3): mean hinge max(0, v_worse - v_better) over each decision's option pairs whose search values differ, where an option's predicted value is its afterstates' predictions weighted by outcome probability plus the probability-weighted exact score of its finished outcomes; 0 when every pair is in order. Pairs are ordered by the options' search values (the same order as switch 1's mixed labels, since the game's score is shared). Weight default 1.0; the decision state itself isn't in any pair. Training batches are cut only between decisions (~512 examples). With switch 1 off, the afterstates are still sampled (labels at lambda 1, i.e. every label is the final score) so the leave-one-out config "all on but switch 1" has pairs to rank; that config therefore also trains on afterstates labelled with the final score.
- No-death HP-loss target (step 5, switch 6). Engine: `CombatState::no_death` (off by default; `GameSpec::no_death`, `sts.run(no_death=)`, `sts.Combat(no_death=)`) lets the player's HP go below 0: damage and HP loss aren't floored at 0 for the player, the player is never dead, so `OwnerLostHp` hooks (Rupture) keep firing below 0, and multi-hit attacks keep hitting. The combat ends on a win, with **no end-of-combat heal** (so `hp_end` is the HP left and the formula applies healing itself), or as a loss when turn 50 ends (`NO_DEATH_TURN_LIMIT`, checked at the next turn start). The heuristic's damage estimate (`heuristic::hp_loss_estimate`, the `taken` its score is built from; 0 when over) and the formula's inputs (`hp`, `start_hp`, `max_hp`, `win_heal`) join `heuristic` in batches encoded with `heuristic=True` and in search batches for `wants_heuristic` evaluators. Labels: HP lost from the state's HP to the game's final HP, capped at 150; the turn limit's fixed penalty is the cap (150). With switch 1, a search value v (a 0-2 score) converts to HP lost as hp - start_hp + (2 - v) * 100 + heal, capped at 150 (the HP lost a won game with that score implies; exact when the heal isn't capped by max HP), and labels mix lambda * HP label + (1 - lambda) * that. Net: 9 outputs (10th-90th percentiles), times 50 so they start near the labels' range, pinball loss; validation reports the quantile loss (not comparable with MSE runs); outputs aren't forced to be ordered. External formula: each quantile has mass 1/9; a quantile wins when it is below the current HP; its end HP min(hp - q + heal, max HP); score = mean over quantiles of win * (2 - max(start - end, 0) / 100), which equals P(win) * (2 - expected HP lost when winning / 100). With switch 2 the quantiles are `heuristic_hp_loss` + the correction (zero-initialised: an untrained net predicts a point spread at the heuristic's estimate). With switch 3 the ranking term orders options by the formula's score with the win step smoothed to a sigmoid of width 2 HP (the exact step has no gradient); a finished no-death outcome's exact part is scored as real play would (0 at 0 HP or below, else healed). Self-play for switch 6 is its own dataset (`no_death` in its generating config and in each game record, so replays run in no-death mode).
- Self-play rounds (step 6, switch 4) and the deeper teacher (switch 5). Exploration is an engine option (an exception to the spec's engine scope, kept at the owner's call, 2026-10-24): `SearchAgent::explore` (`sts.run(explore=)`, default 0) picks the option by softmax over the root option values at that temperature, drawing from the agent RNG only when > 0, so default play and the golden trajectories are unchanged (`agent::softmax_pick`, first best at temperature 0). Round 1 trains on the teacher's data (reused through the registry); round k > 1 self-plays fresh spec seeds (train_seed + 100 * (k - 1)) with search + round k-1's net at temperature 0.05, its dataset recording the parent run id and the temperature, and trains a fresh net (same seed and architecture) on round k's games plus round k-1's (`Dataset.concat`; decision ids kept distinct). The validation set is the teacher's, fixed across rounds, so val MSE compares rounds. Monotone check: on the bench's tight fights (every `every`-th spec; default all 1,160), the round's net with the agents' one-turn search against the search that generated its data, without exploration (round 1: search + heuristic with the data search; round k: round k-1's net with the data search); ok when, on both halves, the net's 95% win interval is not wholly below the generator's. It is written to each round's `round.json` and the log; it doesn't stop the loop. The full bench per round runs only with `--bench`. Switch 5 swaps the data search (train and validation sets) for 2 turns, sample_k 4, limit 16. Cost at full size (30,000 training games; measured 2026-10-24 on the shared dev machine): heuristic one-turn ~1,000 games/s, net one-turn ~17 games/s (~30 min per later round's self-play, before training on twice the data), heuristic deeper ~1.3 games/s (~6.6 h, once per teacher), net deeper ~0.3 games/s (~30 h per round): the sweep (step 7) must size data per round, and switch 4 + 5 together only fit with far smaller rounds.
- Sweep (step 7, `scripts/sweep.py`): 12 configs, the ladder then leave-one-out from all on (all on minus 4 is the ladder's sixth rung, so 7 + 5 = 12). Sizing is projected from measured rates (games/s, all threads: heuristic one turn 1000, deeper teacher 1.3, net one turn 17, net with the deeper search 0.3; no-death self-play (switch 6) 1.5x slower, measured with the heuristic at both depths (games run ~2x the turns); tight fights 400 / 1.3 / 17 / 0.3; training ~1.7 ms per example, 7 examples per game, 34 with afterstates (switch 1 or 3); bench 4 min), measured on the shared dev machine. Rule: round-1 data from a net-independent teacher that would take over 40 min at full size (only the deeper teacher) is generated once per setting (with and without switch 6) at the largest size whose train + validation generation fits 40 min (945 games per group, 630 with switch 6), shared by every config using it and counted once in the night's total, not in a config's budget; everything else (cheap teacher data, training, later rounds' self-play and training, the monotone checks and the bench) counts in the config, which gets the largest games per group (≤ today's 10,000) fitting 40 min; switch 4's later rounds use the same size, except over the shared deeper-teacher data, where they get what fits (76 per group, 54 with switch 6); the monotone check thins tight fights so each run fits 2 min (every 33rd with the deeper search); validation sets are a tenth of training. Projection at commit time: 470 min including 80 min of shared teacher data. A 60-min teacher budget projected 8.6 h and 45 min 8.0 h (before the no-death factor; over the 8 h night), so 40 min it is. The projection is uncertain: rates vary ~2x with other load on the dev machine (the deeper teacher measured 1.3 and 0.67 games/s on different runs), and in the tiny dry run, rounds 2-3 of no-death configs with the deeper search ran at ~0.02-0.06 games/s (nets trained on 6 games lose and play to turn 50; better nets should be faster, unmeasured). Data sizes therefore differ between configs (10,000 / 1,386 / 945 / 630 per group), against the spec's "data size per round fixed across configs": a uniform size would be set by the all-on config (76 per group) and leave every config near-empty. The tiny dry run (`--tiny`, all 12 configs at 2 games per group, quick bench) took 40 min end to end. Only the last round of switch-4 configs is benched (the earlier rounds keep their `round.json`).
- Sweep size controls (owner's call, 2026-10-24): because switch 5 forces ~15x smaller data, the sweep adds `ctrl-1236` (1+2+3+6 at ladder+12365's 630 games per group) and `ctrl-all-5` (all on minus 5 at ladder+123654's 630 / 54 per group), so switch 5's effect is read against the same data size. Projection: 14 configs, 488 min (8.1 h), over the 8 h budget, so the sweep starts only with `--force`. The monotone check no longer measures the generator after the last round (review fix; it was ~2 min per deeper-teacher rounds config and not in the projection).

## Learned play Amendment 1 as built (provisional)

- Ground-truth targets (A1). Self-play rounds are part of every config (`"rounds"` at the top level of a config, defaults n 3, temperature 0.05, every 1; the `rounds` switch 4 is gone). Rounds are numbered 0..N: round 0 plays search + heuristic with the same seeds and settings as the old teacher data (so those datasets are reused), and its labels are the games' real outcomes only, with no afterstates; with switch 3 its examples carry inert ranking fields (each its own decision, option -1) so batches keep working, and the ranking term is 0 on them. Round k >= 1 plays seeds `train_seed + 100 k` with search + round k-1's net (exploration temperature 0.05) and trains a fresh net on its games plus round k-1's (window of 2: round 0's drop out from round 2). Switch 1 mixes the real outcome with the recorded search values of round k-1's net (the net that played those games), and switch 3 ranks by them; both act only from round 1. Validation is always the heuristic val set labelled with real outcomes (val MSE against ground truth, comparable across rounds and configs). Each example stores its real outcome label (`Dataset.outcome`), and `round.json` records `label_scale` per training dataset (|mean label - mean outcome|), warned over 0.1 (score) or 10 HP (switch 6); round 0's is exactly 0. The monotone check measures each round's net (rounds 1..N, one-turn agent search, tight fights thinned by `every`) and from round 2 compares it with the previous round's (ok unless a half's interval lies wholly below); it is recorded and logged, never stops a run. Switch 2 (heuristic correction) is removed: `ValueNet(correction=)`, the `heuristic` / `heuristic_hp_loss` dataset fields and `configs/correction.json` are gone; loading a saved correction net raises. This supersedes the step 4 heuristic-correction entry above and the switch 4 parts of the self-play rounds entry. Registry caches are `v4`.
- Histogram HP-loss head (A2). Switch 6's net outputs log-probabilities over 47 bins of HP lost from a state to the end of combat: 1 HP wide for 0-29, 5 wide for 30-59, 10 wide for 60-149, one bin for >= 150 and one turn-limit bin (`stsnet.BIN_LOW`, `BIN_REP`). A bin stands for its lower edge (1-HP bins) or midpoint (wide bins); the last two stand for 150 and never win. Loss: cross-entropy against target histograms (validation reports it; not comparable with MSE runs). Formula: P(win at HP h) = mass of the winnable bins whose HP lost is below h (exact for whole HP in the 1-HP range); score = sum of p * win * (2 - HP lost after the end-of-combat heal / 100), with the heal capped at max HP; the ranking term smooths the win step to a sigmoid of width 2 HP centred half an HP below it. Labels: a one-hot of the real HP lost (the turn-limit bin when the game hit the limit), so round 0's labels are exactly the real outcomes. With switch 1 from round 1: per option, H = its outcomes' histograms as the playing net (the dataset's parent run, loaded from `runs/<id>/model.pt` in the same registry root) predicts them, finished outcomes as one-hots, each shifted by the HP the outcome already lost relative to the decision state (bin by bin through `BIN_REP`, exact in the 1-HP range) and averaged by probability; the decision state's label is lambda * one-hot + (1 - lambda) * the best option's H (best = highest recorded search value), an afterstate's lambda * its own one-hot + (1 - lambda) * its option's H shifted to HP lost from it. The label scale check reads a histogram label as its expected HP lost (round 0 differs from the real HP lost only by the wide bins' rounding, at most 5 HP). The quantile head, the pinball loss and the score-to-HP conversion (`hp_equiv`) are removed; loading a quantile HP net raises. This supersedes the net, formula and switch-1 parts of the step 5 no-death entry above. Registry caches are `v5`.
- Self-play depth and sweep (A3). Net-guided self-play speed (effects net `models/value_effects.pt`, exploration as self-play uses it, all threads, games/s; full-HP mixed train-deck encounters, 2026-10-24, shared dev machine): one turn, limit 16: 5.0-12.1 normal, 7.9-8.4 no-death; one turn with sample_k 2 / 4 / 8: the same 300 games move for move as sample_k 0 (normal and no-death; only timing noise differs); two turns, sample_k 1: 0.28 / 0.30 (no-death); two turns, sample_k 4: 0.20 / 0.21; heuristic one turn: 150-310 normal, 130-230 no-death. Two-turn net search would give a 20-minute round ~110 games per encounter group, so the self-play search is **one turn, limit 16** (`learn.SELFPLAY_SEARCH`, the agents' search; sampling at one turn is a no-op, so it is left off), for round 0 and every later round; switch 5 (`deeper_teacher`, `configs/deeper_teacher.json`) is removed. Sweep (`scripts/sweep.py`): the 8 subsets of switches {1, 3, 6} (`f-base` ... `f-136`), each round 0 + 3 rounds (temperature 0.05), one seed. Sizes are the same for every config so they stay comparable: round 0 at 10,000 games per group (heuristic data, shared per target type and counted once; the existing teacher datasets are reused), later rounds at `n_round` per group, the largest whose projected total fits the 8 h night and whose rounds' self-play each fits 20 min (1,079 at commit time; each round's self-play ~8 min; rates in `sweep.RATES`: heuristic 300 / 150 no-death, net 6.5, tight fights 10, the lower middle of the measured spread). Round 1 thus trains on 30,000 heuristic games plus ~3,200 net games, rounds 2-3 on ~6,500 net games. Guard: after each config, if its point estimate of tight-fight win rate or contested ranking on either half is below the random evaluator's (`bench-baseline.md`: held-out 0.178 / 0.744, train 0.184 / 0.701), the sweep writes its table, prints the reason and exits 3. This supersedes the step 7 sweep and size-control entries and the switch 5 parts of the step 1 and self-play rounds entries above.

## Learned play Amendment 2 as built (provisional)

- Round-0 window rule (B1). Round 0's heuristic games stay in every round's training window (Dk + D(k-1) + D0) until a round's net reaches the heuristic: its tight-fight win rate (one-turn search, the monotone check's thinned specs) at or above search + heuristic's by point estimate on both halves, the heuristic measured once per config on the same specs. Retirement is permanent; from the next round the window is the last 2 rounds and each round plays `n_late` games per group (config key, default `n_round`). `round.json` records the window (`datasets`, `round0_in`) and the comparison (`heuristic`: per half net, heuristic, reached; and overall). Supersedes Amendment 1's "round 0 retired after round 2". Switch 1 (own-search targets) is removed: every label is a real outcome (`selfplay.mix_labels`, the HP own-search histogram mixing and `registry.parent_histograms` are gone). The ranking loss is in every config (`learn.RANK_WEIGHT` = 1.0; `labels` gives round 0 inert ranking fields and rounds >= 1 the options' afterstates, labelled with the real outcome). A leftover `search_values` or `ranking` key in a config is ignored.
- Branch rollouts (B2, switch 7 `branches`). `sts.run(..., forced=...)` takes one opening action list per spec; the binding plays them before the agent (a `Forced` wrapper agent and its own thread loop over `runner::play` in `py/src/lib.rs`; the engine is unchanged), forced decisions record empty search values, and an illegal forced action raises. From round 1 with the switch on, `registry.selfplay` picks branches with `selfplay.pick_branches` (per game, uniformly among decisions with an option valued below the decision's best by more than the exploration temperature, then uniformly among those options; RNG seeded from the config's `sample_seed`), plays them with the same search and net, and stores them after every main game with `branch_at` / `branch_of`. Sampling starts after `branch_at` (`selfplay.first_sampled`), so a branch's examples and ranking decisions are states after its forced action with its own outcome, and main games' labels and samples are unchanged. Measured (effects net, 300 games, temperature 0.05): 96% of games got a branch; branch games ran at 34.8/s against 15.0/s for main games, so self-play took 1.42x as long.
- Sweep (B3). target x branches = 4 configs, 2 seeds each (seed = training seed and `round_seed` offset of rounds >= 1; round-0 data shared per target type), seed-major order; a branch config reuses its twin's round-0 run (identical inputs; `learn.learn(round0=...)`). Costs recalibrated on Amendment 1's sweep (log `results/sweep-2026-10-25.log`): net self-play 11 games/s normal, 6 no-death (it was 6.5 for both; HP configs ran over their projection); training 1.6e-3 / 2.0e-3 s per example (score / HP, early stopping included); 9.5 / 14 min per run outside self-play and training (bench, tight-fight runs, encoding); branches 1.42x self-play time and half a main game's examples per branch game (the latter assumed). Sizing: n_round = Amendment 1's 1,079, or less when even n_late = n_round doesn't fit; n_late the largest >= n_round that fits, worst case of each window rule (round 0 in every training, n_late from round 2). Result: the 8 h night holds only n_round = n_late = ~595, since 2 seeds double the runs and round 0 stays in every training; 600 min would give ~948, 720 min 1,079 / 1,427, and 1 seed in 8 h 1,079 / 1,690 (n_late then capped by the 20 min round). Supersedes Amendment 1's factorial sweep entry.
- Heuristic pool and sampling (B3b, owner 2026-10-25). Round 0 is a pool of 20,000 heuristic games per encounter group (60k per target; validation stays 1,000 per group). Round 0's net trains on a random half of the pool's examples (sampled across all games, not whole games; fixed sample seed and training seed 0), once per target: the other seed and the branch twins reuse it. While round 0 is in, later rounds use a random sixth of the pool's examples, drawn once per seed (`learn.d0_samples`). Today's 30k-game set had 0 duplicate feature vectors, so no pruning. Memory: the 30k set loads at ~0.9 GB and its half adds ~0.45 GB, so the 60k pool peaks around 3.5 GB while sampling. Re-sized night: n_round 908, n_late 909 (from ~595); round 0's training now counts twice per night and later rounds train on ~70k round-0 examples instead of ~210k, so the remaining costs are the per-run overhead (bench, tight-fight checks) and HP self-play at 6 games/s.
- Colab (owner 2026-10-25). The B4 sweep can run on free Colab, one plan row per session (`sweep.py --only`, at the local plan's sizes: n_round 908 / n_late 909, not re-fitted to 2 cores), with the registry on Google Drive and feature caches on local disk (`STS_CACHE_DIR`). A target's round-0 run is reused across sessions when a finished one with the same round-0 inputs and rules version is in the registry (`sweep.find_round0`); `--table` builds the table from the newest finished run per row. The heuristic pools are uploaded, not regenerated (`results/colab-registry.zip`). `py/pyproject.toml` allows Python 3.12 (Colab's).
- Rust inference (spec `rust-inference`, built 2026-10-25). The value net's forward pass for search runs in Rust in the binding crate beside the `Encoder` (`py/src/net.rs`, `sts.NetEvaluator`, built by `stsnet.rust_evaluator`; engine untouched); weights pass from Python as numpy arrays at construction, so old nets load and nothing new is saved; layer sizes come from the weights, and the HP head's bins from `stsnet.BIN_REP` (one source). Agreement with torch is statistical (the same net's tight-fight win intervals overlap with Rust vs Python inference), not a per-state tolerance; measured: scores within ~1e-6 of torch on 2,000 stored states (score, ids and trained HP nets) and 290 of 291 tight fights (every 4th) scored identically. Search threads each clone the evaluator (own scratch buffers) and never take Python's lock; `stsnet.NET_THREADS` applies to Python callables only (`callable(evaluator)` in `bench.run_specs` and `registry.play`). The bench's static prediction metric stays on PyTorch. Speed (`scripts/inference_speed.py`, dev machine shared, median of 5 interleaved runs, Python on 4 threads vs Rust on 16): self-play 23.5 → 179 games/s (7.6x), no-death HP self-play 13.8 → 174 (12.6x), tight fights 74 → 353 (4.8x). `sweep.RATES` keep the Python calibration from Amendment 1's real sweep (whose rounds ran 8-20 games/s, below the benchmark's Python figures) times these speed-ups, rounded down: net 80 / 75 no-death, tight fights 48; the Colab speed cell measures the Rust evaluator. Re-fitted night: n_round 1,079 (Amendment 1's size), n_late ~2,264; self-play is ~35 of 480 projected minutes, so training is now what bounds the sizes. The B4 sweep (Colab, cloning `main`) runs on Python inference throughout: the call-site switch went to `main` only after B4's last run had started (owner). Possible follow-up (not built, tentative): with net search cheap, gradient-free fine-tuning (evolution strategies on the head or the external formula's constants, scored by search + net's tight-fight win rate), prompted by zeroth-order training work (qlabs Dust, `qlabs-eng/noise`, 2026), which is new and mostly tested on language models.
- Parallel sweep runs (`sweep.py --jobs N`, 2026-10-25, owner). Plan rows run as N worker processes (`--only <row> --worker`), same results per run as one process (tested: two tiny rows give identical index.csv lines); a target's first row (it trains the round-0 net) finishes before the target's other rows start. Training is overhead-bound (one torch thread or eight, ~45 ms per batch), so parallel runs fill idle cores. The projection list-schedules rows with each run slowed by PARALLEL_SLOWDOWN = 0.15 per extra job (assumed, to calibrate on the first parallel night); with --jobs 2 the 8 h night fits n_late ~4,670 (from ~2,264). ~3.5 GB per worker at peak.

## Learned play Amendment 3 as built (provisional)

- Varied setups (C1). Every self-play and validation game draws, from the spec seed right after its deck, a whole starting HP uniform over [ceil(10% of max), 100% of max] (Ironclad 8-80) and a deck of the starter plus 3-15 training-pool cards (`selfplay.VARIED`, `varied_deck`, `varied_hp`). It is learn.py's default (`"setups": "varied"`), recorded in each dataset's generating config (`setup`, `decks: varied_deck`), so no dataset of the full-HP setups is reused for it; `"fixed"` keeps the old setups. `sts.run` accepts 4-field specs whose HP overrides the run-wide `hp` (binding only, a `SpecArg` enum in `py/src/lib.rs`); `registry.records` stores each game's own HP and replay starts there. The bench is unchanged. Speed on the same encounters (400 per group, 2 runs, 2026-10-25): heuristic self-play 0.77x, net self-play (Rust inference) 0.43x, examples per game 38.3 vs 35.6 with afterstates, 5.8 vs 4.7 KB per example. `sweep.VARIED_SPEED` (0.75 / 0.42) scales the rates; `ROUND_EXAMPLES` is 37.
- Stop rule and sweep (C2). `rounds.min` (learn.py) turns on the stop rule: from round `min`, a run stops after the first round whose gate is met (`learn.gate`: per half the net's 95% interval wholly above the heuristic's, lower bound > upper bound; on both halves), else at round `n`; `round.json` records `gate` from round 1, and the final round is the one benched (the bench moved from `fit` to after the gate check). The sweep's plan is `sweep.CONFIGS` x 2 seeds, CONFIGS = [score, no branches] (Amendment 2's four configs by setting CONFIGS), rounds 6-10, varied setups (`setups` joins the round-0 reuse keys, so B4's full-HP round-0 runs are never reused). `sweep.py --round0` trains each target's round 0 (pool, validation, net) before the night, so with it in the registry no row waits and both seeds start at once with `--jobs 2`. The projection counts round 0 before the night, sizes the night for 6 rounds and prints the 10-round worst case; each row carries its cumulative minutes per round for the watcher. **Memory, not time, bounds the sizes** (found while sizing; the spec assumed time): the time-fitted `n_late` (~11k games per group) would make a ~2.5M-example training set, ~29 GB at its peak (the loaded parts plus their concatenation), more than the dev machine holds. `fit` now drops the parts after concatenating, and the sizing rule caps the largest training set (round 0's sixth plus 2 rounds at `n_late`) at `WORKER_GB` = 5 GB per run at 2x the examples' size: 431k examples, `n_late` 1,626 (`n_round` 1,079). The night then projects 104 min with `--jobs 2` (177 min if both runs reach round 10).
- Watcher (C3). `scripts/sweep_watch.py`; the sweep process writes `logs/sweep.log` (ISO-timestamped lines) and `logs/plan.json` (pid, jobs, per-row cumulative projected minutes scaled by the parallel slowdown, `first_round` 1 when round 0 was already trained, else round 0's data and training added). Memory is the system's commit charge over its commit limit (`GlobalMemoryStatusEx`, no new dependency); evidence lists the python processes' memory from `tasklist`. "Past 2x" compares a row's time since its start with 2x its projection through the round after its last finished one, so a run going on to round 10 isn't flagged for the extra rounds; a row with no projection (dry runs) is never flagged. Only lines appended after the watcher starts raise problems; the sweep's end (finished, stopped, or the process gone) is read from the whole log.

## Learned play Amendment 4 as built (provisional)

- Greedy self-play with branch rollouts (D1). The sweep's config is `score+branch` (`sweep.CONFIGS` = [(score, branches)]), temperature 0 (`sweep.TEMPERATURE`): the search agent plays its first best option, so main games are fully greedy. Branches qualify at options valued more than `branch_gap` below the best (config key, `sweep.BRANCH_GAP` = 0.05, recorded in the dataset config; `registry.selfplay` falls back to `explore` for configs from before Amendment 4, so old datasets stay findable). Measured at temperature 0 on varied setups with an Amendment 3 net (400 per group, 2 runs): 96% of games get a branch, self-play 1.23x / 1.52x as long (B2's 1.42 kept), branch games add 0.73x a main game's examples (`BRANCH_EXAMPLES`, was an assumed 0.5). Round 0 has neither exploration nor branches, so Amendment 3's round-0 run is reused (the round-0 reuse key doesn't include the switches).
- Sizing and memory (D2). Rates recalibrated on Amendment 3's real sweep (2 runs at once): net self-play ~200 games/s (the projection had 34: Amendment 3 finished in 56 of 177 projected minutes), round-0 pool 238, training 0.9 ms per example (now 1.0e-3, was 1.6e-3); the monotone run's per-round cost is its tight fights at TIGHT_RATE_NET instead of the 2-minute cap. `train_examples` is now the largest set `learn.learn` really builds (round 0's sixth + 2 rounds at `n_round` while round 0 is in, 2 rounds at `n_late` after), and `n_round` is sized like `n_late` (largest that fits) instead of fixed at 1,079. The 2x memory model was checked on a real round 2 (534k examples): the peak was 9.79 GB, 5.9 GB of it from `Normalizer.fit`, whose whole-array float64 `std` copied the training set; `Normalizer.moments` now accumulates mean and std in 64k-row chunks (same statistics to ~1e-9), and the re-measured peak is 6.88 GB = 0.7 GB base + 2x the examples (while concatenating). `sweep.BASE_GB` = 0.7 joins the model; with `WORKER_GB` = 6.5 the cap is ~500k examples: `n_round` 1,119, `n_late` 1,301, projected 69 min with `--jobs 2` (117 if both runs reach round 10). A whole real run at that size (rounds 1-2 at `n_round` 1,119, one process, a fresh registry so its feature caches were built too) peaked at 8.21 GB commit, above the model's 6.5: something outside load / concatenate / normalize (likely building a fresh dataset's feature cache, or self-play holding every recorded state) peaks higher. **Backlog (owner, 2026-10-26: not a big deal):** find that peak and fit the model to it; until then the sizes stay, and two runs may reach the dev machine's memory limit (paging would show as a slow run, which the watcher flags).
- Monitor procedure (D3). The sweep's session runs `sweep_watch.py` as its own background job; the watcher's exit wakes it, and it fixes the problem then (restarting the watcher) or tells the owner. `logs/` is gitignored.

## Learned play Amendment 5 as built (provisional, 2026-10-28)

- The deciding gate is paired (owner, 2026-10-28): per half, the lead is mean(net - heuristic) over each tight-fight spec's result (1 won, 0 lost), its interval mean +- 1.96 * sd / sqrt(n) (normal approximation; n is 550-610, so it's fine); a half passes when the lower end is above 0. `learn.tight_results` replaces `tight_win` (per-spec results; `win_rates` gives the Wilson intervals), and `round.json` keeps both players' results as 0/1 strings (`tight_results`), so later paired comparisons (round against round) need no replay. Replayed on the curriculum night's 20 nets: intervals about +-0.03 per half, none met.

## Solver bounds as built (provisional, 2026-10-28)

- Upper bound of a combat (`CombatState::upper_bound`, engine/src/bound.rs): the score of winning at the current HP plus the end-of-combat heal, capped at max HP; 2.0 when any heal source is left (`can_heal`; `Effect::heals` matches every variant, no catch-all); the score when finished; floored at 0 in no-death mode. Healing cards are never generated mid-fight (owner, as in the original game), so only cards already in the fight count.
- Pruning is opt-in (`SolveConfig.bounds`, `sts.solve(bounds=True)`), only at decisions, never at random events, off in distribution solves; finished children first; values stay exact. Only the curriculum's solve step uses it (`puzzles.solve_dataset` defaults `bounds=True`); the bench build and registry dump stay exact.
- Storage: a bounded option is flag byte 2 in the options blob (0 and 1 as before, so no schema bump); `fetch` options are `(actions, value, bounded)`, `lookup` adds a list of flags, `solve` adds `bounded`. An unbounded solve never answers its root from a row with bounded options. `is_trivial` needs all options exact.
- Training: dataset field `bounded` (0 exact, 1 target is the bound: one-sided value term `max(0, pred - bound)^2`, 2 ranking only); missing in a part means 0 beside parts that have it. Ranking pairs a bounded option only as the worse one, with an exact option at or above its bound.
- Measured on the night's two slowest rounds: no game without positions (was 70%), 5-7x the positions, 9-18x one turn or more out, faster per round.

## Solved-state cost (provisional, 2026-10-28)

- Bug: a state's cost added up its hits' stored costs, but hits' subtrees overlap (transpositions: card orders that reach the same state, random events whose outcomes share later turns), so each step of a walk back counted the shared states once per path. On one greedy game walked back with every state stored, the walk's expansions grew linearly (1.8k to 710k over 19 decisions) while the root's cost about doubled per decision (2.3k to 31M, 44x the walk's whole work). Over a whole game it passes 2^64: `u64` wraps in release, and stored as `i64` the row reads negative.
- Cost now: the larger of the expansions its subtree took in this solve and one more than its costliest child's cost (a store hit's, or a child solved earlier in the same solve). It is a lower bound on what a cold, unbounded solve of the state expands, and never above the expansions that produced it, so it can't compound or overflow. In a cold solve it changes only where a child was already solved in another branch (now counted once instead of not at all), so cold costs only rise. Checked by `store_cost_bounded` (engine/tests/solve.rs): along walks reusing hits, every cost is at most a cold solve's nodes and at most the walk's total expansions; it failed on the old rule at the second decision.
- Read by: `keeps` (cost at least `min_nodes`), eviction (cheapest first), the explorer, the `db` stats' cost quantiles.
- Existing rows: a row costing over one solve's node budget (1M, `MAX_NODES`) got the excess from hits, so it is wrong, and a negative one wrapped. `SolvedDb.repair_costs(max_cost)` / `puzzles.py db --repair-costs` (with `--max-nodes` as `max_cost`) gives each such row one more than its costliest child's cost, children repaired first (a child with no row counts 0: it cost under `min_nodes`). It is the new rule's lower bound without the row's own expansions, which are lost, so at most 1M too low. A bad `trivial` row is repaired when a repaired state reaches it (it has no state bytes to start from); the rest are set to `max_cost`. Checked by `db_repair_costs` (solvedb/tests/db.rs): on a walked database with every row above the median broken, each repaired row is between 1 and its true cost and one more than its costliest child; other rows are untouched. Run on `db/train.sqlite` (owner, 2026-10-28; backup `db/train.sqlite.bak-cost`), 96 s: 95,554 `states` rows repaired (15,644 had been negative, 38,747 at 1e12 or more), 8,350 `trivial` rows repaired and 116 set to 1M; nothing else changed. Afterwards no cost is negative or above 1M. The repaired rows land at 0.9M to 1M (median 988k), among the costliest 1% of rows, which is where the early decisions with the most solved work under them belong. Unrepaired, eviction would have deleted the negative rows first, and a hit on a bad row passes its cost on to every new parent. `db/solved.sqlite` never wrapped, but 5,708 `states` and 3,286 `trivial` rows were above 1M (the largest about 1e9). Repaired the same day (owner; backup `db/solved.sqlite.bak-cost`), 52 s: 5,708 `states` and 3,110 `trivial` rows repaired, 176 `trivial` rows set to 1M, nothing else changed; the repaired rows land at 0.1M to 1M (median 867k).

## Exact solver and position finder (provisional, spec docs/specs/exact-solver.md)

- The solver is exact or silent: past its node budget it reports "unsolvable", never an approximation; it runs to the end of combat with every random event fully listed, in a new `engine/src/solve.rs` (no other engine file changes, no engine dependency).
- Solved positions persist: a permanent SQLite database (`db/solved.sqlite`, gitignored) that Rust reads and writes directly through a new crate `solvedb` (`rusqlite`, bundled SQLite; the only new dependency). Tables: `versions` (rules fingerprint, codec version), `states` (decodable state bytes, value, cost, `turns_left`, and per-option values and distributions on decision states), `positions` (played positions with their source: `bench` or a registry run id; the bench set and dumps are exports), `meta` (schema version). Stored: every solved state whose cost (expansions for a cold solve) is at least `min_nodes`. Rows are deleted only to save space (cap `max_gb`, default 5): stale versions first, then the cheapest to re-solve. A run reads the database as it was when opened, so its output doesn't depend on timing.
- States are stored in an explicit engine encoding (`engine/src/codec.rs`, round-trip tested, every field named so a new field fails to compile), so any row can be rebuilt as a training example; lookup is a 64-bit hash confirmed by full-byte equality.
- Rows go stale when the rules fingerprint changes: a hash of the engine's rule files with comments and whitespace stripped, the content tables' name order and the codec version (the golden-trajectory hash would miss rule changes the golden games never touch).
- Puzzles come from real games' tails only, walked back from the end to the first unsolvable decision, one store per game over the database. The bench set is tight-spec games by search + heuristic on fresh seeds (9,010,000 + pass × 2,000 + half × 1,000 + spec index, under 9,100,000: 9,000,000-9,001,599 are calibration cell 40's seeds, so the set skips that block's used part), one puzzle per game, train and held-out halves; the registry dump keeps every solved decision for training later.
- Puzzle metrics (accuracy, exact regret, ranking, per horizon) join `bench.py` as a new set; existing numbers stay byte-identical.
- Tunable defaults, not fixed choices: `max_nodes` 1M, `min_nodes` 1,000, `max_gb` 5, 1,000 puzzles per half, contested gap 0.05, solver threads from the measured peak memory.
- Measured (step 7, 2026-10-26; search + heuristic on 200 tight specs per half, evenly spaced, seeds 9,000,000 + 100,000 × half + spec index, walked back per the finder rules over one scratch database, release build, shared dev machine):

  | Quantity | Value |
  |---|---|
  | Codec bytes per state | mean 65.8, max 110 (102k states, step 5) |
  | Database bytes per row (states, with options and indexes) | ~252 |
  | Rows per game at `min_nodes` 100 / 1,000 / 10,000 | 9,664 / 1,257 / 180 (30 games); `min_nodes` 0 stores mostly 1-3-node states, 1.4M rows for part of the same 30 games |
  | Games with ≥ 1 puzzle at 1M nodes | train 79.5% (159/200), held-out 75.5% (151/200) |
  | Puzzles per game (contiguous from the end) | 3.5; horizon 0 / 1 / 2+ = 61% / 25% / 14% |
  | Peak memory, one solve to the 1M budget | 0.48 GB (table-bound, an opening); the worst tail (a stalling line) 0.35 GB after the fix below, 2.5 GB before |
  | Peak commit, 6 threads, whole run | 4.63 GB (≈ 0.74 GB per thread with Python and the hash set) |
  | Time per solve, 6 threads | solved decision mean 0.5-1.0 s (median 22-26 nodes); a budget-out stop 8-10 s, about two thirds of all walk time |
  | Walk time, 200 games, 6 threads | 290-400 s (≈ 1.75 s per game) |
  | Second walk over the filled database (30 games, `min_nodes` 1,000) | 45 s vs 54 s cold, and 124 puzzles vs 118 (hits reach further back) |

  So 1,000 games with a puzzle per half need 2.1 (train, 610 specs) and 2.4 (held-out, 550) seed passes: within the spec's 3, no stop. Defaults: `min_nodes` stays 1,000 (100 stores 7.7× the rows without a faster second walk; 10,000 throws away most re-usable subtrees); finder `threads` 6, capped at run time to (free memory − 2 GB) / 0.75 GB so other processes don't page.
- The solver keeps states as codec bytes in its table and its stack frames (`solve.rs`; values unchanged, bit-identical on every test). With whole states (788 bytes) as table keys a 1M-node solve took 2.66 GB, and a stalling line (the player can block forever) runs the depth-first stack as deep as the budget, 262k+ frames each holding a state and its children, 2.5 GB more. Bytes cut both to under 0.5 GB and made solves faster (hashing 70 bytes instead of 788).
- States out of the representable range are unsolvable (step 2): a state with ≥ 60 copies of one card in a pile, ≥ 200 cards played in a turn, or `turn` / `created` / `removed` ≥ 60,000 isn't expanded. Only endless stalling lines reach these (u8 pile counts would otherwise wrap into a wrong state), and those never solve, so no value changes.
- Equal options (within 1e-12, rounding) keep the first for the distribution and `turns_left`; the value is the plain maximum (step 5).
- The database connection waits up to 10 minutes for another writer: at a low `min_nodes` one solve's batch can be a million rows.
- Bench puzzle set built (step 9, 2026-10-26): `data/bench/puzzles.json`, 1,000 puzzles per half, 3 seed passes per half (3,480 games), 10,426 s (2.9 h, ≈ 3.0 s per game) on 6 threads from an empty database; the database ended at 1.23 GB, 3,875,208 rows, 12,625 `bench` positions.
- End-to-end check (step 9, 2026-10-26): 200 puzzles (100 per half, picked with seed 9,500,000 + half), each position played on 400 sampled continuations (the state's codec bytes with a fresh RNG seed per continuation; `step` samples every random event).
  - The solver's own policy (best option of an exact solve over a copy of the filled database) averages inside its 95% interval of the exact value on 198 / 200 puzzles (99%; 170 have one certain outcome). Largest |mean − value| is 0.076.
  - Search + heuristic (one turn, limit 16) falls short of the exact value by 0.012 on average. It is above the value outside its interval on 1 puzzle: a zero-width interval, because the 400 samples missed outcomes of total probability 0.0006 (P(loss) 0.00045).
  - Both flagged puzzles re-run on 20,000 continuations land inside (the solver at 1.69349 ± 0.0011 vs 1.69409, and 1.90856 ± 0.00037 vs 1.90914; search below or inside). 2.6 min on 6 processes.
- Second build over the filled database (step 9, 2026-10-26): a copy of the database, 100 per half (pass 0 of each half, 1,160 games), 1.60 s per game against the first build's 3.00.
  - Every decision both builds solved (4,203) has bit-identical option values; 96.9% of them were answered whole from the database. The rest of the time is the walks' failing stops (budget-outs), which partial subtrees only shorten.
  - Hits let 98 games reach 134 decisions further back. So games with a puzzle and the seeded picks change after the first game whose puzzle count changes: a one-option draw (`integers(1)`) uses no randomness, so the pick stream shifts from there on. Train kept its 100 games and 57 picks; held-out kept 25 games. Expected (the header records the database's row count); the committed set is the first build's.
- Bench puzzle section (step 10, 2026-10-26): `bench.py`'s `puzzles` set reads only `data/bench/puzzles.json`. Its settings (`contested` 0.05 = `bench.PUZZLE_CONTESTED`, `exact` 1e-9, the file's fingerprint, budget and seeds) sit in `sets.puzzles.settings`, so the top-level `settings` and every existing number stay byte-identical. Accuracy and regret are bootstrap means over puzzles (like the other sets, so the held-out gaps work); ranking ties in the evaluator's values count half, as in the decisions' ranking. The per-horizon cells are on all puzzles. Quick mode keeps every 20th. A random leaf evaluator searched through ranks 77-82% of contested puzzle pairs (the puzzle floor; the decisions' is ~72%), since 77% of puzzles end within the searched turn, where every evaluator is exact. Results: `docs/research/exact-puzzles.md`.
- Trivial states (Amendment 1, built 2026-10-27, provisional): a state whose value is 0 or whose options are all within `TIE_EPS` (1e-9) is written to a `WITHOUT ROWID` table `trivial (version, key_hash, check_hash, value, cost, turns_left)` instead of `states`; `check_hash` is 32-bit FNV-1a (the column isn't `check`, an SQL keyword). A hit there rebuilds the options from the state in hand (`solve::group_options`, now public; solve.rs isn't in the fingerprint), each at the row's value, and never carries a distribution, so a distribution solve re-solves it. Puzzles always keep full rows (`add_position` moves a trivial one back). Schema 2; a version-1 file gains the empty table on open. Eviction drops other versions' trivial rows first and keeps the current version's. `SolvedDb.compact` / `puzzles.py db --compact` moves existing trivial rows no puzzle points at, then VACUUMs. Measured 2026-10-28: `db/train.sqlite` 969 MB to 766 MB (607k rows moved, minutes); `db/solved.sqlite` 1,235 MB to 803 MB (about 1.44M rows moved over two runs, 3.5 h of wall time on top of a first run cut off at 50 min). The slow part is the per-row delete from `states` and its three indexes with SQLite's default ~2 MB page cache (ideas#61).

## Curriculum labels (provisional, spec docs/specs/curriculum.md)

- Labels follow a ladder per example, replacing outcome-only labels for score configs: exact value if the state is in the solved-position database; else, inside the playing net's verified zone, 0.8 × its one-turn search value + 0.2 × the game's final score; else the final score. Round 0's heuristic games use exact and outcome only.
- The verified zone is measured, not scheduled: per-horizon exact regret on the bench's puzzles (≥ 50 puzzles, ≤ 0.01 regret), an unbroken run of horizons from the end, plus one turn. Each dataset uses its playing net's zone.
- Not-played options are ranking-only (value-loss weight 0), no longer labelled with the played game's ending. Divergent options (End turn, big draws) never take search labels: their search value is the old net's own rating.
- Each round solves its own games' tails into the database (game-count cap, ~15 min); exact database examples (≤ 50,000) get 20% of the value loss. Dataset caches hold label inputs (v6), so labels follow the database and frontiers without rebuilding.
- Learned-play Amendment 4's D4 sweep is superseded by this spec's run; success is judged against the heuristic on tight fights and by the puzzles per horizon.
- Round 0 is a different run from learned-play's (owner, 2026-10-26): the heuristic only plays its games (positions to solve, endings where unsolvable). Recorded games are reused; round-0 nets are reused only with the same labels and label settings (`labels` and its settings join `sweep.ROUND0_KEYS`), so outcome-labelled round-0 nets from Amendments 1-4 never are.
- Memory (owner, 2026-10-26): use as much as speeds the run up, as long as other processes aren't pushed into paging. Runs are sized to the memory free at plan time minus `MEM_MARGIN` (2 GB), split across jobs, replacing `WORKER_GB` 6.5; the peak model is refit to measured whole-round peaks, including Amendment 4's unexplained 8.21 GB. This supersedes the memory-cap backlog item in "Learned play Amendment 4 as built".

## Curriculum as built (provisional, steps 1-7, 2026-10-27)

- Value loss (step 2): `train.value_loss` is the batch mean of weight x each example's loss (divided by the batch size, not the weights' sum), so globally scaled weights keep their proportions; with every weight 1 it equals the old loss to the bit (`weight_one_identity`). Validation stays unweighted. Switch 6 takes weights too (all 1).
- Label inputs (step 3, cache v6): every example stores its raw search number (NaN when none), kind, played, distance (the game's last decision turn minus the state's turn, an afterstate taking its decision's; the puzzles' horizon rule) and codec bytes; `learn.ladder` decides at load time. Not-played afterstates stay weight 0 even when the database has their value. Equal states share an exact value.
- Exact examples (step 4): drawn only from decision rows (chance-paused rows skipped, their featurizing unchecked), read in seeded order until the next row's examples wouldn't fit `exact_cap` (decision states and afterstates counted together); each decision state weighs `share x W_self / ((1 - share) x n)`, afterstates 0; `distance` -1 and `outcome` = the exact value (left out of the label scale). They join every round, round 0 included. The draw orders decision rows by `key_hash, id`, not row id, since row ids follow the solver threads' write order (same content, different draw otherwise). `solvedb` gained read-only queries (`lookup`, `decision_ids`, `fetch`); schema and write path unchanged. Training reads and writes its own `<root>/db/train.sqlite` (starts empty, filled only by the runs' solve steps), not the bench build's `db/solved.sqlite`: that file's 2.7M decision rows are all the bench puzzles' tails, and the review found 7 actual puzzles among the first 10k drawn rows, which would inflate the trusted zone they measure; without it there is no rung 1.
- Trusted zone (step 5): per-horizon regret uses each puzzle's own horizon (0, 1, 2, 3, ...), both halves pooled; the set holds 1,552 / 313 / 101 / 26 / 5 / 3 puzzles at horizons 0-5, so with `min_puzzles` 50 the frontier can't pass 3 on today's puzzles. Only played examples (decision states, played options of kind deterministic or chance) take rung 3. A playing net with no recorded zone (an older round-0 net) gives outcome labels.
- Solve step (step 6): the first `SOLVE_GAMES` 300 games of each round's dataset (round 0's pool: `SOLVE_GAMES0` 1,200), branch games counted as games. `solve_games` isn't in the round-0 key. With `--jobs 2` the runs share one database, so a full-size run's rung-1 labels and exact draw are reproducible only from the same database state (`db_rows` in round.json shows it).
- Memory (step 7, `scripts/memprobe.py`: a real run, rounds 0-2, every phase wrapped and the process's commit sampled every 50 ms by a second process). The unexplained 8.21 GB (Amendment 4, D2) was the feature-cache build of a fresh round dataset, as far as small runs show: replaying a 3,000-game chunk held ~1.3 MB per net-round game (~4 GB at real round sizes), on top of every chunk's float32 encoder batches (~2x the result). Cheap fixes, caches byte-identical: `registry.CHUNK` 500 and each chunk converted to storage form at once; the exact draw encodes per fetched chunk (its decoded states had held ~1 GB). Measured after them at two sizes (71k-151k training examples, exact included): each round peaks while concatenating its training set, at 1.15 GB + 12.8 KB per example (fit); the model is `BASE_GB` 1.25 + `PEAK_BYTES` 12.8 KB per example, never below the six rounds and at most 8% above (`test_peak_model_matches`, data in `scripts/tests/data/memprobe.json`). A dataset's cache build stays under its round's training peak; the solve step peaks at most `BASE_GB` + 0.75 GB per thread.
- Budget: each run gets (free physical memory at plan time - `MEM_MARGIN` 2 GB) / `--jobs`; the planner passes the free memory it sized for to its workers (`--free`), so rows match. The solve step's threads are `sweep.solve_threads` (what fits the run's budget, at most 6), recorded as the config's `solve_threads`. The plan refuses below `MIN_N_ROUND` 500 games per group (tunable: about half the sizes Amendments 3-4 ran), and `--round0` refuses when its pool's cache build (420k examples, ~7.3 GB modelled) doesn't fit one process's budget; `--force` overrides both.
- Solve rate: 3.5 s per game for a net round's games and 2.4 for heuristic pool games on 6 threads (18 games each over a copy of the real database, 3 threads, scaled; the bench build's 3.0), so `SOLVE_S_PER_GAME` 3.5: a round's 300 games ~18 min, round 0's 1,200 ~70 min before the night. The projection counts them and the exact examples' training time.
- The night (projection, 2026-10-27): with 12 GB free, `--jobs 1` fits both seeds' 6 rounds at `n_round` 1,467 / `n_late` 1,649 in 6.1 h (10.2 h if both go to round 10); `--jobs 2` gives 450 per group, under the floor (500+ needs 12.5 GB free). With 10 GB free, `--jobs 1`: 1,060 / 1,242, 5.6 h; `--jobs 1` reaches the floor at ~7.3 GB free, and `--round0` needs ~9.3 GB. With the memory free during the build, nothing fits.

## Curriculum Amendment 1 as built (provisional, 2026-10-27)

- Caches are v7 directories of uncompressed `.npy` files, built chunk by chunk (peak flat in dataset size: 732 / 734 MB at 600 / 2,400 games) and memory-mapped; a round's training set is a view over its parts (per example ~0.14 KB in RAM), with nets bit-identical to the in-RAM concatenation. Exact examples go to a temporary mapped cache per draw.
- Re-measured (memprobe at 300 and 1,200 games per group, `scripts/tests/data/memprobe.json`): a round peaks at the largest of fixed phases (2.0 GB), self-play (2.29 GB + 100 KB per main game) and training (1.43 GB + 0.2 KB per example); never below a measured round, within 10% of the largest round at each size (repeats at one size vary by 18%). Self-play now sets a round's peak. Round 0 ~2.0 GB (the stored pool is reused).
- Training speed: 91 us per example per epoch through the view with the data in file cache (in RAM: 93); 271 us once the mapped caches exceed it, as at night sizes on the dev machine (round 0's 1/6 sample touches nearly all of the 1.9 GB pool cache). Owner's call at the stop point: plan with the measured 2.9e-3 s per example (night ~8 h, ~1,065 games per group at 4.7 GB free) rather than build block shuffling first; block shuffling (sequential reads, not bit-identical) is the follow-up if nights are too long.
- Solve steps are sized by time (15 min per round, round 0 60 min) at the run's memory-limited thread count. The planner refuses when free disk is below the night's caches (up to `CACHE_CAP`, 4,600 bytes per example), the exact temp cache per job, the training database's 5 GB cap, plus `DISK_MARGIN` 2 GB. Dead processes' `*.tmp<pid>` caches are deleted at run start; `fit` and `training_set` delete their exact temp cache on failure. Re-measured 2026-10-27 on round 0's solve step over the empty `db/train.sqlite`: 12 s per game at 6 threads (`SOLVE_S_PER_GAME`, was 3.5, measured over the filled `solved.sqlite`); the steps keep their minutes and solve about 3.4x fewer games.
- Solver touches bound (2026-10-28, found when the night stalled 95+ min inside one `sts.solve` at 1M nodes): expanding a state lists every child, every outcome of a random event included, and a draw from a varied deck can have thousands, uncounted by the node budget. Children listed are now bounded at `TOUCHES_PER_NODE` 16 per node of the budget (the event is listed with the remaining room as its limit; past it, unsolvable). Measured over 400 bench puzzles solved cold at 1M nodes: at most 4.4 per node, median 2.1, so no solvable puzzle changes. `sts.solve` returns `touches`.
- `MEM_MARGIN` lowered from 2 to 1 GB (owner, 2026-10-27): rounds are sized by time, not memory, so the extra GB only reaches the solve step (5 solver threads instead of 3 at ~6 GB free, so more of each round's games solved in its 15 minutes). Free RAM otherwise stays file cache, which is what keeps training through the mapped caches fast.
- Resume per round (owner, 2026-10-27): before training round k, `learn` reuses a finished run (`finished` in its round.json, written after `run.finish`) with the same config (`solve_threads`, `solve_games`, `solve_games0` aside), round, training datasets, parent run and rules version, replaying its tight fights, gate and window instead of solving and training again. Training is deterministic, so that run is what the round would train again; a stopped night loses at most the round in progress. A restart must plan with the same `--free` (round sizes shift slightly with free memory), or its datasets differ and nothing is reused.
- Amendment 2 (owner, 2026-10-27): the trusted zone counts only puzzles whose options are not all equal (best minus worst exact value > `TIE_EPS` 1e-9); `round.json` records `n`, `tied` and `regret` per horizon. Tied puzzles were 73% / 27% / 10% of the bench set at horizons 0 / 1 / 2 and diluted the mean regret (horizon 0: effective limit about 0.037, not 0.01). In the solved db, 17% of decision states are certain losses (value 0) and 42% flawless wins (value 2.0). Extended the same day (owner, from the explorer) to dull decisions: every option except End turn tied at the best value (all tied, or only ending the turn with cards still playable loses); the zone and the exact examples both skip them. Bench puzzles counted per horizon 0 / 1 / 2 / 3+: 172 / 174 / 73 / 25 of 1,552 / 313 / 101 / 34 (tied alone left 417 / 227 / 91 / 32). Round 0 was re-run with it.

## Explorer as built (provisional, 2026-10-27)

- `scripts/explore.py` + `explore.html` (docs/specs/explorer.md). Memory, measured on db/solved.sqlite (3.9M rows) with picks cached, ten wrong-pick puzzles viewed, every option stepped, unsolved children solved, the bench positions listed: heuristic only, peak working set 339 MB and peak commit 829 MB; with a net (`--model`), 423 MB and 962 MB. Of that, importing `bench` (which pulls in torch through `selfplay` / `stsnet`) alone is 207 MB working set and 696 MB commit. Over the spec's 500 MB stop point by commit, under it by working set. Accepted as measured (owner, 2026-10-27); dropping torch from the heuristic path needs `stsnet` split into a data and a net module, a later spec.
- `sts.SolvedDb` reads every row's hash when it opens: about 2.5 min on db/solved.sqlite, so the explorer opens it in a thread and lists puzzles at once; picks over the 2,000 bench puzzles take about a second (heuristic or net) and are cached under cache/explore/.
- The server runs a thread per request (`ThreadingHTTPServer`), not one at a time as the spec said: browsers open spare connections that send nothing, which blocked the single-threaded server for good. Tests call the endpoint functions directly, so they stay deterministic.
- Superseded in part by "Explorer v2 as built" (2026-11-08): `--db` and `--model` are gone (the page picks the database and the comparison nets), the explorer starts without a database, and it imports its own copy of `sts`.

## Extending the engine and the net (concept, 2026-10-26)

- Settled with the owner and recorded in `docs/extending.md` (concept and dated decisions) and `docs/specs/rules-engine-upgrade.md` (the umbrella: model, contract, checks, and the series of ten engine specs, each with its own proving content; `docs/specs/warm-start.md` for the net side). Headlines: the engine takes data only, no scripting; every input column is named and nets saved under the contract always load; no spec in the series trains a net; per-copy card state is the card's own numbers, never a play counter; the known top of the draw pile is bucketed by draw turn; monster move patterns become data with a distributional golden check.

## Rules-engine umbrella review (2026-10-26)

- The umbrella was reviewed against the code; the must-fix gaps are folded into `docs/specs/rules-engine-upgrade.md` and `docs/extending.md` (owner's go-ahead), the rest are its open questions. This supersedes the previous entry where they differ.
- Contract: exact reload is by gather (the batch's columns picked in the saved net's order, unknown ones dropped), not by permuting or zero-padding weights, which changes floating-point summation order; the padded wider layer is for fine-tuning only, under a tolerance. Bit identity is per forward pass (torch, Rust). Row kinds, the power dimension set and named pile slots are vocabulary too: rows of kinds a net doesn't list are dropped for it, a power keeps its dimension when it gains rows, and a pile a net doesn't know folds into its parent (the known top into draw), since the head's width is one slot per pile (`stsnet.py`, `py/src/net.rs`).
- Recorded games (registry datasets, the bench's decisions, reference and puzzles, the round-0 pools) replay from setup and actions, so every spec keeps existing content's golden games identical: spec 9's patterns make today's random calls in today's order (distributional check only as a per-monster fallback), and spec 6 keeps the Silent Defend stand-in as the default starter (Survivor's real starter is a named variant; switching the default is one later re-baseline). "Must stay true" now matches the series: the solver database is retired at each fingerprint change and refilled once after the series.
- Proving atoms corrected: Caltrops needs an `OwnerAttacked` trigger (every attack hit, blocked or not) with the attacker as source and target (spec 5); Burst is a card replay, not a replacement (spec 6); Intangible caps an amount, with the damage pipeline's order fixed in the format (spec 4); debuff countdowns run on a new `RoundEnd` trigger, since the player's turn end fires before the monsters act; Well-Laid Plans' turn-end choice is deferred (decisions come from cards only), so the Retain proving card retains itself.
- A large draw before a pick in the same card is still a search leaf, so the features carry the pending decision. Spec 1's play encoding carries per-copy overrides. The state representation (fixed-size piles and powers, `u8` card ids, `&'static` definitions) and the registry's scope are decided at spec 8's interview; from spec 10 the fingerprint and the registry's rules version also hash the loaded content files.
- Owner's answers to the review's open questions (2026-10-26): each spec checks the heuristic bit-identical on the fixed state set (whether it reads new rows generically is decided per spec, by whether the atom reaches round-0 content); spec 2 keeps Body Slam's, Heavy Blade's and Perfected Strike's columns, computed from the expression, so old nets stay exact; spec 8 is "load as-is" (Rampage's growth and Retain are additive columns an old net drops); a card shuffled under a known top becomes a floater (known card, position uniform over the pile, rolled at the draw) instead of dissolving the prefix, which would change the game's odds. Answered 2026-10-26 (owner): spec 1 ships `scripts/convert_net.py`, converting a known pre-contract layout into a contract net, checked bit-identical on the curriculum's final net, which is the Ironclad parent for the learning curve (no net trained for it); spec 9 has no distributional fallback, the pattern format is today's call shape (ordered rows over the two-deep executed-move window, one lazy 0..99 roll, `chance(p)` pairs for repeat limits) so the data gives the same result with the same RNG, all 15 encounters migrate in spec 9, and a monster gains one internal scalar `phase`; the per-spec checklist is in the umbrella. Speed (2026-10-26): each spec measures before and after on the existing harnesses its change can touch (check 4, `search_speed`, `inference_speed.py`, nodes per decision on the fixed set), median of 5 interleaved runs on an idle machine; budget 10% per spec, 25% over the series, node counts identical on existing content, empty prefix / floaters / overrides free in clone and hash; per-spec table in the umbrella's "Speed checks". Answered later the same day: the heuristic stays blind to new row kinds through the series (it learns one only when content using it enters the round-0 pool); the net reads an amount expression as both its resolved value in the damage column and its form (base, k, quantity one-hot) as columns beside it. Floaters under a later push: each floater carries `above`, the number of known cards certainly above it (the review's levels, one integer per floater); only `above` 0 floaters can be drawn next, a push raises every `above` by 1, drawing the known head lowers them.
- Monster state, checked against the whole game (2026-10-26, against sts_lightspeed, which reimplements every monster through the Heart with a two-entry move history; the game's decompiled code not read): no monster looks further back than the move before last, so the two-deep `moves` window holds. The rest is conditions, not depth: slot (needed already for the Sentries, whose slot 1 opens with Beam, so spec 9's closed condition list gains it), move before last and either of the last two (Champ, Chosen, Spire Shield and Spear, Nemesis), turn modulo or equal on the combat turn (Champ, Corrupt Heart, Collector), the player's powers (Spire Growth), an ally's missing HP (Mystic), and `phase` as one per-monster byte holding a used-once flag, a phase flag or a counter (Gremlin Wizard, Hexaghost's cycle, Spiker, Bronze Automaton), read inside its pattern rows as (phase, threshold) with `AddPhase` beside `SetPhase`. Details under "Monsters" in the umbrella.

## Tight fights v2 as built (2026-10-29)

- `docs/specs/tight-fights-v2.md`. The rounds' tight fights are `tight2.json`: 1,226 calibrated cells (616 train, 610 held-out, v1's 116 family cells among them), 20 seeds each. The gate and `tight_win` take intervals over cells (`learn.cell_interval`); `every` thins seeds within each cell. v1's sets regenerate byte-identical.
- Seed ranges: calibration from 10^15, test seeds from 2 x 10^15, past every seed `sts.make_specs` hashes (input x 1,000,003 + i, ~2 x 10^9), v1's and self-play's.
- After the full calibration's 6 redraw batches per half, cultist (5 train / 14 held-out) and two_louse (6 held-out) were still short: 82-90% of their decks still win at 1 HP. The spec wants every encounter filled, so `--topup2` continues from the saved calibration: its cells kept, fresh decks (seed [77, 1]) for the short encounters only, batches sized by each one's kept share so far. Its cells follow the first run's in each half.
- Sweep: `TIGHT_FIGHTS` 24,520, `TIGHT_RATE_NET` 100 and `TIGHT_RATE_HEUR` 150 (118 and 158 measured under ~50% other load). `MONO_MIN` raised from 2 to 5 so each round plays every seed (~4 min): at 2 min the thinning keeps 7 of 20 seeds and the held-out interval widens to ~0.013, past the spec's 0.012. `MONO_MIN_CAL` 2 keeps `OVERHEAD_MIN`'s calibration as it was; the heuristic's run (once per run, ~2.5 min) is now counted on its own.

## Rung 4 check as built (2026-10-29)

- `docs/specs/rung4-check.md`. `engine::runner::play_from` plays a state on with a given chance generator (a pending chance event first); `play` builds the start state and calls it, every game unchanged. `sts.play_on` plays decoded positions on with `sts.run`'s search agent; each play-out's agent RNG comes from its chance generator (unused at explore 0).
- Rung 4 labels: (ending + K x play-out mean) / (K + 1) for valued examples that would take rung 5, in rounds >= 1, only with a config's `"rung4": {"k": K}`; a missing or mismatched cache stops the run. Nightly configs don't carry the key, so their labels are unchanged. Play-out caches live in `runs/rung4/playouts/` (gitignored), not `cache/rung4/`: `registry.evict` treats `cache/` folders as LRU caches and could delete them.
- The pre-check's item 1 is judged on the band-weighted gap, not per band: bands are defined by the game's realized length, which conditions each band's endings (spec's per-band reading was wrong). Paused states were checked to decode exactly.
- Seeds: play-out chance seeds from 3 x 10^15 + slot x 10^10 + example x 16 + play-out; step 4's first play-outs reuse the pre-check's.
- Amendment 1 (training seeds, 2026-10-29): averaged over three training seeds on the night's database, rung 4 gains +0.001 / +0.002 (train / held-out), intervals around 0: it fails, and stays off. The first check's +0.017 came from the bounds-walked database copy weakening A. Rung 4 isn't wired into nightly rounds (no spec). Training-seed spread of a round's lead: sd 0.006-0.0075, and B - A at one seed varied by sd 0.004-0.006; a one-retrain comparison needs a gap of ~0.01-0.02 before training luck is ruled out.

## Seed check (spec, 2026-10-29, confirmed by the manager, owner away)

- `docs/specs/seed-check.md` (ideas#65): the night's passing rounds (s1 r2, r4, r7; r10 from the rung-4 check's arm A) retrained at training seeds 1, 101, 201. A round holds up when the gate on each fight averaged over its retrained nets lies above 0 on both halves and every seed's held-out lead is above 0 (owner). Each round retrains against its own database: a copy of `db/train.sqlite` with `states` ids above its `db_rows` deleted (ids only grow; `db_rows` is the round's largest id; `trivial` kept whole). The night's own net is reported beside the retrains, not counted (owner).

## Label settings back to the night's (owner away, 2026-10-29)

- `learn.label_settings` defaults are the 2026-10-28 night's again: `EXACT_CAP` 50,000, `EXACT_LEAVES` False, `EXACT_SPLIT` None (no split draw). Curriculum Amendment 3 (cap 150k, paused states, split draw) failed its one-round check and its step 3 is on hold, but its values were the live defaults, so any new sweep would have used them unannounced. Amendment 3's values stay as `learn.A3_CAP` and `learn.A3_SPLIT`; `round_check.py` uses them, so its check reproduces. Alternatives: keep Amendment 3's defaults (rejected: unproven, and the night's settings are the ones every later check measured against); require every sweep config to set them explicitly (rejected: more change for the same effect). Reversible: three constants.

## Contract spec confirmed (owner away, 2026-10-29)

- `docs/specs/contract.md` (rules-engine spec 1) confirmed with all 14 proposals as drafted (gather in the Rust encoder, today's column names with ids columns renamed `id_<name>`, aligned normaliser arrays, integer schema 1, one row kind `triggered`, an explicit six-power list in effects mode, converter for `rows` nets only, converted files beside the original). Changed after checking the draft against the code: `sts.NetEvaluator` builds its own encoder, so it takes the same `columns`/`row_kinds`/`piles`; HP-histogram nets save `bin_rep`; a pre-contract net loads through its `<name>.contract.pt` when one exists instead of being refused outright (alternative: refuse and make every caller convert first; rejected, it would break every script that loads a night net by path), and every existing net is converted in the build; nets the loader already refuses (correction, quantile HP) are refused by the converter. Reversible until nets are saved under schema 1 in a sweep.

## Seed check as built (owner away, 2026-10-29)

- `scripts/seed_check.py` (8837c83; spec folded, in git history at b076af5): no round of the 10-28 night holds up over training seeds 1, 101, 201, so the night does not meet the gate and the curriculum is flat on it. Every round beats the heuristic on train cards and none on held-out cards (results doc, "Seed check"; follow-up ideas#67). #65 stays open for a nightly gate that counts training luck. Next: the rules-engine series (`contract`), then generated cards as the training distribution (manager's call, owner away).

## Contract as built (owner away, 2026-10-30)

- `docs/specs/contract.md` (folded; `git show 8ff0ca0:docs/specs/contract.md`) built on branch `contract` (b5b1741, 58e3d66, d9e5d7b, 21610b8, 112894a, this commit). Every net is saved with `schema` 1, `columns` per path, `row_kinds` and `piles` (and `bin_rep` for HP-histogram nets); loading gathers in the Rust encoder (`sts.Features` / `sts.NetEvaluator` take `columns=`, `row_kinds=`, `piles=`), so both forward passes read the net's own layout and stay bit-identical. Row kinds (`triggered`), the effects-mode power list (`MODIFIER_POWERS`: Strength, Dexterity, Vulnerable, Weak, Frail, Artifact, replacing "no hooks") and pile names are vocabulary; a pile a net doesn't list folds into its parent (`PILE_PARENTS`, empty today), and with no listed parent the layout is refused.
- The gather runs as a pass over the full batch after encoding, not inside it: simpler, and it can't change today's batches. A layout equal to the full one skips it. A non-full layout costs about 2x the encoder time (step 3: effects 22.6 → 46-50 ms, ids 14.5 → 35-63 ms on the 3,104 fixed states). If a later H3 needs it, write columns in the net's order during encoding.
- Ids columns are `id_<name>`; the status cards with two slots (Wound, Slimed, Dazed) name the second, upgraded slot `id_<name>+`, so names stay unique. Batches unchanged.
- `stsnet.save` refuses a net whose widths, normaliser or pile count don't match its meta's encoder (the spec's "refuse when in doubt"; it caught `test_net`'s round-trip test saving a full-layout net under a 3-card meta, now fixed in the test). The layout is saved at the file's top level and inside its `meta`, so a loaded meta goes straight to `features_for` / `rust_evaluator`. `stsnet.load_pre_contract` reads an old file as saved, for the converter and the pins.
- Pre-contract nets convert only from the `rows` layout, checked bit-identical on the fixed set (golden.py's states, `decisions.json`, new `data/bench/fixed_silent.json`: 500 Silent decisions per standard half, seed 7,100,000), torch and Rust. End-to-end 0: of 143 nets (`models/*.pt`, `runs/*/model.pt`), 140 converted and 3 refused, all heuristic-correction nets (`runs/2026-10-24-ctrl-1236-7106414`, `ctrl-all-5-r1-7994d1c`, `ctrl-all-5-r2-98dc890`). The curriculum's final net (s1 r10) and `models/value_effects.pt` converted bit-identical; the converted s1 r10's bench file equals the original's under the old code byte for byte.
- Pins: feature batches are pinned as sha256 per array (full arrays would be tens of MB); three tiny untrained `rows` nets (effects, ids, effects with HP head; `hidden` 256 because `save` doesn't store it) are pinned as float32 outputs (`scripts/tests/data/contract/`, ~750 KB).
- Specs stay keyed as stored; `sts.run` also takes dict specs (`encounter`, `deck`, `seed` required, `hp` optional; unknown keys refused). Record readers default missing `hp`, `character`, `no_death` (`action_text.combat_of`). Action text is one module, `scripts/action_text.py` (`registry` and `bench_decisions` alias it), with reserved forms `Done`, `Choose:<card>|#i`, `Potion:<slot>[@target]`, `Card{field=value/lifetime,...}[@slot]` that parse and raise `NotSupported` on replay. The engine is untouched except a comment in `engine/src/codec.rs` reserving tags 2-4. Not changed: `scripts/bench_probes.py:81` still reads `p["hp"]` directly (outside the scope; probe files always store `hp`).
- H3 (`scripts/inference_speed.py`'s Rust workloads, `models/value_effects.pt` vs its `.contract.pt`, 8 cores by affinity, 5 interleaved runs, CPU load 25-56% from two other test processes): self-play 285.8 → 280.6 games/s (-1.8%), tight fights 318.9 → 312.7 (-1.9%). Within the 10% budget.

## Play turn limit (owner away, 2026-10-30)

- `runner::play_from` stops a combat still running after `PLAY_TURN_LIMIT` (100) turns and reports it lost (score 0). Found when `test_sweep.py`'s tiny dry run hung for 4 hours: on a tight fight (lots_of_slimes, HP 9, held-out seed 2000000079800000, a deck with Metallicize, Defends and 0-cost cards) its untrained round-1 net blocked every hit and never finished a Spike Slime on 3 HP, and normal play had no turn limit. The limit is in the play loop only: combat rules, the exact solver, the codec and solved databases are unchanged, and a stalled self-play game now yields a lost trajectory, which tells the net stalling is bad. Alternatives: a limit in `CombatState` for all play like `NO_DEATH_TURN_LIMIT` (rejected: changes solver values and stored states); a lower limit such as 50 (rejected: no measured Act 1 fight needs it, and 100 costs a stalled game only ~100 search turns). Reversible: one constant and one loop condition.

## Warm-start spec confirmed (owner away, 2026-10-30)

- `docs/specs/warm-start.md` finished and confirmed by the manager. Parents are the generalise pair (`models/value_effects.pt`, `value_ids.pt`), not the curriculum's s1 r10 named on 2026-10-26: the thesis needs an ids twin trained on the same data, which no curriculum run has (training one costs a night), and s1 r10's replay would need the curriculum's label ladder; s1 r10 as a warm start is a follow-up. Alternatives: s1 r10 against `value_ids` (confounds data with features); an ids curriculum twin first. Widening places weights by name into the new vocabulary's natural column order (not saved order plus appended columns): fine-tuning is checked by tolerance either way, and this lets the standard encoders encode replay and new data. Replay share 0.5, constant; fine-tuned nets sit beside their parents; a small calibrated Silent tight set (10 cells x 20 seeds per encounter and tier); labels are final scores; the gate is on Silent MSE with win rate reported, since 3 seeds can't separate win-rate effects of this size from training luck. All reversible: nothing saved under these choices is read by other code.

## Job queue spec confirmed (owner away, 2026-10-30)

- `docs/specs/job-queue.md` written and confirmed by the manager (Next item 2 of the 2026-10-30 re-plan). One file per job in `jobs/pending|running|done/` (alternatives: one shared JSON-lines file, SQLite; rejected: two writers on one file, and harder to read or fix by hand); the runner starts the first pending job only when its own heavy slots (2), its thread budget, the system's measured idle CPU and free memory all allow, so runs started by hand and other projects count. It flags stalled logs and never kills. The test-size profile for the slow suites is left to its own spec. Reversible: a new script and a gitignored folder.

## Job queue as built (owner away, 2026-10-30)

- `scripts/jobs.py` (spec folded; `git show 22f749b:docs/specs/job-queue.md`), commits 980f736, f37823a; usage in README "Job queue". Statuses: `ok`, `failed` (non-zero exit, or the program/cwd couldn't start, with `reason`), `lost` (gone before a restarted runner saw it end), `ended` (an adopted job that went away; exit code unknown), `cancelled`; a job above the thread budget is refused as `failed`. A relative program path is resolved against the job's cwd (CreateProcess doesn't). File moves retry while a reader holds the file. The runner is started detached with PowerShell `Start-Process`, so it outlives the session that starts it; jobs break away from the runner's job object when Windows allows it.
- Review (spec-reviewer): three must-fix findings fixed with failing tests first (start error killed the runner, and it did, live, on a relative `.venv` path; a file held open by a reader killed a move and could start a job twice after a restart; the "first pending job blocks" rule wasn't pinned). Optional, not done: `cancel` racing a start can leave a job in two folders; two simultaneous `add`s can take one number; `wait` can miss an event split across a half-written line; pid reuse can keep an adopted job "running".
- Not checked: a job surviving a TaskStop of the session that started the runner (the runner itself is now started outside any session).

## Warm start as built (owner away, 2026-10-30)

- The learning curve ran (`results/warm-start/curve.json`; results doc "Warm start on Silent: the learning curve"). Gate FAIL: once fine-tuned, effects features transfer no better than ids (every row within training luck); they help only zero-shot (unchanged parents, +0.024 / +0.060 Silent win). Warm start beats fresh in play at every size, with no forgetting of Ironclad. Consequence for the plan: the effects encoding stays the default (it is the only edge on unseen content, goal 1's case), but "better features" is not the route to transfer; mechanic coverage in training (Next 6) and play-based judging (the ladder) are. Fine-tuning code (`stsnet.widen`, `scripts/finetune.py`, replay in `train.train`, the Silent tight set) stays as built.

## Search shares sampled outcomes (owner away, 2026-10-30)

- `docs/specs/search-crn.md` (Next 4's first step, from `docs/research/depth-pilot-2026-10-30.md`). At a sampled chance node, sample `i` is drawn with an RNG seeded from `(seed, turns left, state.turn, ord, i)`, `ord` counting sampled events since the searched turn began, so sibling options see the same luck (common random numbers). Alternatives: a seed from a hash of the state (rejected: siblings differ in state, so they'd get different luck again); one shared stream (the old way: the optimizer's curse). `max_nodes` is settable from Python and `sts.search` reports `cuts`. One-turn search with `sample_k` 0 is bit-identical (no sampling).
- `data/bench/reference.json` (two-turn, k 8, 3 seeds) was recomputed under the new sampling, and its head now names it (`"sampling": "crn"`), so an old file reads as stale. Old and new agree on the best option on 96% of the 2,000 decisions; the old pick's regret under the new reference averages 0.0006. Decision metrics (ranking, regret, contested MSE) in bench results from before 2026-10-30 15:00 used the old reference; they differ slightly (the heuristic's train ranking 0.898 -> 0.924 on the quick bench), play results not at all. Reversible: git holds the old file and code.
- As built: spec folded (`git show 97b7eda:docs/specs/search-crn.md`). The seed also takes turns left, because monster rolls happen before `turn` moves on and would otherwise share `(turn, 0)` with the turn before's first sampled event. Review (spec-reviewer): no must-fix. Optional, not done: the memo is keyed on (turns left, state), so a state reached with two different `ord` values reuses the first subtree's draws (deterministic, still shared between siblings); the node count can overshoot `max_nodes` by one decision's children (cap 100 gave 124).

## Act-1 bosses as built (owner away, 2026-10-30)

- `docs/specs/act1-bosses.md` (folded; `git show 51d6d61:docs/specs/act1-bosses.md`). Hexaghost (250 HP: Activate, Divider = 6 hits of player HP / 12 + 1 fixed when chosen, then Sear, Tackle, Sear, Inflame, Tackle, Sear, Inferno repeating; Inferno upgrades every Burn and later Sears add Burn+) and The Guardian (240 HP: Charging Up, Fierce Bash, Vent Steam, Whirlwind; Mode Shift 30 counts every HP lost, then 20 block after the card in play, Close Up (Sharp Hide 3), Roll Attack, Twin Slam, back to Offensive with Whirlwind and a threshold 10 higher). New: card Burn/Burn+ (`CardDef.turn_end`: 2/4 thorns damage per copy held at turn end, after the player's turn-end powers), powers `ModeShift`, `SharpHide`, monster kinds and encounters `hexaghost`, `the_guardian`. A0 values recalled from the wiki/game, not re-fetched this session: check against slaythespire.wiki.gg if a number looks off.
- The new encounters are in `Encounter::ADDED`, not `ALL` (alternative: append to `ALL`, which changes `make_specs("boss")`'s alternation, the 9,000 golden games, `encounter_names()` and every bench generator). Reachable by name (`Encounter::from_name`, so `sts.Combat(deck, "hexaghost")` and dict specs work); the Python side lists them nowhere yet.
- Hexaghost's state lives in move ids: the cycle after the first Inferno is a second set of ids (alternative: a monster field, a codec change). Divider's per-hit damage and The Guardian's next threshold reuse `Monster.rolled_damage` (unused by both otherwise), so the codec format is unchanged; only `MONSTER_KINDS` grew.
- Sharp Hide fires after the card resolves through `Hook::after_card` (a monster's `CardPlayed by Opponent` hook that deals damage), so Iron Wave's block comes first and a card that kills its owner takes nothing back (alternative: a new trigger kind, which grows the feature vocabulary). The Guardian's shift and Twin Slam's return are code in `CombatState::lost_hp` / `after_move`, like Lagavulin's waking.
- Values checked against slaythespire.wiki.gg (Hexaghost, The Guardian, Burn; fandom refused automated fetches) by the manager: every A0 number and the move order match. Twin Slam restores Mode Shift at 30 + 10 per trigger so far (40, then 50), which is what `rolled_damage` holds. The wiki calls Close Up "Defensive Mode"; the name has no effect on play.
- Consequences to handle on merge (Python, needs a rebuilt `sts`): default-vocabulary feature widths grow (2 powers, 1 card kind), so `scripts/tests/test_contract.py`'s batch pins and the tiny pre-contract nets (no saved vocabulary) must be re-pinned on purpose; contract nets load by column name and are unaffected. Burn's turn-end damage is not encoded in features yet (a card row with trigger `OwnerTurnEnd` would show it; `trigger_OwnerTurnEnd` already exists). The rules fingerprint changes, so the solved database's cached states are not reused. Engine: all tests pass, golden games identical, codec encodings identical (`codec_golden`'s debug text re-recorded for the wider arrays).

## Act-1 bosses merged (owner away, 2026-10-30, manager run 16:06)

- Fast-forwarded main to the bosses branch (87d2124) and rebuilt `sts`.
  Checked before re-pinning: the new feature batches on `py/tests/golden.py`'s
  states equal the old ones with the new columns removed, and every new
  column is zero there (effects rows 88 -> 90, ids cards 97 -> 99, ids
  monsters 102 -> 110, ids player 32 -> 34). So the change is additive;
  re-pinned `golden_rows.npz`, `scripts/tests/data/contract/` (tiny nets and
  outputs, rebuilt by `contract_pins.py`) and `test_net.py`'s `TRAIN_PIN`
  (the wider input changes the init).
- Every real pre-contract net that can be converted already has its
  `.contract.pt` (only the three 10-24 correction-head nets lack one, which
  the converter refuses anyway). Pre-contract conversion only works while the
  default vocabulary is unchanged, so it is now closed for nets saved before
  this merge without a converted file: there are none.
- `ModeShift` is neither a modifier nor a hook power, so effects-mode nets
  don't see The Guardian's damage-until-shift counter at all;
  `test_modifier_list` names it as the one unencoded power (alternative:
  give it a dimension now, a feature change before any Guardian data
  exists). With Burn's turn-end damage (also not in features), this is a
  goal-1 gap: two new mechanics the general encoding can't express yet.
- The merge changes the rules fingerprint (39bfc65e541f073d ->
  efc07b3eaf3c0809). `db/solved.sqlite` keeps its 2.43M rows under the old
  version (nothing deleted), but its current version is empty, so
  `test_bounds.py`'s database check fails (no decisions to sample) until
  the database refills or old rows are carried over. Left failing on
  purpose, not loosened. Structural point: a whole-rules fingerprint
  throws the cache away on every content addition, even when existing
  states play identically (golden games unchanged here), which is what
  goal 1 will do constantly. Idea filed: carry rows over when the change
  is additive (alternatives: refill by solving, ~CPU-hours; fingerprint
  per encounter or per content used).

## Champion ladder spec confirmed (owner away, 2026-10-30, manager run 17:33)

- `docs/specs/champion-ladder.md`, parameters from the big-picture review's
  SPRT replay. Champion starts as the heuristic (alternative: start from the
  best-measured net, which trusts a fixed-size bench pick). The fight pool
  weights fight types as tight2 does, reported by type (alternative: equal
  weight per type). Ensembles left to a later spec (they need a new
  evaluator). All reversible: the ladder is a script and JSON files.

## Two-turn search: the node cap biases the choice (owner away, 2026-10-30, manager run 17:33)

- The depth tests ran two-turn search at the default 50,000-node cap; the
  tree is built depth-first, so options reached after the cap are scored as
  mid-turn-1 states (before the monsters attack) and win the comparison
  unfairly. All two-turn results so far carry this bias; the 400k reruns
  (jobs 0016-0018) decide whether depth is dropped. One-turn search almost
  never reaches the cap (1 in 2,202 decisions), so other results stand.
  Details: `docs/research/depth-pilot-2026-10-30.md`.

## Lean loop spec confirmed (owner away, 2026-10-30)

`docs/specs/lean-loop.md`. Chosen: test the lean loop as configs and a
`--round0` flag, without touching `learn.py`'s defaults (reversible; the
defaults change only if three seeds say so). The low-HP slice applies to
rounds >= 1 only, so round 0's pool is shared across all six runs.
Alternatives: change the defaults now (cheaper to type, but every other
caller changes with no evidence); low-HP slice in round 0 too (needs a
new 20,000-per-group pool, ~1 h, and confounds round 0). Share 0.25 at
1-8 HP is a tunable default, not an owner question.

## Coverage pilot spec confirmed (owner away, 2026-10-30)

`docs/specs/coverage-pilot.md`: held-out lead against 4 / 10 / 21
training card kinds, 3 seeds each, before any generated-content work.
Chosen over building a runtime registry and generated cards first (days
of engine work on an unmeasured premise) and over a mechanic-removal arm
first (Bash is in the starter, so removing a mechanic cleanly needs more
design; it comes next if the curve isn't flat). Pools of 5,000 games per
group keep each run ~40 min.

## Depth stays; guarded player before the engine fix (owner away, 2026-10-30)

At node cap 400,000 two-turn search with heuristic leaves beats one-turn by
+0.056 (se 0.014) on train elite+boss fights and +0.016 (se 0.015) on
held-out (depth-pilot doc), so depth is not dropped. Next measured: a
Python-side player that uses one-turn's choice where the two-turn tree cut
(fallback) or unless two-turn prefers another option by more than a margin
(guard). Chosen over building the fallback in the engine first (needs an
`sts` rebuild while the job queue holds the module, and doesn't test the
guard) and over going straight to net leaves (the held-out losses on
Lagavulin and Sentries are unexplained). The Python player matches the
engine's one-turn play fight for fight (15 of 15 checked).

## Threshold and held-card rows spec confirmed (owner away, 2026-10-30)

`docs/specs/threshold-and-held-rows.md` (Next 7): The Guardian's Mode Shift
and the large slimes' split become one general `threshold` row kind ("when
this monster has lost N more HP, these effects happen"); Burn's turn-end
damage becomes a `held` row kind with a new `damage_plain_self` scalar. New
row kinds, not new triggers, so every saved net encodes bit-identically.
No rules change (read-only `threshold::threshold` accessor in `engine/src/threshold.rs`, outside the rules fingerprint; checked against
the rules by a Rust test). Built in a worktree with its own venv while the
job queue holds main's `sts`. Alternatives: a `power_ModeShift` column
(simplest, but no training content has it, so no zero-shot help); rules as
data (cleaner for custom content, but touches the rules fingerprint; left
for the rules-engine series). Test: lean-recipe nets with and without the
rows, paired on held-out Guardian cells (baseline -0.131, MDE ~0.06).

## Lean recipe for experiments (owner away, 2026-10-30)

Lean loop result (learned-play-results "Lean loop"): without the solve
step and the database, r2 nets lead the heuristic within ~1 se of the
seed check's (train +0.017 / +0.022 vs +0.027, held-out level). New
experiments use the lean configs; `learn.py`'s defaults (`solve_games`)
are not changed yet. Alternatives: change the defaults now (affects every
caller on a result that only bounds the loss at ~0.02); keep the solve step
(~70% of a round's time for no measured gain). The low-HP slice stays
optional (no held-out effect).

## Threshold rows step 5: reuse the night's round 0 (owner away, 2026-10-31)

The reviewer's open question: `--round0` reuses an old-layout round-0 run.
`learn.learn` uses round 0's net only to play round 1's self-play games;
every round's net is fitted fresh (no warm start) on encodings made at fit
time under the current layout. So `lean-thr-s*` reuse the night's round 0
(`2026-10-27-score+branch-s0-r0-bd9a1c3`) like `lean-s*` did: round 1's
self-play games come from the same policy, and the only difference between
arms is the trained nets' layout. No fresh round 0 and no pre-merge
control build. Alternatives: fresh round 0 for both arms (adds round-0
luck to a comparison that doesn't need it, ~2x CPU); a switch to train
without the new rows (code for a one-off control).

## Data scaling spec confirmed (owner away, 2026-10-31)

`docs/specs/data-scaling.md`: cover21 (5k round-0 games per group, fresh
round 0s) trails lean (20k, one shared round 0) by ~0.04 on both halves at
round 1. Three arms (5k / 20k / 40k), three fresh round-0 seeds each, all
on the merged layout, configs only. Also found: the seed check and the
lean arms share one round-0 net across seeds, so the seed sd used for MDEs
(0.0066 / 0.0076) leaves out round-0 luck; this experiment measures sd
with it. Alternatives: rerun only lean at 20k with fresh round 0s (no
curve); skip and take 20k as given (the 0.04 rests on one round-0 net).

## Monster lookahead spec confirmed (owner away, 2026-10-31)

`docs/specs/monster-lookahead.md` (Next 7b): per monster, the expected
effects of the next and second-next move, the 4-move damage and hit rate
(the heuristic's own rollout, moved to `agent::lookahead`), and an
`intent_pending` flag for stale intents at End-turn leaves. Behind an
encoder option `lookahead`, off by default, so every pin, saved net and
queued experiment stays unchanged; config key `lookahead` for training.
Test: `lean-look-s*` vs `lean-thr-s*` r2, same shared round 0; adopt if
held-out elite+boss >= +0.045 or held-out Guardian >= +0.06 with train no
worse than -0.015. Alternatives: kind one-hot columns (no help on unseen
monsters, invites id reliance); full spec 9 now (800-1,500 lines, flips the
rules fingerprint); columns always on (re-pins everything and changes
data-scaling and lean-thr runs mid-series); replacing the stale `intent_*`
columns with the pending roll (changes today's columns' meaning).

## Coverage pilot read: generated content moves up (owner away, 2026-10-31)

Held-out lead at round 1 rises with training card kinds (4 / 10 / 21:
-0.074 / -0.039 / -0.025; train -0.054 / -0.023 / -0.010), falling returns
per doubling, both halves alike (learned-play-results "Coverage pilot").
Per Next 6's rule the curve isn't flat, so a runtime-registry +
generated-cards spec moves ahead of the fidelity specs in
`docs/specs/queue.md`, behind data scaling (lean at 20k leads cover21 at
5k by ~0.03, larger than 10 -> 21 kinds). Alternatives: a mechanic-removal
arm first (cheaper, but the curve already says breadth pays; it can run
later on generated content); keep the fidelity order (the curve says
content breadth buys more than fidelity of existing content would).

## Monster lookahead as built (owner away, 2026-10-31)

Branch `monster-lookahead`, steps 1-4 (`docs/specs/monster-lookahead.md`).
Deviations from the spec, all small: `heuristic::damage_rate` is now `pub`
(the rate test compares against it from `engine/tests`; no logic change);
`scripts/rung4.py` reads `learn.feature_mode` like `learn.py` (one line, so
a rung-4 config with `lookahead` encodes the same way); the option is
detected in Rust (`make_encoder`) from a net's monster columns as well as
passed by `stsnet`, which also covers `sts.NetEvaluator`. Speed: off, the
encoder is within 3% of main's (best of 25, 40.2 vs 38.7 ms on the fixed
set); on, about 2.9x (~117 ms), over the spec's 25% budget, which was a
guess. The cost is `move_distribution` (~2 us per call, in the
fingerprinted `chance.rs`); memoising by history within one rollout halved
it (28 -> 15 us per monster). Not optimised further: the long run's round
minutes against lean-thr's say whether it matters (fitting reads cached
features; only self-play and the bench encode live). Alternatives for later:
a cheaper `enumerate` (rules file, fingerprint unchanged if the change is
code-only), or caching by monster kind and history across a batch.

## Two-turn player: fallback, no margin (owner away, 2026-10-31)

Held-out elite+boss at cap 400k (depth-pilot doc "Fallback and guard
players"): using one-turn's choice wherever the two-turn tree cut gains
+0.044 (se 0.011) over plain two-turn, so two-turn heuristic search now
beats one-turn by +0.061 on held-out. A margin guard (0.05) on top costs
-0.025, -0.14 on Slime Boss. Decided: the two-turn player is fallback with
no margin, for the ladder and the teacher check. Alternatives: margin
sweep at 0.02 / 0.1 (rejected: the margin's best case is under the 0.02
bar, its worst is large); build the fallback into the engine now (later,
when an `sts` rebuild fits a queue gap; the Python player matches it).
Reversible: one flag in `depth_paired.py`.

## Registry-lite spec confirmed (owner away, 2026-10-31)

`docs/specs/registry-lite.md` (review direction 6, Next E). Provisional:
generated powers and power cards load from a JSON pack at runtime and bind
per combat to 8 reserved power slots and 8 reserved card slots stored in
the combat state. Alternatives: widen ids to u16 with sorted inline lists
(spec 10's plan; re-pins everything, slower clones), one global slot table
per process (caps a training run at 11 generated powers). Power cards
granting to the player only; no new feature columns (ids mode sees
generated content as unknown); split by (trigger, effect-kind) pair with
official training pairs counted as train, so turn start -> +Strength is a
test mechanic like Demon Form. With no pack loaded every golden game, pin
and the fingerprint stay identical. Built in a worktree with its own venv.

2026-10-31, step 2 (owner away): the solved-DB fingerprint can't stay
identical. `solvedb/src/fingerprint.rs` hashes the rule files' source text
(state.rs, cards.rs, powers.rs, hooks.rs, ...), and step 2 must edit them,
so it moves from `efc07b3eaf3c0809` to `3568b919318ba6e0` at this step
(and again at any later rule-file edit). What stays identical is
`content_tables()` (official names only, now pinned in
`solvedb/tests/fingerprint.rs`: FNV `7abf2c1218fcd614`), the codec bytes and
golden file, and the rules version (`golden.txt`). The solved DB was
already behind the current fingerprint (ideas#72), so nothing live
depends on it. Also: play timing with no pack is level with the pre-step
build (process CPU time on a loaded machine: random play -2% to -4%,
heuristic search -4% to -6%, both within noise), after replacing a chained
iterator in the hook loop with a slice (`Binding::powers_in_play`).

## Rate features spec confirmed (owner away, 2026-10-31)

`docs/specs/rate-features.md` (Next D, review direction 4 arm (a)), from
the Demon Form probe: the r2 nets value playing Demon Form 0.09-0.15 below
their best option where the heuristic plays it 41% of the time. Provisional:
the heuristic's `hook_rates` sums become named per-entity columns
(`rate_*`, `grant_rate_*` on cards that grant powers), plus a turns-left
estimate and two rate x turns products, behind an off-by-default `rates`
option. Alternatives: raw rates only (leaves the product to the MLP);
sandbox-simulated rates (arm (b), later). Builds after registry-lite
merges (both edit features.rs). Also from 0041b: one self-play round adds
~+0.02 over round 0 (2.5 se over 9 runs), so rounds stay in the recipe
(Next A's rule).

## Depth with net leaves passes: distillation next (owner away, 2026-10-31)

Job 0044b: two-turn fallback search with the champion's net at the leaves
beats one-turn net play by +0.055 (se 0.013) on held-out elites and bosses,
over the +0.02 bar set before the run; depth and the net's gains add
(net two-turn 0.591 vs heuristic one-turn 0.498 on the same fights). So
the next depth step is a spec that distils two-turn values into the net
(review 2026-10-31 direction 3), not more test-time depth runs. Two-turn
self-play was the alternative; at ~145x the time per decision it would
cut games per round too far. The train half (0057b) still runs and sizes
the gap there.

## Threshold rows: no transfer detected, layout stays (owner away, 2026-10-31)

lean-thr vs lean (jobs 0042-0044, 0044c): held-out Guardian +0.038 (se
~0.047), under the spec's 0.06 bar; tight2 and the other bosses within
noise. Threshold rows stay in the merged layout (removing them would
re-pin everything for no measured gain), but "shared primitives transfer
zero-shot" is not supported by this test. Goal 1 work leans on the rate
features (Next D) and generated content (Next E), where the measured
gaps are. Alternative not taken: more seeds to shrink the MDE (6 more
lean-thr runs, ~5 h) for a question whose best case is a small gain.

## Distillation spec confirmed (owner away, 2026-10-31)

`docs/specs/distill-two-turn.md` (Next C, review direction 3 step 3).
Provisional: in rounds >= 1, up to 10,000 elite and boss decisions per
round are re-searched two turns deep with the playing net at the leaves
(cap 400k, fallback on cuts), and their options' `rank_value` becomes the
two-turn values; value targets unchanged. Alternatives: value-target
blend (later arm); 20k states (halved for round time; a config number);
champion as fixed teacher (mixes nets within a decision). Read: three
`lean-distil-s*` nets paired against `lean-thr-s*`, adopt at >= +0.03 on
elites + bosses on both halves with hallways >= -0.015.

## Rate features built and merged (owner away, 2026-10-31)

Merged 1516994 (review: nothing must-fix). As built: `turns_left_est` is
the heuristic's own rounds-to-kill estimate (`heuristic::turns_left_estimate`,
capped 50), so no fallback formula; `grant_rate_*` counts only powers a
card applies to its user (Ironclad cards apply no hook powers to
monsters, and mixing an enemy's rates into the user's columns would blur
them). Encoding with rates on is ~7x slower (one heuristic estimate per
state), so search with a rates net is slower too; the first runs
(0049b-d) will show round minutes. Read `lean-rates` against `lean-thr`
(the columns-off twins on the merged layout), not `lean`.

## Generated-power training arms spec confirmed (owner away, 2026-10-31)

`docs/specs/gen-training-arms.md`. Arms lean-gen16 / lean-gen128 (3 seeds)
= lean-thr plus 16 / 128 generated train powers (generator seed 2, 19 /
176 powers, nested), content_share 0.5, reusing the night round 0; control
is the existing lean-thr r2 nets. Read net against net, paired by cell and
seed index, on a 12-fights-per-cell version of the first check's bench.
Alternatives: a fresh round 0 with content (more content exposure, but
fresh round 0s double the seed sd and need new controls); arms judged
against the heuristic (rejected: the first check showed it is blind to
most generated mechanics); fixing the generator's pricing first (deferred:
pricing matters for realism, not for whether breadth transfers). Rule:
gen128 >= +0.02 (> 2 se) on the generated set with the train half >= -0.015
-> content joins the experiment recipe; within +-0.02 -> goal-1 work moves
to per-mechanic features and adaptation.

## Hang and memory fixes (2026-10-31, owner present)

- Cause, from a six-lens review with a skeptic per finding (owner asked
  after 0049e hung ~3 h and 0049d / 0052 died out of memory): net search
  scored all of a search's leaves in one feature batch (several GB at a
  400k-node two-turn search; every failed allocation in the logs was a
  feature width x 2^k); jobs used every thread inside `sts.run` whatever
  `--threads` said (`STS_JOB_THREADS` was set but unread); the runner
  checked free memory only at a job's start, so jobs admitted in a light
  phase peaked together later; a dead `multiprocessing.Pool` worker hung
  its parent, the runner never ended a stuck job and freed its slot while
  children still held RAM; teacher and depth runs saved only at the end.
- Fixes (merged 0e0a3ff): `NetEval::evaluate` scores leaves 4,096 at a
  time (bit-identical: nothing in `forward` or the encoder spans the
  batch; Rust test on real two-turn leaves, full and gathered layouts,
  and old vs new build on three searches); Rust `default_threads` and
  Python `stsnet.job_threads` follow `STS_JOB_THREADS`; `learn.teach`
  writes `teacher-<key>.npz.partial.npz` every 500 decisions / 10 min and
  resumes from it, `depth_paired.py` appends one line per fight to
  `<out>.partial.jsonl`; `registry.play` / `selfplay` drop `states` unless
  `keep_states=True` (datasets byte-identical) and `write_dataset`
  streams; `demon_form_probe.py` uses `ProcessPoolExecutor`;
  `depth_paired.probe` has a turn limit. Job runner: `--mem-gb` is a
  reservation (sum of running jobs' + this <= total - 1 GB) plus a live
  free-memory check; impossible or malformed jobs
  are refused; each job runs in a Job Object (no kill-on-close, so jobs
  outlive the runner) and ends only when its tree is gone; `jobs.py kill`;
  `suspect` events; ids from file names; adopted jobs end as
  `ended-unknown`. This supersedes the job-queue entries where they
  differ ("It never kills anything" no longer holds: it kills on request).
- Measured after the rebuild: a 145k-node, 45k-leaf two-turn search peaks
  at 0.76 GB of commit (teacher workers averaged 3.6 GB before, up to 9).
- Not done (optional, from the review): store each search leaf once
  (`search.rs`, ~0.3-0.6 GB per 400k search); Pool workers exiting when
  their parent dies; pid reuse checks after a reboot (creation time);
  `jobs.py status` crashing on a malformed pending job; quadratic chance
  outcome merge in `chance.rs` (dormant: no solve steps run); the py
  crate's Rust test isn't in the workspace's default members (needs
  `PYO3_PYTHON` and Python313 on PATH); `depth_paired`'s summary crashes on
  a one-fight group.

## Rate features: off by default for now, Guardian cost hunted (owner away, 2026-10-31)

lean-rates vs lean-thr (results doc "Rate features"): the spec's rule
fails (held-out bosses +0.022 on `tight_bosses`, +0.055 on tight2, bar
0.06; train bosses -0.027, bar -0.015), so `rates` stays off by default.
But the split by deck is sharp: on boss fights whose deck holds Demon Form
the rate nets gain +0.10 to +0.20 (all seeds; they now play it as often
as the heuristic), while Guardian fights without it lose about -0.06
(against lean) to -0.10 (against lean-thr), on both halves; power-card
timing is not the cause (probe). So the feature is right in kind and has
one side effect. Next: find the Guardian cost (decision-diff probe, a
fork of this run), fix it, re-run three seeds, and adopt if the rule then
passes. Alternatives not taken: adopt now on the Demon Form gain (breaks
the pre-registered rule, and costs the train half); drop rates (throws
away the only feature that moved an unseen mechanic this much).

## Rate features: more seeds before a Guardian fix (owner away, 2026-10-31)

The Guardian cost rests on three seeds that disagree widely (train
Guardian, rates minus thr: -0.001, -0.204, -0.120; sd ~0.10, so the mean
-0.109 is under 2 se), on a boss no net trains on, where each net lands
wherever its training luck puts it. The decision diff shows *how* two
seeds' nets differ, not that the difference is systematic. So before
building a fix (damage-to-threshold feature, Slime Boss diff, two-turn
play), two more paired seeds of each arm run (lean-thr / lean-rates s301,
s401; jobs 0057a6a-d, ~30 min each), then `boss_lead.py` on them
(0057a7a). With 5 pairs the se on the Guardian diff falls to ~0.045. Read:
if the 5-seed Guardian diff (both halves) stays below -0.05, the cost is
real and the fix hunt goes on; if it lands within ~1 se of 0, apply the
spec rule to the 5-seed means and adopt rates if it passes. Alternatives
not taken: build the threshold feature now (may fix noise); re-run three
fresh seeds of rates only (loses the pairing).

## Data scaling: 80k next (owner away, 2026-10-31)

40k beats 20k by +0.013 train / +0.009 held-out (3 paired seeds, se
0.004 / 0.003), and per doubling the gain isn't shrinking (results doc
"Data scaling"). That is the "clear slope" the plan asked for, so 80k
runs, 3 seeds (0057a9a-c, mem 6 GB, ~150 min each), queued after the
distillation runs and before the long 0057b depth run. Defaults stay at
their current `n_train` until 80k reads. Alternatives not taken: raise
the default now (one more point costs ~7 h and tells whether the slope
holds); stop at 40k (each doubling is still worth ~+0.01, more than any
label-side change ever gave).

## Generated-power arms: no transfer, content stays out of the recipe (owner away, 2026-10-31)

On 326 held-out cells with an unseen generated power card, nets trained
with 128 generated powers play -0.006 (se 0.010) against the same recipe
without them; 16 powers -0.004 (results doc "Generated-power training
arms"). Per the spec's rule that is "no transfer at this scale": content
does not join the experiment recipe, and goal-1 work moves to
per-mechanic features plus an adaptation burst (a short fine-tune on a new
mechanic's games). The generator and `content` keys stay (cheap, tested,
needed to make adaptation tasks). Alternatives not taken: a bigger arm
(512 powers, share 1.0): 16 -> 128 showed no slope, so a bigger one is
unlikely to clear the MDE and would cost ~3.5 h; keep content in the
recipe for realism: it costs ~0.04 on elites.

## Review 2026-10-31b: queue re-ranked (owner away, 2026-10-31)

After the second big-picture review (`docs/research/big-picture-2026-10-31b.md`):
a ladder job for 12 newer-recipe nets against the champion and an ids
twin probe (`ids5k-s1`) jump the queue; a held-out hallway depth read is
added; data80k drops to 2 seeds (s201 parked in `jobs/parked/`; the
seeds pair at corr 0.87-0.99); the train-half depth job drops from 8 to 4
fights per cell (~5.5 h -> ~2.8 h; still ~3 se for the expected +0.055).
The seed sd used for MDEs is now 0.010 train / 0.013 held-out.
Alternatives not taken: running all three data80k seeds (one more
doubling point costs 2.5 h and pairing already decides it); dropping the
train-half depth job (it is the only check of the fallback rule on fights
it wasn't chosen on). Not done, left for the owner: re-scoping the
rules-engine series.

## Rate features: Guardian cost real but smaller; test depth, not a feature fix (owner away, 2026-10-31)

On 5 paired seeds the rate nets lose -0.082 (se 0.043) on train Guardian
fights and -0.052 (se 0.029) on held-out Guardian fights without Demon
Form, and gain +0.12 to +0.17 on Demon Form fights (results doc "Rate
features on 5 seeds"). The rule (held-out boss >= +0.06, train >= -0.015)
still fails, so rates stay off. Instead of hunting a feature fix, the
next test is whether two-turn search removes the hesitation (job
0057a6i). Alternatives not taken: a damage-to-threshold feature (another
hand-written per-mechanic column, which the review argues against);
adopting rates anyway for the Demon Form gain (fails the train bar).

## Top-3 two-turn player: test without a Rust filter (owner away, 2026-10-31)

Next 3 asked for a root-option filter in `engine/src/search.rs` so
two-turn search could be limited to one-turn's top few options. For a
*quality* test that isn't needed: `depth_paired.py`'s guarded arms already
hold both searches' values for every root option, so a `topk` policy picks
two-turn's best among one-turn's top `--top-k` (fallback on cuts, as
before). The Rust filter would only save nodes, and the puzzle check found
no saving at a median of 4 options; it waits until topk wins. Every
guarded arm now also counts `outside` (uncut decisions where two-turn's
own best lies outside one-turn's top k), the ceiling on how often topk and
fallback can differ. Alternatives: build the Rust filter first (slower,
same answer); skip (the puzzles' 0.0046 vs 0.0061 regret is a real hint
and the test is one job).

How it moves goal 2: the two-turn player is our strongest player and the
distillation teacher; a better override rule raises both. Pre-registered
read (job 0057a8z3, `results/depth/paired-net-held_out-cap400k-topk3.json`,
same args as `paired-net-held_out-cap400k-fallback.json`, so fights pair by
index): topk3 minus fallback on held-out elite+boss wins, per-fight paired.
>= +0.02 (about 2 se) -> run the same on the train half (pc4, against
0057b) as the independent check before topk replaces fallback; within
+-0.02 -> no change, fallback stays (simpler); <= -0.02 -> drop the idea.
Also read the `outside` share: under ~2% of decisions means the arms can't
differ by 0.02 and the result is a tie by construction.

## Depth repairs unseen powers? A check on fresh fights (owner away, 2026-10-31)

Post hoc split of the held-out depth runs (depth doc "Where net-leaf depth
gains"): net-leaf two-turn gains +0.076 on fights with an unseen power card
vs +0.012 without; heuristic leaves don't show it. Queued one
pre-registered check on fights not used for that split (0057a9a5, held-out
tight_bosses, ~5 h at 4 threads, after data80k s1, ahead of 0057b and the
lean-look runs). Rule in the depth doc. Alternatives: no check (keeps a
2-se post hoc claim in the docs unchecked); a smaller run (MDE too large
to say anything). Placed after data80k s1 so the product line keeps
moving.

## Distillation closed; rates retested under depth (owner away, 2026-10-31)

Distillation over 3 seeds: elites -0.030 train / -0.035 held-out vs
lean-thr, ladder s101 and s201 fail. Below its +0.01 bar, so the
search-labelled scale-up (Next C) is dropped; the code stays (off unless
a config asks). Alternatives: a 4th and 5th seed (the mean is negative on
both halves, so more seeds can't plausibly lift it to +0.01); a top-k
teacher (waits for the topk3 read, 0057a8z3).

Rate features: two-turn search closes the rate nets' Guardian cost from
-0.162 to -0.031 over 3 seeds (results doc). So the adoption question
changes from "fix the Guardian cost" to "do rates help the two-turn
player": job 0057a8z4 plays rates and thr r2 nets at one and two turns on
all tight_bosses bosses, both halves. Rule (same as the spec, applied to
two-turn play): rates2 - thr2 held-out boss >= +0.06 and train boss >=
-0.015 -> spec rates on for the two-turn player (one-turn defaults
unchanged); else rates stay off. Hallways and elites at two turns aren't
in this run (cost); a pass needs them checked before any default changes.
Alternatives: hunt a one-turn Guardian fix (a damage-to-threshold
feature; costs a spec and 3 retrains, and depth already does the job for
the strongest player); drop rates (throws away the Demon Form gain).
Placed first in the queue because it needs 2 GB and data80k's 6 GB
reservation couldn't start beside topk3 anyway.

## Oracle arm for the generated-power bench (owner away, 2026-10-31)

The gen arms (16 / 128 generated train powers) showed no transfer to
unseen generated powers. That null means something only if the bench can
show learning at all. Oracle arm: lean-thr plus the bench pack's own 43
test powers in training (`content_split: "test"`, new config key, absent
by default so all datasets stay bit-identical; test in
`test_content_selfplay.py`), share 0.5, night round 0, 3 seeds
(`configs/lean-oracle-s*.json`, jobs 0057a8z5-z7, ~45 min each; play
0057a8z8).

How it moves goal 1: it tells whether a short adaptation burst on a new
mechanic's games (the next goal-1 step) can be measured on this bench, and
gives its ceiling. Read: `gen_powers_read.py arms --bench
data/bench/gen_powers12.json --control lean-thr --arms lean-oracle`, same
as the gen arms. Oracle minus control >= +0.03 (about 3 se): the bench
works and the gen-arm null is a real no-transfer; spec the adaptation
burst. Below +0.03: the bench (or share 0.5) can't show learning on these
powers; fix the bench before any more generated-content tests.
Alternatives: skip (keeps an unexplained null); a bigger share (a second
knob; only if this one fails).

## Top-3 two-turn player: no change (owner away, 2026-10-31)

0057a8z3 read (depth doc "Top-3 player vs fallback"): topk3 minus
fallback on held-out elites+bosses is +0.005 (se 0.009), outside share
3.4%. Inside the pre-registered +-0.02 band, so the fallback player stays
(simpler) and the Rust root filter is not built. No train-half check.

## Rates under depth: rule fails, rates stay off (owner away, 2026-10-31)

0057a8z4 held-out half: rates2 - thr2 = +0.033 (se 0.015) on held-out
bosses, under the +0.06 bar (results doc "Rates vs thr under two-turn
search"). Rates stay off by default; the train half is read for the record
only. The columns stay in the code (off), since they cost nothing off.
Alternative: lower the bar post hoc to call +0.033 a pass (rejected:
pre-registered, and 3 seeds' training luck is ~0.013 per arm).

## Prior art: search in stochastic card games (owner away, 2026-10-31)

`docs/research/search-stochastic-cards.md` (8 angles, ~64 cards, 7 sources
verified). Provisional framing: the product is net + search at play time;
the net is trained to be a better leaf. First step: a seed-net ensemble
as the leaf evaluator (no training), checked on the ladder and in two-turn
play. Alternatives listed in the report (a depth gate; cost-sensitive
distillation targets). Also checked: two-turn search does not see the
draw order (it samples a multiset pile with its own RNG), so the depth
gain is not clairvoyance.

## Ensemble evaluator spec confirmed (owner away, 2026-10-31)

`docs/specs/ensemble-evaluator.md`: search may score leaves with the mean
of several NetEvaluators (`a.pt+b.pt+c.pt` in any evaluator spec). First
test: champion + its seed twins on the ladder and in two-turn play; read
rule in the spec. Mean of scores rather than of raw outputs; no training.
Alternatives: min-over-members (pessimism, the MBRL paper) or mean + k*std
(Milos et al.), kept for later if the mean helps; skip ensembles (the
prior-art scan and three earlier proposals favour trying them).

## Ensemble evaluator: no change at two turns; spec folded (owner away, 2026-11-01)

Built as specified (4fda986, fecd817): any evaluator spec may join net
paths with `+` (`a.pt+b.pt+c.pt`); search scores each leaf with the mean
of the members' scores (mean of scores, not of raw outputs, so HP-loss and
score nets can mix); `[]` and a list holding `"heuristic"` raise; a single
path containing `+` that exists as a file is not split. Members must share
the feature layout (checked in Python, not Rust).

Read by the spec's pre-registered rule: (a) ladder (test 0018) lead +0.002,
SPRT fails -> not a one-turn product candidate; (b) two-turn ensemble minus
two-turn champion on held-out elites + bosses +0.008 (se 0.007, 1336 paired
fights) -> within +-0.02, **no change**: the champion alone stays the
two-turn evaluator. At one turn on the same fights the ensemble gains
+0.021 (se 0.008), so depth absorbs most of what averaging buys (results
doc "Ensemble of three seed nets under two-turn search"). Min-over-members
and mean + k*std not tried (they were the follow-ups if the mean helped).
Spec `docs/specs/ensemble-evaluator.md` deleted (git keeps it at d86d933).

## Oracle arm read: the 1-copy bench is blind, the 3-copy bench sees a little (owner away, 2026-11-01)

Oracle (lean-thr + the bench's 43 test powers, share 0.5, 3 seeds) minus
lean-thr on unseen-in-control generated powers: `gen_powers12` +0.001 (se
0.012); `gen_powers12c3` (new `build --copies 3`: the swapped card at 3
copies in both sets) +0.013 (se 0.009), all seeds positive, bosses +0.064.
Both under the pre-registered +0.03, so: (1) the generated-power arms'
"no transfer" (decisions "Generated-power arms: no transfer") is not
evidence; it was measured on a bench where even the oracle shows nothing;
(2) generated-power tests use the 3-copy bench from now on; (3) before the
adaptation-burst spec, check that concentrated training on a power moves
the bench: the burst itself is that check (fine-tune the champion on games
holding one or a few generated powers, read those powers' cells on the
3-copy bench). Alternatives: rerun the gen arms on the 3-copy bench (cheap,
6 nets x 2 min; worth doing alongside, since gen128 might show a little
transfer there), a bigger oracle share (one more 3-seed run, ~2.5 h, still
diluted over 43 powers), or drop generated-power work (goal 1 needs a way
to measure adaptation, so no).

## Depth repairs unseen powers: the check holds (owner away, 2026-11-01)

Job 0057a9a5 (fresh held-out tight_bosses fights): net-leaf two-turn gain
on decks with an unseen power minus decks without is +0.096 (se 0.039,
clustered by cell), above the pre-registered +0.05 bar, so the hypothesis
stands. It rests on Hexaghost (+0.149); the Guardian gains from depth with
or without a power (+0.168 / +0.144). Overall two-turn beats one-turn by
+0.118 on held-out bosses. The train half (0057b) gains +0.035 (se 0.020),
two thirds of held-out's +0.055. Depth doc, sections of 2026-11-01.

What it changes: the two-turn player (net leaves, fallback) is the player
to measure new-mechanic work with, including the adaptation burst (a burst
that helps one-turn play may be redundant with what depth already
repairs; read both). No default changes: one-turn stays the self-play
player for cost (~145x). Alternatives: a second fresh check on elites with
unseen powers (costs ~5 h; would show whether it's more than Hexaghost);
treat the pass as Hexaghost-only (too narrow: Demon Form fights gain
+0.207, pooled over both bosses).

## Adaptation burst spec confirmed (owner away, 2026-11-01)

`docs/specs/adaptation-burst.md`: `finetune.py` learns generated-pack
content (Ironclad train decks plus 1-2 of a few generated power cards,
games played by the parent net), and the burst is measured on the 3-copy
bench as target-card gain minus other-card gain in the same nets, with the
original fights as a forgetting check. Rule: contrast >= +0.04 and >= 2 se,
originals >= -0.015. Alternatives: a no-content fine-tune control arm (more
CPU, same question), heuristic-played games (it can price only ~25% of the
powers), a burst inside `learn.py` rounds (bigger change, off limits).
Provisional: net player and the 8 target cards.

## Data scaling: 80k shows no gain over 40k; no night recipe at 80k (owner away, 2026-11-01)

data80k minus data40k, r1 tight2, 2 paired seeds: +0.004 train / +0.003
held-out (seeds disagree on held-out, +0.024 / -0.019), against +0.009 to
+0.013 for 40k - 20k on the same seeds; both 80k nets fail the ladder
(-0.018, -0.024). The rule in manager.md Next 1 / B ("if 80k - 40k is
again ~+0.01, run the night recipe at 80k") fails, so the night80k
champion candidate is not run and the default `n_train` stays. Results
doc "data80k vs data40k, 2 seeds". Alternatives: a third seed (s201 is
parked; ~1 h uncontended) to firm up the flat slope (cheap, but even a
+0.01 third seed wouldn't move the 2-seed mean above the bar); run
night80k anyway as a champion candidate (~2 x 3 h; the data lever looks
spent at 40k, so the expected lead over the champion is under the
ladder's reach); raise `n_train` to 40k for new experiments (round 0
costs ~2x the 20k run's time for ~+0.01; worth it only for product
candidates).

## Review 2026-11-01: stop list adopted (owner away, 2026-11-01)

The big-picture review of 2026-11-01 (`docs/research/big-picture-2026-11-01.md`)
found depth the only recent lever that cleared noise several times, and the
one-turn tight2 held-out lead flat (within about ±0.01) across label, loss,
curriculum, content and data arms. Adopted, as trimmed by the skeptics: no
more training-side arms judged on one-turn tight2 held-out lead or the
Amendment 5 gate (the gate stays a sanity floor); no data scaling past 40k
(data80k s201 stays parked; 0061 score-r0 parked); no more exact-solver,
endgame-puzzle or exact-label work (because label work lowered MSE several
times and never moved play, not because of the review's "1% ceiling",
which the skeptics showed is a lower bound); no generated-content training
arms or new hook-row columns until depth on generated content is read; no
more tuning of the two-turn player's pick rule, margin, sample_k or
ensembles; no effect sizes read where a ladder SPRT stopped; val MSE,
regret or err² no longer count as evidence for a training change;
from-scratch recipe arms only when the expected effect is at least twice
the MDE, or the arms are paired with a measured correlation of 0.9 or more;
`test_sweep` out of the default test set. Work moves to measurement (ladder
fixes, HP lost at run-level start HP, an Act gauntlet) and cheaper, deeper
search. Alternatives: keep running paired recipe arms at 0.01 (allowed
when pairing is measured, but low value now); adopt the whole synthesis
including the rules-engine re-scope (left to the owner: it reverses the
series' design rule); ignore the review (the queue had already run out of
arms that could move play). The skeptics also qualify decisions "Depth
repairs unseen powers: the check holds": on the same boss bench depth gains
as much on train as on held-out (+0.133 vs +0.129 over six lean nets), so
depth repairs mis-pricing where one-turn play is weak, not novelty as such.

## Monster lookahead: no gain, stays off (owner away, 2026-11-01)

lean-look minus lean-thr over 2 paired seeds (results doc "Monster
lookahead, 2 seeds"): held-out elites + bosses +0.020 against the spec's
+0.045 bar; the named slices Lagavulin +0.021 and Gremlin Nob -0.014,
under the +0.04 bar set for this read. The seeds disagree (+0.060 /
-0.020), so the reading is seed luck. The columns stay off by default and
we record that move patterns aren't the Act-1 bottleneck for one-turn
nets. s201 (0060) finishes but no third seed is added. Alternatives:
wait for s201 (can't move a +0.02 mean past +0.045), test lookahead under
two-turn search (search already sees monster moves; not worth CPU now).

## Ladder v2 spec confirmed (owner away, 2026-11-01)

`docs/specs/ladder-v2.md`: the champion's results are cached (key: net
hashes, `sts` module hash, limit, mode; run-HP also bands and seed), tests
rotate over 8 block slots so they no longer all share one champion draw
but still reuse the cache, `--fixed-n` reports a lead at a fixed number of
pairs beside the SPRT verdict, and `ladder.py runhp` scores HP lost at
run-like start HP (hallways 70-100% of max, elites and bosses 40-100%,
death = start HP + 30) against the heuristic. Alternatives: a fresh block
for every test (no cache reuse), the informative fight book (later, if
ladder cost matters).

## HP weight spec confirmed (owner away, 2026-11-01)

`docs/specs/hp-weight.md`: run-HP showed every net losing ~2x the
heuristic's HP at the same win rate, mostly by dragging multi-monster
hallways out (thugs 6.4 vs 3.8 turns). Config key `hp_weight` w scores a
won outcome 2 - w x HP lost / 100 (floor 0.1) in labels only; the engine
score and search's finished-combat scores stay unweighted. Arms w = 2 and
4, 2 seeds each, own round 0, judged on run-HP against lean-thr paired by
fight (pass: >= 2.0 HP saved on the mean, >= 1.0 each seed, <= 20 extra
deaths per 2000, tight2 held-out lead drop <= 0.02). Alternatives: weight
in the engine's score (rebuild, changes every measurement), a turn-count
feature (doesn't price HP), switch 6 histograms (null before, on tight
wins). Review notes: `branch_gap` acts on the weighted scale, so arms may
branch more (small confound); `label_scale` warnings grow with w.

## Selective two-turn search: fails its first check, not merged (owner away, 2026-11-01)

Branch `worktree-agent-ad3bc362ec97b5aef` (spec `docs/specs/selective-depth.md`
there). Restricting turn 2 to one-turn's top-3 root options saves ~3% of
nodes: different first actions reach the same end-of-turn states. The
built variant, `end_k` (search turn 2 only under the K best-scored
end-of-turn states), on 205 held-out elite/boss decisions: K 2 is 2.4x
faster in total (1.9x median) at 90% agreement, K 8 1.4x at 99%; the rule
(>= 2x median and >= 95%) fails for every K. The full fallback player
stays; the branch is kept unmerged (merging needs an `sts` rebuild).
Alternatives: merge anyway for a strength test at K 4 (90 min; a pick that
differs isn't necessarily worse, and K 4 hits the cap far less often), or
cut cost elsewhere (fewer sample_k, bosses-only depth).

## Burst8 s1 promoted to champion (owner away, 2026-11-01)

burst8 s1 / s101 (champion fine-tuned ~10 min on varied games holding 8
generated power cards) pass the ladder (+0.011 at fixed n 6000, both),
and the no-card control fails (-0.005), so the gain is the generated
content. burst8 s1 is the ladder champion now (champion.json keeps the
previous). Reversible: write the old path back. Alternatives: wait for the
train-split burst (cleaner for goal-1 benches; queued and will be laddered
against the new champion), or keep the 10-29 net until run-HP is read
(queued 0059d8). The adaptation-burst spec's own rule stays "between"
(+0.036); this decision is about the product, not that rule.

## Burst ratchet and more cards queued (owner away, 2026-11-01)

Run 06:07 queued 6 short fine-tunes (0059g1-g6), all on train-split
generated power cards so `gen_powers12c3` stays clean for them:
- `ratchet8tr-s1/s101`: a second burst on the new champion (burst8 s1)
  with 8 fresh train cards (none of burst8tr's), game_seed 32.
- `burst16tr-s1/s101`, `burst32tr-s1/s101`: from the 10-29 net (burst8's
  own parent) with 16 / 32 train cards (burst8tr's 8 plus fresh ones).
Read (pre-registered): `ladder.py test --no-promote --fixed-n 6000`
against the current champion (burst8 s1). A ratchet that passes on both
seeds is promoted (the better seed). More cards: compare each net's
fixed-n lead with burst8tr's (same parent, same setup, 8 cards); if 16 or
32 beat 8 by >= 0.01 on the mean of 2 seeds, more cards becomes the burst
default. Alternatives: wait for burst8tr's read first (it ends ~20 min
earlier; these jobs are ~5 min each, so waiting buys little).

## Run-HP at two turns (owner away, 2026-11-01)

`ladder.py runhp --two-turn` plays the candidate net with the fallback
two-turn player (node cap 400k, sample_k 4; the opponent stays one-turn,
cached), resuming from `runhp/two-<sha>.partial.jsonl`. Queued 0059h1:
the champion (burst8 s1) at two turns, 2000 pairs, the same fights as its
one-turn run-HP 0005. Read (pre-registered): saved HP = 0005's cand_lost
minus 0059h1's, paired by fight (cell, seed). >= 2.0 HP: depth is the HP
lever, and the product's run-HP is measured at two turns from now on;
< 1.0: the bleeding isn't a search-depth problem (with the hp_weight read,
points at a tempo/turn feature). Between: report. Alternative: a tempo
feature first (needs a spec and retraining; this check costs ~1.5 h CPU
and no build).

## HP weight 2 passes; burst with HP weight queued (owner away, 2026-11-01)

lean-hpw2 saves +2.44 HP per fight over lean-thr (2 seeds, each >= 1,
no extra deaths, held-out lead within the bar): the spec's rule passes
(results doc "HP weight: w = 2 passes"). So hp_weight 2 joins the product
recipe. Done the cheap way first: `finetune.py` takes `hp_weight` (weights
the burst's targets, replay and validation), and `burst8hp2-s1/s101`
(burst8's games and seeds, labels weighted) are queued. Read
(pre-registered): run-HP paired with burst8 of the same seed (0005, 0059a3)
and `ladder.py test --fixed-n 6000 --no-promote` against the champion.
Promote the better seed when it saves >= 2.0 HP on the mean of 2 seeds
and its fixed-n ladder lead is >= -0.005 (win rate no worse within noise):
the product then trades nothing for HP. Alternatives: retrain the night
recipe with hp_weight 2 (hours of CPU, two-seed MDE ~0.02 on win rate) or
keep the champion and only report HP (ignores goal 2's main cost).

## Burst8hp2 s1 promoted; promotion now also checks run-HP (owner away, 2026-11-01)

burst8hp2 passed the pre-registered rule (+2.19 HP saved, ladder +0.006 /
-0.000), so s1 is the champion (results doc "Burst with HP weight
promoted"). Reversible: write burst8 s1 back into `champion.json`. From
now on a candidate is promoted only if it also loses no more than 1.0 HP
per fight more than the champion on run-HP (paired, 2000 pairs): win rate
alone would let an unweighted net (the ratchet8tr / burst16tr / burst32tr
jobs queued before this) undo the HP gain. Those unweighted jobs are read
for what they say about cards (vs burst8tr); a ratchet with hp_weight 2 on
the new champion (`ratchet8trhp2-s1/s101`, 0059g71/g7101) is the product
candidate. Alternative: weigh HP and win rate into one ladder score (needs
a spec; HP and win trade at no agreed rate yet).

## Bursts: ratchet and more cards closed (owner away, 2026-11-01)

Ratchets (with and without hp_weight) are level with the champion on the
ladder; 16 / 32 cards per burst don't beat 8. No promotion; no more burst
variants for the product ladder. The burst stays the goal-1 adaptation
tool (unseen generated powers +0.014 to +0.019 over a no-card burst, three
card sets). Alternatives considered: promote ratchet8trhp2 s101 for its
+1.0 HP (ladder +0.003, SPRT fail; the rule needs a pass, and HP alone
isn't the promotion criterion).

## Adaptation burst rerun and depth on generated powers queued (owner away, 2026-11-01)

Burst work for the ladder is closed, so Next N3 runs: the adaptation burst
(burst8 config, 10-29 parent) again with a fresh `game_seed` 41, 2 seeds
(job 0059l1, `scripts/analysis/burst_rerun.py`: fine-tunes, then the
`gen_powers12c3` play and `burst` read in one job, so the read never
starts before both nets exist). Rule as the spec's: target - other
contrast >= +0.04 and >= 2 se works, under +0.02 doesn't, read pooled with
the game-seed-31 seeds (`burst8`) too. `gen_powers_read.py burst` now
skips seed indices that weren't run.

Review 2026-11-01 rank 4 (job 0059l2): new `gen_powers_read.py depth`
plays the 10-29 net (not trained on any bench card, unlike the bursts and
the champion) under the fallback two-turn player on the bench's 2,064
elite and boss fights and pairs it with its saved one-turn results. Read:
per cell, (two - one) on the generated twin minus (two - one) on the
original. Pre-registered: contrast >= +0.03 and >= 2 se: depth repairs
generated mechanics more than official ones (depth becomes the goal-1
tool to pair with the burst); |contrast| < 0.015: depth's gain isn't
content-specific (fits the review's "repairs short-horizon mis-pricing
anywhere"); between: report only. Expected se ~0.015-0.02 (86 cells), so
only a large effect shows. Alternatives: the review's ~30-minute first
check on the worst trigger families (cheaper, but picking families post
hoc invites the slicing the skeptics flagged); a heuristic two-turn
control arm (CPU for a question the net arm answers first; run it if the
net arm passes); the champion as the net (contaminated: its burst used
the bench's test cards).

## Run-HP at two turns: burst8 s1 fails the rule; the HP-weighted read decides (owner away, 2026-11-01)

Two-turn burst8 s1 saves -0.55 HP (se 0.33) over its one-turn play (rule:
>= 2.0 depth is the HP lever, < 1.0 not), with elites and bosses +0.9 and
hallways -1.1 (Wildlife -8.7). Not acted on yet: its leaves carry no HP
weight, so depth had nothing to optimise in hallways. 0059h2 (burst8hp2
s1, two turns, paired with 0011) is read on the same rule; if it also
fails, the tempo / turn-count feature (Next N2) is next. Results doc "Run-HP
at two turns, burst8 s1". Alternative: call the depth question closed now
(cheaper, but would judge depth on leaves that can't see HP).

## Run-HP at two turns fails; hallway HP loss is racing, not tempo (owner away, 2026-11-01)

The HP-weighted champion at two turns saves +0.59 HP (se 0.19), under
the 1.0 bar: depth is not the HP lever; product run-HP stays one-turn. A
tempo probe shows the champion wins hallways *faster* than the heuristic
(3.12 vs 3.21 turns) while losing 0.56 vs -0.09 HP per turn: it
under-blocks. So Next N1's tempo / turn-count feature is replaced by an
`unblocked_incoming` feature spec (off by default; judged on run-HP
hallways, pre-register >= 1.0 HP saved there). Alternatives: tempo
feature as planned (targets the wrong thing in hallways); hp_weight above
2 (w 4 saved no more); depth on hallways only (+0.39, too small).
Adaptation burst rerun (game_seed 41): contrast +0.027 (se 0.017), between
again; over 5 seeds and 2 game sets ~+0.03, every seed positive (elites
+0.10 target over other), under the +0.04 bar. Read: the burst teaches its
own cards modestly and the wider gain (original +0.036, other generated
+0.015) is general; no more reruns, the burst stays the goal-1 tool as is.

## Start-HP column replaces `unblocked_incoming` (owner away, 2026-11-01)

The HP price probe (results doc "The nets don't price HP: no start-HP
column") shows every net prices an HP in hallways at 0.0001-0.001 of
score against its label's 0.01-0.02, because no column holds the start
HP that the score counts from. `docs/specs/start-hp.md` confirmed by the
manager: an encoder option `start_hp` (one player column, off by default,
on from a net's columns; plumbing copied from `rates`), config key
`start_hp`, four arms (lean-thr and lean-hpw2, each + `start_hp`, 2 seeds,
own round 0 on the shared games), read on run-HP against their twins.
Rule (pre-registered): saves >= 1.0 HP per fight over 2 seeds, each seed >
0, deaths <= control + 20 per 2000, tight2 held-out lead >= control -
0.02; pass -> burst the champion with the column and run the promotion
tests; < 0.5 HP on both arms -> HP price is not the lever. Alternatives:
`unblocked_incoming` (dropped: the leaf already shows the HP lost);
`hp_lost_so_far` instead of raw start HP (same information, one linear
step; raw kept); a full-layout column (rejected: every older net would
take the ~2x-slower gather path); labels relative to the state's HP
(rejected: leaves of one decision would lose their common reference).
Reversible: off by default, nothing re-pins.

## HP bonus at the leaves: next product candidate (owner away, 2026-11-01)

The champion with leaf value + 0.01 x min(1, value / 2) x (HP - start HP)
saves +2.75 HP per fight on run-HP at level wins (results doc "HP bonus at
the leaves closes the HP gap with no training"). It is a search-time
correction, so it applies to any net and needs no retraining. Next: build
it into the Rust net evaluator (an `hp_bonus` setting, off by default),
then confirm on fresh run-HP fights and the ladder before promotion. The
start-HP arms still run: a net that prices HP itself may beat the bonus,
and bonus + start-HP nets are compared once both exist. Alternatives: wait
for the trained arms only (slower; the bonus is evidence now); promote the
Python-evaluator version (too slow for the ladder and two-turn search).

## HP bonus promoted (owner away, 2026-11-01)

The champion is now `runs/2026-11-01-burst8hp2-s1-9f89b6f/model.pt@hpb0.01`:
the same net, with search adding 0.01 x clamp(value / 2, 0, 1) x (HP -
start HP) to each leaf. It passed the burst8hp2 rule (run-HP saves >= 2.0,
fixed-n ladder lead >= -0.005): +2.75 / +2.80 HP saved (same / fresh
fights), ladder -0.0012 (test 0041). The champion now loses less HP than
the heuristic (5.43 vs 5.75 on fresh fights). Reversible: the previous
`champion.json` is saved beside it as `champion.prev-burst8hp2.json`.
Consequences: every ladder or run-HP comparison against "the champion"
now plays it with the bonus; new nets should be tested both bare and with
`@hpb0.01`; the start-HP arms are read against their twins bare (the spec's
rule) and also against the twins with the bonus (does a net that prices HP
itself beat a search correction?). c 0.01 was chosen from 5 settings on
one fight set and confirmed on a fresh one; c isn't tuned further (0.02
scaled was level on HP and worse on elite wins). Alternatives: keep the
bare champion until the start-HP arms read (hours; the bonus is already
confirmed twice); bonus without scaling (costs boss and elite wins).

## Gauntlet spec confirmed (owner away, 2026-11-01)

Spec `docs/specs/gauntlet.md` (big-picture review 2026-11-01 rank 7): goal
2's headline measure, an Act-1-like chain of 11 fights (3 easy hallways, 5
hard, 2 elites, a boss) with HP carried over, Burning Blood's heal (the
engine's) and a 30% rest before the boss; clear rate paired by sequence.
Taken now because the HP bonus closed the per-fight HP gap, so the next
goal-2 question is Act clears, not HP per fight. Choices: a fixed Act shape
instead of a map walk (simple, tunable later); a fixed deck per sequence
(no rewards: it measures combat play only); no promotion rule (the ladder
stays the test). Alternatives: wait for ranks 5-6 (two-turn product
ladder, three-turn probe) first (the gauntlet is cheap and CPU-light to
build, and those need the job slots anyway); a map simulator with rewards
(much bigger, belongs to the full-game subgoal).

## Gauntlet HP-price sweep queued (owner away, 2026-11-01)

Prior-art scan `docs/research/sts-bots-and-runs.md` (option B): the HP
bonus constant c = 0.01 was chosen on HP per fight; the run-level target is
Act clears, so c is retuned on the gauntlet. Jobs 0059l4b-l4f play the
champion at c = 0.01 / 0 / 0.005 / 0.02 / 0.04 on the same 500 sequences.
Rule (pre-registered): if the first check's clear rates sit outside
~10-90%, retune the gauntlet shape first and ignore the sweep. Otherwise a
c replaces 0.01 only if its clear rate beats 0.01's by >= +0.04 and >= 2 se
(paired by sequence; se ~0.02 expected at 500 sequences), and then must
pass the ladder (lead >= -0.005) before promotion. Not adopted: the
scan's framing 1 (an outside yardstick in the sts_lightspeed / A20 setting),
which is the owner's call. Alternatives: keep c = 0.01 untested at run
level (cheap to test, so no); tune c on run-HP again (wrong target).

## Survival score: HP lost from now, survival at a fixed price (owner present, 2026-11-01)

Owner's design, built from `docs/specs/survival-score.md` (5d13285..3d7048e).
The engine score counts HP lost since the fight's start, which the net
can't see (training fights start at 10-100% of max HP), so it learned HP
nearly for free. Now, opt-in (`score: {"kind": "survive", "c", "w"}` with
`switches.hp_loss`, `no_death: false`): the net predicts a histogram of HP
lost from the state to the end (switch 6; deaths and the turn limit are
the non-win bin), and search and training score a win c + w x end HP / 100
(end HP healed and capped at max HP), a loss 0. Survival is worth c in
every fight; start HP appears nowhere. Defaults c 1.0 (survival = 50 HP),
w 2.0 (the champion's HP price); `@sc<C>` replaces c at play time.
- Histogram, not two scalar outputs: it exists and keeps an HP-value curve
  possible without retraining (curve deferred until full-game data can set
  its shape).
- Normal-mode labels count the end-of-combat heal once (`hp_end` already
  has it; the formula adds it back; a capped heal still gives the exact end
  HP). No-death labels unchanged. Survive is refused with no-death (Python
  can't read max HP for the cap), with `hp_weight`, without hp_loss, with
  `@hpb`, and in mixed-rule ensembles.
- Search scores finished combats by the evaluator's rule (`SearchConfig.rule`,
  search.rs, not hashed); Rust NetEvaluator and Python callables
  (`score_rule` attribute, set by `stsnet.Evaluator`) both carry it. The
  engine's `score()`, heuristic, solver and fingerprint are untouched.
- Known gaps (review, optional): round-0 reuse keys (`sweep.find_round0`,
  `learn.check_round0`) ignore `score` / `no_death`; `branch_gap` 0.05 means
  2.5 HP on the survive scale (same as lean-hpw2's); finetune/bursts don't
  support HP-loss nets; `bench.split_player` has no callers left.


## Gauntlet first check and HP-price sweep: c = 0.01 stays (owner away, 2026-11-01)

Read of 0059l4a-l4f (results doc "Act-1 gauntlet: first check and HP-price
sweep"): clear rates 0.45-0.62, inside the spec's 10-90%, so the shape
stays. No c beats 0.01 by the pre-registered +0.04 (0.005: -0.036, 0.02:
-0.008, 0.04: -0.134), so c = 0.01 stays and nothing goes to the ladder.
The champion with the bonus is level with the heuristic (+0.020, se 0.016);
500 more sequences (0059l7p1/p2) tighten that before it's quoted. The
bonus feeds Gremlin Nob (more skills, more Enrage; `nob_probe.py`): noted
as the bonus's short-horizon weakness, to be read on the survival-score
arms, not patched (an encounter-specific fix would not generalise to
custom content). Alternatives: retune the shape (not needed); tune c per
fight group (post hoc, and Nob would want c lower while hallways want it
higher: that's what a learned price should do).

## Start-HP column passes but the bonus stays (owner away, 2026-11-01)

Spec `start-hp.md` rule passes on start-hpw2 (+2.49 HP saved over bare
controls, both seeds > 0, held-out within 0.02). But the arms lose to their
own controls played with `@hpb0.01` (-0.26 / -1.79 / -0.82 HP) and gain
nothing with the bonus on top, so the column buys what the bonus already
gives. Not done: bursting the champion with the column (the spec's pass
action), because the manager's N1(a) condition, a trained net beating twin
+ bonus, fails. The column stays in the code, off by default; w 1 s101
(0059l8) parked. Alternatives: follow the spec's pass action anyway (a
widened champion that plays like the current one, at the cost of a
re-ladder); a third seed (the answer vs the bonus is clear on all three
nets).

## Depth on generated powers: not content-specific (owner away, 2026-11-01)

0059l3/l4 read (results doc of the same name): contrast +0.005 (se 0.024)
for net leaves, +0.003 for heuristic leaves, under the rule's 0.015: depth
repairs the net's errors broadly, not generated mechanics in particular.
So depth isn't a goal-1-specific tool; it stays the general play-time
lever (two-turn product on the ladder and the gauntlet next). No
burst-plus-depth pairing run.

## Review 2026-11-01b: depth reads before the survival arms (owner away, 2026-11-01)

Big-picture review 2026-11-01b (`docs/research/big-picture-2026-11-01b.md`):
the two-turn run-HP with the bonus (now 0059l7r1) and the two-turn
gauntlet (now 0059l7r2) run before the survival-score arms (0059l8a/l8b).
Why: the product question (does depth add at run level, on top of the
bonus?) is answered by fixed-net reads with no training luck, and the
survival arms must now beat the bonus controls, which the start-HP column
didn't. The arms stay queued (the owner designed them today and set no
order; the owner session had queued them after the two-turn run-HP).
Two-turn gauntlet pass bar: clears >= +0.03 over one-turn + bonus, paired
by sequence. Both survival jobs got fresh log files (they pointed at
0061/0062-bash.log, which hold old Tracebacks and would flag "suspect").
Memory: a two-turn run-HP job measured ~4.7 GB over 6 workers, so 6 GB
reservations stay. Alternatives: survival arms first (the owner's newest
idea; ~4 h later is the cost of waiting); one survival seed first (the
spec's rule needs 2 seeds, so no time is saved overall).

## Enemy-Strength price spec confirmed (owner away, 2026-11-01)

Spec `docs/specs/enemy-strength-price.md` (review 2026-11-01b direction 4):
a search-time price `@esp<k>` on living monsters' Strength, beside the HP
bonus, off by default. Confirmed by the manager under the standing grant.
Why now: it's the cheapest fix candidate for the gauntlet's one specific
loss (Nob's Enrage fed by the HP bonus), it needs no training, and it's
content-free (prices a primitive). Pre-registered: Nob probe qualifies a k
(wins >= 0.985, skills <= 1.8), then gauntlet clears >= +0.03 and 2 se.
Alternatives: wait for the survival-score arms to learn the price (queued;
a learned fix would be better, but its prior is low after the start-HP
read); lower c only on elites (post hoc and encounter-typed, no carry to
custom content); give the net a "Strength per skill" column (a feature
change: retraining, and the rate columns already exist and stayed off).
Build waits for memory: two-turn jobs leave < 1 GB free.

## Enemy-Strength price fails at run level (owner away, 2026-11-01)

Built (9bc3af4, review fixes 6f32ad4) and read per the spec: k 0.04 fixes
Nob (wins 0.972 -> 0.994, skills 2.28 -> 1.06) but the gauntlet loses
-0.020 (se 0.009) vs the champion + bonus (bosses and HP at the boss pay
for it). `@esp` stays in the code, off by default; no k 0.02 retry (it
didn't qualify on Nob, and the run-level cost is in the mechanism, not the
size). Alternatives: price Strength by expected hits left (a monster-turns
estimate: closer to a learned value, deferred to the survival-score read);
restrict it to Enrage-type Strength (encounter-shaped, no carry to custom
content).

## End-HP bonus spec confirmed (owner away, 2026-11-01)

Spec `docs/specs/end-hp-bonus.md`: a player setting `@hpe<c>` that prices
HP after the coming end-of-combat heal on every leaf, `c x clamp(score / 2)
x (min(HP + heal, max HP) - start HP)` on unfinished leaves and the same on
finished wins (HP already healed). Off by default; `@hpb` and the champion
are unchanged. Why: two-turn + `@hpb` loses -0.93 HP per hallway against
one-turn + `@hpb` (run-HP 0036 vs 0023), because search scores a finished
combat with the engine's floored score (`2 - max(0, start - end HP) / 100`,
end HP after Burning Blood's 6) and no bonus, so up to 6 HP of damage in a
won fight is free while unfinished leaves pay for every HP; two-turn reaches
many more wins inside its horizon. Alternatives: add the existing bonus to
finished wins (an undamaged finish gets +6c over an undamaged unfinished
leaf, still pushing toward fast kills); record pre-heal HP in the state
(changes the state's hash and the solved database's keys); change `@hpb`
itself (not reversible against the champion's tests). Pre-registered read:
two-turn `@hpe0.01` vs 0036 on the first 1000 fights, pass if hallways save
>= +0.5 HP with no more deaths; one-turn `@hpe0.01` vs 0023 expected level.

## Fast search tables spec confirmed (owner away, 2026-11-01)

A profile of two-turn decisions (results doc "Two-turn search: where the
time goes") puts ~25% of the time in SipHash over whole 1 KB states and
~19% in growing the search's state tables. Spec `fast-search-tables.md`:
an Fx-style hasher written in the engine for `memo` and `leaf_index`
(no new dependency), results bit-identical, checked by a dump of 150
searches before and after. Alternatives: add `rustc-hash` (a dependency
for 20 lines); key tables by a 64-bit state hash only (faster still, but a
collision would silently merge two states: rejected). Provisional.

## Fast search tables built (owner away, 2026-11-01)

Built f7bbe85 (spec folded here): search's `memo` and `leaf_index` hash
states with an Fx-style hasher in `search.rs`; every result bit-identical
(dumps of 150 heuristic-leaf and 240 net-leaf searches compared). Tree
building alone 1.84x faster; whole two-turn search 1.13x with heuristic
leaves, ~1.2x with net leaves (by profile shares; timings too noisy under
load to pin it), under the spec's 1.3x bar but free. The planned
small-entry tables (step 2) were dropped: after the fix table growth is
~10% of a net-leaf decision and the net's layers ~65%. Profiling tool:
`engine/examples/two_turn_phases.rs` (`--check <file>` dumps results for
comparing builds); symbol builds go to `target/prof` (rebuildable).

## Net leaf cache spec confirmed (owner away, 2026-11-01)

Spec `net-leaf-cache.md`: `Net::forward` computes each distinct hook row's
and card's layer output once per call (keyed by raw input bits, cleared per
call), the encoder reserves its buffers, the Fx hasher moves to a public
engine module. Scores bit-identical. Alternatives: fold the head's first
layer into per-card contributions (faster still but changes summation
order, so scores move in the last bits: rejected for now); a cache kept
across a whole search (more hits, but unbounded memory: rejected).
Provisional.

## Net leaf cache built (owner away, 2026-11-01)

Built f2b42a9 (spec folded here): `Net::forward` keeps a per-call cache of
hook-row and card layer outputs keyed by raw input bits (cleared each call,
so a shared `Scratch` carries nothing over); `Encoder::encode` reserves its
buffers from the first state's size; the Fx hasher lives in
`engine/src/fxhash.rs`. Bit-identical: 40 two-turn searches against both
earlier builds, and the reviewer's 60 dumps over five nets (logits,
scores, shuffled batches with repeats, one-state calls). 1.57x on net-leaf
two-turn search (min-of-3 cycles, 3 alternated pairs). `sts` swapped 22:05.
Review optional items (not done): the old-vs-new dump isn't a committed
test; Python-side `Features.encode` / `PyEval` reserve over the whole
input, not 4096-state chunks; each cache miss allocates its key.

## Heuristic rate cache spec confirmed (owner away, 2026-11-01)

Spec `heuristic-rate-cache.md`: `damage_rate` (93.5% of the heuristic's
leaf estimate, which is ~77% of a heuristic-leaf two-turn decision) caches
its 4-roll move walk's term list per (kind, slot, moves) in a thread-local
table and re-sums damage in the same order: bit-identical. Relies on every
monster AI reading only its own kind, slot and move history (true for all
17 today; documented on `Ai` and tested per kind). Alternatives: change the
`Ai` signature to take only the move history (structural guarantee, but
limits future AIs that need more state, e.g. ally counts: rejected);
precompute per-move weights (faster still, but changes summation order:
rejected); a per-call cache (fewer hits, no gain in safety: rejected).
Provisional.

## Heuristic rate cache built (owner away, 2026-11-01)

Built 83237cb (spec folded here): `heuristic::damage_rate` caches its
4-roll move walk's (probability, move) terms per (kind, slot, moves) in a
thread-local table (bounded by static content) and re-sums damage in the
same order; `monsters::Ai` documents that an AI reads only its kind, slot
and move history, and `tests/monsters.rs::ai_reads_only_moves` checks all
18 kinds x 5 slots x every move pair against changed HP, block, powers,
rolled damage, other monsters, turn and player. Bit-identical: 150
heuristic two-turn and 150 one-turn searches (`two_turn_phases 150
--check`, now dumping both) equal to the previous build's. Heuristic-leaf
two-turn search **5.1x** faster (min-of-3, alternated, 60 elite/boss
states: 46.3 -> 9.0 s; every pair agrees); the estimate drops from ~77% to
~6% of a decision, leaving the tree (tables, stepping) as the cost. Cargo
tests and the Python binding / search-values / HP-loss / survival tests
pass on a wheel built from the branch. No separate spec-reviewer (built by
a manager fork, which can't spawn one); self-review found nothing to fix.
Optional: the test's kind list is written out, so a new `MonsterKind` must
be added to it by hand. Not yet swapped into the main `.venv`.

## Amount expressions built (rules-engine spec 2; owner asked for the series, 2026-11-02)

Spec `amount-expressions.md` (folded here and into the umbrella), built on
branch `engine-next` (2ec1ab4 and the review fix). Confirmed by the manager
under the standing grants; the owner asked for the series to be worked
through overnight.
- `Effect::ScaledDamage { amount, hits, target }` with `Amount { base, k,
  of: Option<Quantity> }` replaces `DamageFromBlock`, `StrengthMultiplier`
  and `PerStrikeBonus`. Quantities: `OwnBlock`, `OwnStrength`,
  `EnergySpent`, `CardsTagged(Tag)`; at most one of amount and hits reads
  one. Heavy Blade is `14 + 2 x Strength` (the attack adds Strength once
  more, as the game does). Alternative: every amount in `Effect` an
  expression; rejected for now (sweeping, inner-loop cost, no content).
- Card tags (`CardDef.tags`, `Tag::Strike`; spec 4 adds `Shiv`): every
  official card whose name holds "Strike" carries it (a test pins that).
- X-cost: `CardDef.x_cost`, `cost` stays 0 for every cost reader; playing
  spends all energy as X, kept in `Stage::PlayingCard { x }`. The codec
  writes a new stage tag 7 only when X > 0, so existing encodings are
  byte-identical (`codec_golden` hex lines unchanged, debug text
  re-recorded) and `CODEC_VERSION` stays 1. Alternative: cost -1 as in the
  game; rejected (every cost reader would need a case).
- Proving content Whirlwind (Ironclad, X: 5 (8) to ALL, X times) under a
  new `CardDef.proving` flag: in no deck pool and not a check-9 held-out
  card, so pools, `held_out_card_names` and `bench_sets.py` are unchanged.
  Alternative: `held_out`; rejected (it would change check 9's lists).
  Golden games: a fixed proving set per spec (`golden.rs` `PROVING`,
  keys `proving-<name>:...`, 40 games per encounter); the fuzz decks add
  the class's proving cards.
- Features: the legacy columns are computed from the expression, so old
  nets stay exact; new effect scalars `expr_value` (amount x hits resolved
  against the state now, card path only; X = current energy, or the card
  in play's X), `expr_base`, `expr_k`, `expr_q_block|strength|energy|strike`,
  `expr_all`, and card property `x_cost`. **Changed from the umbrella**:
  the resolved value goes in `expr_value`, not in `damage_single` (it
  would have changed old nets' inputs on the three cards; the series row
  says they stay exact).
- Checks: all engine and solvedb tests (content-table fingerprint pin
  re-pinned for Whirlwind; the rules fingerprint changes as the series
  table says); golden identical; `scripts/series_check.py` (new: dumps the
  heuristic, contract nets' torch and Rust outputs and every feature column
  over the fixed set, compares two builds by column name) PASS on 3,736
  states, 632 of them holding Body Slam, Heavy Blade or Perfected Strike
  with varying block and Strength: heuristic, 4 contract nets and every old
  column bit-identical. Python pins re-pinned on purpose after checking the
  change is additive (`golden_rows.npz`, contract `pins.json` and tiny
  nets, `lookahead_off_names.json` (only appended names), `lookahead_rows.npz`
  (old columns equal, new ones zero), `test_net.py` `TRAIN_PIN`).
- Speed (`scripts/series_speed.py`: old/new interleaved, 5 runs, medians;
  CPU ~88% busy with other work at the start): random combats -5.7%,
  clone +1.8%, search 1 thread +1.3%, all threads +15% (noise). Within the
  10% budget.
- Review (spec-reviewer): no correctness bugs; must-fix was the missing
  proving golden games and fuzz coverage (fixed). Optional, not done: the
  Python test pins Body Slam's `expr_value` only at block 0; `expr_value_col`
  is a linear lookup per card entry; Heavy Blade's `expr_value` excludes
  the Strength the attack adds again (it is amount x hits, as specified).

## Static modifiers spec confirmed and built (rules-engine spec 4; 2026-11-02)

Spec `static-modifiers.md` (folded here and into the umbrella). Spec 3
(`entity-shape`) moved after spec 5: it reformats the batch, the stored
datasets and both forward passes with no new content, and specs 4-5 don't
need it (their rows go through today's row path). Provisional.
- `hooks::Static { modifies, stage, amount, num, den, condition }` and
  `statics(p)`: Strength `Add DamageDealt 1`, Dexterity `Add BlockGained
  1`, Weak `Multiply DamageDealt 3/4`, Vulnerable `Multiply DamageTaken
  3/2`, Frail `Multiply BlockGained 3/4`; Accuracy `Add DamageDealt 1 if
  the card in play is tagged Shiv`; Red Skull `Add DamageDealt 1 while HP
  <= half`.
- The damage pipeline's order: base, every add (attacker's dealt, target's
  taken), multiplies, round down once, never below 0 (spec 5 inserts
  replacements, then block).
- Fast path kept: `attack_damage` / `gain_block` hard-code the five
  built-ins and read the table only for `GENERIC_STATICS` (Accuracy, Red
  Skull: two stack reads per attack). `interpret_attack_damage` /
  `interpret_block` read every row; `statics_table_matches_fast_path`
  checks they agree over 20,000+ attacks and 2,000+ blocks on fuzzed states.
  Alternative: interpret rows in the inner loop; rejected for the speed risk
  the umbrella names (it allows this fallback).
- Countdowns: Vulnerable, Weak, Frail have `RoundEnd -> ReduceSelf(1)`;
  `Trigger::RoundEnd` runs after every monster's turn-end hooks (player,
  then monsters by slot), then `Powers::clear_round_flags` (replaces
  `end_of_round`). `run_hooks` already skips `just_applied` powers, which
  is the first-round skip.
- Proving content: Accuracy (Silent power, 4 (6), `proving`), power
  `RedSkull` (no card; relics are out of scope), `Tag::Shiv` on Shivs.
- Features: row kinds `static` and `countdown` (old nets drop them by
  gather; alternative: countdowns as `triggered`, rejected, old nets would
  see new rows on every debuffed state). Static row: trigger name
  `Static(DamageDealt|DamageTaken|BlockGained)`, condition names
  `CardInPlayTagged(<tag>)`, `OwnerHpAtMostHalf`, effect scalars
  `static_add` (amount x stacks) and `static_mult` (factor - 1); trigger
  `RoundEnd`. Entities write them for their powers, cards and intents as
  granted rows. Modifier dimensions unchanged; `hook_power_names` still
  lists only non-modifier hook powers.
- Checks: all engine and solvedb tests; the 9,000 golden games unchanged;
  `series_check.py` PASS on 4,980 states (pre-series row kinds; `--cards`
  Bash, Inflame, Uppercut, Clothesline, Thunderclap, Flex, Body Slam, Heavy
  Blade): heuristic, 4 contract nets and every old column and row
  bit-identical; Python suites pass after additive re-pins.
- Speed (baseline = pre-series, 5 interleaved runs, CPU ~74% busy at the
  start): random combats **-15.9%** (every pair slower; spec 2 alone was
  -5.7%, so spec 4 cost ~-10%, at the budget), clone -2.6%, search 1
  thread -5.0%, all threads +4.5%. Cause: the generic static loops ran on
  every attack and the `RoundEnd` hooks on every entity every round.
  Guards added with spec 5 (generic statics skipped unless a side holds
  one; `RoundEnd` hooks only for entities holding a `ROUND_END_POWERS`
  power; `clear_round_flags` returns at once when nothing is flagged);
  re-measured there.
- Review (spec-reviewer): must-fix 1, the proving golden games had gone
  into `golden.txt`, whose hash is the registry's rules version
  (`scripts/registry.py`), so recorded datasets would have been refused:
  fixed, they live in `engine/tests/data/golden_proving.txt` and
  `golden.txt` is byte-identical to its pre-series version (rules version
  `7042d1d6a6149ba0` kept). Must-fix 2, these speed numbers. Optional, not
  done: Red Skull has no golden games (no card grants it); the equality
  test rarely activates a monster's Red Skull (monster HP not randomised).

## Replacement hooks spec confirmed and built (rules-engine spec 5; 2026-11-02)

Spec `replacement-hooks.md` (folded here and into the umbrella). Rules
checked against the decompiled game (`AbstractPlayer.damage`,
`IntangiblePlayerPower`, `WraithFormPower`, `ThornsPower`, `DamageAction`,
via github.com/aeubanks/sts); the wiki's wording is vaguer. Provisional.
- `hooks::Replacement { event, action, then }`, `replacements(p)`. Events
  `DamageTaken` (any damage, after the pipeline, before block), `HpLoss`,
  `DebuffApplied`; actions `Cancel`, `Cap`, `Add`, `Multiply` (the last
  two without content). Several rows on one event apply in power order,
  each on the running amount, `Cancel` stops (the umbrella's open
  question; alternative: the game's application order, which needs
  per-entity order state). The engine reads them for `REPLACEMENT_POWERS`.
- Artifact is `DebuffApplied -> Cancel, then ReduceSelf(1)` (golden
  identical). Intangible: `DamageTaken` and `HpLoss -> Cap(1)`, countdown
  `RoundEnd -> ReduceSelf(1)`. The pipeline: base, adds, multiplies, round
  down, replacements, block. Intangible doesn't cap the shown intent (the
  game does): `intent_damage`, the heuristic and old nets stay unchanged;
  the net reads the replacement row.
- `Trigger::OwnerAttacked` (every attack hit, blocked or not, after block
  and HP loss, unless the combat is over) and `Target::Attacker`. Thorns:
  `OwnerAttacked -> PlainDamage 1 per stack to Attacker`. A monster that
  dies mid-move makes no more hits (the game's `DamageAction`), its later
  non-attack effects still apply (sts_lightspeed lets the hits land).
- Proving content (`proving`): Wraith Form (Intangible 2 (3), `WraithForm`
  1: lose 1 Dexterity per stack at the player's turn end), Caltrops
  (Thorns 3 (5)); golden proving set `wraith`.
- `Powers::just_applied` is `u64` (26 official + 8 slots); the codec
  already wrote it as a varint, so encodings are unchanged. `Powers`
  implements `Default` by hand (arrays past 32 don't derive it).
- Features: row kind `replacement` (trigger names
  `Replace(DamageTaken|HpLoss|DebuffApplied)`, scalars `replace_cancel`,
  `replace_cap`, `replace_add`, `replace_mult`, `replace_stacks`, then
  the `then` effects); trigger `OwnerAttacked`; `Attacker` reads as an
  opponent. `is_hook_power` (`hook_power_names`) means a non-modifier with
  a hook other than `RoundEnd` (Intangible is not one).
- Speed guards for spec 4's cost went in here (see spec 4's entry).
- Speed (baseline = pre-series, 5 interleaved runs, CPU 74-84% busy with
  other work): first build, random combats +2.9% (spec 4's cost gone),
  search 1 thread **-23%** (every pair slower), clone 47 -> 70 ns. Causes:
  every attack hit scanned the target's powers for `OwnerAttacked` hooks,
  and `just_applied` as `u64` aligned every power block to 8 bytes. Fixed
  (committed with spec 6): `ATTACKED_POWERS` guard (a test checks the
  list) and `just_applied` as two `u32` words (same bits, same codec
  varint). Re-measured, cumulative specs 2-5: random combats -7.9%, search
  1 thread -7.6%, all threads +2.0%; clone ~68 ns vs ~58 (state 1,028 ->
  1,176 bytes; noisy). Within 10% per spec and 25% for the series.
- Review (spec-reviewer): no correctness bugs; must-fix was these numbers.
  Known divergence (optional finding, not fixed): when Thorns damage during
  a monster's own move changes its intent (The Guardian's Mode Shift to
  Close Up, a slime's split), the roll after the move overwrites it; the
  game probably keeps it. Only proving content (Caltrops) can cause it.
  Also optional: a monster killed mid-move still gains its move's later
  block (harmless, but a state field differs).
- Checks: all engine and solvedb tests (content-table pin re-pinned, codec
  debug text re-recorded with hex unchanged); golden.txt unchanged, the
  earlier proving sets unchanged; `series_check.py` PASS on 4,703 states
  (`--cards` Bash, Clothesline, Uppercut, Thunderclap, Bloodletting,
  Hemokinesis, Combust: Sentries' Artifact and HP-loss cards); Python
  pins re-pinned after the additivity check.

## Decision points spec confirmed and built (rules-engine spec 6; 2026-11-02)

Spec `decision-points.md` (folded here and into the umbrella). Provisional.
- `Action::Choose(CardId)` and `Action::Done` (codec action tags 2 and 3,
  as the contract reserved; action text `Choose:<card>` and `Done` now
  decode). `Effect::Pick { kind, n, exact }` pauses the card in play;
  kinds, engine-owned: `DiscardFromHand`, `ReturnFromDiscard` (no pick
  while the hand is full). Skipped when there is nothing to pick; `exact`
  ends by itself after n, otherwise `Done` is offered each step.
- The pick lives in `Stage::PlayingCard`'s new `more: InPlay { pick,
  replays, copy }` (alternative: a new `Stage` variant; rejected, every
  in-card reader would need a second arm). `awaiting_action()` is true at
  a pick; `legal_actions` there is one `Choose` per distinct candidate
  (piles are multisets) plus `Done` when offered. The codec writes a new
  stage tag 8 only when `more` is non-empty: existing encodings unchanged.
- Search doesn't apply the node cap at a pick (the subtree is bounded by
  the transposition cache), so in-card decisions are never leaves; the
  solver, options, random and search agents needed nothing; the greedy
  agent takes the first option at a pick.
- Card replay: `Effect::ReplayCard` in a hook adds a replay to the card in
  play; after it resolves the copy plays: free, same target and X, counted
  in `cards_played_this_turn`, seen by monsters' `CardPlayed` hooks and the
  player's after-card hooks, purged (no pile). New `Trigger::OwnerPlaysCard`
  (before the card's effects, the game's `onUseCard` timing, so a power the
  card applies isn't there yet); it doesn't fire for copies (the game fires
  `onUseCard` for copies, but Burst ignores them; no other reader yet).
- Proving content: Survivor (Block 8 (11), discard 1), Burst (power
  `Burst` 1 (2): `OwnerPlaysCard` Skill -> `ReplayCard`, `ReduceSelf(1)`;
  removed at turn end), Hologram (Block 3 (5), return 1 from the discard
  pile; base exhausts; Ironclad class like the other Defect cards here).
  Golden proving sets `survivor` (Silent) and `hologram` (Ironclad).
  `Character::starter_deck_variant("game")` / Python
  `sts.starter_deck("silent", variant="game")`: the game's Silent starter
  with Survivor; the default starter is unchanged.
- Python: `sts.Action.choose(card)`, `sts.Action.done()`, `Action.kind`;
  `card` names the chosen card. Features: player scalars
  `pick_discard_from_hand`, `pick_return_from_discard`, `pick_left`;
  effect scalars `pick_discard`, `pick_return`, `replay`; trigger
  `OwnerPlaysCard`.
- Fuzz invariants count a card paused at a pick (not a copy) and allow
  its mid-card bookkeeping (deferred block, Rupture triggers).
- Checks: all engine and solvedb tests (content-table and codec debug
  re-pins, hex unchanged); golden.txt and earlier proving sets unchanged;
  `series_check.py` PASS on 4,703 states; Python pins re-pinned after the
  additivity check.
- Speed (cumulative specs 2-6 vs pre-series, 5 interleaved runs, CPU ~79%
  busy): random combats -3.2%, clone 51 -> 64 ns, search 1 thread
  **-12.8%** (every pair slower; -7.6% after spec 5, so spec 6 ~-5%),
  all threads -5.1%. Within 10% per spec and 25% for the series; the state
  is 1,196 bytes (1,028 before the series), which hashing and cloning in
  search pay for.
- Review (spec-reviewer): must-fix 1, a pick of a generated card wrote
  `Choose:gen:<id>`, which `action_text` refused: fixed (the candidate's
  `gen:` prefix is stripped before the reserved-character check, and
  `decode_in` looks generated picks up among the legal actions). Must-fix
  2, the node-cap test couldn't fail: `search_never_scores_a_pick` (a 1-node
  cap with an evaluator that refuses pick states) fails without the
  exemption, checked. Optional, not done: a replayed copy whose target died
  does nothing (the game picks a random target; only generated Skills could
  reach it); the tag-8 decoder accepts some non-canonical bytes; no unit
  test for Burst+ or Burst on Burst.

## Known top spec confirmed and built (rules-engine spec 7; 2026-11-02)

Spec `known-top.md` (folded here and into the umbrella). Provisional.
- `draw` stays the whole draw pile; a new field `top: Top` holds what the
  player knows of its order: `known` (ordered, the next drawn first) and
  floaters (card, `above`), all also counted in `draw`. Fixed-capacity
  inline arrays (known 16; floaters 8 distinct (card, above) entries, each
  with a copy count). Past capacity the bottom known card is forgotten,
  and a card of a 9th distinct pair is not tracked: the model treats it as
  certainly below every known card, so the known head is drawn first more
  often than in the game. Reachable with packs (`AddCard` to `Draw`, spec
  10 stage 1); official cards can't reach it in practice. Alternatives:
  also raise `TOP_FLOATERS` (+3 bytes per entry in every state); evict the
  entry with the largest `above` first (a smaller error). Alternative: the prefix outside `draw`; rejected, every reader
  of the draw pile (heuristic, Perfected Strike's count, Inferno) would
  change.
- Push (`PickKind::DiscardToTop`, Headbutt): to the front of `known`,
  every floater's `above` +1. Shuffle in (`AddCard` to `Draw`) under a
  known top: a floater with `above` 0. Draw while something is known: a
  floater kind with `above` 0 with probability count / pile size, else the
  head (positive `above` drop by 1); floaters dissolve when nothing is
  known; with nothing known, today's code path. Listing goes card by card
  then `draw_outcomes`, merging equal states; sampling draws the same way.
  Checked against hand-enumerated orderings (Bash known, a Wound shuffled
  in: two draws give {Wound, Bash} 1/2, {Bash, Strike} 1/4, {Bash, Defend}
  1/4) and 20,000 samples.
- Inferno upgrades Burns in `top` too. The codec writes `top` as an
  optional trailer only when non-empty (existing encodings unchanged,
  `CODEC_VERSION` 1). The golden dump prints `top` only when set.
- Headbutt (Ironclad, 9 (12) damage, a card from the discard pile on top),
  `proving`; golden proving set `headbutt` (with Wild Strike for floaters).
- Features: piles `next_draw` (the first k known cards, k =
  `next_draw_size`: the base draw, the Silent's first-turn extra before
  turn 1, and the player's turn-start `Draw` hooks times stacks) and
  `known_later`, both with parent `draw`, so an older net folds them into
  its draw slot; the `draw` slot holds the draw pile less the known cards.
  Player scalars `next_draw_size`, `known_top`, `pick_discard_to_top`;
  effect scalar `pick_to_top`.
- Checks: all engine and solvedb tests (pins re-pinned, codec hex
  unchanged); golden.txt and earlier proving sets unchanged;
  `series_check.py` PASS on 4,703 states.
- Speed (cumulative specs 2-7 vs pre-series, 5 interleaved runs, CPU 90%
  busy with other work, so noisy): random combats -10.5%, clone 44 -> 72
  ns, search 1 thread -10.1%, all threads **-20.1%** (every pair slower but
  one). Spec 7 alone is within 10% on 1 thread; all threads swing most
  under load. The series total nears its 25% budget on H2; the steady
  driver is state size (1,028 -> ~1,230 bytes: wider piles and power
  blocks for proving content, `top`, the card-in-play stage). Hashing only
  non-empty pile words and non-zero powers was tried and made no
  measurable difference (reverted). The state-representation change of
  spec 8 / 10 (sparse inline piles) is the lever.
- Review (spec-reviewer): must-fix, the spec's `inferno_upgrades_known_burns`
  test was missing (added; drawing an un-upgraded known Burn would panic)
  and these speed numbers. Optional, recorded: when a floater is the same
  kind as the known head (Headbutt puts a Wound on top, Wild Strike
  shuffles one in), drawing one Wound gives two states with the same hand,
  one still knowing a Wound on top: the odds are exact but the state then
  holds more than the player can know (the true knowledge, "one of these
  two Wounds is on top", isn't expressible as known cards plus floaters).
  Also optional: the Python test doesn't reach `known_later` or Brutality's
  `next_draw_size`.

## Monster patterns spec confirmed and built (rules-engine spec 9; 2026-11-02)

Spec `monster-patterns.md` (folded here and into the umbrella), built
before spec 8 (`per-copy-overrides`), which it doesn't need: spec 8 carries
the state-representation decision and is the larger change. Provisional.
- Move selection is data: `MonsterDef.pattern`, ordered `PatternRow { when,
  then }`; the first row whose conditions all hold fires. Conditions:
  `FirstTurn`, `LastMove`, `LastTwo`, `Window(last, before)`, `Slot`,
  `RollBelow(n)` (the lazy 0..99 roll, made once the first time a row
  reads it; conditions stop at the first false one). Picks: `Move` or
  `Chance { p, yes, no }` (one `chance(p)` call). One interpreter,
  `pattern_ai`, is every monster's `ai`, so listing, sampling, lookahead
  and the heuristic's rate cache read the same data. The 15 hand-written AI
  functions became tables.
- Proof: golden games identical; `engine/tests/patterns.rs` keeps the old
  functions as references and checks every kind, slot and two-deep history
  (`enumerate` walks the random-call tree, so equal lists mean the same
  calls in the same order).
- Features: row kind `pattern`, one row per possible next move (from
  `move_distribution`, i.e. after the intent on show): trigger
  `Pattern(Next)`, `condition_param` the probability, the move's effect
  vector. Old nets drop the kind.
- Deferred (recorded, not built): reactions as hooks (Lagavulin waking, the
  slimes' split, The Guardian's Mode Shift stay named reactions in
  `lost_hp`), `SetIntent` / `SetPhase`, the `phase` monster scalar (no
  current monster needs it), `Spawn`, setup rolls as `Setup` rows.
- Checks: all engine and solvedb tests (no pin changes: no new content,
  codec unchanged); `series_check.py` PASS on 4,703 states.
- Review (spec-reviewer): tables match the old code line by line; must-fix
  was that comparing `enumerate` outcome lists can't see the calls (a
  `chance(0.25)` and a `below(100) < 25` give equal lists): the test now
  records every call (`below(n)` / `chance(p)`) per path and compares
  (move, calls) lists. Optional, done: pattern rows are skipped when the
  net's layout drops the kind (older nets don't pay for them). The spec's
  "three" next moves for a Jaw Worm after Chomp was wrong (two: Chomp
  can't repeat). The rules fingerprint changes (monsters.rs is a rule
  file), as the series table says.

## Per-copy overrides spec confirmed and built (rules-engine spec 8; 2026-11-02)

Spec `per-copy-overrides.md` (folded here and into the umbrella), built
after spec 9. Provisional.
- A card with its own numbers is a *variant*: (base card, `Overrides {
  damage }`, lifetime combat), interned process-wide (append-only, read
  without a lock, like registry-lite's bound cards). A combat holds up to
  `VARIANTS` = 4 in `Binding::variants`, sorted by interned index, at
  reserved card ids from `VARIANT_BASE` (after the generated slots), so
  every `binding.def` reader sees the copy's numbers (a variant's
  definition is its base's with the damage replaced, named
  `Base{damage=N/combat}`). Inserting or dropping a variant renumbers the
  ids in every pile, the known top and the card in play, so equal sets of
  copies are equal states; a variant no copy holds is dropped.
- **The state-representation decision moved to spec 10** (the umbrella put
  it in spec 8's interview): today's fixed pile arrays stay; the sparse
  inline piles with `u16` ids are for content loaded from files, where the
  id space becomes open-ended, and need their own speed work (alternative:
  build them now; rejected for risk and time). With all four variant slots
  in use a copy doesn't grow (unreachable with the proving content).
- `Effect::GrowDamage(k)` (Rampage 8, +5 (+8)); `CardDef::retain` (stays in
  hand at turn end; Protect, a Watcher card, Ironclad class here). Golden
  proving set `rampage`; the golden dump names cards by their definition,
  so a variant shows its override form (existing games' text unchanged).
- Codec: card ids may be variant ids; the optional trailer is now tagged
  sections (1 the known top, 2 the variants by value); a decoded state
  must name only cards it holds. Existing encodings unchanged.
- Python: a variant's name is its override form, so action text is the
  contract's `Rampage{damage=13/combat}@0`, replayed by `decode_in` among
  the legal actions (picks of a variant too); `Combat.step` checks a named
  card with `Binding::is_bound`. Features: card property `retain`, effect
  scalar `grow_damage`; a variant's card vector comes from its definition
  (`damage_single` 13).
- Fuzz (quick and full) passes with every proving card in the decks; the
  fuzz helper reads definitions through the binding.

## Series speed and search identity after specs 2-9 (2026-11-02)

- **H4 (nodes per decision): identical.** `two_turn_phases 100 --check` on
  the pre-series build (ee259ff, built in a temporary worktree) and on
  06fc5c0: 100 two-turn and 100 one-turn searches give byte-identical
  check files (nodes, leaves, cuts, chosen action, every option value's
  bits).
- **H1/H2 after the move-distribution cache** (pre-series vs 06fc5c0, 5
  interleaved runs, a quieter machine): random combats **+10.0%** (faster:
  the cache more than pays for the pattern interpreter), clone 52 -> 49 ns,
  search 1 thread **-7.5%**, all threads **-13.7%**. Within the 25% series
  budget. Spec 9 alone, before the cache: random combats -15.9%, search 1
  thread -12.3% (over its 10%); the cache (`move_distribution` per kind,
  slot and history, which is all a pattern reads) fixed it.
- **Where the rest goes** (`two_turn_phases`, 1,205,400 nodes, same tree):
  memo lookup 2.59 -> 2.88 s, memo insert and freeing 4.89 -> 5.86 s, leaf
  store 4.63 -> 5.50 s, apply_action 3.22 -> 2.36 s. About 75% of a
  two-turn search copies and hashes whole states, which grew 1,028 -> 1,268
  bytes (piles 128 -> 152 slots for proving content, generated and variant
  ids; power blocks 21 -> 27 official powers; `top`; the card-in-play
  stage; variant slots). The levers: the sparse state representation
  (spec 10) or a search memo that stores each state once (a separate speed
  spec). Hashing only non-empty pile words alone measured no gain.

## End-HP bonus built and read (owner away, 2026-11-02)

Built 9c790b5 (spec `end-hp-bonus.md` folded here; README lists `@hpe<c>`).
One-turn `@hpe0.01` plays level with one-turn `@hpb0.01` (run-HP 0037 vs
0023: -0.05 HP, se 0.04). Two-turn `@hpe0.01` vs two-turn `@hpb0.01` on
the same 1000 fights (run-HP 0038 vs 0036): hallways +1.41 HP (se 0.09),
all +1.24, deaths -2: the pre-registered rule (>= +0.5 HP in hallways, no
more deaths) passes. On the Act-1 gauntlet the two-turn `@hpe` champion
clears 0.676 vs the one-turn champion's 0.616 (+0.060, se 0.016; bar
+0.03) and two-turn `@hpb`'s 0.640 (+0.036, se 0.012). Results doc
sections "Two-turn run-HP with the end-HP bonus passes" and "Two-turn
champion with the end-HP bonus on the gauntlet". Left: `@hpb` stays as
is, since the champion's ladder entry and tests use it.

## Two-turn @hpe is the product player (owner away, 2026-11-02)

Goal 2's headline player (gauntlet, any run-level read) is now the
champion net searched two turns deep (`--two-turn`, fallback player,
max nodes 400k, sample k 4) with `@hpe0.01`: it beats every other player
we have on the gauntlet (+0.060 over the one-turn champion, +0.080 over
the heuristic). The ladder still compares nets one turn deep with
`@hpb0.01`, because a two-turn ladder test costs ~50x and the nets'
order is what it decides. Alternatives: keep one-turn as the product
until depth is cheaper (gives up +0.06 clears); a two-turn ladder (too
slow for every candidate). Reversible: it is a player string. Costs:
two-turn play is ~50x one-turn, so speeding up search is now the
throughput lever for every run-level read.

## Gauntlet protocol (owner away, 2026-11-02)

Goal-2 candidates (a net, a search setting, a player) are read on the
Act-1 gauntlet, not tight2 or the ladder alone (tight2 read the HP bonus
at -0.0012 while the gauntlet read +0.168 clears). Rule: paired end-HP
(boss HP left if cleared, else 0) against the product player's cached
per-sequence file, normal SPRT with H1 +1.5 HP, alpha = beta = 0.05,
first look at 50 sequences, in sequence order; a pass fails if paired
clears so far have z <= -2. Screen on sequences 0-499; confirm finalists
on 500-999 (c, `@hpe`, `@esp` were tuned on 0-499). Replay over the
existing files (results doc "Gauntlet protocol replay"): no direction
errors, real effects stop at 50-160 sequences instead of 500. Not yet
built into `gauntlet.py` (play writes the whole file at the end); until
then, run fixed blocks (e.g. 125 sequences) and apply
`scripts/analysis/gauntlet_protocol.py`'s rule by hand. Alternatives:
fixed-n clears (4-5x the CPU), trinomial GSPRT on clears (end-HP is ~2.5x
more sample-efficient). Reversible.

## Card-rewards spec confirmed (owner away, 2026-11-02)

Spec `docs/specs/card-rewards.md`: card rewards on the existing gauntlet
(3 seeded offers from the half's pool after each won non-boss fight;
choosers skip / random / sim, the last scoring each option by 8 one-turn
fights of the next floor's pool with common seeds), start from the cell
deck or the starter deck. A measurement of how much deck choices move
clears, after review 2026-11-02 found the fatal fight rarely savable
(rollouts 7 / 117) and sequence draw ~72% of clear variance. Rule (on the
10-29 net, one turn, starter start): sim - random >= +0.05 clears or a
gauntlet-protocol pass on end-HP -> card rewards become a goal-2
workstream. Alternatives: a run layer on our engine (pre-empts the
owner's simulator decision), building on `sts_lightspeed` (the owner's
call), a learned chooser (no evidence yet that choices matter).
Reversible: an option of `gauntlet.py`, `skip` reproduces today's files.

## Gauntlet early stop built (owner away, 2026-11-02)

`gauntlet.py play --against <control>` applies the gauntlet protocol after
each block of 50 sequences and stops on a verdict (spec
`gauntlet-early-stop.md`, review: no must-fix). The protocol's replay
expects screens to stop at 50-160 sequences instead of 500, about 2-3x
less CPU per goal-2 read. Effects are still reported at fixed n on the
confirmation book (review 2026-11-02 stop list). Blocks cost one process
pool start each; two-turn jobs that compare wall time pin `--block` to
their full size. Alternatives: fixed blocks by hand (the old way), a
streaming pool with no per-floor barrier (bigger change). Reversible.

## Per-copy overrides review fixes (2026-11-02)

Spec-reviewer on spec 8, three must-fix, all fixed:
- Variant slots were ordered by interned index, which is the order a
  process first met each variant: the same state could encode to other
  bytes in another process, or not decode there (the reviewer showed both
  with two processes). Slots are now ordered by value (`registry::
  variant_key`: base card, then damage), in `hold_variant` and in the
  decoder's check; `slots_are_ordered_by_value` grows Rampage+ first and
  still finds Rampage in slot 0. The `rampage` golden proving set was
  re-recorded (its games depended on the old order; golden.txt and every
  other proving set unchanged).
- `sts.solve`, the solve store's `fetch` and `positions` named actions
  through an empty binding and would panic on a variant (or a generated
  card): they now use the state's binding.
- Spec 8's own speed numbers (below, with H3).
Optional, done: a replayed copy's variant is dropped once no card holds it;
with every slot in use, a copy whose own old variant frees a slot still
grows (`a_full_slot_table_still_grows_the_copy_that_frees_its_slot`).
Optional, not done: ids mode shows a variant as `id_unknown`; the
interner replaces damage only in a card's on-play effects (no in-scope card
has damage in a conditional row); a card both Ethereal and Retain is kept
(the game exhausts it); render's `action_name` prints `<generated>` for a
variant (Python labels use the variant's name).

## Content packs carry every atom (rules-engine spec 10 stage 1; 2026-11-02)

Spec `pack-every-atom.md` (folded here; the `runtime-registry.md` draft
holds the remaining stages for the owner). Built on `engine-next`.
- Pack cards: any type, every flag, `tags`, conditional `rows`,
  `turn_end`; pack powers: `hooks`, `statics`, `replacements`, `debuff`;
  every effect but the monster-only ones, every target, trigger and
  condition. Generated attacks and skills now load (the big-picture
  re-scope's first step); `scripts/gen_content.py` still writes power cards
  only.
- Generated powers' statics and replacements apply at play time: the fast
  paths' power lists also scan the bound generated slots (none in an
  official-only combat, so existing play is untouched).
- `registry::card_json` / `power_json` write any official card or power as
  a pack entry; `engine/tests/packs.rs` loads every official card (128) and
  every official power with hooks, statics or replacements back and checks
  the definitions equal, field by field; generated Accuracy-, Intangible-,
  Body Slam- and Survivor-like content plays as the official.
- Not done (stages 2-5, owner's call): versions hashing packs (content
  datasets already carry their pack's hash), monsters in packs, official
  content from files, the sparse state representation. A generated card
  can't grow (variants need an official base).

## Search memo stores each state once (2026-11-02)

Not a series spec: a speed change the series' profile pointed at (about
75% of a two-turn search moved whole states into and out of `HashMap`
buckets). `search::Tree` keeps expanded states in an append-only `Vec` per
turns-left value and leaves in the evaluator's `Vec`; an `Index` maps each
state's FxHash to a chain of indices, comparing full states only on a hash
match. Nothing reads table order, so results can't change.
- H4: `two_turn_phases 100 --check` byte-identical to the pre-series build
  (nodes, leaves, cuts, actions, value bits).
- Speed (interleaved, before vs after on the same branch): one-turn search
  **+52%** games/s at 1 thread, **+32%** at all threads (5 runs, every pair
  faster); two-turn real search 12.0-13.0 s -> 7.0-7.5 s for 60 elite and
  boss decisions (3 runs each), about 1.7x. Against the pre-series build,
  search is now faster than before the series.
- `engine/examples/two_turn_phases.rs` still times its own copy of the old
  tree for its phase split; its `real search` line and `--check` use the
  real search.
- Follow-up idea: the exact solver keeps its own state-keyed tables
  (`solve.rs`) and is ~70% of a non-lean training round; the same storage
  may pay there.

## Cross-spec review of the series branch (2026-11-02)

A workflow ran four reviewers on the whole branch (rule interactions,
codec and records, features and nets, search and speed), each finding
checked by an independent skeptic told to refute it: 13 findings, 9
confirmed, all fixed, each with a test (`engine/tests/packs.rs` unless
named):
- **Warm start refused every saved parent** (`stsnet.widen` refused any
  change of the pile list; spec 7 appended `next_draw` / `known_later`):
  widen now accepts piles appended after the old ones and gives their head
  slots zero weights (`test_warm_start.py::test_widen_identity` widens the
  saved `value_ids` net, five piles, within tolerance).
- `sts.run(record=True)` / `values=True` named actions through the spec's
  starting binding and would panic once a Rampage variant was played: each
  recorded action is named through its own state's binding.
- A replayed copy's grown variant was never dropped (the drop ran while the
  copy was still in play): it now runs once the copy has left play.
- Damage and block fast paths ignored negative stacks of a generated `Add`
  static and rounded a generated block multiply before Frail: any side
  holding a generic or generated static power now goes through the row
  interpreter (`interpret_attack_damage` / `interpret_block`, the
  reference; equal to the fast path on official content, checked by
  `statics_table_matches_fast_path`); official-only combats keep the fast
  path.
- `DebuffApplied` replacements other than `Cancel` (cap, add, multiply)
  were computed and dropped: the replaced amount is applied.
- A replaced HP loss below zero would heal: floored at 0.
- Packs accepted picks and random hits in hooks and at turn end (play
  would panic) and zero denominators: refused at load.
Refuted (with reasons in the run's journal): non-canonical floater bytes
(the decoder sorts), ids mode naming variants `id_unknown` (documented),
widened parents not reproducing on old states.

H3 (spec 8's owed number, `scripts/inference_speed.py`, old module vs the
branch, Rust inference, 3 alternations of 3 runs, medians): self-play 344
vs 348 games/s (level), tight fights 281 vs 309 (+10%, the search memo).
The encoder skips building row kinds a net's layout drops (static,
countdown, replacement, pattern), so older nets don't pay for them.

## Series row kinds are opt-in (2026-11-02, confirmed by the owner)

Supersedes the "features" lines of specs 4, 5 and 9 on one point: the row
kinds `static`, `countdown`, `replacement` and `pattern` are **written only
when asked for**, like lookahead, rates and start HP: `sts.Features(...,
extra_rows=True)`, or automatically when a layout's `row_kinds` lists one
(so a net trained with them reads them back). By default the encoder writes
the pre-series kinds (triggered, threshold, held) and `row_kinds` says so.
Why: written by default they made rows per state 12.0 -> 21.1 and row data
2.5x on the fixed set (static +3.6 rows, countdown +2.8, pattern +2.5,
replacement +0.3), so every new net and training cache would have doubled
its row memory (memory was the binding limit; `test_curriculum`
could no longer allocate its cache under the running jobs). Off by default,
rows per state are as before; rows are 131 wide instead of 92 (new
trigger, condition and effect-scalar columns). Alternative: on by default
(the series' intent that nets read the new atoms); rejected for now since
no spec in the series trains a net and the warm-start curve can opt in.
How a net opts in: its meta's `row_kinds` lists the kinds (`layout_of`
saves it, and loading turns the kinds back on); `sts.Features(...,
extra_rows=True)` alone isn't recorded in a saved net. `stsnet.widen`
keeps a parent's own row kinds unless the caller names kinds, and never
drops one (refused). `finetune.py` names today's defaults plus the parent's
opt-in kinds (plus its config's `extra_rows` / `row_kinds`) and encodes its
training, validation and replay sets with them, so the saved net reads what
it was trained on (series review fix A1, option (b)). Reversible: the default is
`extra_rows=false` in `PyFeatures`' signature and the `false` passed by
`Combat.features` and `PyNet`'s load (`py/src/lib.rs`). Old contract nets
are unaffected either way (`series_check.py` PASS).

Also from the review of this change: a `DebuffApplied` replacement acts on
the debuff's size (a Strength loss's too) and cancels it at 0 or below, so
a pack's replacement can't leave a negative debuff or a 0-stack round
flag; `widen` gives an appended pile (`next_draw`, `known_later`) its
parent pile's head weights, so the widened net scores a known top as its
parent did (`test_warm_start.py::test_widen_known_top`).

## Series review fixes: the cut (2026-11-02, manager's call, owner present)

The owner's max-effort code review of `engine-next`
(`docs/specs/series-review-fixes.md`, one file per finding group) lists 36
build steps. An independent check found every top finding real, but only
A1 reaches the official pipeline: since 662b6c6 a warm fine-tune of a
parent saved before threshold and held rows (the 10-29 champion,
`models/value_effects.pt`) trains on rows its saved net then drops. B1 and
B2 are generated-content rule bugs already on main; the rest needs
hand-written packs or crafted bytes that nothing produces today. So the
spec is cut in three:
- **Pre-landing slice, built now:** A1 with option (b) (a fine-tune trains
  and saves today's default kinds plus the parent's opt-ins; `widen` takes
  named kinds and refuses to drop one); a finetune config key to opt into
  the series' row kinds (`extra_rows`, `row_kinds`), which the planned
  rows-on vs rows-off burst needs; `registry.replay` checks each replayed
  game's outcome (option (a)); H1 option (a) (`runtime-registry.md` stays,
  marked "DRAFT, not queued"); E4 (the fingerprint hashes registry.rs).
- **Generator-hardening bundle, later:** B1, B2, C1-C5, D1-D7, built with
  the extension of `scripts/gen_content.py` to attacks and skills. D7 is
  widened to refuse GrowDamage in pack hooks too, which retires most of E1,
  E2 and C3 (they need a pack hook that grows the card in play).
- **Backlog:** A2-A5, B3, E3, E5, E6, F, G, K and the unverified follow-ups.

Owner decisions taken as the spec recommends: 1 (b), 2 (a), 3 (a).
Alternatives: build all 36 steps before landing (days of build and review
for paths no job reaches; rejected as out of proportion); for A1, option
(a) (the parent's own kinds: old parents never learn Mode Shift, split or
Burn rows, and new fine-tunes would read different inputs from main's 0059
arms); for decision 2, re-record the 31 generated datasets now (machine
time) or build spec 10 stage 2 first; for H1, remove the draft from the
branch. E4 hashes all of registry.rs rather than moving the variant rules
into cards.rs, so the next official rule put there can't slip past the
fingerprint; the solved DB is retired at landing anyway.

## Card rewards are a goal-2 lever (owner away, 2026-11-02)

Reads of `docs/specs/card-rewards.md` (results doc "Card rewards: deck
choice is a goal-2 lever as big as depth"): from the starter deck a
simulating chooser beats random picks by +0.184 clears (se 0.027; rule
bar +0.05), random beats skipping by +0.364; from cell decks random adds
+0.188 and sim +0.049 more. Card rewards become a goal-2 workstream.
The spec is folded here; as built, with two amendments to its text: the
sim chooser scores the pre-boss floor at the post-rest HP; the reward
pool leaves out Strike / Defend / Bash. Known gaps (optional review
items, not done): `tag()` ignores rewards / start, so always pass
`--out`; sim encounters ignore the no-repeat rule.

Decided: (1) the next card-reward step is a less myopic sim chooser
(score each option against the next floor and the boss pool), read
against today's sim from the starter deck with the gauntlet protocol;
(2) after that, goal 2's headline number moves from the cell gauntlet to
`--start starter --rewards sim` (the cell decks are pre-built and clear
more than a starter deck with rewards, so they overstate a run).
Alternatives: keep the cell gauntlet as the headline (cheaper, but it
can't see deck choices); a learned chooser now (no data yet on how much
a better hand-made chooser adds); a run layer (the owner's simulator
decision). Reversible: options of `gauntlet.py`.

## Sim-boss spec confirmed (owner away, 2026-11-02)

Spec `docs/specs/sim-boss.md`: the sim chooser also scores each option
against the boss pool (1:1 with the next floor), because boss deaths
barely moved under today's one-floor chooser. Read against today's sim
from the starter deck with the gauntlet protocol. Alternatives: more
fights per option (doesn't address the horizon), a two-turn sim (much
slower), a learned chooser (wait for this read). Reversible: a flag.

## Sim-boss passes: new headline setting (owner away, 2026-11-02)

The sim chooser with the boss in its horizon beats plain sim from the
starter deck: protocol pass at n 162, clears +0.155 (se 0.042), boss
deaths 44 vs 69 of 200 (results doc "Sim chooser with a boss horizon
passes"). Spec folded here (as built; `--sim-boss`). Decided: goal 2's
headline setting is now `--start starter --rewards sim --sim-boss`
(Act-1 gauntlet from the starter deck with card rewards); the cell
gauntlet stays as a fixed-deck combat read. Product reads from now on
play both. Alternatives: keep the cell gauntlet (can't see deck
choices, and its pre-built decks overstate a run); wait for a learned
chooser (the hand chooser already passes). Reversible: options.

## Review 2026-11-02b adopted in part (owner away, 2026-11-02)

`docs/research/big-picture-2026-11-02b.md`. Adopted: (1) measure
run-level training-seed noise before any more training verdicts (seed
twins on the one-turn gauntlet, queued); (2) goal-2 effort goes to the
run layer next (rest-site heal vs upgrade, removal, path choice), each
screened one turn deep with `--against`; (3) heuristic anchor second half
(b4) parked, its question answered. Not adopted yet: raising the runner's
two-slot cap (an operating rule in manager.md; more threads per job is
the skeptics' cheaper lever, tried first); parking the survival arms (the
owner's design; they stay queued behind the twins). Skeptics corrected
"training never moved run level": the learned net beats the heuristic by
+0.04-0.06 clears at equal depth; what failed was selection on proxies.

## Rest-site spec confirmed (owner away, 2026-11-02)

Spec `docs/specs/rest-site.md`: `gauntlet.py --rest sim` lets a chooser
heal or upgrade one card at the rest before the boss, scoring each option
by 16 one-turn fights against the sequence's own boss (the real game shows
the boss on the map). Next Q3; built 90a8ad5, read queued (0059l7r3b37g)
against the sim-boss headline file extended to 500 sequences.
Alternatives: score against the boss pool like sim-boss (less faithful to
what a player knows at the rest site), a fixed rule (upgrade above some
HP; would need its own threshold sweep), more rest sites in the gauntlet
shape (changes every existing file's comparability). Reversible: a flag.

## Product net: the 10-29 net (owner away, 2026-11-02)

The product player stays two-turn search `@hpe0.01` (decisions "Two-turn
@hpe is the product player") but its net changes from burst8hp2 s1 to the
10-29 net (`runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpe0.01`):
it passed on 0-249 (+2.37 end-HP) and the pre-registered confirmation on
500-749 (+3.01 end-HP, z 4.1; clears +0.052, se 0.021; both halves).
The ladder's champion file (tight2, one turn) is not changed: the ladder
decides net order one turn deep on tight2, which the gauntlet re-rank
shows doesn't track run-level play; changing it would only re-cache.
Alternatives: keep burst8hp2 (worse on both reads); also replace the
ladder champion (no reason yet; the ladder may be retired as a product
gate). Reversible: a player string.

## Rest-site chooser closed (owner away, 2026-11-02)

`--rest sim` failed the protocol at n 50 (-1.22 end-HP): 16 fights per
option let a lucky upgrade beat heal (results doc "Rest-site chooser
fails"). The flag stays (off by default); no further rest-site work on
the 11-fight gauntlet, whose one rest sits just before the boss. Next run
layer item: card removal. Alternatives: 64 fights per option, or a
margin rule (upgrade only if it beats heal by 2 se); both cheap, but the
expected gain on this gauntlet is under the ~1 HP MDE.

## Card-removal spec confirmed (owner away, 2026-11-02)

Spec `docs/specs/card-removal.md`: one removal after the first elite
(shop proxy), arms `--remove none / strike / sim`; the sim chooser reuses
the reward chooser's scoring over option decks. Reads: strike vs none
(what a removal is worth), sim vs strike (what choosing adds). Next Q3
after the rest site closed. Alternatives: Neow-style removal before floor
1; path choice first (needs a map, bigger); a shop with gold (needs an
economy). Reversible: a flag.

## Mixed depth for screens (owner away, 2026-11-02)

`--one-turn-floors 3` (floors 1-3 one turn deep, the rest two turns) is
level with full two-turn play on the cell gauntlet (end-HP -0.02, se 0.05;
clears identical) and takes 57% of the wall time (results doc "Mixed
depth"). Two-turn screening jobs on the cell gauntlet use it from now on.
The headline setting (starter deck + rewards sim + sim-boss) keeps full
depth: a starter deck loses more HP on floors 1-3 and the check hasn't
been run there; the queued headline halves (0059l7r3b39a/b) stay at
full depth so the number is the product player's. Alternatives: adopt it
for the product player too (saves 43% of every run; unchecked on the
headline deck); one-turn floors 1-4 (floor 4 is a hard hallway, not
checked). Reversible: a flag.

## Card removal read: a removal is worth ~1.8 HP, the chooser is closed (owner away, 2026-11-02)

Strike removal after the first elite gains +1.78 end-HP (se 0.83) and
+0.038 clears on the headline setting, above the spec's ~1 HP bar, so
removal and shops stay on the run-layer list (a shop with gold is the
real version). The sim chooser fails the protocol against the strike rule
(-1.41 end-HP, fail at n 222) because it removes earned reward cards 24%
of the time and keeps 23%: the second chooser lost to selection noise
after the rest site, with ~9 options on 16 fights each. The flag stays;
no further removal-chooser work on this gauntlet. If a chooser is wanted
later, score only starter cards + keep (4 options, and Defend = Strike on
this read so there's little to gain) or require a 2-se margin over
`strike`. The headline setting is unchanged (no removal); removal joins
the run layer when the full-run number is built. Alternatives: make
`--remove strike` part of the headline now (would need every control
file re-run); 64 fights per option. Reversible: flags.

## Elite-skip spec confirmed (owner away, 2026-11-02)

Spec `docs/specs/elite-skip.md`: `gauntlet.py --elites skip|hp [--elite-hp
40]` fights a hard hallway instead of an elite, always or when the HP
entering the floor is under the threshold. On this gauntlet an elite has
no payoff (no relics; the card reward is a hallway's), so `skip` measures
the ceiling of what any path choice could be worth here, not a product
rule; `hp` is the one plain rule. Reads one turn deep on the headline
setting against the headline file. Ceiling under ~1 HP end-HP: path
choice drops off the run-layer list and a map waits for the owner's
simulator decision; large and mostly captured by `hp`: the rule joins the
full-run number. Next Q3 after the removal read. Alternatives: a map
with elite payoffs (relics) first (bigger, and it pre-empts the owner's
open simulator decision); a sim chooser for the path (with no payoff it
always skips). Reversible: a flag.

## Line-seed spec confirmed (owner away, 2026-11-02)

Spec `docs/specs/line-seed.md`, from approach 1 of the owner-requested
approach review (`docs/research/approach-review-2026-11-02.md`, on main since
7328936): `gauntlet.py --two-turn --line-seed` seeds every
two-turn search of a combat turn with the same sample seed, so later
decisions in the turn re-search under the first tree's luck and the
player decides as one that commits to the first tree's line would,
except where the tree cut. No engine change; a probe records how a
turn's two-turn cost splits by decision index. The read is an
equivalence read against the product's own file (end-HP within +-1.0 HP,
clears within +-0.012): a pass means exporting the principal line from
Rust (stage 2, ~1.5-1.9x cheaper two-turn play) is worth specifying once
the engine-next branch has landed (it reworks search.rs, so a Rust change
on main now would collide); a fail closes the approach. Alternatives:
build stage 2 directly (collides with engine-next; and the question
"does committing cost strength?" is answerable without it); the review's
agreement probe first (it would fail trivially: a changed seeding scheme
disagrees ~6% like any reseed, which is not the question). Reversible: a
flag.

## Next re-ranked from the approach review (owner away, 2026-11-02)

The owner asked the engine-next session for a high-level review of every
approach (`docs/research/approach-review-2026-11-02.md`, 99 read-only
agents, skeptic-checked). It is newer and deeper than the 11-02b
big-picture review, so the manager re-ranks "Next" from it while keeping
what is already running: (1) cheap depth (line seed now, stage 2 after
the landing; the sampled-draw leaf belongs to the branch module), (2) the
fitted run value as the choosers' unit (step 0 half-passes: floors 6-8
yes, floor 5 no), (3) the result cache for run-layer reads, (4) the
mutated-monster bench stage A, (5) the generated character (needs the
branch module and the owner's bundles-vs-atoms answer). Its stop list is
adopted as far as it is the manager's to adopt (no more training-recipe
arms as goal-2 levers; no promotions on tight2 / run-HP / ladder for goal
2; no c raises; no runtime-registry stages 3-5 or entity-shape without
a bench that needs them). Not adopted (the owner's): dropping the solved
DB and the solver as a label source, the manager cadence, the survival
arms (they stay queued as the owner designed them), the simulator and
arena decision. The seven "Decisions for the owner" are listed under
"For the owner". Alternatives: wait for the owner's reading of their own
review (the queue would idle on the old order meanwhile); treat it like
a big-picture file and re-rank wholesale (it isn't the manager's to drop
owner-designed arms).

## Headline number: two-turn product on starter + rewards + sim-boss clears 0.804 (owner away, 2026-11-02)

Goal 2's headline is now the 10-29 net searched two turns deep with the
end-HP price on the headline setting: 0.804 clears over 500 sequences,
+0.124 (se 0.022) over the same net one turn deep and +0.270 over the
heuristic (results doc "Two-turn product on the headline setting").
Consequences: (1) every headline read from now is two turns deep, so the
mixed-depth screening check runs on this setting next (queued b39b2; a
level result makes `--one-turn-floors 3` the default for headline reads
too); (2) cheap depth stays lane 1 (the committed-line read b39b1 is
queued; stage 2 waits for the engine-next landing); (3) the heuristic
two-turn anchor on this setting is not queued (it would cost ~4.5 h for a
number about the net's share, which the cell anchor already gives:
0.612 vs 0.648 on 0-249). No new big-picture review after this result:
the owner-requested approach review of 12:28 today already covers the
state and predicted this direction (A2); the next review runs after the
next headline change, as that review recommends. Alternatives: a
big-picture review now (99-agent review 2 h old); queue the heuristic
two-turn anchor (4.5 h of a two-turn slot). Reversible: all reads.

## Elite-skip read: path choice is real, the headline keeps no path rule (owner away, 2026-11-02)

Skipping every elite (no payoff on this gauntlet) is worth +14 HP end-HP
and +0.20 clears at n 50; the plain rule "skip an elite entered under 40
HP" is worth +1.53 HP (se 0.61, protocol pass at n 83) and fires on 11%
of elite floors (results doc "Elite skip"). Per the spec's rule the
ceiling is large and the HP rule captures a part of it, so path choice
stays on the run-layer list for the full-run number, next to removal
(+1.8 HP). Not adopted into the headline setting: on a gauntlet where an
elite pays nothing, any path rule makes the yardstick reward avoiding
elites, and the honest measurement needs an elite payoff (relics, better
rewards), which is the owner's open simulator decision. `--elites
skip|hp` stay as flags (README); the spec is folded. Alternatives: add
`--elites hp` to the headline now (every control file re-run; biased
yardstick); a threshold sweep (30, 50) before deciding (it would only
move a number that isn't entering the headline). Reversible: flags.

## Training: when it runs and when it stops (owner, 2026-11-02)

The approach review (`docs/research/approach-review-2026-11-02.md`, "The
record has one shape" and pattern 6) found every gauntlet gain since
10-29 at search time or in the run layer, while training took about 260
of 575 booked thread-hours: round 1 gave +0.017, rounds 2-10 +0.006 to
-0.003, 40k to 80k games +0.003. Training games come from the same
one-turn search the net plays in, so the net catches up with its teacher
in about one round. Agreed with the owner:
- **When.** A training job gets CPU only for something new to learn: a
  stronger teacher (two-turn product games, review approach 7), inputs
  the net can't see today (engine-next's layout, the survival histogram),
  or new content. Judged on the gauntlet protocol, never on tight2,
  run-HP, the ladder, regret or validation loss across recipes.
- **How much.** Not a measured minimum (a learning-curve experiment costs
  the CPU this saves), but a stop at the plateau. Each round's net plays
  the one-turn cell gauntlet once (500 sequences, about 2.5 min at 3
  threads); the read is `--against` the file of the net from two rounds
  back with `--d1 4`. The protocol's SPRT passes when the mean paired
  end-HP gain is above about D1/2, so a pass means the two rounds gained
  more than about 2 HP (1 HP per round) and training continues; a fail
  stops it. Comparing two rounds back rather than with the previous round
  doubles the signal for the same noise (se about 0.55 HP at 500
  sequences) and judges a slow climb by its total. A climb under 1 HP per
  round isn't worth a round's CPU when free search-time changes buy 1.4-1.8
  HP. A false stop is cheap: training resumes from the last net.
  Cheap fine-tune bursts may look three rounds back (`--d1 6`).
- **Free pre-screen (optional, not built).** The share of
  `data/bench/decisions.json` picks the new net changes against the
  previous one; far below the round 0 -> 1 share means stop without
  playing. It can stop training, never promote a net.
- **Goal 1.** How few games a net needs to adapt to new content is the
  goal-1 number (the warm-start curve), so there the curve is measured.

Alternatives: a measured minimum per recipe (costly, and the plateau is
already known for today's recipe); a window of three pairwise reads
(about 0.6% false stops instead of 3%, but one more round of training
before every stop, and it still misses a slow climb); no rule (training
took 45% of the CPU for no run-level gain).

## Two-turn self-play round: kept, small and targeted (owner, 2026-11-02)

Approach 7 of the approach review (pattern 6, "teacher equals student")
stays, as one run. A check on existing files first: on the cell gauntlet,
fights that the 10-29 net started from the same state (same fight, same
entry HP) one turn deep (`net1029-hpb0.01.json`) and two turns deep
(`net1029-hpe0.01-two-a.json`) almost never change outcome (0% flips on
hallways and elites, 2.8% on bosses, n 72), and two-turn play saves only
+0.90 HP per hard hallway (sd 3.3), +0.51 per elite (sd 6.4), -0.03 per
boss (sd 11.9) when both win; but a third of elites and over half of
bosses end 5+ HP apart. (A rough slice: matched entry HP favours early
floors, one file prices with `@hpb` and the other `@hpe`, and different
play changes later draws.) So the stronger teacher moves outcome labels
by about the round 0 -> 1 step (+0.017), and it does not address the
leaf's large mis-pricings (HP, enemy Strength), which today's labels
already contain. Kept as: a few thousand games on elite and boss cells
only, from the two-turn product, outcome labels, a burst fine-tune of
the 10-29 net (2 seeds), read `--against` the 10-29 net one turn deep and
confirmed two turns deep; after the line-seed read (cheaper two-turn
games) and after the engine-next landing. A null closes the
outcome-label family. Alternatives: drop it (the label shift is small;
but it is the one training test with a reason to beat the plateau, and a
null settles the question); the full 20k-game round (hallways add almost
no label change); labels from the two-turn search's own values (far less
noise than single outcomes, idea #49; a later form if this run passes or
the outcome noise is the reason it fails).

## Run value along HP: the plan (owner, 2026-11-02)

On the headline file, boss win by arrival HP is an S-curve (0.31 in the
30s, 0.44 in the 40s, 0.83 in the 50s, 0.97 in the 70s, 0.99 in the 80s;
approach review pattern 3): above the HP the boss can take off this deck
before it dies, the win is nearly sure; below it, it depends on draws.
The jump sits per boss and per deck, so one deck's curve is sharper than
the average, and it blurs early in the act (step 0: floors 6-8 pass, 5
fails). The owner approved using it where the player trades HP, as
players do: (a) a causal check first, HP-swept boss replays (the 14x
slope is observational: low arrival HP also means weaker decks, so it is
an upper bound); (b) the run decisions (card picks, rest vs upgrade,
elites) scored by V_run instead of raw HP or noisy sims; (c) a combat
price by floor, after a (b) pass; (d) the survival score's leaf as
P(lose h) x V_run(HP - h), if the survival arms pass. Each read on the
headline gauntlet with `--against`. manager.md Next L2 holds the steps.
Alternatives: use the observational curve directly (too steep if the
confound is large: a uniform price raise already lost -0.032 clears);
keep flat c and rules like HP-40 (leaves most of the +14 HP elite-skip
ceiling); a learned chooser (no data on held-out offers yet).

## Goal-1 yardstick: paired modifiers, measured per modifier (owner, 2026-11-02)

Insight 5 of the approach review: the goal-1 benches mixed how much
harder new content is with how unfamiliar it is, and their reference
(the heuristic) can't see 84% of generated powers. Agreed with the owner
(`docs/research/chimera-cards-2026-11-02.md`):
- **Mutations as boon + bane pairs** on official parents, in the style of
  the Chimera Cards mod: cards ("near": number and keyword trades from
  atoms the heuristic prices; "far": the few new atoms) and monsters (our
  own, e.g. Metallicize 4 with -15% HP, +2 Strength per turn with -30% HP,
  +30% HP with -1 damage per hit, two half-damage hits, Weak on hit with
  -20% damage, Thorns 2 with -10% HP). The parent is the strength
  reference, and the player's drop beyond the parent's difficulty is the
  novelty cost.
- **Balance is measured, not assumed.** The owner played the mod and some
  modifiers aren't balanced. Each modifier's strength change is measured
  on its parent fights (win and HP lost) with the heuristic and the
  two-turn product; where both agree the content got harder or easier,
  that's difficulty, recorded per modifier; modifiers far off balance are
  retuned or kept as labelled one-sided changes. The net's drop beyond
  the measured difficulty change is the goal-1 number.
- **Stacking.** Several modifiers may land on one card or monster, as in
  the mod (n rolls, each picking a modifier with a rarity weight). The
  number stacked is the "distance from the parent" axis (1 = near, 2-3 =
  far). Check on a sample that a stack's measured difficulty is about the
  sum of its parts before using the sum.
- **One-sided changes stay too** (HP x1.25, +Strength, Ritual): they
  measure how the player copes with harder content (Ascension-like), a
  different question from novelty.
Alternatives: one-sided perturbations only (confounds difficulty with
novelty); trusting designer balance (the owner found it uneven); a
learned strength reference (an oracle net trained on the content: costly
per pack, kept for later).

## Q6 two turns: search takes over most of the encoding's edge on unseen cards (owner away, 2026-11-02)

On the generated bench's elite and boss cells the effects encoding beats
ids by +0.059 one turn deep and +0.017 (se 0.012) under the product's
two-turn search, on the same s1 twins and cells (results doc "Effects vs
ids on the generated bench, two turns deep"); on known cards +0.166 ->
+0.076; on bosses ~0 at both depths. Decided: the effects encoding stays
(one-turn screens, the sim choosers and +0.08 on known elites still use
it); goal-1 numbers are read under the product's two-turn search, not one
turn deep (the goal-1 yardstick's "two-turn product" reference already
says so); no ids-vs-effects arm is run again. Alternatives: drop the
effects columns for a cheaper encoder (loses +0.08 on known elites and
the one-turn choosers' edge); more seeds (the shrink is paired and ~3x
its se; not worth 5 h of two-turn CPU). Reversible.

## Cost-saving candidates are read at fixed n (owner away, 2026-11-02)

`--against` runs the gauntlet protocol, which stops with "fail" as soon
as a candidate is clearly not 1.5 HP better than the control. For a
candidate meant to be level and cheaper (mixed depth, line seed) that
verdict arrives at the first look and says nothing about "worse". Rule:
such a candidate plays a fixed block (250 sequences) without `--against`
and is read paired: level = end-HP within +-1 HP and clears within +-0.02
of the control, with the se beside it. The queued line-seed read b39b1
runs with `--against` and will stop the same way if it is level; its
file keeps the rows played, so it is read at whatever n it reaches and
continued to 250 if needed. Alternatives: a non-inferiority SPRT (H1 =
-1.5 HP) in `gauntlet_protocol.py` (a small change, do it when the next
such read is queued). Reversible.

## Boss replays: the boss curve is causal; the run value is per boss (owner away, 2026-11-02)

L2 (a)'s check (decisions "Run value along HP: the plan") passes: with
only entry HP varied on each headline deck's own boss fight, 87% of the
observational slope between the 40s and the 60s remains (Hexaghost 1.04,
Slime Boss 1.24, Guardian 0.78) and arrival HP barely predicts a deck's
win at fixed HP (corr +0.13). So L2 (b)-(d) keep their full size, and the
curve they price with is per boss (Slime Boss near-sure from 40 HP, the
Guardian a cliff around 50, Hexaghost a slow climb to 0.90), taken from
`results/boss_replay/` (one-turn causal replays, pooled over decks),
with the per-deck step (median width 10 HP) as the room for a chooser
that knows its deck. Alternatives: the observational curve (within 13%,
so also usable; the Guardian's is 22% too steep); a pooled curve (wrong
for two of three bosses); per-deck curves at choice time (24 fights per
option, 3x the sim-boss cost; later, if (b) passes). Reversible.

## Run-value chooser spec confirmed (owner away, 2026-11-02)

Spec `docs/specs/run-value-chooser.md` (L2 b, card picks): the sim
chooser's next-floor fights are scored by the run value instead of
`1 + 0.01 x end HP`: V(h, floor, boss, deck) = P(reach the boss at h |
neighbours in a fit half of the headline file by HP at the floor after
next, non-parametric) x P(win the sequence's own boss | h, deck), the
boss's causal curve (`BOSS_CURVE` from the b39d1 replays) shifted to the
deck's level from 8 fights against that boss at the post-rest HP; the
boss enters once, through the curve. Rows record `took_sim` (the old
score's pick on the same fights) for the pick-change rate. Check: fit
250-499 / play 0-249 and the mirror, one turn, against the one-turn
headline file; pass = pick change >= 10% and a protocol pass (or > 1.5 HP
end-HP) on both halves. Choices: the actual boss rather than the pool
draw (information the map gives; the old `--sim-boss` is unchanged), and
neighbours rather than a logistic per floor (250 fit sequences give
20-160 per HP band; nothing to fit). Alternatives: a fitted logistic per
floor and boss; per-deck curves at choice time (3x the sims); keep the
flat price. Reversible (a chooser kind).

## Mutated monsters stage A spec confirmed (owner away, 2026-11-02)

Spec `docs/specs/mutated-monsters-a.md`: the goal-1 enemies rung on what
a patch of the fight's start state can express today (HP scaled, a power
added), as the owner's yardstick asks: one-sided modifiers (HP x0.8 /
x1.25, Strength +1 / +2, Metallicize 3, Ritual 2, SharpHide 2), the
owner's boon + bane pairs (Metallicize 4 with HP x0.85, Ritual 2 with HP
x0.7, SharpHide 2 with HP x0.9) and one stack of two pairs, on 200 of
the gauntlet's elite and boss starts with 8 common seeds; difficulty per
modifier = the heuristic's and the two-turn product's win change (a
verdict when both move the same way); novelty cost = the one-turn net's
drop beyond the heuristic's, paired by start; depth repair = the two-turn
product's contrast on a 40-start subset. Stand-ins: SharpHide (damage to
the attacker per hit) for Thorns, which the engine lacks; Ritual 2 for
"+2 Strength per turn"; `play_on`'s plain two-turn search for the
product's guarded fallback (no play-from-state entry; the contrast
cancels the difference). Pattern mutations (damage per hit, split hits,
Weak on hit) are stage B after the engine-next landing. Alternatives:
the bias audit's leaf ratio only (doesn't track play); a per-combat
monster override in the registry first (engine work, blocked by the
landing). Reversible (an analysis script).

## Crossed chooser arms read: the chooser is the larger one-turn lever (owner away, 2026-11-02)

Results doc "Crossed chooser arms": of the one-turn headline lead over
the heuristic (0.688 vs 0.532), swapping the chooser moves ~0.09 and
swapping the fighter ~0.06, interacting (the net's chooser is worth most
with the net fighting); on held-out cards the chooser swap is -0.184 and
the fighter swap -0.024 / -0.096. Decided: chooser work stays a goal-2
workstream beside depth; goal-1 reads on the headline setting keep the
chooser in the loop (a new card's price enters through the chooser's
sims as well as through play); the two-turn split is not run unless a
decision needs it. Spec `chooser-player.md` folded (`--chooser` stays as
a tool). Reversible.

## Run-value chooser: fails, use (b) closes for card picks (owner away, 2026-11-02)

Results doc "Run-value chooser: fails its first check": -0.044 clears
and -1.45 HP (se 0.026 / 1.0 pooled over the two cross-fitted halves)
against the sim chooser, 22-24% of picks changed; the rule (a protocol
pass or > 1.5 HP on both halves) fails. Decided: card picks keep the sim
chooser with the sim-boss term; `--rewards vrun` stays in the code as a
tool (spec folded); the run value's other uses are unchanged: (c) the
combat price by floor after the landing, (d) the survival leaf if the
arms pass; the rest-site and elite uses of V_run are not built (they
would inherit the same unit). Ideas recorded, not run: V from the pooled
per-boss curve without the deck shift; the old score as a tiebreak where
the curve is flat. Alternatives: more seeds on the sims (3x the CPU; the
sim chooser has the same noise and wins); a learned chooser (no held-out
offer data yet). Reversible.

## Mutated monsters stage A, one-turn read: stat changes cheap, an unseen power on a new enemy costly (owner away, 2026-11-02)

Results doc "Mutated monsters, stage A, one turn deep": on 200 elite and
boss starts the product net loses -0.012 to -0.021 of a win beyond the
heuristic on HP x0.8 / x1.25, Strength +1 / +2 and Metallicize 3, but
-0.048 to -0.091 on SharpHide 2 (alone, paired, stacked), all of it on
Three Sentries and Gremlin Nob and none on the Guardian, which holds that
power in training; Ritual 2 costs -0.038. Two of the owner's three pairs
are off balance (Metallicize 4 + HP x0.85 is easier than the parent,
SharpHide 2 + HP x0.9 clearly harder); the stack's difficulty is about
the sum of its parts. Decided: the HP-class rule is not met (no max_hp
change); the SharpHide and Ritual drops go to the two-turn subset
(0059l8b4) for the horizon-vs-burst call; pairs are kept as labelled
one-sided changes until retuned (Metallicize 4 + HP x0.75, SharpHide 1 +
HP x0.9 are the candidates, to measure, not assume); stage B (pattern
mutations) waits for the landing. Alternatives: a burst on mutated
monsters now (the review admits it only if depth doesn't halve the drop);
treating the stack as additive without the check (it is, within 0.02).
Reversible.

## Line seed passes: stage 2 (export the principal line) is justified after the landing (owner away, 2026-11-02)

Results doc "Line seed: a two-turn player that commits to its first
tree's line plays level or better": on cell sequences 0-249 the
committed-line player is +0.60 HP (se 0.52) and +0.024 clears (se 0.019)
against plain two-turn play; the rule (within +-1.0 HP, +-0.012 clears,
not worse) is met. Decided: approach 1 (cheap depth by committing to the
line) stays open; spec its stage 2 (Rust: export the first tree's
principal line and step it until a cut or chance event, `search.rs`)
once engine-next has landed, read it on the headline setting with
`--against` the two-turn headline file (a cost-saving candidate: fixed n
250). `docs/specs/line-seed.md` stays until stage 2 is built or closed.
Alternatives: build stage 2 on main now (collides with the landing);
close approach 1 on this one read (the saving is ~1.7x of the product's
cost and the read is clean). Reversible.

## Headline re-rank: the 10-29 net is the product net, the headline setting is the final ruler (owner away, 2026-11-02)

Results doc "Standing players re-ranked on the headline setting": with
rewards in the loop every other standing net is -0.06 to -0.15 clears
below the 10-29 net (data40k closest at -0.056; data80k, best on tight2,
-0.104; the ex-champion burst8hp2 -0.148, level with the heuristic).
Decided: product candidates are read on the headline setting (starter +
sim rewards + sim-boss) with `--against` the 10-29 net's file, the cell
gauntlet stays a screen; tight2 and ladder standings from 10-29 to 11-02
are not used to rank nets for the product. Open, cheap: lean s1 (no
solve step) on the headline setting, to see whether the solve step is
what sets the 10-29 net apart under rewards (it was level on cells).
Alternatives: keep the cell gauntlet as the ruler (it understates the
gaps 3-5x); re-run the ladder on the headline setting for every net
(~8 min per net, worth it only for a candidate). Reversible.

## Lanes runner spec confirmed (owner present, 2026-11-02)

`docs/specs/lanes-runner.md`, asked for by the owner ("fold them"): lanes
with shares by dominant resource, a reservation for a waiting head (any
reason, after 10 min, or at once with `first`), memory reserved at the
measured peak with half slots for 2-thread jobs, conditions decided by
check processes, `set` for pending jobs, a filler lane, jobs pinned by
default to a snapshot of their commit (worktree with junctions, hard links
for `data/` files, a per-commit module that main's swap also installs),
exit codes kept across runner restarts by a frozen wrapper, and `impact`
for unpinned jobs. Evidence: 49% booked threads over the runner's life,
216 of 277 ids renamed to reorder, `0059l8b` waiting 29 h, a condition
("park a7/a8") never applied, about 15 module swaps under running jobs.
A review (runner, pinning and goals lenses, a skeptic per finding) found
must-fixes now in the spec: the l8b case wasn't prevented; the junction
plan didn't fit `runs/` and `data/`; removal would refuse every used
snapshot and let git delete outputs; 3 slots on declared memory would
bring back out-of-memory kills; the wrapper loaded live code; checks could
block the runner. Deferred: filler preemption (thrash risk; fillers are
short or resumable) and `needs`/`about` (wait for the claims store).
Alternatives: keep renaming and manual parking (the measured waste);
module-only pinning (fails at a landing). The lane set, charters and the
manager cadence stay with the owner.

## Mutated monsters stage A, two-turn read: horizon, not a training gap; no burst on mutated monsters (owner away, 2026-11-02)

Results doc "Mutated monsters, stage A, two turns deep": on the matched
40-start subset the product net two turns deep loses nothing beyond the
heuristic on any modifier (within +-0.025, se 0.02-0.04), while one turn
deep it loses -0.03 to -0.09 on SharpHide and the stack (elites -0.06 to
-0.09, Three Sentries -0.19); depth repairs +0.04 to +0.06 on the four
power modifiers and ~0 on the stat modifiers. The spec's rule: a one-turn
drop that depth halves is a horizon problem, no training. Decided: no
adaptation burst on mutated monsters; the goal-1 enemies rung is read on
the product player (two turns deep) from now, with the one-turn net's
drop reported as the leaf's cost; stage B (pattern mutations) after the
landing is the next enemies measurement; the pairs are retuned by
measurement (Metallicize 4 + HP x0.75, SharpHide 1 + HP x0.9 queued one
turn deep); spec `mutated-monsters-a.md` folded. Alternatives: a burst
anyway as a goal-1 "games to adapt" number (the training rule allows new
content, but nothing here is broken for the product, so the number would
not be about a failure); a power-feature row for the one-turn net (fixes a
player the product doesn't use). Reversible: the subset is 40 starts x 4
seeds; a bigger two-turn subset is a 3-hour job if the reading is doubted.

## Mixed depth on the headline: screening default, headline reads keep full depth (owner away, 2026-11-02)

Results doc "Mixed depth on the headline setting, fixed n 250":
`--one-turn-floors 3` is level with full depth by the pre-set bar (-0.012
clears, se 0.007; -0.27 end-HP, se 0.34; HP at the boss -0.2), with a
small real HP cost after floor 3 (-0.25, se 0.10) that washes out, and
saves ~30% of the wall time on the headline (43% on the cell gauntlet).
Decided: two-turn screening jobs on the headline setting (cost-saving
reads, arms compared with each other) use `--one-turn-floors 3`; headline
reads of product candidates and anything that may move the headline
number keep full depth; a paired read never mixes the two settings
between its arms. Alternatives: full depth everywhere (~1.4x the cost of
every headline screen); mixed depth for the headline number too (a likely
~0.01 clears cost on the final ruler for a 30% saving: not worth it).
Reversible.

## Lanes runner as built (owner present, 2026-11-02)

`docs/specs/lanes-runner.md` built in six steps by session
lanes-runner-ee6762, each tested first and reviewed by a spec reviewer,
merged into main and the runner restarted on it (commits 12063ab, f58998b,
b5dc8c5, a864747, 2dc8e0d with a0e4dc2, and the step 6 commit that adds
this entry). `scripts/jobs.py` now has: a frozen wrapper
(`jobs/runner-<pid>/exec.py`) that writes each job's exit code, so a
restarted runner still records `ok`/`failed`; lanes with shares from
`jobs/lanes.json` (use = the larger of thread and reserved-memory share);
a reservation for the top lane head after 10 min of waiting, or at once
with `first`; memory reserved at the measured peak; half a slot for heavy
jobs of 2 threads or fewer; conditions (`--after`, `--if-passed`,
`--on-fail`) decided each poll with parking that cascades, `--check`
processes giving verdicts, `set`, `unpark`, `verdict`; filler lanes (share
0); jobs pinned by default to a snapshot of their commit under
`sts-builds/` (`pins`, `unpin`, a 24 h sweep); and `impact sts|scripts`.
Tests: 42 in `scripts/tests/test_jobs.py` (17 new for the spec's
Verification). End to end: on the real repo with a private queue, a pinned
5-sequence one-turn gauntlet (10-29 seed-check net @hpe0.01) loaded `sts`
from its snapshot `5f699ba202f6`, main's `sts` was swapped while it ran
(rename aside, reinstall), it ended `ok`, and its rows equal those of an
unpinned run made before the swap, although the snapshot's `.pyd` (built
in `sts-builds/target`) differs in bytes from main's; an `--if-passed`
chain whose check exits 1 parked the second job; `status` showed lanes,
`RESERVED` and the park reason. The first snapshot build took 142 s at 4
cargo jobs.

Choices made while building (reversible): `after` is satisfied by any end
and parks only on a parked or missing dependency (the park list applies to
`if_passed`); only one automatic reservation at a time; "fits alongside"
checks slots only for a job that takes one; BACKFILL_MIN is gone (the
reservation replaces its cap); ids on the command line are comma-separated
and `--check` takes one string; the wrapper runs with `python -I`.

Review findings left open (optional, not built): in-lane backfill has no
time cap for a head that isn't the top lane head; `mem_gb_low` matches the
script and first word after it, often a flag; `set --lane filler` skips
the filler check and `first` lets a filler hold the reservation; `set` can
make a dependency cycle (both wait, nothing logged); `cancelled` from
`on_fail: cancel` doesn't wake `wait`; a check's Job Object handle isn't
closed (one handle per check); a killed job found dead at restart with an
exit file ends `ok`/`failed` instead of `killed`; a missing program now
ends `failed exit 127` with the error in the log. From step 5: an `add`
racing the sweep could get a snapshot being removed; a data file replaced
in main (not rewritten in place) stops matching its hard link, so the
sweep refuses that snapshot until someone looks and unpins it; default
pinning in the CLI has no test. Main's `sts` still has its own build's
bytes: install the snapshot's wheel at the next swap (AGENTS.md) so pinned
and unpinned runs share ladder caches.

## kb adoption spec confirmed (owner present, 2026-11-02)

The owner's session asked for the `kb` claims store to be turned on here
(spec `docs/specs/kb-adoption.md`, confirmed under the manager mandate by
session kb-adoption-5acbb5). Stages 1-3 are built in this session: the
store is on (`kb init`; the pre-commit hook in git's common dir judges
only staged `docs/claims/` files), seeded with about 80 sourced facts;
status is computable (product registry, spec `Status:` lines, the job
queue named as the source of "what runs"); managers record facts in
shadow mode beside manager.md. Stage 4 (manager.md's "Next", "For the
owner" and most of "Running" become facts and the queue) waits for the
stage-3 probes, a week of `kb stats`, and the owner being told, since it
changes the hand-over format. Alternatives: no store (the status quo:
sessions re-derive, docs disagree); move manager.md over at once (no
uptake data; the research found memory can hurt a strong model).
Reversible: delete `docs/claims/` and the hook.

## Product registry: configs/product.json, promoted only by product.py (owner present, 2026-11-02)

The product player lives in a tracked `configs/product.json` (player,
flags, since, decision, control files, earlier players) written by
`scripts/product.py set`, which also sets the kb fact `product/net`
(with a check that re-reads the registry). `results/ladder/champion.json`
stays the tight2 ladder's state (decisions "Product net: the 10-29 net"
kept it; it still names burst8hp2), and the fact `how/ladder-champion`
says so. Alternatives: `results/product.json` (ignored by git: worktrees
and history can't see it); rewrite `champion.json` (the ladder would
re-cache and it is a different thing). Reversible.

## Spec status is line 3 of each spec (owner present, 2026-11-02)

Every spec's line 3 is `Status: <state> (<date>[, text])` with a closed
word list (idea, draft, confirmed, building, built, closed, superseded,
umbrella), read by `scripts/spec_status.py` (exit 1 on a missing or bad
line; `--open` lists specs in flight). Specs in flight also have a kb
fact `spec/<slug>/status` re-confirmed by that script. Alternatives: a
fact per spec (most are closed); front matter (a bigger edit to every
spec). Reversible.

## Survival-score arms fail: the HP price stays the constant bonus (owner away, 2026-11-03)

The owner's survival-score design (`docs/specs/survival-score.md`, folded:
a histogram head for HP lost from now, search scores win c + w x end HP /
100) ran as two arms, s1 and s101. They save ~2.6 HP per fight over a bare
net but ~0.9 less than the same net with the constant search bonus
(`@hpb0.01`), lose 0.06 of a win on tight2 held-out against the bar's 0.02,
and a play-time c sweep (2, 4) doesn't move them (results doc
"Survival-score arms: fail"). Decision: the arms fail by the spec's rule;
the survival score is closed as an HP lever, and use (d) of the run-value
plan (the survival leaf) closes with it. The product's HP price stays the
end-HP bonus `@hpe0.01`; a state-dependent price comes next, if at all,
from the fitted run value. The code stays (`score: survive`, `@sc`,
`hp_loss` labels: small, tested, and goal 1 may want a histogram head
later); the spec is folded into README and this entry. Alternatives: a c
sweep in training (0.5 / 2; ~3 h of CPU for a recipe 0.06 of a win
behind), a bonus on top of the survive rule (the spec forbids it: it prices
HP twice). Reversible: the configs and nets stay.

## Solve step at run level: not shown on three seeds, left to the owner (owner away, 2026-11-03)

Three seed pairs of the 10-29 recipe with and without the solve step, one
turn deep on the headline: pooled -0.032 clears (se 0.021) and -1.58 end-HP
(se 0.79) without it, between the pre-registered verdicts (results doc
"Seed twins of the solve step on the headline"). Decision: no more pairs
are queued; the question goes to the owner with its cost (3 more pairs,
~3 h light, halve the se) beside decision 7 of the approach review. The
headline re-rank's "the solve step is the suspect" is withdrawn to "at
most a small part". Alternatives: queue the 3 pairs now (cheap, but it
answers a question whose decision is the owner's); call it a null (the
data don't say that). Reversible.

## engine-next landed (owner's OK of 2026-11-02; landed 00:20 2026-11-03, owner away)

The rules-engine series and its pre-landing slice (branch `engine-next`,
merged with main at c3f81f4) are on main: `cargo test --release` all
green, `series_check` PASS (3104 states, heuristic and the product net
bit-identical, old columns equal), `sts` swapped from the branch's wheel
with no Python process holding it, `jobs.py impact sts`: none (the queue
was empty). The rules version over the golden games is unchanged
(7042d1d6a6149ba0), so recorded games, datasets and the solved DB still
replay; the solvedb fingerprint over the engine sources changed, so cached
solved states are not reused by the new module. New nets get the wider
default layout (rows 92 -> 131, cards 60 -> 82, piles next_draw /
known_later; new row kinds opt-in), so a training run compared against a
pre-landing net must account for the wider columns. Unblocked: line-seed
stage 2, mutated monsters stage B, the two-turn self-play round, the
branch module's sampled-draw leaf. The branch is kept (merged).

## Line-step spec confirmed (owner away, 2026-11-03)

Spec `docs/specs/line-step.md`, stage 2 of line seed (approach 1 of the
approach review): `sts.search` also returns the principal line of the tree
it built (best child at every decision up to End turn or the first chance
node), and `gauntlet.py play --two-turn --line-seed --step-line` plays that
line when the tree had no cut instead of searching every decision. The
probe measured the first tree at 59% of a turn's two-turn time, so the
stepped player should cost ~0.6 of today with the same decisions as the
stage-1 player (identity where nothing cut, checked by a compare probe
with a 0.99 agreement bar and a 0.65 cost bar). The product does not
change by the build; the headline read at fixed n 250 decides whether the
stepped player becomes the play mode for two-turn reads. Alternatives:
continue the line through listed chance nodes (more saving, more state to
get right; later), or skip the engine change and keep paying for every
re-search (stage 1 only). Confirmed without the owner: the engine change
is small (the search module only, values untouched), reversible, and the
owner approved the approach when re-ranking Next. Build: 2 code steps and
a probe, forks.

## Line seed and line step built and folded (owner away, 2026-11-03)

`docs/specs/line-seed.md` (stage 1, built 2026-11-02) and
`docs/specs/line-step.md` (stage 2, built 2026-11-03: c2a326e the principal
line in `search.rs` and `sts.search(...)["line"]`, 7adb302 the `--step-line`
player, flag and `line_probe.py --compare`, 9780a94 the review fix) are
folded into README (the gauntlet player lines) and these entries.
Spec-reviewer on the range: two must-fix. (1) At margin 0 a two-turn tie
keeps one-turn's choice while the line starts with two-turn's first maximal
option: fixed (the line is stepped only when the pick is two-turn's best;
test first, the tie case failed then passed; the product passes margin
-1.0, so no result changes). (2) The spec's "Fits with" named a test
`principal_line_one_turn` that doesn't exist; its claim is covered by
`principal_line_starts_with_the_action_and_is_legal` over the default
(one-turn) config; resolved by the fold. Optional, not done: the spec's
line that `--against` accepts a control without the flag was out of date
since the settings check (`--vary step_line` is needed; README says so);
the compare probe doesn't record peak RSS; `principal_line_stops_at_chance`
doesn't assert that the Sword Boomerang branch was taken;
`test_search_line_key` passes two unused search arguments. Follow-up idea
ideas#80 (continue the line through listed chance nodes). The reads
(step 4) run as jobs 0064 / 0065 and decide the play mode.

## Line-step probe: identity exact, cost 0.70, the reads go ahead (owner away, 2026-11-03)

The compare probe (results doc "Line step: the stepped player makes the
committed-line player's decisions exactly") passes the agreement bar with
nothing to spare (1.0000 over 526 decisions, 20 of 20 fights identical)
and misses the cost bar (nodes 0.704, leaves 0.681 against <= 0.65).
Decision: step 4's reads run anyway. The cost bar was the review's estimate
of the saving, not a correctness condition, and the code is built and
tested; 0.70 of the two-turn cost with identical decisions is a plain win
for every later two-turn read. Recorded as a bar miss, not re-scaled.
Alternatives: park the spec at the bar (throws away a 30% saving over an
estimate), or extend the line through listed chance nodes first (more
state to get right; an idea, not now). Reversible: `--step-line` is a
flag; without it nothing changes.

## Operating model confirmed: steward, navigator, project lanes (owner, 2026-11-03)

The owner set the system's purpose: long-term management of an automated
project, with the owner only adding ideas or shifting direction. Its first
function is a healthy environment; its second is driving the project
forward (big-picture thinking, continual exploration); health wins when
they conflict. `docs/specs/operating-model.md` replaces the single 2-hourly
manager with a steward (health, every 2 h, Haiku), a navigator (portfolio of 2-3 lanes incl. one exploration lane,
big-picture work from facts, reversible defaults on the owner's behalf;
event-driven, with a daily backstop) and a lane
worker (temporary project lanes with charters split by writer, claims,
CPU-hour caps and end dates; work in lane worktrees). The owner gets a
daily digest and rare escalation notices, never questions. manager.md is
archived in one cut-over step with every heading mapped (owner-dated
sections verbatim into `docs/operating.md`); this supersedes kb-adoption
stage 4. A review (mechanics, autonomy, migration; skeptic per finding)
confirmed 11 must-fixes, all folded in: an overlap window with the old
manager, a shared checkout breaking rebase and pinned adds, charters with
three writers, uncomputable health metrics, red metrics gating the
navigator from day one, doubled wake-ups with no cap, 9 kb facts and
several owner rules orphaned by the archive. Alternatives: keep one
manager with a lighter file (doesn't separate frequent cheap upkeep from
infrequent deep direction); a scheduled task per lane (tasks to create and
delete as lanes change); keep asking the owner (against the owner's
stated role).

## Line step is the two-turn play mode (owner away, 2026-11-03)

The stepped committed-line player (`--line-seed --step-line`) is level with
plain two-turn play on the headline setting at fixed n 250 (end-HP +0.04,
se 0.80; clears -0.016, se 0.020; results doc "Line step on the headline
setting") and reproduces the stage-1 committed-line player row for row on
cells 0-49 (544 floors). It costs about 0.55 of plain two-turn's wall time
there (69.5 min at 3 threads against 127-128 min at 2 threads per 250
sequences; the probe's 0.70 was an upper bound). Decision: every two-turn
read and the product's play flags use it from now (`configs/product.json`
flags `--two-turn --line-seed --step-line`, same net and price; facts
how/two-turn-search, yardstick/cost-savers). A control played without the
flags needs `--vary line_seed --vary step_line` under `--against`. The
headline number 0.804 stays until the stepped file holds 500 sequences and
becomes the control (job 0066). Alternatives: keep plain two-turn for
product reads and the stepped player for screens only (the hand-over's fail
branch: it gives up ~45% of every two-turn read's CPU for no measured
strength); wait for the 500-sequence file before switching (delays the
two-turn self-play round's cheaper games by one run). Reversible: flags;
the plain files stay and pair with the stepped ones by sequence.

## Two-turn round spec confirmed (owner away, 2026-11-03)

`docs/specs/two-turn-round.md` builds the one two-turn self-play round the
owner kept (decisions "Two-turn self-play round: kept, small and
targeted"), now that both preconditions hold (line step passes and is the
play mode; engine-next landed). Decisions inside it, each reversible by
config: games on the engine's elite and boss groups only (Nob, Lagavulin,
Sentries, Slime Boss: the parent's training set, so the run tests the
teacher, not new content; Hexaghost and the Guardian may join a second
round under the "new content" rule); varied decks at run-like HP (40-100%)
rather than tight2 cells (the read's train half is those cells); 1500
games per group plus 150 for validation (~20 thread-hours stepped, the
owner's "few thousand"); a one-turn control arm on the same specs (same
net one turn deep, seed 1) so a gain can be told from "fresh net-played
elite and boss games"; no hp_weight (the HP price lives in search). The
recorder is the stepped fallback player with actions recorded; the
fine-tune is the burst recipe with a `source` key. Reads: the gauntlet
protocol one turn deep against the 10-29 net's cell file, confirmed two
turns deep against the line-seed file with `--vary step_line`. A null on
both seeds closes the outcome-label family (owner's rule). Alternatives
not taken: 20k games (overnight slot for a +0.017-sized effect); tight2
cells as setups; adding the two newer bosses now.

## Two-turn round built (owner away, 2026-11-03)

Spec `two-turn-round.md` built by three forks and folded (README
"Fine-tuning on new content", this entry, the jobs' notes): 582dcd6
(`depth_paired.guarded_fight` records actions on request; result and
`row_key` unchanged without it), 8c51dd3 (`scripts/two_turn_games.py`:
elite and boss varied-deck games at HP 40-100% from a player two turns
deep (stepped fallback player) or one turn deep, stored as a registry
dataset without search values; `registry.records` takes action text),
d3c6b75 (`finetune.py` `source` key, configs twoturn-s1 / twoturn-s101 /
oneturn-ctl-s1, `two_turn_round.py arm` = fine-tune then the one-turn
cell read with the protocol). spec-reviewer on cfb4dec..d3c6b75: no
must-fix; it also checked depth one end to end, the hallway drop, resume
across chunks and turn-limit fights. Optional, not done: the first-chunk
pace line counts resumed fights (meaningless after a resume); the
replay-pool fetch moved before encoding on the existing path too; the
partial key ignores `record` (unreachable today); `--max-nodes` is ignored
at depth one (shares the real id; harmless); the games CLI's parser is
untested. Jobs 0067-0071 (lane train, pinned d3c6b75): 0067 J1 games,
0068 validation games, 0069 / 0070 arms s1 / s101, 0071 the one-turn
control arm; read rules in their notes and `docs/manager.md` Running. The
baseline for the build was the fast suites the spec names (62 passed);
the full suite was not run (it trains nets for ~80 min while two heavy
jobs run): `test-full` should run as filler when a slot frees.

## First lane charters (on the owner's behalf, 2026-11-03)

Build step 3 of the operating model (`docs/specs/operating-model.md`)
charters the first lanes as kb facts (`lane/<name>`) and sets their shares
in `jobs/lanes.json`. The spec named three; the two-turn self-play round
(Next L6) was specced, built and queued by the manager meanwhile (decisions
"Two-turn round built"), so it gets a short fourth lane until its read:

| Lane | Kind | Share | Cap | End | Why |
|---|---|---|---|---|---|
| cheap-depth | project | 30 | 45 cpu-h | 2026-11-10 | line-step passed and is the play mode; the sampled-draw leaf is next (review approach 2) |
| two-turn-round | project | 20 | 45 cpu-h | 2026-11-07 | jobs 0067-0071 run now; a null closes the outcome-label family |
| run-decisions | exploration | 20 | 60 cpu-h | 2026-11-10 | the boss curve priced where the player trades HP; one probe, one read each |
| goal1-yardstick | project | 20 | 90 cpu-h | 2026-11-13 | goal 1 has no standing number; bundles of known atoms first |

`main` keeps 10 and `filler` 0. Caps are the backlog's CPU-hour estimates
x 1.5 in thread-hours (as `scripts/health.py` counts); the two-turn round's
queued jobs alone book about 37. Four lanes is one over the spec's 2-3:
the navigator trims when the two-turn round closes. Alternatives: three
lanes with L6 as cheap-depth's next step (rejected: a training read is a
different measure from search cost); leaving L6 to finish under the old
lane `train` without a charter (rejected: no checkpoint, no stop rule, and
its read would have no owner after the cut-over). Pending jobs 0068-0071
move to lane `two-turn-round`; running 0066 (lane `depth`) and 0067 (lane
`train`) keep their lanes. The step facts `lane/<name>/step` are seeded by
this build from the manager's Running notes (they are the lane worker's
from now on); running jobs' read rules stay in their notes.

## Draw-leaf spec confirmed (on the owner's behalf, 2026-11-03)

Spec `docs/specs/draw-leaf.md` (lane cheap-depth, review approach 2): at
one-turn search's `EndTurn` leaves, sample k draws with common random
numbers, play to the next decision and score that state. Decided:
(1) the setting rides on the Rust net evaluator as the player setting
`@dl<k>`, so caches and `--vary price` pick it up; alternative: a
`draw_k=` keyword on every `sts` entry point plus gauntlet and ladder
flags (about 3x the plumbing). (2) The charter's "costs over 1.5x" is
read as 1.5x one-turn's wall time on the same read; alternatives: 1.5x
the review's 10x estimate, or a share of two-turn's cost (both looser).
The screen measures k = 1, 2, 4 so the cell read uses the largest k under
the bar; each read also reports the ratio to two-turn. (3) The review's
bias-audit leaf comparison is dropped from the screen (no stored states);
puzzle regret is the gate. Most reversible: a config field defaulting to
off.

## Navigator's first defaults (on the owner's behalf, 2026-11-03)

The approach review's "Decisions for the owner"
(`docs/research/approach-review-2026-11-02.md`) left (1), (2), (5), (6) and
(7) open (fact `owner/open/approach-review`). The navigator's first run
decides each by the most reversible option; the owner can overturn any of
them in `docs/direction.md`.

1. **What goal 1 means.** New bundles of the engine's known atoms first: a
   generated character as the headline (lane `goal1-yardstick`), new cards,
   mutated monsters from existing triggers, effects and patterns, reachable
   with depth plus a short burst and measured by retention on the
   generated-character gauntlet. New atoms arriving as data (runtime-registry
   stages 2-5, a content-agnostic price) are scoped once bundles have a
   number. Alternative: new atoms as data now; passed over because it has no
   known zero-shot method and no yardstick to judge it on yet.
2. **Which engine and arena carry goal 2, and what "dominant" means.** This
   engine stays the only play and training engine. Arena ladder: level 0,
   our gauntlet against an outside-designed fixed chooser; level 1, a stated
   headless Act-1 setting on our engine with a map, common relics, potions
   and Ascension knobs, reported with a parity caveat; level 2, the real game
   through a mod bridge, waits for the owner's StS1 install. A half-day
   parity harness for level 0 (sts_lightspeed, parity only) is allowed.
   "Dominant" is written down once level 1 has relics, potions, a map and
   the roughly 40 missing Ironclad cards; until then no number in the
   field's unit is claimed. Alternatives: sts_lightspeed as a play or
   training engine (the review: it cannot represent an A20 Act-1 fight
   exactly); claiming dominance on today's gauntlet (not the field's unit).
3. **db/.** Neither archived nor deleted: the grants forbid deleting
   non-rebuildable data, and nothing forces it.
   Alternative: archive to another drive (none to hand; reversible later).
4. **The headline's unit.** Unchanged (clears of 500 sequences on
   `yardstick/headline-setting`); boss end-HP is reported beside it in every
   headline read (the gauntlet files already hold it). Alternative: fold
   end-HP into the unit (re-states every past number; reopen if clears
   saturate).
5. **The solve step in training.** Stays in the recipes until a lane
   measures it (`decision/solve-step-owner`: the 3-pair read sat between its
   verdicts). Alternative: drop it now (the review's stop item); the data
   don't show it, and while nothing trains the cost of waiting is zero.
Nothing else from the review stays open except level 2 (the StS1 install),
which only the owner can do. Filed as `decision/goal1-meaning`,
`decision/goal2-arena`, `decision/db-kept`, `decision/headline-unit`;
`decision/solve-step-owner` and `owner/open/approach-review` re-set.

## Lane cheap-depth closed (2026-11-03)

Its step says `done:`. Outcome, half and half: the line-step part passed.
The stepped committed-line player (`--line-seed --step-line`) is level
with plain two-turn on all 500 headline sequences (end-HP +0.41 se 0.58,
clears 0.834 vs 0.804) at about 0.55 of the wall time, so it is the
two-turn play mode and its file is the headline control at 0.834 clears
(`measurement/line-step@headline`, `measurement/headline@two-turn`,
`decision/line-step-play-mode`, `yardstick/headline-control`). The
sampled-draw leaf failed its pre-registered screen
(`measurement/draw-leaf@puzzles`: on 448 exact puzzles of horizon >= 1 the
regret gain at k 1, 2, 4 is within one se of zero while the time is
3.2-4.3x one-turn's), so it gets no cell read; the code stays off by
default (`@dl<k>`). Its lesson: two-turn cut the same puzzles' regret to
about a third, so two-turn's gain is the second turn's play, not seeing
the hand. Predicted at opening: p ~0.4 that the leaf gains +1.5 HP at no
more than 1.5x the cost, ~30 CPU-h (cap 45). Used: about 8 thread-hours
(0066 at 3 threads 07:34-10:04 under the built-in lane `depth`, which
`health.py` counts as 0.0 for this lane; the puzzle screen took minutes).
Follow-ups stay in the backlog: `line-through-chance` (ideas#80) only if
line-step's 0.70 cost blocks its use; the depth question moves to the new
lane `depth-headroom`.

## Lane depth-headroom opened (on the owner's behalf, 2026-11-03)

With `cheap-depth` closed, no lane probes the owner's first interest
(`docs/direction.md`: search and depth). The approach review paused
three-turn search, rollout leaves and two-turn search inside the choosers
"until the matched-HP probe shows headroom" and listed that probe among its
cheap reads (reads 1 and 8). This lane runs the probe and the anchor, one
read each, then goes or stops: (a) the matched-HP replay probe, the headline
control's decisive fights (floor-9 elites that lost 15+ HP, bosses entered
at 50-69 HP) replayed by the two-turn product, by three turns (`--turns 3`)
and by a rollout leaf (`scripts/analysis/rollout_probe.py`), elites first,
one thread per fight, paired HP lost and wins; (b) the heuristic two-turn
anchor on sequences 250-749 at fixed n against the stepped product file.
Expected value: p ~0.3 that deeper search recovers 1.5 HP or more per
decisive fight; a go unpauses three-turn or a rollout leaf as a product
candidate, a stop closes that family on the dev machine and sends the depth
budget to the run layer. Either outcome decides 10-20 CPU-h of later work.
CPU: ~7.5 thread-hours (the anchor ~70 min at 3 threads and 4-5 GB, the
probe capped at 4 thread-hours), cap 12, end 2026-11-08. Kind exploration
(one probe, one read, go or stop). Alternatives passed over, in value
order: `feasibility-ladder` (~2 CPU-h; cheaper reads, no strength; next in
line), `test-size-profile` (~1 CPU-h of code; saves ~7 thread-hours per
`test-full`; a lane step rather than a lane, offered to the next lane
that touches tests), `rows-on-burst` (~3 CPU-h; training, and which burst
content uses the new rows is unknown), `mutated-monsters-b` (~10 CPU-h;
needs a spec; goal 1 is `goal1-yardstick`'s for now), `prior-art-card-ai`
(no CPU; an exploration source, not a lane). Four lanes is one over 2-3,
allowed while `two-turn-round` ends 2026-11-07. Shares: `two-turn-round` 25,
`run-decisions` 25, `goal1-yardstick` 30, `depth-headroom` 10, `main` 10.

## Review 2026-11-03: job threads, the half swing, two charters (on the owner's behalf, 2026-11-03)

From `docs/research/big-picture-2026-11-03.md` (navigator's reading):

1. **Lane jobs are sized at 4-6 threads when memory fits.** The booked-thread
   share was low because of the two-heavy-slot cap with 3-thread jobs; a
   6-thread two-turn job peaked 5.4 GB. Two heavy jobs at once stays.
   Reversible: a threads value per job.
2. **The plain two-turn control's half swing is not replayed.** No code
   channel was found (same command, module, sequences and schema, 5 minutes
   apart, no engine swap); one skeptic reads chance, one an unexplained
   reproducible weakness of the plain player on 250-499. The stepped file is
   the control, so a 4 CPU-h replay decides nothing we act on. Alternative:
   replay 250-499 under the plain player (reproduces 0.756 by determinism;
   only a differently seeded book would add information).
3. **goal1-yardstick charter: the product is subject and reference.** The
   generated-powers bench could not separate "depth generalises" from "the
   generated cards are weak" because its reference heuristic prices 14% of
   the test powers and all players converge under two-turn search. Novelty
   cost is read as the product informed (after a short burst) minus the
   product zero-shot; the heuristic is a floor only. Alternative: keep the
   heuristic as reference (the review's blind-reference finding).
4. **Backlog re-ranked** from the review: deck-matched-reads first
   candidate, then throughput-fixes (absorbing test-size-profile),
   mini-run-headline, chooser-margin-rule, horizon-leaf-screen,
   boss-replay-score, experiment-ledger; depth-headroom is open.
5. **Two-turn round.** Its arms ended during the review with protocol fails
   (s1 n 120, s101 n 119, the one-turn control arm n 179). The lane reads
   them (why the fine-tune hurts); on its done: the navigator closes the
   lane and the outcome-label training family on the dev machine.

## Operating model as built (2026-11-03)

Spec `docs/specs/operating-model.md` built and cut over: steps 1-3
(da67084, 8099f32, dbe27d6, 9908c64), amendments 1-3 (f32ac12, 0d052e3,
81b0837), cut-over 38728a3 (`docs/manager.md` appended to
`docs/manager-archive.md`, the 9 facts citing it re-set to
`docs/operating.md`, `sts-manager` disabled). Reviews: a spec-reviewer
pass per step (must-fixes: 2, 6 + 2, 1, all fixed); dry runs of each role
in scratch clones; owner-run trials of all three roles.

How it differs from the spec, and why:
- **Amendment 1 (owner):** instruction files state rules as they stand;
  the owner sections lost their dates and point-in-time facts.
- **Amendment 2 (owner):** each role's model is its task's setting
  (steward Haiku, lane worker Opus, navigator Fable); the app's
  default was Fable at high effort.
- **Amendment 3:** no role starts another. An unattended app run can't get
  `run_scheduled_task` approved ("Allow once" only), so the lane worker
  runs every 2 h and the navigator daily, each taking `health.json`'s
  events first. Draft spec `role-launcher.md` (CLI sessions started by a
  launcher loop) is the follow-up.
- `scripts/test_full.py` exists so the full suite has the job id
  `test-full`; `health.py` also holds the lock commands and the event list.

First runs: the steward ran clean at 12:25 (first digest), 12:38 and 14:33
(Haiku); a lane worker repaired the 13 `test-full` failures (b47437a); the
navigator closed cheap-depth and opened depth-headroom. Known issues: the
cut-over's edit to the `big-picture-review` workflow put backticks inside a
JavaScript template string and broke it (fixed by the navigator, a46b86e,
6afb9fa); auto mode refuses `jobs.py cancel` and `kill` ("Interfere With
Workloads"), so 0075 (a duplicate `test-full` on pre-fix code) waits for
the owner or runs once; push notifications need Remote Control on.

## Role launcher as built (owner, 2026-11-03)

Spec `role-launcher.md` (confirmed by the owner's /build; folded here and
into `docs/operating.md`, `scripts/roles.py`'s docstring): the lane worker
and the navigator run as headless Claude Code sessions (`claude -p`, auto
mode; lanes Opus, navigator Fable) started by
`scripts/roles.py run`, a loop the steward restarts like the job runner
(health blocker `launcher`). Each 5-minute tick: stop sessions over their
limit (lanes 4 h, navigator 2 h), refresh `health.json` when over 15 min
old, start nothing while a blocker is red or the CLI is
missing; start the navigator on a new trigger or its backstop (24 h, counted from its last start or `navigator_ran`), and a lane
session on a new `wakes.lanes` event or the 4 h backstop while a lane is
open; at most 2 lane sessions (the second only for an unclaimed lane),
never beside the navigator, 4 a day. One event starts one
session (`health.py woke`). A session is ours only while its pid's process
was created no later than its start (a pid reused after a reboot isn't).
Prompts: `docs/roles/`. Commits: 485d45f (spec), 2c9ae67, 20e3e4b, c3c9750,
956104d, 11185b8 (review fixes); tests `scripts/tests/test_roles.py` (17)
and `test_health.py` (50). The probe (`roles.py probe`) found all seven CLI
assumptions true, including that an auto-mode CLI session may cancel a
pending job (an app session was refused). Review: 4 must-fixes fixed
(jobs/roles never created, a navigator restarting every tick, a reused pid
killed, app-only tools in the docs); optional items went to the owner's idea list.
The app tasks `sts-lanes` and `sts-navigator` are disabled; the steward
stays an app task (Haiku, every 2 h).

## Lane two-turn-round closed (2026-11-03)

Its step says `done:`. Outcome: null on both seeds. The 10-29 net
burst-fine-tuned on 3000 elite and boss games played by the stepped
two-turn product fails the protocol one turn deep on the cell gauntlet on
both seeds (s1 fail at n 120, end-HP -1.37 se 0.83 at n 150; s101 fail at
n 119, -1.02 se 0.70), both below the one-turn control arm fine-tuned the
same way on one-turn games of the same specs (-0.05 se 0.58 at n 200;
`measurement/two-turn-round@cells`). The stop rule fires: no two-turn
confirmation, no second round. The read's why (results doc "Two-turn
self-play round: both arms fail the protocol"): the fine-tune learned
little (validation MSE at its best by epoch 1-2, early stop after 5-9
epochs); the loss sits on the boss floor (+1.3-1.4 HP more lost at matched
start than the control arm, other floors level); held-out halves are worse
than train halves, a weak sign of fitting the training decks. The
outcome-label training family closes on the dev machine: a stronger teacher's
outcome labels do not lift the net either, which was the last untried exit
in `cause/teacher-equals-student` (re-set); `decision/two-turn-self-play`
is re-set to the closed state. A training job now needs one of the owner's
other two exits, inputs the net cannot see today or new content (goal 1's
domain). Predicted at opening: p ~0.3, +1-2 HP at run level, ~37 CPU-h
(cap 45). Used: about 20 thread-hours (0067 16.6 under the built-in lane
`train`, 0068 2.0, the three arms 0.6; `health.py` counts 2.8 for this
lane). An open question stays with the reviews, no CPU on it: whether
labels valued under the two-turn continuation make a one-turn player
optimistic about states it cannot exploit (testable only by the two-turn
read the stop rule skipped).

Portfolio after the close: three lanes, `goal1-yardstick` (project),
`run-decisions` and `depth-headroom` (exploration). No lane opens: three
is the spec's 2-3, none ends within a few days, and `deck-matched-reads`
stays first for the next slot. The closed lane's 25 share goes by the goal
weights (no checkpoint has passed yet, so no lane earns a record bonus):
`goal1-yardstick` 40, `run-decisions` 35, `depth-headroom` 15, `main` 10.

Alternatives: extend the lane for the two-turn read of one arm (rejected:
~5 thread-hours chasing a mechanism after a pre-registered null on both
seeds); a second round with scaled labels or the solve step restored
(rejected: training without something new to learn, the owner's rule).

## Goal-1 lane re-aimed at the owner's yardstick; charters re-set (owner's review, 2026-11-03)

An independent review the owner asked for found that the navigator's first
default ("Navigator's first defaults", item 1) and the `goal1-yardstick`
charter redefined the goal-1 number (a generated character, no parent
reference) without citing the owner's decision "Goal-1 yardstick: paired
modifiers, measured per modifier (owner, 2026-11-02)"
(`decision/goal1-yardstick`). The owner's decision stands:
- goal 1's number is the net's drop beyond the measured difficulty of boon
  + bane modifier pairs on official parents; each modifier's difficulty is
  measured on its parent fights with the heuristic and the two-turn
  product; stacking is the distance axis;
- the lane's first bench is mutated-monsters stage B with paired modifiers
  (pattern mutations, `docs/engine-next.md`), then cards; a generated
  character comes later, built from mutated official parents;
- `decision/goal1-meaning` is re-set to say so, and the navigator's prompt
  now cites owner decisions and never contradicts one.

Charters, from the same review: `run-decisions` is a 60 cpu-h multi-probe
project, so its kind is `project`, leaving `depth-headroom` as the one
exploration lane; shares live only in `jobs/lanes.json` (the charter facts'
share fields disagreed with it and are dropped); the navigator keeps at
least one open project lane whose next step is queueable CPU work.
`lane/goal1-yardstick/step` is re-set by this fix (the lane hadn't started).

## Lanes goal1-yardstick and run-decisions: a first CPU step and the probe order (on the owner's behalf, 2026-11-03)

Navigator run 16:18 on the trigger `direction:5b86e13`: the edit is wording
(the goal-1 interest now cites `decision/goal1-yardstick`, which the
goal1-yardstick charter already follows); no ranking changed, the backlog
order stands.

The CPU has been idle with an empty queue: all three lanes' first steps
are specs. The rule "keep at least one open project lane whose next step is
queueable CPU work" isn't met. Two charter amendments fix it and tighten
the lanes' value:

- **goal1-yardstick, first CPU step:** widen stage A's two-turn product
  read from 40 starts x 4 seeds to 200 x 4 (`mutate_monsters.py play
  --players two --two-starts 200 --two-seeds 4 --threads 6 --out
  results/mutate/a.json`; the script loads its output file and plays only
  the missing starts). Why: the owner's yardstick measures each modifier's
  difficulty with the two-turn product, and stage A's two-turn column has
  se 0.02-0.05 on all fights and 0.03-0.12 on bosses
  (`measurement/mutated-monsters@stage-a`), no per-modifier number at the
  yardstick's precision; 200 x 4 brings it to about 0.01-0.02. Cost ~17-20
  thread-h (0059l8b4: 40 x 4 took 83 min at 3 threads, peak 3.9 GB), within
  the 90 cap; 6 threads per `decision/job-threads`. Stage B's spec stays the
  first build step and the first bench. Alternatives: wait for the stage B
  spec (10+ more idle hours); play the two-turn player with the stepped
  flags (0.70 of the cost, but a new column, not comparable with the 40 x 4
  already played; the lane may choose it for stage B); a generated character
  first (the owner's review put it after stage B and cards).
- **run-decisions, probe order:** rest vs upgrade stays first (cheap: one
  turn on the headline, ~0.5-1.5 thread-h per read; its ceiling is small,
  one rest before the boss). The elite and path probes don't run on the
  current headline setting: with no elite payoff the skip ceiling is already
  measured (+14.0 HP, `measurement/elite-skip@headline`) and a path rule
  would bias the yardstick (`decision/no-path-rule`), so a pass couldn't be
  adopted. The lane's second step is the mini-run headline design (backlog
  `mini-run-headline`, review 2026-11-03 direction 6: an elite payoff and
  one path choice, later potions), and the elite and path probes run on it,
  read against a control played on the same setting. Alternatives: run the
  elite probe as charted (a number nobody can act on); close run-decisions
  and open mini-run-headline as its own lane (the same work with more
  churn; the lane keeps its cap and end date, extendable once).

No lane opened or closed: three are open (goal1-yardstick and
run-decisions project, depth-headroom exploration), none near its cap or
end. Shares unchanged. `deck-matched-reads` stays the first candidate for
the next slot. Both charters re-set from this entry.

## Dashboard as built (owner, 2026-11-03)

Spec `dashboard.md` (confirmed by the owner; folded here, into
`scripts/dashboard.py`'s docstring and README "Job queue"): a read-only
local page, `python scripts/dashboard.py [--port 8766]`, on 127.0.0.1 only,
started by hand, standard library only. The owner's choices: no controls
(it never starts, stops or cancels sessions or jobs, edits files or takes
suggestions; suggestions go through `/approach`), no results charts, no
page off the dev machine, no extra summaries written by the roles; glanceable
over complete: the first screen (refreshing every 60 s) holds the health
light, running sessions and jobs, the last 10 `roles.log` lines and the
open lanes, everything else one click away (`/log`, `/health`, `/queue`,
`/digest`); a role session's stream-json log reads as a conversation
(`/session/<record>`: text, one line per tool call with its output
collapsed and cut at 20 KB, thinking and hooks skipped, the outcome last).
A session's lane is the claim `jobs/locks/lane-<name>.json` holding its
session id. Built choices: `health.json` counts as stale past 1 h (the
launcher refreshes it every 15 min) and then never shows green; a missing
file shows as missing; it reuses `roles.Launcher.ours` and
`health.parse_time`, never writes a file or runs `kb`, escapes everything.
`--root` points it at another checkout (the end-to-end test uses it).
Commits: 8a7911d (spec), e368d0b, 69ab323; tests
`scripts/tests/test_dashboard.py` (10, fixture checkout under
`scripts/tests/data/dashboard/`, its logs force-added past the `logs/`
ignore). The stream-json assumption held on the three logs in
`logs/roles/`. Review: no code must-fix.

## Rest probe: 64 fights and a 2-se margin (on the owner's behalf, 2026-11-03)

Lane run-decisions, first probe (rest vs upgrade, priced by the boss
curve). The plain sim chooser already failed this probe's setting on
11-02 (-1.22 HP at n 50; results doc "Rest-site chooser fails"): 16 boss
fights per option let a lucky upgrade among 6-9 beat heal. Both fixes that
entry named are now flags of `gauntlet.py play --rest sim`:
`--rest-fights N` (fights per option, default 16) and `--rest-margin Z`
(upgrade only if the best upgrade beats heal by Z standard errors of the
paired per-seed score difference; default 0, the old rule). Non-default
values label the file's `rest_choice` as `sim-f<N>-m<Z>`, so older files
still match. The probe plays 64 fights and Z = 2, one turn deep on the
headline, `--against` the one-turn control with `--vary rest_choice`.
Heal's value comes from the boss fights themselves at the healed HP, which
is the boss curve at that sequence's boss and deck; a separate curve
lookup would add a model and no new information. Ceiling is small (one
rest, right before the boss; ~20% of sequences upgraded at 16 fights), so
a null is the likely read, and it closes the rest probe on this setting.
Alternatives: the curve-priced rule (heal's gain from
`measurement/boss-curve` per boss against the upgrade's simulated gain at
the current HP; a pooled curve, no per-deck signal); 64 fights without a
margin (still picks the best of 6-9); skip the probe (the charter names
it first).

## Mini-run setting: a second card offer after an elite, a heal after floor 5 (on the owner's behalf, 2026-11-04)

Lane run-decisions, second step (spec `docs/specs/mini-run.md`, confirmed
under the mandate). The elite and path probes can't be adopted on the
headline setting (`decision/no-path-rule`): an elite pays nothing there, so
skipping is +14.0 HP. `gauntlet.py play` gains `--elite-offers N` (a won,
not skipped, elite floor runs the reward chooser N times; extra offers from
their own seeds, rows record `extra`) and `--mid-rest K` (heal 30% after
floor K is won, before its reward; rows record `mid_rest`). The mini-run is
`--elite-offers 2 --mid-rest 5` on the headline setting. Both fields are
absent from settings at their defaults, so every existing file still
matches; both are in `VARY`. The path choice stays elite-or-hallway at each
elite floor (`--elites`). This doesn't change the headline setting: the
navigator decides that from the probes. Alternatives: max HP or a relic as
the payoff (the engine has neither; the relic subgoal); a branching map
(more code, the same decision at the probe's precision); the rest after
the second elite or before it (then skipping it is rarely right); a rest
chooser mid-act (a later probe once the elite read is in). Reversible: flags
only.

## goal1-yardstick: stacking check and two more owner pairs on stage A's bench, queued behind job 0083 (on the owner's behalf, 2026-11-04)

The lane's stop rule needs a first stacking check (a stack's difficulty about
the sum of its parts, on a sample) besides stage A's widened table and stage
B's paired table. Stage A's state patches can stack today, and the landed
engine expresses two more of the owner's pairs as patches: "Thorns 2 with
-10% HP" with real Thorns (damage to the attacker per hit; SharpHide stood in
before the landing) and "+30% HP with -1 damage per hit" as Strength -1.
`mutate_monsters.py` gains those pairs, Thorns 2 alone, and five stacks of
pairs (four of two, one of three), and its read prints per stack, for the
heuristic and the two-turn product, the stack's win change, the sum of its
parts' and their paired difference (interaction, se). The stack already in
the file reads -0.022 (se 0.009) heuristic and -0.039 (0.014) two-turn at
175 starts: harder than the sum, so the check is worth a sample. Two jobs
append to `results/mutate/a.json` after 0083 (heuristic and one-turn
200 x 8, ~10 min; then the two-turn product 200 x 4, ~7.5 h at 3 threads).
Pass: every stack's interaction within 2 se of 0 on both players -> stack
difficulty is read as the sum of parts. Fail: the sum is not usable as the
distance axis; stacks are measured directly. Alternatives: stacks only
after stage B's pattern modifiers (leaves the CPU idle while stage B is
spec'd and built); a separate output file (replays every parent and part,
~2x the CPU). Reversible (an analysis script).

## Lane run-decisions closed (2026-11-04)

Navigator run 14:06 on the trigger `lane-done:run-decisions`. The lane's
step says `done: failed`: its stop rule (done after the three probes, fail
if all three are null) is reached. Outcome, by probe, each one turn deep
on the 10-29 net `@hpb0.01` against a control on the same setting:
- Rest vs upgrade (headline, the one rest before the boss, 64 fights per
  option, 2-se margin): null, -0.10 HP at n 50, 2 of 50 sequences upgraded
  (`measurement/rest-probe@headline`).
- Elite skip on the mini-run (a second card offer after a won elite, a 30%
  heal after floor 5; `measurement/mini-run@control`, 0.900 clears): the
  protocol stays open at n 500, +0.99 HP (se 0.86), no go by the +1.5 HP
  bar; clears +0.054 (se 0.014, both halves alike), boss deaths 22 vs 40
  (`measurement/elite-skip@mini-run`).
- Skip under 40 HP on the mini-run: fail at n 50, the rule fires on 20 of
  996 elite arrivals after the heal, so bounded under +1 HP at any n
  (`measurement/elite-hp40@mini-run`).

The finding to carry: on both settings an elite costs more HP than its
payoff returns (the headline pays nothing, +14.0 HP ceiling; one extra card
plus a heal brings that to +1.0 HP on end-HP but skipping still wins clears
by about 4 se). Run-level choices stay one-sided until the run layer has a
bigger elite payoff (a relic or max HP: engine work, the owner's relics
subgoal) and rest sites with a choice before hard fights. Filed as
`cause/elite-does-not-pay`.

Cost: 6.5 cpu-h as `health.py` counts (about 10 thread-hours by the lane's
own count, jobs 0081 and 0087-0089) of a 60 cpu-h cap; predicted ~40 CPU-h
with p ~0.3 that one probe gains +1.5 HP or more (backlog entry; "First
lane charters"). The three probes were cheap because each stopped at its
one read, as chartered. What it leaves behind: `gauntlet.py` keeps the
mini-run flags (`--elite-offers`, `--mid-rest`), the rest-probe flags
(`--rest-fights`, `--rest-margin`) and the path flags; the mini-run control
file stays on disk for a later setting that pays elites more. Retired:
`lane/run-decisions`, `lane/run-decisions/step`, `lane/run-decisions/checkpoint`;
filed `measurement/portfolio-run-decisions`. Alternatives: extend the lane
for a fourth probe on a richer payoff (rejected: no payoff exists in the
engine, so the next step is a spec, not a probe); keep the lane open for the
chooser-margin rule (rejected: that is a chooser fix, not an HP trade, and
it joins the cheaper-reads lane's follow-ups).

## Lane cheaper-reads opened (on the owner's behalf, 2026-11-04)

Opened in run-decisions' place, from the backlog's first candidate
`deck-matched-reads` (review 2026-11-03 direction 2) with two small reads
folded in: `boss-replay-score` (direction 7) and the gauntlet thread check
from `throughput-fixes` (direction 1). All three cut the CPU a headline
verdict costs, which multiplies every goal-2 read to come (machine time is
the bottleneck; `cause/headline-pairing-weak`: between nets pairing buys
only ~1.2x on the headline, paired end-HP sd 20-23, and the protocol's SPRT
mostly ends open at the 500 cap for a true +1.0 HP).

Goal: halve the CPU per headline verdict. Steps, each with its own bar:
1. **Deck-matched reads** (code 1-2 h, then ~0.5 thread-h): a `gauntlet.py
   play` option that replays the control file's recorded card picks (and
   its rest and removal choices where the setting has them) into the
   candidate's run, so a combat-player read varies only the fighter;
   end-HP stays the tested quantity, clears the guard. First check one turn
   deep on 250 sequences against a control's recorded picks: go if paired
   end-HP sd falls from ~23 toward 12; fail if it stays above ~18 (the
   divergence is in the fights, not the picks). A pass buys one two-turn
   read of a known candidate to show the gain at depth (~5 thread-h).
2. **Boss-replay score** (~0.3 thread-h, `scripts/analysis/boss_replay.py`):
   score a sequence that reaches the boss by k=8 boss replays from the
   arrival state with common seeds (or HP-at-boss as a control variate on
   paired end-HP); 62 of 83 deaths are at the boss and HP-at-boss has paired
   sd 8 vs end-HP's 13. Adopt if the paired sd of mean boss win falls 1.4x
   or more.
3. **Thread check** (~1 thread-h, queueable now): sequences 0-99 at 3 vs 8
   threads, two turns deep, when memory allows; adopt per-floor parallel
   play if 8 threads take under 0.6x the wall time.
Optional follow-up if the cap allows: the `chooser-margin-rule` offline
check on the removal file (0 CPU).

Expected value: p ~0.6 that step 1 passes, which makes a headline read 2-4x
cheaper (a +1.5 HP effect at sd 12 decides near n 130 instead of running
open at 500); steps 2 and 3 are small and independent. CPU: ~8 CPU-h
(checks ~2, one two-turn confirm ~5); cap 12 cpu-h; end 2026-11-11. Kind
project: its next step is a designed job (the thread check), so the CPU has
lane work while the deck-matched code is written. Alternatives passed over:
`mini-run-headline` as a lane (the mini-run as built isn't the next
headline, see the entry below; a real elite payoff is engine work first);
`horizon-leaf-screen` (p ~0.2 after the skeptics); `feasibility-ladder`
(an exploration probe; depth-headroom can take it when its reads are in);
`experiment-ledger` (process, no CPU; not a lane); extending run-decisions
(nothing left to probe without a payoff).

## Run layer after run-decisions: the headline setting stays, the mini-run stays a probe setting (on the owner's behalf, 2026-11-04)

The run-decisions lane left the navigator one question: does the mini-run's
clear gain from skipping elites (+0.054, about 4 se) matter for the
headline? Decision: no change to the headline setting or its control
(`yardstick/headline-setting`, `yardstick/headline-control`), and the
headline keeps no path rule (`decision/no-path-rule` stands). Why: the gain
says again that elites don't pay on either setting
(`cause/elite-does-not-pay`), so a skip rule would still bias the
yardstick toward never fighting elites; and the mini-run as built is not
the next headline: a 30% heal after floor 5 makes it an easy setting
(0.900 clears one turn deep; the two-turn product would leave little room
in the clears unit) and a second card offer is too small a payoff. The
mini-run flags stay as a probe setting for a later version that pays an
elite a relic or max HP (backlog `elite-payoff-relics`, then
`mini-run-headline`). Until then the run-layer family is paused: no new
run-level probes on the current settings. Alternatives: adopt the mini-run
as the headline now (rejected: easy, and the elite still isn't two-sided);
a headline with `--elites skip` (rejected: bias, as before); a heal-only
or offer-only setting to separate the +0.22 (rejected: it would say which
half carries an easy setting's clears, which changes no decision).

## Standing filler successor and the review's timing (on the owner's behalf, 2026-11-04)

- **Filler.** `docs/filler.md`'s standing CPU job (the two-turn control on
  500-999) finished on 11-03 and names no successor, so `cpu` has been red
  at every steward run since (zero-job minutes while lanes wrote specs).
  Successor, for the steward to add to `docs/filler.md` (its file) as entry
  `one-turn-control-500-999`: the one-turn screen control
  (`yardstick/one-turn-controls`, the 10-29 net `@hpb0.01`) on the headline
  setting, sequences 500-999, into
  `results/gauntlet/net1029-hpb0.01-starter-simboss-500.json`, so a passing
  one-turn screen (chooser rules, probe settings) can be confirmed on 500-999
  at fixed n without waiting for a control. Resumable; 2 threads, 1.5 GB
  (0087 peaked at 0.99 GB), ~90 min (0087: 500 sequences in 65 min at 3
  threads). After it, filler has no standing CPU entry: the lanes carry the
  CPU (this run's cheaper-reads lane has a queueable job), and idle minutes
  with nothing worth running are not a fault. Alternatives: the two-turn
  control on 1000-1499 (~9 thread-h; with paired sd 20-23 between nets,
  n 1000 still leaves a +1 HP effect at 1.5 se, so deck matching is the fix,
  not more sequences); no successor (leaves the steward reporting red).
- **Review.** The big-picture review waits for the next backstop, when
  the two reads that would feed it (0083, stage A's 200-start two-turn
  table; 0090, the heuristic two-turn anchor) are in.

## depth-headroom anchor: the heuristic fights, the product chooses, 250 sequences (on the owner's behalf, 2026-11-04)

The charter's anchor (b) is the heuristic two turns deep on sequences
250-749 against the stepped product file. A smoke run on the headline
setting took ~30 s per sequence at 2 threads, so 500 sequences cost ~8
thread-hours of the lane's 12 cap and leave the replay probe (a) too little.
Played instead: the heuristic two turns deep with the product's flags
(`--line-seed --step-line`) and the product's chooser (`--chooser` the 10-29
net `@hpe0.01`), headline setting, sequences 500-749 at fixed n 250 (~4
thread-hours), read pair-wise against
`net1029-hpe0.01-two-line-step-starter-simboss-500.json`. With the chooser
held equal only the leaf differs, so the gap is the net leaf's worth at two
turns (the chooser's share is already `measurement/chooser-vs-fighter@headline`),
and 500-749 is a book the HP price was not tuned on. Alternatives: all 500
sequences 250-749 (~8 thread-hours; over the cap with the probe); the
heuristic as chooser too (mixes in the known chooser share); 250-499 (on the
tuned book). Reversible: a later job can play 750-999 into a second file.

## Deck-matched reads built; boss-replay score not adopted (on the owner's behalf, 2026-11-04)

Lane cheaper-reads, steps 1 and 2 (results: docs/research/learned-play-results.md,
"Deck-matched reads one turn deep" and "Boss-replay score").
- `gauntlet.py play --match <file>` replays a file's recorded card picks,
  rest and removal; it passed its one-turn check (paired end-HP sd 20.6 ->
  13.4 and 10.1, means kept). It is a tool for fighter-only reads; it
  can't read a chooser or run-decision change, and on a new net it
  measures only the net's fighting. `match` is not compared by
  `--against` (it pins choices, not play). Whether matched reads become
  the default for two-turn fighter reads waits for the two-turn confirm
  (job 0107). Alternatives: matching inside `run()` (passed over: run
  stays a plain floor loop); declaring `match` with `--vary` (passed over:
  more flags for no safety, since `--match` already refuses a file made
  in another choice setting).
- The boss-replay score (8 replays at arrival) is not adopted: 1.17-1.28x
  on end-HP sd, 1.25-1.52x on clears, under the 1.4x bar, and two turns
  deep its replays would cost more than the sequences they save. The
  protocol keeps real end-HP and clears. `boss_replay.py --hp arrival` and
  `pair` stay as tools. Alternative: adopt on clears only for matched reads
  (passed over: one pair of four, and end-HP is the tested quantity).

## depth-headroom: outcome-blind elite reads (on the owner's behalf, 2026-11-04)

The charter's probe replays fights chosen by the control's own outcome
(floor-9 elites where it lost 15+ HP). A replay that plays differently
regresses toward its mean on those fights, so it looks better there even
at equal strength; 0093's rollout gain (-1.54 HP, se 0.46) rises with the
control's loss (-0.56, -1.88, -7.36 by band), the pattern of that bias.
Decided: the go rule is read on all 498 floor-9 elites (rollouts: the 237
decisive plus the other 261, `--kind elite-rest`, ~2.4 thread-hours);
three turns play the first 48 of all floor-9 elites (`--kind elite-all`)
instead of the first 48 decisive ones (0094 cancelled before it started,
same ~4.3 thread-hours); the lane stays inside its 12 thread-hour cap.
Go stays "1.5 HP or more per elite at 2 se", now per elite of any kind,
which is a harder bar than per decisive elite (the easy ones have less to
recover). Alternatives: take the decisive-fight read as it stands (biased
toward go); a null arm (the product with another search seed on the same
237, needs a seed offset in `depth_paired.py`, off limits for the probe);
re-select on a second independent control replay (twice the cost).
Reversible: the decisive-fight rows stay in their files and can be read
against a null arm later.

## goal1-yardstick: stage A two-turn table accepted at ritual2 se 0.023 (on the owner's behalf, 2026-11-04)

Job 0083's checkpoint asked for every modifier's two-turn win change at
se <= 0.02; 12 of 13 rows meet it and ritual2 reads -0.172 (0.023).
Decided: the widening is done and the checkpoint `stage-a-two-turn-200`
passes. Ritual2's effect is 7 se from zero, its verdict can't move, and
bringing its se to 0.02 needs about 1.3x the samples (~13 thread-hours
for the whole table, or a ritual-only extension the script doesn't
have). Alternatives: widen to 200 x 6 for all modifiers (~21
thread-hours, buys the bar on one row); record the checkpoint failed and
leave stage A open (blocks the stop rule on a row no read depends on).
Reversible: the play command resumes, so more seeds can be added later
if a read needs ritual2's two-turn number tighter (its boss-only cost is
the lead that might; results section "Mutated monsters, stage A, two
turns deep at 200 x 4").

## Mutated monsters stage B: three monster powers, unblocked Weak on hit, floor-halved split hits (on the owner's behalf, 2026-11-04)

Spec `docs/specs/mutated-monsters-b.md` (confirmed under the mandate)
builds the owner's two remaining monster examples ("two half-damage
hits", "Weak on hit with -20% damage") as three official powers appended
to `Power::ALL` (codec bytes, golden.txt and the rules version unchanged;
no official content holds them): `DamageDown` (attack damage x4/5, a data
static), `WeakOnHit` (new trigger `OwnerAttackHit`: 1 Weak per stack to
the target per hit that made it lose HP) and `SplitHits` (each monster
attack as twice the hits at half the base, rounded down, Strength per
hit; one helper feeds the actual hits and every intent reader).
Alternatives: Weak on every hit, blocked or not (mirrors `OwnerAttacked`;
passed over: block countering it is the game's on-damage timing, as
Envenom, and the more interesting mechanic to learn); half rounded up
(never loses damage on odd bases; passed over for the game's floor
rounding); generated pack powers on monsters (the registry binds them
through cards only; needs binding work outside the bench's need);
per-monster move overrides in state (a codec change). Reversible: the
powers are unused by official content, and the rules are a line each.

## Runtime registry first: Act 1 enters as content files (owner, 2026-11-04)

The engine upgrade exists to make content data instead of code, so it
supersedes the earlier "static Rust tables" decision ("Triggers and
conditions (SPEC.md Amendment 4)"). Finish `docs/specs/runtime-registry.md`
stages 2-5 (content in the version hashes, monsters from files, official
content as files, the new state layout) before any Act 1 content. After
stage 4 the Rust tables are removed once the files are checked equal to
them: one source of truth. Act 1 then goes in as content files; a card
that can't be written as data names a missing building block, which is
goal-1 work. The registry's speed budget (`scripts/series_speed.py`, at
most 10% per step) guards run time; stage 5's smaller states are the
expected speed gain. Alternatives: Act 1 as Rust tables (faster to build,
about the same speed to run, but it grows the code the registry
replaces); keeping the tables as a fallback after stage 4 (two sources of
truth).

Content identity: content is named by strings, as in the game; numbers
exist only inside a running engine, as fast handles in the order of the
loaded pack. Every net, dataset, recorded game, run result and solved
value is identified with the content pack it used (its hash), so the
pack fixes what each number meant. A pack is stored however is most
efficient, as long as any recorded hash recovers the exact pack.
Alternative: a committed, append-only table of numbered ids (an id
outlives every version, but it adds a second record beside the packs).

## No StS1 install; content parity from the wiki and sts_lightspeed (owner, 2026-11-04)

Superseded by "Parity source: the game's own code (owner, 2026-11-10)".

The real game is too slow to be a check. Content values come from the
wiki; behaviour is checked against sts_lightspeed where it covers it, and
the wiki decides where it doesn't (about half the Ironclad cards, the
Slavers, the Gremlin Gang, curses). Level 2 of the arena ladder (the real
game through a mod bridge) is dropped; levels 0 and 1 stand
(`decision/goal2-arena`). Alternative: wait for an install (never coming).

## Lane runtime-registry opened (on the owner's behalf, 2026-11-04)

Opened on the owner's direction of 2026-11-04 (`docs/direction.md`:
development weight goal 1 0.8; interest "Act 1 implementable in the engine
through the runtime registry") and the owner's decision "Runtime registry
first: Act 1 enters as content files" (`decision/registry-first`), which
names `docs/specs/runtime-registry.md` stages 2-5 as the prerequisite of
every Act 1 content file. The draft's questions for the owner are answered
there: stage order 2, 3, 4, 5; the files are the source after stage 4 and
the Rust tables go once the files are checked equal; speed budget
`scripts/series_speed.py`, at most 10% per step. The one it leaves open,
registry scope (one per process or a handle per state), takes the
reversible default: one per process stays until stage 5's spec shows a
need for a handle.

Goal: land stages 2-4 on main, each a `/spec` confirmed under the mandate
then a `/build` with the series checks (golden identical, `series_check.py`
PASS, `series_speed.py` within the budget): (2) content in the version
hashes (the rules fingerprint and the registry's rules version hash the
loaded packs); (3) monsters from packs (HP, moves, pattern rows, start
powers; code-only setups stay official-only until they become rows); (4)
official content as `content/*.json` generated from today's tables, loaded
at startup, checked equal, then the tables removed. Stage 5 (sorted inline
piles and sparse power lists, the speed lever) is specced with its speed
case measured and built if the window allows. Act 1 content itself is the
next lane (backlog `act1-content`), not this one.

Expected value: p ~0.7 that stages 2-4 land by the end date (the series
landed nine specs in a week by the same path; stage 1 is built). It moves
no score; it is the owner's named prerequisite for goal 1's content work
and for generated content as first-class, and the only development item
the direction ranks first. CPU: the builds are code; the CPU is the tests
per landing (test-full ~130 min at 4 threads, cargo tests, series_speed),
~30 cpu-h for three landings; cap 45 cpu-h; end 2026-11-13. Kind project.
Shares (`jobs/lanes.json`, from the direction's CPU weight goal 1 0.6):
goal1-yardstick 45, cheaper-reads 25, runtime-registry 10, depth-headroom
10, main 10 (goal 1 lanes 55 of the 90 lane points). A fourth lane while
depth-headroom is within days of its end (2026-11-08, one queued job
decides it). Alternatives passed over: `act1-content` directly (the owner
says registry first); `new-mechanics-workflow` (ideas#51: the registry is
its backbone; it follows); `horizon-leaf-screen` (p ~0.2); extending
goal1-yardstick to cards now (its stage B table is still running);
waiting for a lane to close (the direction's first item would sit a week).

## Backlog re-ranked for the owner's direction of 2026-11-04; small defaults (on the owner's behalf, 2026-11-04)

- **Re-rank.** `docs/backlog.md` is re-ranked under `docs/direction.md`
  (development goal 1 0.8 / goal 2 0.2; CPU 0.6 / 0.4): the registry and
  Act 1 content lead, then goal 1's yardstick and the cheaper-reads work
  (every read); run-level decision work (`chooser-margin-rule`,
  `mini-run-headline`) is parked under the direction's "Avoid" until the
  content it chooses between is in the engine; `elite-payoff-relics` folds
  into `act1-content` (relics as content files through the registry, not
  state patches); `outside-yardstick` is parked (level 2 of the arena is
  dropped, `decision/goal2-arena`). `decision/no-registry-stages` (owner
  away, 2026-11-02) is retired: the owner's decision supersedes it.
- **Unfiled 0067/0068.** The two-turn games of the closed two-turn-round
  lane are a dataset, not a read; filed as
  `measurement/two-turn-games@j1` (3000 + 300 games, pace, registry ids)
  so the record exists for a future stronger-teacher read; their value was
  read through 0069-0071 (`measurement/two-turn-round@cells`).

## Thread count for headline reads: 3 threads stays the default; 8 only for a read alone on the machine (on the owner's behalf, 2026-11-04)

The thread check (`docs/research/learned-play-results.md`, "Thread check",
0095-0096) put 8 threads at 0.599x the 3-thread wall time two turns deep,
at the charter's 0.6 bar, for 1.6x the thread-minutes per sequence and
7.76 GB peak against 3.31 GB. Alternatives: (a) adopt 8 threads for every
headline read (rejected: fewer sequences per CPU-hour and memory rarely
free for it, against "machine time is the bottleneck"); (b) reject 8
threads outright (rejected: when nothing else can run beside a read whose
result gates the next step, the idle cores are wasted); (c) chosen: 3
threads, two jobs at once, stays the default; a read whose wall time gates
the next decision and that would run alone may use `--threads 8 --mem-gb
8`. Reversible by editing a job's flags.

## Runtime registry stage 2: records name their packs, the store recovers them; versions stay official-only (on the owner's behalf, 2026-11-04)

Stage 2 of `docs/specs/runtime-registry.md` ("content in the versions") is
built as content identity under `decision/registry-first`: every pack a
dataset manifest (`content_hash`) or a training round names is stored as
`datasets/packs/<hash>.json`, the exact text the engine loaded; a replay
whose pack isn't loaded loads it from the store after checking FNV-1a of
the bytes against the name, and refuses a missing or mismatched file. The
solved-DB fingerprint and `rules_version` stay official-only while the
codec refuses states with generated content (it asserts on any registry
binding): no solved value can hold a pack's content, and hashing loaded
packs in would give every process that loaded one (learn.py's mixed
training) its own empty DB version. Stage 4 puts the official content
files into the fingerprint; a stage that lets the codec write generated
states puts the packs in. Alternatives: packs in both hashes now (the
draft's sketch; splits the DB and protects nothing); a combined content
version per record (same information, one more field); the store in git
(jobs writing tracked files dirty the tree) or a new top-level folder
(snapshots don't junction it). Packs loaded before this stage aren't
stored; their datasets replay from the generator as before.

## Deck-matched reads stay a one-turn screen tool; two-turn reads stay unmatched (on the owner's behalf, 2026-11-04)

0107 (the heuristic two turns deep with the product's picks, 500-749)
cut the paired end-HP sd 1.27x against 0090's unmatched read, under the
1.4x bar its note set, with the means equal; it also took 0.48x the wall
time (results "Deck-matched reads two turns deep"). Decided by that
pre-set rule: `--match` stays a one-turn screen tool, and two-turn
headline reads keep the protocol unmatched. Alternatives: adopt matched
reads for two-turn fighter reads on the CPU-per-verdict figure (0.29x on
this pair), which was measured but not the rule set before the run, so it
needs its own pre-set check (left to the navigator); or rerun the confirm
on a candidate closer to the product (another ~0.5 thread-h each; the
lane's reads are done). Reversible: one flag on a read.

## Lane depth-headroom closed (2026-11-04)

Navigator run 21:20 on the trigger `lane-done:depth-headroom`. The lane's
step says `done: no go`: its stop rule (go if three turns or a rollout leaf
recover 1.5 HP or more per decisive fight over the two-turn product, paired,
2 se; else stop and the paused depth family closes on the dev machine) is
reached on the stop side. Outcome, each read paired against the two-turn
product's own play on the headline control's floor-9 elites:
- Rollout leaf (n 16, product policy) on all 498 elites: +0.67 HP lost
  (se 0.31, worse), wins -0.008 (`measurement/rollout-leaf@elites`); the
  -1.54 HP gain on the 237 decisive elites (`measurement/rollout-leaf@decisive-elites`)
  was regression to the mean (the non-decisive half +2.69).
- Three turns (guarded, 1.6M nodes) on the first 48 elites: -0.75 HP lost
  (se 0.81), wins 48/48 both; decisive half -2.82, non-decisive +1.00:
  the same pattern (`measurement/three-turn@elites`). Under the bar; the
  boss probe not run.
- Anchor: the heuristic leaf two turns deep with the product's picks is
  9.3 HP and 0.200 clears behind the product on 500-749
  (`measurement/depth-anchor@headline`): two turns deep the learned leaf
  carries the edge.

The finding to carry (`cause/depth-saturated`): on the dev machine's budget the
two-turn product sits where more depth stops paying on elites; the two
"decisive-fight" gains were both selection on the outcome. The paused
depth family (three-turn search, rollout leaves, two-turn search inside
the choosers) is closed, not paused (`decision/depth-family-closed`);
what a horizon-complete leaf could gain two turns deep is bounded by what
a third turn sees, so `horizon-leaf-screen` loses its goal-2 case. Search
budget goes to the run layer once it has content to choose between
(`docs/direction.md` "Avoid"). CPU: 8.8 cpu-h of the 12 cap (predicted
~7.5), two days of its five. Shares after the close: see the next entry.

## Lane adaptation-curve opened (on the owner's behalf, 2026-11-04)

With `depth-headroom` closed the portfolio has no exploration lane. The
owner's training rule (`docs/operating.md`) makes goal 1 the exception in
kind: "how few games a net needs to adapt to new content is the goal-1
number, so there a curve of games against retention is worth measuring",
and `docs/direction.md` names "few games to adapt" first under goal 1
(development weight 0.8). No lane measures that curve;
`decision/no-mutated-monster-burst` only ruled a burst out as a product
lever (two turns deep the cost is repaired), which stands. This lane
measures the curve itself as an exploration probe, kill-fast: one burst at
the largest game count first, one read, then go or stop.

- Content: stage A's unseen-power modifiers, where the one-turn novelty
  cost is largest (`measurement/mutated-monsters@stage-a`: SharpHide 2
  -0.048, its hp pair -0.062, Ritual 2 -0.038, se ~0.01-0.015), so a
  halving is readable at 200 starts x 8 seeds.
- Recipe: the adaptation burst (`docs/specs/adaptation-burst.md`,
  `configs/burst8-s1.json`'s fine-tune from the 10-29 net) with its games
  played against the patched monsters (the state patches of
  `scripts/analysis/mutate_monsters.py`, or packs once
  `lane/runtime-registry` stage 3 lands monsters from packs); the lane
  worker picks the game counts (defaults: the largest first, about 1600
  fights, then 400 and 100 only on a go) and one training seed (a lead,
  written as such).
- Read: per game count, the one-turn novelty cost per modifier on the
  parents (`mutate_monsters.py play --players one` with the burst net, 200
  x 8) and retention: the one-turn cell gauntlet 0-499 `--against` the
  10-29 control (`yardstick/one-turn-controls`) at fixed n, and the
  official parents' rows.
- Go: the largest count cuts the SharpHide 2 and pair costs at least in
  half (at 2 se) with retention within 1.5 HP paired on cells; the curve
  (games against cost and retention) is then goal 1's first "games to
  adapt" number and a backlog entry for the paired-modifier bench. Stop:
  it doesn't, which says the gap is inputs the net can't see (the net
  half of `new-mechanics-workflow` gets it, after the registry's atoms)
  or retention fails (the burst recipe is the wrong tool for goal 1).

Expected value: p ~0.4 that the burst halves the cost with retention
(bursts on generated cards gained +0.011 on the ladder; an unseen power on
a known enemy is a smaller step than new cards). CPU: ~5 cpu-h (games
minutes, a fine-tune ~10 min at 6 threads, reads ~15 min each; three
counts on a go); cap 8 cpu-h; end 2026-11-11. Kind exploration.
Alternatives passed over, in value order: `horizon-leaf-screen` (p ~0.2;
`cause/depth-saturated` bounds what a horizon-complete leaf could add two
turns deep by what a third turn sees, which is nothing on elites, so its
goal-2 case fails the owner's trade-off rule; its goal-1 case, a leaf that
reads rows, is the registry's atoms plus the net half of the workflow, a
project lane later); `feasibility-ladder` (ideas#77; proves fixed-deck
cell sequences unwinnable, but cells no longer rank nets
(`yardstick/headline-setting`) and headline losses are boss deaths after a
built deck, so it gains nothing on the current setting: parked by the
trade-off rule); `rows-on-burst` (~3 CPU-h; which burst content uses the
new rows is still unknown, so the read is blind); `prior-art-card-ai`
(no CPU; an exploration source). Shares: `goal1-yardstick` 45, `cheaper-reads` 25,
`runtime-registry` 10, `adaptation-curve` 10, `main` 10.

## Lane cheaper-reads closed (2026-11-04)

Navigator run 21:20 (the same run that closed `depth-headroom`); the lane's
step says `done:` after its three reads, so it closes now rather than on
its own trigger. Outcome, by step:
- Deck-matched reads: one turn deep, variance 2.4x and 4.2x lower with the
  means kept (`measurement/deck-matched@one-turn`, passed); two turns deep
  the sd fell 1.27x against the 1.4x bar with means equal and the wall time
  0.48x (`measurement/deck-matched@two-turn`, failed the bar). Matched reads
  stay a one-turn screen tool (`decision/matched-reads`).
- Boss-replay score: sd ratios 1.17-1.28 on end-HP, not adopted
  (`measurement/boss-replay-score@one-turn`).
- Thread check: 8 threads take 0.599x the 3-thread wall at the 0.6 bar,
  1.6x the thread-minutes; 3 threads stay the default, 8 only for a read
  that has the machine alone (`decision/read-threads`).

What it changes: the variance between players on the headline is in the
fights, not the picks (two turns deep the picks explain a third of it), so
cheaper verdicts come from fewer or shorter sequences, not from pairing.
The lane's lead for the navigator: on 0107's pair a matched two-turn read
costs 0.29x the CPU per verdict (variance 1.63x lower and the chooser's
sim fights skipped). Not adopted now: no two-turn fighter candidate is in
sight (the depth family and the training arms are closed), so the
decision waits for one. Pre-set check, recorded in the backlog as
`matched-two-turn-adopt`: the next two-turn read of a fighter-only
candidate runs matched beside its protocol read on the same sequences
(sequences 0-249 of both); adopt matched reads for fighter-only two-turn
reads if the CPU per verdict is under 0.5x with the paired means within
2 se, on that second pair. Alternatives: adopt on 0107's pair alone (one
pair, the heuristic as candidate, far from the product); or drop the lead
(forgoes a ~3x saving on every fighter read). CPU: 11.4 cpu-h of the 12
cap (predicted ~8). Shares after both closes: `goal1-yardstick` 50,
`adaptation-curve` 25, `runtime-registry` 15, `main` 10 (goal 1 holds
every lane with CPU work; `docs/direction.md` CPU 0.6 / 0.4 has no goal-2
job to give the rest to).

## Adaptation-curve burst design (on the owner's behalf, 2026-11-04)

Lane `adaptation-curve`, spec `docs/specs/adaptation-curve.md`. The burst
trains on games against the patched monsters themselves: `finetune.py`
gains a `{"mutated": [...]}` content kind whose games start at the
gauntlet's elite and boss fights with the stage A patch applied, played
one turn deep by the 10-29 net at `@hpb0.01`, recorded by a Python loop of
`sts.search_action` (`sts.run` takes only specs; 0.1 s per fight, the same
wins as `sts.play_on` on 20 fights). The read's 200 fights are never
trained on (`skip` 200); validation is the last 100 fights. First burst:
SharpHide 2, its hp pair and Ritual 2, 534 fights each (1602 games), one
training seed (a lead). Read against the stage A file on the same starts
and seeds (`mutate_monsters.py compare`: the heuristic cancels), and
retention on the one-turn cell gauntlet at fixed n against
`yardstick/one-turn-controls`. Alternatives: wait for packs
(runtime-registry stage 3) and use `sts.run` specs (days later, same
games); play the games with the heuristic (it is the novelty baseline,
so its games teach nothing net-specific); include the unmodified parents
in the burst (the replay pool already carries official content). Most
reversible: code is additive, string and generated kinds unchanged.

## Role models: navigator Opus high, lane worker Opus medium (owner, 2026-11-04)

The navigator runs on Opus at high effort, the lane worker on Opus at
medium effort (`scripts/roles.py` `ROLES`: `--effort` passed to each
headless session). Reasons, from the approach review: most of a navigator run is
scripted bookkeeping (closing and opening lanes in the prompt's order);
its lane picks mostly carry out the backlog's order and the owner's
direction. No record compares the two models on this role.
Alternatives: keep Fable (status quo); Opus for the navigator with Fable
kept for the big-picture review; a read-only Opus trial of a past
trigger first.

## Lane adaptation-curve closed (2026-11-04)

Outcome: go, curve filled (`measurement/adaptation-curve`,
`measurement/adaptation-curve@1602`; lane facts retired). The 10-29 net
fine-tuned on games against SharpHide 2, its hp pair and Ritual 2 cuts
the one-turn novelty cost of sharp2 / sharp2-hp0.9 by 1.17x / 1.06x at
99 games (33 per modifier), 1.66x / 1.27x at 399 and 1.65x / 1.34x at
1602, the whole gain on elites (Three Sentries most); retention on the
one-turn cell gauntlet holds within 0.6 se at every size. Ritual 2, whose
payoff (growing Strength) lies past the horizon, is cut only 0.15-0.46x at
any size, and two-turn search leaves it at -0.036 too
(`measurement/mutated-monsters@stage-a`). Goal 1's first games-to-adapt
number: about 100 games for an unseen power whose payoff falls inside the
search horizon, plateau by about 400. Leads: one training seed per size,
nested data, one family of powers, one-turn reads.

Predicted at opening: rated even (p ~0.4) that the largest burst halves
the cost with retention; ~5 cpu-h. Actual: go at every size including the
smallest; 1.8 cpu-h of the 8 cap (`wakes.lane_cpu_h`; the lane's own
count ~2). The prediction under-rated the burst recipe (a value net
learns "don't spread attacks into reflected damage" in a few dozen
fights) and over-estimated the CPU (fine-tunes at 99-399 games take
minutes).

What it says beyond its question:
- `cause/novelty-is-horizon` re-set: the one-turn net's cost on an
  unseen turn-start power splits by where the payoff lies. Inside the
  horizon (SharpHide) it is a training gap that about 100 games close,
  and two-turn search also repairs it; past the horizon (Ritual 2)
  neither two turns nor 1602 games repair it. `decision/no-mutated-monster-burst`
  stands as a product decision (the two-turn product has the SharpHide
  cost repaired and a burst cannot repair Ritual 2 either) and is
  re-worded to match the 200 x 4 table.
- The games-to-adapt curve is cheap enough (bursts of minutes, reads of
  minutes) to run per mechanic as a standing part of goal 1's yardstick;
  the next lane does that on stage B's new mechanics (lane `adaptation`,
  below), with the second training seed the lane asked for and a
  transfer read (does a net adapted to SharpHide lose less on Thorns, the
  sibling mechanic it never trained on; `results/mutate/a.json` has
  thorns2's one-turn novelty cost at -0.053 (0.014)).
- Reopen if: a burst at ~100 games fails to cut a new in-horizon
  mechanic's cost (stage B) or retention breaks at a larger burst; or a
  way to put a past-horizon payoff inside the net's view appears (new
  inputs: the net half of `new-mechanics-workflow`), when Ritual 2 is the
  first bench.

## Role models revised: the navigator stays on Fable at high effort (owner, 2026-11-04)

Revises "Role models: navigator Opus high, lane worker Opus medium" for
the navigator only: with its job now new approaches and the ranking
(operating-model amendment 6), it runs on Fable at high effort, and wakes on conditions it sets itself instead of
daily, which cuts its runs. The lane worker stays on Opus at medium
effort. Alternatives: Opus at high
effort (the earlier decision, made when the job looked like bookkeeping);
Fable only for ideas runs and Opus for trigger runs (dropped with the
daily schedule).

## Lane adaptation opened (on the owner's behalf, 2026-11-04)

With `adaptation-curve` closed the portfolio has no exploration lane, and
its result (about 100 games repair an in-horizon unseen power, one seed,
one family of powers) is a lead that asks three cheap follow-up questions,
each one probe and one read (`docs/direction.md`: goal 1's "few games to
adapt", "new mechanics, not new cards, are what hurts"; development
weight 0.8). This lane holds them, in order of cost:

1. **Transfer** (queueable now, no code): the stage A burst nets
   (`runs/2026-11-04-adapt-sharp-s1-1c14a6c/model.pt`, 1602 games;
   `runs/2026-11-04-adapt-sharp-g33-s1-a10d626/model.pt`, 99 games),
   trained on SharpHide 2, its pair and Ritual 2, played one turn deep on
   Thorns 2 (the sibling mechanic they never saw; one-turn novelty cost
   -0.053 (0.014) in `results/mutate/a.json`) and on the stack
   `metal4-hp0.85+sharp2-hp0.9` (-0.091 (0.016)): `mutate_monsters.py play
   --players one --net <model>@hpb0.01 --mods thorns2,metal4-hp0.85+sharp2-hp0.9
   --starts 200 --seeds 8`, read with `compare` against `a.json`. Go if the
   1602-game net's thorns2 gain is at least half its sharp2 gain (about
   +0.04) at 2 se: the net learned the lesson (don't spread attacks into
   reflected damage), so goal 1's number is per mechanic family, smaller
   than per mechanic. Stop otherwise: adaptation is per mechanic (each
   needs its own ~100 games), recorded as such. Rated **even**: for, the
   two powers punish the same play and the gain sat on one three-enemy
   fight; against, a value net can key on the power id it saw rather than
   the mechanic, and Thorns fires per hit, not per attack card.
2. **Second training seed** at 99 games on stage A (a config
   `adapt-sharp-g33-s2.json`: seed 2, same content, `game_seed` and
   `games`), read as the curve's two reads. The 99-game number becomes a
   result (not a lead) if both seeds cut sharp2's cost at 2 se with
   retention. Rated **likely** (the one-seed cut at 99 games was 4 se).
3. **Stage B's mechanics**, after job 0112 writes their one-turn rows
   into `a.json`: bursts at 99 and 399 games (one seed) on `weakhit1`,
   `dmg0.8` and `split` together (finetune's `mutated` kind, which plays
   its games against the patched monsters; `split` is a pattern patch, so
   the first run checks finetune plays it), each read per modifier at
   200 x 8 and retention on the one-turn cell gauntlet 0-499 against
   `yardstick/one-turn-controls` at fixed n. Rated **likely** for
   weakhit1 and dmg0.8 (payoffs inside the horizon, like SharpHide),
   **even** for split (a pattern change the net sees only as damage
   numbers). Goal 1's games-to-adapt number then stands on four
   in-horizon mechanics and two seeds.

Stop rule: done when 1-3 are read; fail if retention breaks (paired
end-HP below -1.5 HP on cells) at any size, which says the recipe forgets
on new mechanics, or if finetune cannot play stage B's modifiers within
1 h of code. Kind exploration; CPU ~2.5 cpu-h (fine-tunes of minutes at
4 threads, reads of ~5 min at 3 threads); cap 4 cpu-h; end 2026-11-11.
On close: wake the navigator either way (a go changes the yardstick's
unit, a stop re-ranks `past-horizon-inputs`).

Alternatives passed over: `prior-art-card-ai` with a few-shot-adaptation
angle (no CPU: the navigator runs it itself); `rows-on-burst` (the read is blind until the
burst content using the new rows is known); a three-turn read on Ritual
2's bosses to separate horizon from inputs (three turns deep 48 elite
fights took job 0109's hours, so 200 boss starts cannot reach se ~0.012
within an exploration cap, and depth is not a lever on the dev machine,
`cause/depth-saturated`); `past-horizon-inputs` for Ritual 2 (a net-input
change, project-size, after the registry's atoms; its 0-CPU first step,
does the encoder carry Ritual's amount and the fight's turn count, goes
to the backlog's open questions). Shares: `goal1-yardstick` 50,
`adaptation` 25, `runtime-registry` 15, `main` 10.

## Lane adaptation extended: step 4, rate-column twins on Ritual 2 (on the owner's behalf, 2026-11-04)

Navigator ideas run (a full ideas pass under
amendment 6). Open question 1 ("what repairs a past-horizon payoff") had a
zero-CPU first step: does the net's encoding carry a power's per-turn
worth? It can. The encoder's off-by-default `rates` columns
(`docs/specs/rate-features.md`, built 2026-10-31) give the player and each
monster the heuristic's `hook_rates` sums as inputs, among them Strength
per turn and Strength x the rounds-left estimate: exactly Ritual 2's
payoff, which the product net (rates off) cannot read and which neither
two-turn search nor 1602 games of fine-tuning repair
(`cause/novelty-is-horizon`, -0.036 two turns deep, the whole cost on
bosses). The columns were closed for goal 2 (held-out bosses +0.022 and
+0.033 against a +0.06 bar; results doc "Rate features"), but on the one
unseen mechanic they targeted, Demon Form (Strength per turn on the
player's side), the rate nets gained +0.12 to +0.20 on every seed. They
were never read on the mutated bench, where the question is goal 1's.
The closed lane `adaptation-curve`'s reopen condition ("a way to put a
past-horizon payoff inside the net's view appears, when Ritual 2 is the
first bench") therefore holds today, with the built columns as its
evidence.

Decision: lane `adaptation` (exploration, opened 23:10) gets a step 4
and its cap rises from 4 to 12 cpu-h (its one extension): the rate nets
`runs/2026-10-31-lean-rates-s{1,101,201}-r2-*/model.pt` and their twins
without the columns `runs/2026-10-31-lean-thr-s{1,101,201}-r2-*/model.pt`
(same config, seed and round 0), each played one turn deep on `ritual2`,
`ritual2-hp0.7` and `sharp2` and their parents
(`mutate_monsters.py play --players one --net <model> --mods
ritual2,ritual2-hp0.7,sharp2 --starts 200 --seeds 8 --threads 3 --out
results/mutate/<arm>-<seed>.json`; the encoder reads `rates` from the
model's meta, `stsnet.py`; `compare` of the rates file against the twin's
file), the novelty cost per net paired by start. Kill-fast: seed s1's pair
first; if the rates net's ritual2 novelty cost is not smaller than its
twin's at all, stop there. Go: over the three seeds the rates nets'
ritual2 novelty cost is at least 0.02 smaller than their twins' (about
half the one-turn cost) at 2 se, with sharp2 (in-horizon, the control)
within 2 se of equal; then `past-horizon-inputs` becomes a project
candidate: a product-lineage net with the columns, allowed by the
training rule ("inputs it can't see today"), read two turns deep on
Ritual 2 and the headline. Stop: the columns don't carry Ritual 2's
payoff either, recorded on `cause/novelty-is-horizon`, and the input
question goes back to the net half of `new-mechanics-workflow` (the
registry's atoms). CPU: ~5 thread-h (rates encoding is ~7x slower per
state; one-turn reads of minutes otherwise).

Why here and not a new lane: the portfolio holds three lanes and a fourth
opens only near an end; the question is the one `adaptation` already asks
(what repairs a novelty cost: games, search or inputs), the probe needs no
code and the lane worker is active now. Alternatives: a ready charter for
a fourth lane (waits days for a slot); a step in `goal1-yardstick` (a
project lane, its queue holds 8 h of stage B work and this is an
exploration); a product-lineage rates net first (~20 cpu-h before the
cheap twin read says whether the columns carry the payoff).

## Adaptation step 4: Guardian guard on the bench's own Guardian starts (on the owner's behalf, 2026-11-05)

The owner's note: `cause/novelty-is-horizon` rev 4 records
the rate columns' side effect (about -0.1 on Guardian fights without
Demon Form, 1.8-3 se over 3 seeds, a post-hoc split, with a decision-diff
mechanism around Mode Shift) and the failed adoption rule; step 4's go
rule checks only sharp2 within 2 se, so a go would not say whether that
cost comes with the columns. One premise differs from the data: the
mutated bench does play the Guardian (15 of its 200 starts are
`the_guardian`, on the parents and on every modifier, x 8 seeds; the
other bosses are Slime Boss 22 and Hexaghost 29), and every `--net` read
replays the parents, so the twins' files already hold 120 Guardian fights
per net at no extra CPU. The substance stands: nothing in the stop rule
read them.

Decision (`lane/adaptation` rev 4): the go rule gains a guard, read and
recorded either way: on the parents' Guardian starts, the rates net's win
rate minus its twin's paired by start, pooled over the seeds read (se
about 0.06 at one seed, 0.035 at three). Pass: above -0.05, or within 2 se
of 0. Fail: below -0.05 at 2 se, which says the side effect comes with the
columns on this bench too. A go with a failed guard is recorded as "go
with a Guardian cost", and the project step it opens (a product-lineage
rates net) must read its Guardian sequences two turns deep against
`yardstick/headline-control` before any promotion, since the product
plays two turns deep, where the record shows the cost mostly removed
(train -0.162 (0.028) one turn, -0.032 (0.023) two turns; held-out +0.002
and +0.061). Alternatives: a separate Guardian read on `tight_bosses`
cells (already in the record for s101/s201/s301 at both depths, so it
adds nothing for the twins and costs CPU); no guard (the owner's concern
exactly); making the guard a stop condition for step 4 itself (too
strong: step 4 asks whether the columns carry Ritual 2's payoff, and the
side effect is the project step's question, where the two-turn product
is the player). Jobs 0128 and 0129 (seed s1) have ended; the lane worker
reads them under this rule.

## Lane adaptation closed (2026-11-05)

Outcome: done, all four steps read (`lane/adaptation`, retired with this
entry). (1) Transfer **passed**: the 1602-game SharpHide burst repairs
Thorns 2 at 0.86x its own SharpHide gain, and the step 3 control showed it
also cuts WeakOnHit's HP cost (1.36 of 1.74 HP, 4.8 se), though WeakOnHit's
effect differs; it gains nothing on DamageDown or split. Transfer carries
across powers that punish the player for attacking, wider than one effect
atom (`measurement/adaptation-transfer` rev 2). (2) Second seed
**passed**: the 99-game point is a result (`measurement/adaptation-curve`).
(4) Rate columns **failed**: no repair of Ritual 2 over three seeds
(`measurement/rate-columns@ritual2`). (3) Stage B bursts **failed** as a
read: one turn deep, stage B's modifiers cost the net little (win -0.016,
-0.006, -0.016), and no burst at 99 or 399 games cut any of them at 2 se
(`measurement/adaptation-stage-b`). Retention held at every size. All
single training seed except step 2. CPU: 3.4 cpu-h used against the cap
of 12 (opened at ~2.5 estimated, cap 4; extended for step 4).

**Reopen if:** a new mechanic with a clear one-turn cost (at least about
0.04 win rate or 3 HP per fight, at 2 se, on the mutated bench) exists to
train on, so a burst has something to cut (stage B's weak modifiers
couldn't give a curve point); or a second training seed is wanted for the
WeakOnHit transfer lead (one 1602-game SharpHide seed, ~0.5 cpu-h for a
new burst plus a 5-minute read), which would settle whether goal 1 trains
per family of punishments; or an input that puts a past-horizon payoff in
the net's view appears (Ritual 2 stays unrepaired by games, depth and
rate columns).

## Stage A re-read: the boss cost follows shifted numbers, not growth, and how a novelty cost is read (on the owner's behalf, 2026-11-05)

Navigator run 1ef7f60b, at the close of lane `adaptation`, from
`results/mutate/a.json` (stage A and stage B's one-turn rows; no CPU).
The record read Ritual 2's cost as a payoff past the search horizon
(`cause/novelty-is-horizon`), and the ready charter `past-horizon-repair`
was built on it. Three cuts of the same file say otherwise.

**1. On bosses a plain stat change costs as much as Ritual 2.** One turn
deep, win-rate novelty on the 66 boss starts: ritual2 -0.066 (0.027),
str2 (a static +2 Strength, visible in every intent) -0.064 (0.024),
hp0.8 (an easier boss) -0.057 (0.027), hp1.3-str-1 -0.040, str1 -0.034;
SharpHide 2 +0.021 and Thorns 2 -0.009 cost nothing there.

**2. Part of that is the win-rate scale.** The net's whole boss edge over
the heuristic on the parents (+0.045 (0.029); seed halves +0.068 and
+0.023) sits in 18 of the 66 starts (those the two-turn player wins 2 or
3 times of 4: heuristic 0.44, net 0.59); the 34 it always wins and the
14 it loses show none. Any modifier that moves the boss decides those 18
starts the same way for both players (hp0.8: 0.90 and 0.89; str2: 0.22
and 0.23; ritual2: 0.22 and 0.22), so a difference of win-rate
differences reads a cost even if the net lost nothing. hp0.8 leaves 22
informative starts and all three players at 0.85-0.87.

**3. A measure free of the base rate still shows the cost on raised
Strength.** The start-stratified (Mantel-Haenszel) log odds ratio of a
player against the heuristic, bootstrap se over starts, modified content
minus parent:

| bosses | one-turn net | two-turn product |
|---|---|---|
| parent (the edge itself) | +0.42 (0.27) | +0.97 (0.24) |
| str2 | -0.64 (0.24) | -0.53 (0.30) |
| ritual2 | -0.82 (0.31) | -0.73 (0.38) |
| ritual2-hp0.7 | -0.54 (0.30) | -0.17 (0.32) |
| hp0.8 | -0.61 (0.32) | -0.84 (0.47) |
| str1 | -0.32 (0.22) | -0.13 (0.31) |
| hp1.25 | -0.26 (0.28) | -0.07 (0.31) |
| hp1.3-str-1 | -0.37 (0.24) | -0.00 (0.28) |
| metal3 | -0.03 (0.22) | -0.09 (0.32) |
| sharp2 | +0.24 (0.29) | +0.12 (0.32) |
| thorns2 | -0.08 (0.28) | +0.17 (0.35) |

A static +2 Strength costs the net its boss edge as Ritual 2 does, one
turn and two turns deep; nothing in str2 lies past the horizon. So the
boss cost follows the boss's shifted numbers, not growth, which also
fits the rate columns' null (`measurement/rate-columns@ritual2`: they
describe growth). All of it is 2-3 se on 66 starts, and the parent edge
itself is 1.5 se: a lead. What is left that is specific to growth:
ritual2 on elites loses +2.42 (0.52) HP beyond the heuristic against
str2's +0.41 (0.18).

**4. On elites the cost is not yet separated from danger.** Elite parents
are won 0.99 by every player, so the net's edge there can't be read on
the parents; in every variant that makes elites contested the one-turn
net is below the heuristic by odds ratio (sharp2 -1.36 (0.29), thorns2
-1.37 (0.29), ritual2 -0.86 (0.30), weakhit1 -0.75 (0.39), hp1.25 -0.55
(0.40)). SharpHide, which the net has seen on the Guardian, costs as
much on elites as Thorns, which it has never seen (+5.47 and +5.53 HP
lost), and the SharpHide burst repairs Thorns and WeakOnHit on the same
elites (`measurement/adaptation-transfer`). Both fit a second reading
the bench has no control for: the net is tuned to the danger of official
fights, and any change that takes a fight outside that range costs it,
whatever the mechanic. The monster inputs carry no identity (alive, hp,
max_hp, block, intent, powers; `py/src/features.rs`), so the net tells a
boss by its HP scale and intents, which a stat change shifts.

**Decisions.**
- `cause/novelty-is-horizon` is re-set: the in-horizon half stands
  (reactive powers on elites, repaired by depth and by ~100 games); the
  boss half is a cost of shifted Strength and HP, not of growth, a lead.
- A novelty cost is read on three columns (`yardstick/novelty-read`,
  refining how `decision/goal1-yardstick`'s "drop beyond the parent's
  difficulty" is computed, which the owner's decision leaves open): the
  win-rate table as before; on bosses the start-stratified odds ratio
  against the heuristic, modified minus parent; on elites HP lost. A
  modifier's cost counts as novelty only against a plain control about
  as hard (a stat-only variant), from the next rung on.
- `past-horizon-repair`'s ready charter is withdrawn: its first probe
  (rate columns plus games on Ritual 2) aims at growth, which point 3
  does not support, and its go rule reads the 66-start boss column. Its
  second probe (the heuristic blend) stays a candidate
  (`novelty-gated-leaf`).
- `decision/no-mutated-monster-burst` stands and is re-set with the new
  reading: the product's boss cost under stat shifts is open at 66 starts.

Alternatives: keep the past-horizon reading and run columns plus games
(3 cpu-h on a target the data no longer supports); drop the boss cost as
noise (str2 and ritual2 are each 2.6-2.7 se by odds ratio one turn deep
and 1.8-1.9 two turns deep: too much to drop, too little to build on);
change the yardstick to the odds ratio alone (the win-rate table is what
the owner's decision describes and stays the first column). Most
reversible: facts re-set, no data or code touched.

## Lane difficulty-shift opened (on the owner's behalf, 2026-11-05)

Exploration slot, free since `adaptation` closed (on-close: wake always).
Charter in `lane/difficulty-shift`. It asks the question the re-read
above leaves open, before any repair spends CPU: is the net's cost on
changed enemies a cost of the new mechanic, or of a fight made more
dangerous than those it trained on?

- **Step 1, the wide read** (no code, ~10 thread-h): the bench on 1000
  starts (325 bosses, 675 elites) x 32 seeds, heuristic and one turn,
  parent and str1, str2, ritual2, hp0.8, hp1.25, sharp2, dmg0.8, read by
  `yardstick/novelty-read`. At 66 boss starts the odds-ratio se is
  0.24-0.32; at 325 it is about 0.12, so a cost of -0.6 is 5 se and
  -0.3 is 2.5.
- **Step 2, the stat burst** (no code, a config; ~1 thread-h per seed):
  the 399-game burst recipe on plain stat changes only (hp0.8, hp1.25,
  str2, hp1.3-str-1), read on the reactive powers it never saw (sharp2,
  thorns2, weakhit1) and on ritual2. If it repairs them as the SharpHide
  burst did, the unit of novelty is the fight's danger, not the
  mechanic, and goal 1's zero-shot lever is training with jittered
  numbers (new content under the owner's training rule), which needs no
  new mechanic at all. If not, the transfer result stands as a family of
  mechanics. Both outcomes inform (the trade-off rule).

Rated **even** that the stat burst reaches half the SharpHide burst's
gain: for, the SharpHide net also gained on WeakOnHit, a different
effect, and the net is below the heuristic on every contested elite
variant, plain hp1.25 included (1.4 se); against, SharpHide and Thorns
ask for a specific answer (fewer, larger attacks) that stat changes do
not teach, and the SharpHide net gained nothing on dmg0.8 and split
(which had nothing to cut). Rated **likely** that the wide read confirms
a boss cost on raised Strength (2.6-2.7 se on both str2 and ritual2 one
turn deep; against: the parent edge is 1.5 se and shared by every row).
~16 thread-h, cap 24.

Alternatives passed over: `past-horizon-repair` as chartered (withdrawn
above); a second training seed for the WeakOnHit transfer lead (0.5
cpu-h; the stat burst is the better control for the same question, and
its seeds 2 and 3 cover the seed doubt); `novelty-gated-leaf` (needs
code, and its target on
bosses is what step 1 measures); `boss-step-hp-price` (goal 2, a long
shot, needs code). The CPU is at 26% use with one job running, so a
lane whose two steps are designed and need no code goes first.
Shares: goal1-yardstick 35, difficulty-shift 35, runtime-registry 20,
main 10, filler 0.

## Lane difficulty-shift closed (2026-11-05)

Outcome: done, both steps read (`lane/difficulty-shift`, retired with this
entry). The net's cost on changed enemies is a cost of the mechanic, not
of a fight made more dangerous. (1) Wide read **failed** its pass rule: at
325 boss starts x 32 seeds the one-turn net has no boss edge over the
heuristic (+0.01 (0.12)) and no boss cost on str1, str2, ritual2, hp0.8
or hp1.25; stage A's boss cost was seed luck in its shared parent edge
(fresh seeds of the same 66 starts: str2 -0.12 (0.19), ritual2 -0.05
(0.26)). On elites plain stat changes cost nothing by odds ratio (str2
+0.29 (0.14), hp1.25 +0.03 (0.17)) and the mechanics do (ritual2 -0.65
(0.21), sharp2 -1.18 (0.20)) (`measurement/wide-bench@one-turn`). (2) Stat
burst **failed** (stop): 400 games on hp0.8, hp1.25, str2, hp1.3-str-1
gain -0.023 on sharp2 and +0.018 on thorns2, against the same-size
SharpHide burst's +0.080 and +0.066; retention -0.85 HP (0.49), clears
-0.032 (0.016) (`measurement/stat-burst@one-turn`; one training seed).
The wide-bench boss check for the burst (0148) was stopped at its start:
no base cost to repair. A new read, `mutate_monsters.py odds`, gives
`yardstick/novelty-read`'s odds-ratio column reproducibly. CPU: about
6.1 cpu-h used against the cap of 24 (opened at ~16 thread-h).

Consequences for the navigator (wake): `cause/novelty-is-horizon`,
`decision/no-mutated-monster-burst` and `yardstick/novelty-read` are
flagged (their boss half or example rests on the seed-luck reading);
`jitter-training` loses its premise (it opened only on step 2's go);
`novelty-gated-leaf`'s boss target is gone one turn deep. A boss novelty
read belongs two turns deep, where the product has an edge to lose.

**Reopen if:** a player with a real boss edge one turn deep appears (a new
net whose parent boss odds ratio against the heuristic is above about 0.3
at 2 se on the wide bench), so the boss column can show a cost; or a stat
burst is wanted at a larger size or with jittered numbers covering the
reactive powers' danger (more than 1602 games, or a second training seed
showing a thorns2 gain at least half the SharpHide burst's), which would
reopen danger as the unit of novelty.

## After difficulty-shift: one shared parent, the bench's decks, the held-out headline, and where bosses kill (on the owner's behalf, 2026-11-05)

A navigator ideas run on `lane/difficulty-shift`'s two failed checkpoints
(decisions "Lane difficulty-shift closed"), from the result files, with
no CPU. Four readings and what each changes.

**1. Every modifier of a table shares its parent's draw.** A novelty cost
is "modified minus parent", and all modifiers of a file are read against
the same parent games. Stage A's one-turn boss costs (str2, ritual2,
hp0.8, 2.6-2.7 se each) were one lucky parent draw, not three findings
(`measurement/wide-bench@one-turn`). The two-turn column has the same
shape and is still open: the product's only costs on the monsters rung
(ritual2 -0.036 (0.012), hp0.8 -0.030 (0.010) over 200 starts) sit on
the 66 boss starts, read against one parent draw of 4 seeds
(`results/mutate/a.json`: bosses, two turns 0.716, heuristic 0.614 on
the same 4 seeds; the heuristic's 24 fresh seeds of those starts in
`results/mutate/wide.json` give 0.646, so about 0.03 of the 0.10 parent
edge was the heuristic's low draw; the two-turn player's own parent draw
has no fresh seeds). Rule, filed in `yardstick/novelty-read`: agreement
across modifiers of one file is one draw; a table of M modifiers plays
its parent at about sqrt(M) times the seeds of a modifier (the known
design for many comparisons against one control, Dunnett's); a boss lead
becomes a result only on starts or seeds the lead was not found on.

**2. The mutated bench plays cell decks, not the product's decks.**
`scripts/analysis/bias_audit.py` `fights()` gives each start the
sequence's pre-built cell deck (`gauntlet.sequences`), at the entry HP
the product file reached with the deck it built from the starter. The
docstring of `mutate_monsters.py` ("the gauntlet's elite and boss fights
replayed") and the facts that call these "the product's fights" read as
if the decks were the product's; the code is right about what was
played. Seen as: on the same 66 boss starts the product file's own boss
fights were won 0.909 and the bench's two-turn replays 0.716 (Hexaghost
0.93 against 0.64). Not a seed leak: the sim chooser's fights use
`SIM_SEED_BASE`, a block apart from the fights' seeds. What it changes:
bench win rates are not headline win rates; the yardstick stays valid
(parent and modifier share the deck); `finetune.py`'s burst games take
their fights the same way; and on the cards rung a card modifier reaches
only starts whose cell deck holds that card (15 cards, 5 beyond the
starter), so the first card modifiers go on Strike, Defend and Bash or
the starts are filtered per card (added to `yardstick-cards`' charter).

**3. The product's headline on the confirmation book is 0.780, and no
fact held it.** `results/gauntlet/net1029-hpe0.01-two-line-step-starter-simboss-500.json`
(the product, sequences 500-999) clears 0.780, against 0.834 on the
screening book 0-499 (`measurement/headline@two-turn`), although the
heuristic finds 500-999 easier (`yardstick/books`). Unpaired the gap is
0.054, about 2.1 se: part chance, part the search settings (@hpe,
line-seed, step-line, Strike removal) having been chosen on 0-499. The
goal-2 number to quote is 0.807 of 1000, or 0.780 held out
(`measurement/headline@confirm-book`).

**4. Half of the boss deaths are Hexaghost, and those are lost in the
fight, not on the way.** Over both books (1000 sequences, 193 deaths,
140 at the boss): Hexaghost 70 deaths of 312 arrivals (win 0.776), the
Guardian 57 of 299 (0.809), Slime Boss 13 of 336 (0.961). The Guardian
and Slime Boss are entry-HP losses (48 of 57 and 12 of 13 deaths arrive
under 60 and under 50 HP; the Guardian wins 0.92-0.97 from 60 HP).
Hexaghost is not: 44 of its 70 deaths arrive with 50 HP or more, 22 with
60 or more (win 0.69 at 50-59, 0.80 at 60-69, 0.93 from 70). The HP on
the way goes at the two elites (17.3 and 13.8 HP per fight; hallway
fights 0.5-3.6). Filed in `cause/boss-deaths`. It answers open question
6's first fact: a boss-shaped HP price has the Guardian's 48 deaths to
aim at and nothing on Hexaghost, and in a fight that is won for sure a
steeper price picks the same line, so `boss-step-hp-price` stays a long
shot with a smaller target.

**Backlog, from these and from the lane's close.** `jitter-training`:
shown wrong (the stat burst repairs nothing and costs -0.032 clears on
official cells). `future-inputs`: withdrawn; its premise was the boss
cost, and lookahead already read as no gain on official elites and
bosses (decisions "Monster lookahead: no gain, stays off"). Reopen if
the two-turn boss read below is a go. `novelty-gated-leaf`: parked by
the trade-off rule; the product has no cost for a blend to gain on until
the same read is a go, or a later rung shows a two-turn cost. New, both
goal 2 and both held: `hexaghost-headroom` (is there fighter headroom in
the Hexaghost fight; the long shot within the exploration slot's reach;
needs a boss kind in `depth_probe.py`) and `own-boss-chooser` (the sim
chooser's boss term against the sequence's own boss; card picks, so
parked under the direction's avoid list until `act1-content`'s cards).

## Lane boss-cost-two-turn opened (on the owner's behalf, 2026-11-05)

The exploration slot emptied with `difficulty-shift`. Opened:
`lane/boss-cost-two-turn`, kind exploration, cap 14 cpu-h, end
2026-11-12, on-close wake always. One probe, one read: the two-turn
player on the 259 boss starts stage A never used (wide bench starts
200-999), parent, ritual2 and hp0.8 at 2 seeds, the heuristic's games
taken from `results/mutate/wide.json` (32 seeds of the same starts).
About 1,550 boss games at about 20 thread-s each by job 0113's pace
(29 boss starts so far: 162 s per 24 games at 3 threads): ~9 thread-h.
It needs a boss-only start filter in `mutate_monsters.py play` (a few
lines and a test); without it the file would also play 675 elite starts,
about 15 thread-h that decide nothing.

What each outcome gives (the trade-off rule): a go (ritual2 or hp0.8
below the parent by 2 se on both the win-rate and the odds-ratio column,
or by 3 se on one, with the parent edge above 2 se) is the first product
cost on the monsters rung, and reopens `novelty-gated-leaf` two turns
deep, `future-inputs` and a Ritual 2 burst read two turns deep
(`decision/no-mutated-monster-burst`). A stop closes the monsters rung
for the product: no novelty cost on any stage A modifier two turns deep,
stage A's two boss rows recorded as one parent draw, and goal 1's CPU
moves to the cards rung and to generated enemies.

Rated **a long shot** that a cost of stage A's size (about -0.08 win on
bosses) is real, **even** that a smaller one shows at 2 se. For: two
turns deep there is a boss edge to lose (0.716 against 0.646), and both
rows were 3 se. Against: the one-turn rows of the same starts vanished
on fresh seeds; part of the parent edge was the heuristic's low draw;
ritual2 and hp0.8 move bosses out of the middle of the win-rate scale
(`yardstick/novelty-read`).

Alternatives passed over: more parent seeds on stage A's 200 starts (the
shared term for all 27 modifiers, ~14 thread-h two turns deep; it needs
a seed offset in the script and a read across two files, and leaves each
boss row its own 66-start noise); the full wide file two turns deep
(~68 thread-h); `hexaghost-headroom` (goal 2; needs more code, and about
8 GB at 3 threads); waiting for the cards rung's spec (the CPU has one
job running and both project lanes' next steps are specs). Shares: goal1-yardstick 40,
boss-cost-two-turn 30, runtime-registry 20, main 10, filler 0.

## Lane goal1-yardstick closed (2026-11-05)

Outcome: done at its cap: the stop rule's three tables are recorded
(`lane/goal1-yardstick`, retired with this entry). (1) Stage A's
two-turn product table widened to 200 starts x 4 seeds: one turn deep
the net pays for new mechanics (SharpHide 2 -0.048, Thorns 2 -0.053,
Ritual 2 -0.038), two turns deep search repairs the reactive powers and
the product's change beyond the heuristic is within +-0.015 except two
boss rows (ritual2 -0.036, hp0.8 -0.030) read against one parent draw
(`measurement/mutated-monsters@stage-a`). (2) The stacking check failed
its additivity rule: the sum of parts misses by up to 0.04, so a stack is
measured as its own row (`measurement/mutated-stacking@stage-a`). (3)
Stage B's pattern modifiers (WeakOnHit, DamageDown, split, the
WeakOnHit+DamageDown pair, two stacks) cost the product nothing beyond the
heuristic two turns deep (all within 1.6 se, se <= 0.020; read at 141 of
0113's 200 starts), the pair's two-turn cost sitting on bosses with the
same parent-draw signature; lead: stacks holding a reactive power cost the
product about 0.03 on elites (`measurement/mutated-monsters@stage-b`;
learned-play-results "Stage B two turns deep"). Goal 1's monsters rung has
its number; the next rung is cards. CPU: 90.1 cpu-h against the cap of 90
(the opening rating: even that the number exists within the cap, ~60
CPU-h estimated).

Job 0113 runs out its last 59 starts (~2.3 h at 3 threads, about 7 cpu-h
past the cap) (on the owner's behalf). Alternatives: cancel it at 141
starts (rejected: no lane has other CPU work ready, `ready` is red, so its
three threads would idle; its rows only tighten the table, the se from
about 0.020 to 0.017); keep the lane open past its cap until it ends
(rejected: the cap is the charter's, and the read already passes). After it
ends, `mutate_monsters.py read results/mutate/a.json` refreshes the stage B
rows; a change beyond 1 se in any verdict is worth a re-set of
`measurement/mutated-monsters@stage-b`, by whoever reads it next.

**Reopen if:** lane boss-cost-two-turn is a go (a product cost on shifted
bosses is real, so the monsters rung has a boss cost the bench should map
per modifier); or the reactive-stack lead holds on a fresh read (two or
more stacks holding SharpHide or Thorns at 2 se beyond the heuristic on
elites, on new seeds or starts 200-999), which would make stacking the
distance axis for the product after all; or monsters from packs land
(runtime-registry stage 3), so new monsters, not patches, can be benched.
No on-close condition in the charter, so no navigator wake: the slot goes
to the first ready charter.

## Lane yardstick-cards opened (on the owner's behalf, 2026-11-05)

Fills `goal1-yardstick`'s slot (closed above). The navigator's ranking of
2026-11-05 08:00 (`docs/backlog.md`, under `docs/direction.md`: goal 1
0.8) puts **yardstick-cards** first, and it is the only candidate with a
ready charter; it is the owner's yardstick's next rung
(`decision/goal1-yardstick`, "then cards"). The charter is copied as
written into `lane/yardstick-cards` (kind project, cap 38 cpu-h, end
2026-11-13, on-close wake always). It takes the closed lane's share, 40,
in `jobs/lanes.json`. Its first step is a spec (the card patches and the
one-turn probe of four modifiers), so the lane has no
CPU job until then. Alternatives: leave the slot empty and wake the
navigator (rejected: a ready charter exists, and the steps say open it).

## Lane boss-cost-two-turn closed (2026-11-05)

Outcome: **stop**, by the charter's rule. Job 0151 played the two-turn
product on the 259 boss starts stage A never used; against the wide
file's heuristic games the parent edge is real (+0.075 (0.013) win,
+1.07 (0.20) log odds), and neither modifier costs the product beyond the
heuristic at the go bar (2 se on both columns or 3 on one): ritual2
-0.017 (0.016) / -0.15 (0.24), hp0.8 -0.038 (0.016) / -0.38 (0.26).
hp0.8's 2.4 se on the win column is the ceiling squeeze the odds column
removes (it sits on slime_boss, where the product already wins 0.87).
The monsters rung costs the two-turn product nothing measurable on any
stage A modifier (`measurement/boss-cost@two-turn`; results doc
"Boss cost two turns deep, on 259 fresh boss starts").

CPU: about 17.9 thread-h against the cap of 14 (estimate 9). The cap was
reached at 12:32 with the job 93% done; the job was let finish, since
cancelling it would have spent 14 cpu-h for no read, and the charter's
fail branch is for a read that cannot finish. The estimate was off
because two-turn boss games take about 41 thread-s, not the 20 taken from
job 0113's mixed elite and boss pace. Alternatives at the cap: cancel
0151 and close as fail (rejected: the remaining ~4 thread-h bought the
whole read); a partial read at 929 starts (rejected: the job's own file
was finishing within the hour, and a partial read is a second look).

Rated at opening a long shot that a cost of stage A's size is real (it
was not: ritual2's -0.036 shrank to -0.017 on fresh starts) and even that
a smaller one shows at 2 se (only on the win column, for hp0.8, and that
is the ceiling).

**Reopen if:** a modifier that moves bosses toward the middle of the
win-rate scale without a ceiling (a growth or reactive power of a new
family on bosses, or generated boss monsters once runtime-registry
stage 3 lands) shows a two-turn cost beyond the heuristic at 2 se on a
first read; or a product with a much larger boss edge than +0.075 (where
there is more to lose) is promoted, which makes the same 259-start read
worth repeating at 2 seeds and ~18 thread-h.

On-close: wake always, so the navigator decides the slot.

## After boss-cost-two-turn: the heuristic is not the zero of a novelty cost; lane adapted-two-turn opened (on the owner's behalf, 2026-11-05)

Navigator run of 2026-11-05 14:00, on the close of `boss-cost-two-turn`
(stop; `measurement/boss-cost@two-turn`).

**What the stop says beyond its question.** Every "costs the product
nothing" on the monsters rung is read beyond the heuristic
(`yardstick/novelty-read`): the product's win change from the parent minus
the heuristic player's. The heuristic player is as new to a mechanic as
the net is (`engine/src/heuristic.rs` has no term for SharpHide or
Thorns), so that column measures whether the product loses more than
another unadapted player, not what an adapted player would win. On Three
Sentries with SharpHide 2 (43 starts of `results/mutate/a.json`, read
today at 197 of 200 two-turn starts) the heuristic falls -0.262, the
one-turn net -0.477 and the two-turn product -0.279: the product ends
level with the heuristic, 0.28 below its own parent, and loses 2.9 HP
more than the heuristic does from the modifier. A burst of 399 games
gains +0.054 to +0.084 wins on sharp2 one turn deep and carries to Thorns
(`measurement/adaptation-curve`, `measurement/adaptation-transfer`); no
adapted net was ever played two turns deep. So
`decision/no-mutated-monster-burst` ("the reactive powers cost the
product nothing") rests on a reference player that cannot show the cost.
Goal 1 is few games to adapt: its number for the product is the adapted
player minus the zero-shot player at the product's depth. Both outcomes
are open: depth took most of the effects encoding's edge on unseen cards
(+0.059 to +0.017, `measurement/effects-vs-ids@gen-bench`) and all of the
rate columns', so the burst's gain may vanish two turns deep; or the
product pays a cost the heuristic column hides.

**Lane adapted-two-turn opened** (exploration; fills the slot
`boss-cost-two-turn` left). Rated **even**. About 24 thread-h (cap 36).
Steps:
1. No code, queued at once (it also keeps the CPU from idling after job
   0113): the product and the heuristic on the 272 elite starts at
   positions 400-799, which no burst net trained on (the 399-game net
   trained on fights 200-332, validation is 900-999) and where the
   reactive-stack lead was not found: `mutate_monsters.py play --starts
   800 --skip 400 --groups elite --players heuristic,two --seeds 8
   --two-starts 800 --two-seeds 2 --mods
   sharp2,thorns2,metal4-hp0.85+sharp2-hp0.9,weakhit1-dmg0.8+thorns2-hp0.9
   --threads 3 --out results/mutate/fresh-elites.json` (~11 thread-h at
   ~13 thread-s per two-turn elite game; re-estimate from the first 20
   starts). It re-reads the stack lead of `goal1-yardstick`'s close (two
   stacks at -0.03, 2.5 se) on fresh starts, and its product games are
   step 3's control.
2. A `--two-net` option in `mutate_monsters.py` (the two-turn player's
   net, as `--net` sets the one-turn player's; `heuristic` for the
   hand-written leaf), then the 399-game SharpHide net
   (`runs/2026-11-04-adapt-sharp-g133-s1-5ad1c9c/model.pt`) two turns
   deep on the 134 elite starts of positions 0-199 at 4 seeds, parent,
   sharp2, thorns2 and metal4-hp0.85+sharp2-hp0.9, read against the
   product's games on the same starts in `results/mutate/a.json` (~8
   thread-h). Steps 1 and 2 may run side by side (two heavy jobs).
3. Only if step 2 lands between its bars: the same adapted player on
   positions 400-799 at 2 seeds against step 1's product games (~6
   thread-h), pooled with step 2.

Go: the adapted player beats the product by 2 se on wins or on HP lost on
sharp2 or on thorns2 (which it never trained against), with the parent
within 1 se. Then the product pays a zero-shot cost on reactive powers,
the yardstick gains an adapted column, and a burst is a product lever
for new content (`decision/no-mutated-monster-burst` is revisited). Stop:
under +0.02 wins and under 1.5 HP on both. Then two-turn search plays
in-horizon mechanics at the adapted level with no games, which is goal
1's number for them stated against the right reference.

Alternatives passed over:
- `hexaghost-content-burst` (goal 2; the owner's discussion of today):
  a long shot, its games need a Hexaghost-only source in `finetune.py`
  (checked: `two_turn_games.py` plays `selfplay.GROUPS`, which hold
  neither Hexaghost nor the Guardian, and the mutated source has no
  encounter filter), and its probe is ~1 thread-h, so it does not keep
  the CPU busy. It now carries the ready charter for the next free slot,
  with a pre-read on step 2's option.
- `hexaghost-headroom` (goal 2): more code, about 8 GB at 3 threads.
- Held-out reads of the product's single settings (line-step against
  plain two turns, @hpe against @hpb, on sequences 500-749; no code, ~4
  thread-h each): not proposed, by the owner's rule that a run whose
  expected effect is below its smallest detectable effect does not run:
  each setting was adopted as level, the expected difference is about
  zero, and 250 paired sequences detect about 0.07 clears.
- The reactive-stack re-read alone: it is step 1's second read, not a
  lane; beyond the heuristic it has the same blind reference.
- Leaving the slot empty until the cards spec can be written: the CPU
  idles (both project lanes wait on specs).

**Goal 2 holds no lane.** The direction's CPU weight for goal 2 is 0.4
and all three open lanes are goal 1. Every goal-2 candidate needs code,
and the only code-free goal-2 run fails the
detectable-effect rule above. The next free slot goes to
`hexaghost-content-burst` (ready charter in `docs/backlog.md`); the
big-picture review takes goal 2's CPU as its first question.

**Shares** (`jobs/lanes.json`): yardstick-cards 35, adapted-two-turn 35,
runtime-registry 20, main 10, filler 0. The lane worker's interim 60 / 30
gave the cards lane the closed lane's share; the registry's CPU is test
runs, and the two measuring lanes split the rest.

**The monsters rung, as recorded from here.** Beyond the heuristic the
two-turn product pays nothing measurable on any stage A or stage B
modifier, bosses included (`measurement/boss-cost@two-turn`); whether it
pays against an adapted player is this lane's question.
`cause/novelty-is-horizon` and `decision/no-mutated-monster-burst` are
re-set with their boss rows closed and this reference named.

### Adapted two turns deep: confirm the go on fresh starts before the close (on the owner's behalf, 2026-11-05)

Job 0154 meets lane adapted-two-turn's go bar on HP lost: sharp2 -1.46
(0.64), thorns2 -1.61 (0.64), parent +0.29 (0.38)
(`docs/research/learned-play-results.md`, "Adapted two turns deep"). It
does so at 2.3 and 2.5 se, on one burst seed and 134 starts, with both
singles read against one parent draw. The go would reopen
`decision/no-mutated-monster-burst`, a product decision. By "Reading
results" (a pass near its bar gets a look before anything builds on it),
the lane runs its designed step 3 anyway: the adapted player on the 272
elite starts at positions 400-799, 2 seeds, mods sharp2, thorns2 and
metal4-hp0.85+sharp2-hp0.9, against job 0152's product games (about
2.3 h at 3 threads), pooled with 0154. The lane then closes on the fresh
read and the pooled read together. Go stands if the fresh starts alone keep
both singles' HP gain above zero and the pooled read stays at 2 se on
either single. Otherwise the lane closes as stop or as a lead.
Alternatives: close now on the go and leave confirmation to the navigator
(cheaper, but the navigator would wake to a lead and likely
queue the same run; the CPU sits idle meanwhile); confirm at 4 seeds
(twice the CPU for an se about 0.8x as large). Reversible: the step
only adds a results file.

### Lane adapted-two-turn closed (2026-11-05)

**Outcome: go, on the win column.** Pooled over 406 elite starts never
trained on (steps 2 and 3), the 399-game SharpHide burst net, played two
turns deep, beats the two-turn product on sharp2 +0.025 (0.008) wins and
on thorns2, which it never trained on, +0.013 (0.006), with the parent's
wins level (+0.001 (0.003)): the charter's go (2 se on wins on a single,
parent within 1 se). On HP it gains about 1.1 per elite fight on the
reactive powers but loses 0.60 (0.23) on unchanged elites, so on HP the
parent is not within 1 se. Step 1 on fresh starts: the product pays
about 2 HP per elite fight beyond the heuristic on every reactive
modifier (+1.75 to +2.66, 3.5-5 se), level on wins; the reactive-stack
win lead fails as stated (Thorns stack only). Lagavulin carries the
burst's gain; on Three Sentries it loses HP. Results:
`docs/research/learned-play-results.md` "Fresh elite starts" and
"Adapted two turns deep, confirmed on fresh starts";
`measurement/adapted-two@elites`, `measurement/reactive-cost@fresh-elites`.

**CPU:** 24.0 cpu-h of the 36 cap (0152 10.6, 0154 6.9, 0156 6.5),
as estimated at the opening (about 24).

**What it changes (the navigator's to re-set):**
`decision/no-mutated-monster-burst` rested on the heuristic as the zero
and is wrong against an adapted player; `cause/novelty-is-horizon`'s
exit "lane adapted-two-turn's go" is reached; the cards lane's table
gains an adapted column (backlog, yardstick-cards revision 14:00).

**Reopen if:** a burst can be kept from costing the parent (mixed-in
official games or a retention guard) and the product question is whether
a burst on a new mechanic should ship, read on the headline setting; or a
second burst training seed is played two turns deep (this go rests on one
seed); or Three Sentries' opposite sign needs explaining (a burst trained
without Sentries, or a per-encounter leaf).

**Next slot:** the charter says `on-close: wake always`: the navigator
decides; the slot stays empty, and its share (35) goes to the open lanes
in `jobs/lanes.json` (yardstick-cards 60, runtime-registry 30, as the
interim split after the last close). Neither open lane has a job queued
and the first ready candidate (`hexaghost-content-burst`) needs code
before its first CPU job, so nothing is queued for the slot; test-full
(filler) is pending.

## After adapted-two-turn: a burst is the adapted column, not yet a product step; lane unseen-boss-burst opened (on the owner's behalf, 2026-11-05)

Navigator run of 2026-11-05 19:10, on the close of `adapted-two-turn` (go
on wins; `measurement/adapted-two@elites`,
`measurement/reactive-cost@fresh-elites`).

**What the go says.** Two turns deep the product pays about 2 HP per
elite fight beyond the heuristic on every power that punishes attacking
(3.5-5 se on fresh starts, wins level), and a net fine-tuned on 399 games
against SharpHide wins +0.025 (0.008) more on sharp2 and +0.013 (0.006)
on Thorns, which it never trained against, while losing 0.60 (0.23) HP per
unchanged elite fight. So:
- `decision/no-mutated-monster-burst` rested on the heuristic as the zero
  of a novelty cost and is retired. In its place
  `decision/burst-adapted-column`: a burst of about 400 games against a
  new mechanic is the adapted column of goal 1's yardstick, read at the
  product's depth against the product on the same starts and seeds, wins
  and HP lost both, with the parent row as its retention and one training
  seed counted as a lead. It is not shipped as a product step yet: it
  gains about 1.1 HP on the mechanic and costs 0.6 HP on unchanged elites,
  so it pays only where most fights carry the mechanic. The form it would
  ship in is a net named by a content pack, decided when packs exist
  (`runtime-registry` stage 4). No burst against Ritual 2 (games do not
  repair it) or on plain stat changes (it repairs nothing and costs
  Hexaghost wins, below).
- `yardstick/novelty-read` is re-set: on elites HP lost is read beside
  wins (the win column missed the cost twice), and rule (e) names the
  adapted column as read above.
- `cause/novelty-is-horizon` is re-set: two-turn search repairs most of a
  reactive power's one-turn cost, not all of it; what is left is in the
  leaf and about 400 games remove half of it.
- `lane/yardstick-cards` gains the adapted column for each card modifier
  whose one-turn novelty cost or two-turn HP column passes 2 se, and its
  cap goes from 38 to 46 cpu-h (one burst and one two-turn adapted read,
  about 6 cpu-h; the lane's one extension). The end date stays.
- Open against the go: one burst training seed (a twin read on hook
  powers has a training-seed sd of about 0.03 wins,
  `yardstick/twin-reads`); the parent cost; Three Sentries' opposite
  sign. Backlog `burst-recipe` holds them.

**What it says together with the boss deaths.** The leaf gains from games
where it has never trained, even two turns deep. The 10-29 net never
trained on Hexaghost or the Guardian, and those two are 127 of the
product's 140 boss deaths (`cause/boss-deaths`). Every mutated-monster
burst trains on the bench's elite and boss fights, so the existing burst
nets have already played 36-177 patched games against each boss. Probe
(jobs 0157-0160, lane main, about 1.5 cpu-h, no code): the four burst nets
replayed one turn deep on the 474 boss fights of the headline decks at
HP 30-80, against the 10-29 net's replay on the same seeds
(`measurement/burst-bosses@replay`). The 1602-game SharpHide net wins
+0.034 (0.008) more Guardian and +0.031 (0.010) more Hexaghost fights
(the same on sequences outside its training fights), the 399-game one
nothing, the stage B net +0.032 (0.009) on the Guardian, and the stat
burst -0.054 (0.012) on Hexaghost; Slime Boss, which the net trained on,
moves at most +0.012. Each net is one training seed and the training-seed
sd on unseen bosses is 0.02-0.04, so no direction is a result. What holds
is that the leaf's play on the two unseen bosses is loosely held: a few
hundred games on other content move it four times as far as they move
Slime Boss.

**Lane unseen-boss-burst opened** (exploration; fills the slot
`adapted-two-turn` left; it takes over the backlog's
`hexaghost-content-burst`, the owner's discussion of 2026-11-05, widened
to both unseen bosses). A burst of official Guardian and Hexaghost games,
read first on the boss replay (minutes per net, se 0.004), on two training
seeds, then two turns deep on bench boss starts. Rated **even** for a
one-turn gain of 0.05 on both seeds: for, on tight cells the net leads the
heuristic by +0.137 on the boss it trained on and +0.07 on the two it did
not (learned-play-results "Boss lead per boss"), and the probe shows that
play is easy to move; against, the training-seed sd, Hexaghost's deck
ceiling (19 of 161 decks win 2 of 4 or fewer at 80 HP), and one-turn
outcome labels gave only +0.017 on trained content
(`cause/teacher-equals-student`). **A long shot** for a headline pass:
about a third of a one-turn gain reached two turns on reactive powers, so
the upside is about +0.01-0.02 clears. Admitted by
`decision/training-stops` as new content; it is not a recipe arm under
`decision/no-goal2-training-arms`, and nothing is promoted on the replay
(`decision/no-proxy-promotion`): the headline read decides. It also gives
goal 1 a number the patched bench cannot: games to adapt to a whole
enemy the net never met. About 20 cpu-h (cap 30). Step 1 is a small
change, not a spec (an identity modifier and a group filter on
`finetune.py`'s mutated source, or the `tight_bosses` train cells), so a
light session can do it.

Alternatives passed over:
- `sequential-bursts` (goal 1, no code, about 1.5 cpu-h): the next ready
  charter. It is a smaller question, and goal 2 has had no CPU since
  11-04 against a direction weight of 0.4.
- `burst-recipe` (a second seed and a rehearsal mix for the reactive
  burst, about 14 cpu-h): after the cards probe says whether the cards
  rung needs adapted columns at all.
- The 1602-game SharpHide net two turns deep on bosses or on the headline
  now (no code): not proposed, by the owner's detectable-effect rule. A
  one-turn +0.025 is about +0.01 two turns deep, against an se of
  0.017-0.026 on the bench boss starts it did not train on, and its
  elite cost lowers boss entry HP on the headline.
- `hexaghost-headroom` (three turns deep): more code, about 8 GB.
- Leaving the slot empty until the cards and registry specs are written:
  the CPU idles.

**Shares** (`jobs/lanes.json`): yardstick-cards 40, unseen-boss-burst 30,
runtime-registry 20, main 10, filler 0.

**The idle CPU.** Both project lanes wait on specs,
so CPU work has to be designed in charters as jobs a light session can
queue. This run's ready charter (`sequential-bursts`) needs no code for
that reason.

**Added the same run: a queueable CPU step for yardstick-cards.** With
`0155-test-full` waiting for memory, nothing is running and
neither project lane has CPU work a light session can queue (the
portfolio rule asks for one). The cards lane's charter gains a step 0
that needs one config and no spec: the adapted column's seed check. A
second training seed of the 399-game SharpHide burst
(`configs/adapt-sharp-g133-s2.json`), played two turns deep on the 272
fresh elite starts with sharp2 and thorns2 against job 0152's product
games (about 5 cpu-h). Both outcomes are open: the HP cost it would
remove is there at 3.5-5 se whatever the burst, and a twin read on hook
powers has a training-seed sd of about 0.03 wins, as large as the gain.
Seed 2 gaining makes `measurement/adapted-two@elites` a result and one
burst seed enough for a column; seed 2 level means every adapted column
needs three seeds, which triples that column's cost in the cards table.
The cap goes to 52 cpu-h (46 above was before this step).

## Boss-replay probes: the seed spread on unseen bosses, the ensemble, and unseen-boss-burst's two-turn rule (on the owner's behalf, 2026-11-05)

Same navigator run, 19:35-19:50, with the machine idle: six more replays
of 5 minutes each (jobs 0161-0166, lane main, about 2 cpu-h with
0157-0160), read in `docs/research/learned-play-results.md` "Burst nets
on the headline decks' boss fights" and `measurement/burst-bosses@replay`.

- **Seed spread.** The two seed twins of the 10-29 net differ from it on
  the headline decks by an sd of 0.010 on the Guardian, 0.017 on
  Hexaghost and 0.008 on Slime Boss. The burst nets' moves of 0.03-0.05
  on the unseen bosses are two to three times that, so the reading
  "loosely held" is measured, and lane `unseen-boss-burst`'s one-turn go
  bar (+0.05 on both training seeds) is three to five seed sd.
- **The two-turn read needs a larger one-turn gain.** Three leaf gains
  reached the two-turn product at about a third of their one-turn size
  (`cause/leaf-gain-third`). By the owner's detectable-effect rule the
  lane's two-turn read (325 bench boss starts at 4 seeds, se about 0.011,
  about 21 cpu-h) runs only from a two-seed mean gain of 0.07 one turn
  deep; a go under 0.07 closes as goal 1's games-to-adapt number on a
  whole unseen enemy, without a two-turn read (`lane/unseen-boss-burst`
  rev 2). Alternative passed over: reading every one-turn go two turns
  deep, which spends 21 cpu-h on an expected 1.5 se.
- **Ensemble on unseen bosses: checked, stays closed.** The 11-01 read
  ("Ensemble evaluator: no change at two turns") had Slime Boss as its
  only boss, and the seed spread is twice as wide on the unseen bosses,
  so the mean of the three seed nets was replayed against its members:
  +0.007 (0.004) on the Guardian, +0.009 (0.004) on Hexaghost, 0.000 on
  Slime Boss. The mechanism holds and is worth under a hundredth one turn
  deep; no candidate.

## Lane unseen-boss-burst closed (2026-11-05)

Lane worker, 2026-11-05 20:50 (on the owner's behalf). **Outcome: fail
by the stop rule, one turn deep.** Four bursts of the 10-29 net on
one-turn Guardian and Hexaghost games (400 and 1600 games, two training
seeds each) raised Guardian plus Hexaghost boss-replay wins by +0.021 and
+0.016 (400) and +0.034 and +0.017 (1600); the rule fails the lane when
either seed is under +0.03, and no size came near the go bar (+0.05 on
both seeds) or the 0.07 a two-turn read needs. Retention held (cells +0.4
to +1.6 HP, Slime Boss +0.005 to +0.012). The Guardian gain (+0.030 to
+0.055) is about what bursts on other content give, and Hexaghost does
not move on its own games (-0.003 to +0.015, inside the seed spread).
`measurement/unseen-boss-burst@replay`; learned-play-results.md
"Unseen-boss bursts, one turn deep".

**CPU-hours:** 1.9 of the 30 cpu-h cap (0170-0181); the two-turn read
(about 21 cpu-h) was not run.

**Reopen if:** the net gains inputs for the state that decides these
bosses (Hexaghost's move-cycle position and its HP-scaled Divider, Burn's
row kind, checked first on the 10-29 layout), or the burst's games come
from a stronger teacher (two-turn games, so labels carry more than the
student already knows), or a probe (backlog `hexaghost-headroom`) shows
Hexaghost decks have play headroom a net could reach. A rerun must beat
the generic burst effect on the Guardian (+0.032-0.034 from bursts on
other content), not the 10-29 net alone.

Alternatives passed over: running the two-turn read anyway on the
1600 s1 net (+0.034, one seed; about 21 cpu-h for an expected gain near
1 se), and a third training seed to rescue the 1600 size (its seed mean
+0.026 is far under 0.07 whatever the third seed does). On-close
`wake always`: the navigator decides the slot.

## After unseen-boss-burst: games do not buy play on a whole unseen boss; lane sequential-bursts opened (on the owner's behalf, 2026-11-05)

Navigator, 2026-11-05 20:55, on the wakes `checkpoint:unseen-boss-burst@1`
and `lane:unseen-boss-burst` (fail one turn deep,
`measurement/unseen-boss-burst@replay`).

**What the result says beyond its own question** (results doc "Boss
replays re-read by boss", `measurement/depth-by-boss@replay`,
`cause/bursts-buy-mechanics`):
- Goal 1. A burst buys back a mechanic the net misreads inside the search
  horizon (SharpHide, Thorns, WeakOnHit: about 100 games,
  `measurement/adaptation-curve`) and nothing a read can see anywhere
  else: plain numbers (`measurement/stat-burst@one-turn`), growth past
  the horizon (Ritual 2), and now two whole official bosses the net never
  trained on (the Guardian about +0.026 over bursts on other content,
  Hexaghost nothing). So on enemies made of familiar parts the zero-shot
  net already plays at the level a burst can reach; the cost of new
  content is the mechanic, and `generated-enemies-bench` should spend its
  first batch on enemies with unseen mechanics, with familiar-parts
  enemies as the cheap control only.
- Goal 2. The Hexaghost bursts did not fail for want of anything to
  learn: on the same decks at the same entry HP the second turn of search
  wins +0.083 (0.024) more Hexaghost fights than one turn (the Guardian
  +0.054, Slime Boss +0.017). A one-turn leaf with outcome labels does
  not pick up what one more turn of search finds
  (`cause/teacher-equals-student`, now on new content too). And the deck
  is as large a lever as the fighter: at a fixed HP the product's decks
  differ by 0.2-0.3 in win rate on both unseen bosses. That lever is the
  card chooser, which the direction holds back until Act 1's cards exist.
- The lane worker's reading "the Guardian lifts like any burst" is half
  right: two of the four bursts on other content lifted it (+0.034,
  +0.032) and two did not (-0.006, -0.003), while all four boss bursts
  did (+0.030 to +0.055). The fail stands either way.

**Decided.**
1. `lane/sequential-bursts` opens in the exploration slot from its ready
   charter (backlog entry 3): do two bursts in sequence keep both gains?
   Goal 1's content workflow adds one pack after another
   (`decision/burst-adapted-column`). Rated **even**; about 1.5 cpu-h
   (cap 4); no code, so a lane session can queue it while the CPU is idle. On-close: wake on fail.
2. `burst-recipe` carries the next ready charter (a burst that rehearses
   the unchanged parent fights; about 7 cpu-h, cap 11): it opens when
   `sequential-bursts` closes on a go or a lead.
3. Goal 2 has no open lane and none is opened now. Its three candidates
   were each checked against this result: a burst from two-turn boss
   games (the lane's second reopen condition) would need about +0.18 one
   turn deep on Hexaghost to show as +0.02 clears, and outcome labels
   from the two-turn product already fit no better on trained content;
   three turns at the boss (`hexaghost-headroom`) does not pass the
   owner's detectable-effect rule on one book (77 Hexaghost fights at
   50-69 HP, detectable about 0.11, hoped-for about 0.045) and needs both
   books and a per-boss filter, about 30 thread-h; `boss-step-hp-price`
   stays a long shot aimed at the Guardian alone. The big-picture review
   takes goal 2's CPU share as its first question.
4. Shares in `jobs/lanes.json`: yardstick-cards 50, runtime-registry 25,
   sequential-bursts 15, main 10, filler 0.

**Alternatives passed over.**
- `hexaghost-headroom` in the slot now, on the control's 203 boss fights
  with no code: about 40 thread-h at 5.5 GB for two threads, a third of
  it on Slime Boss, for an effect under what the run could detect.
- `burst-recipe` first: it waits for `lane/yardstick-cards`' seed-2 read
  (job 0169, running), which says whether the gain it protects is real.
- A full retrain of the 10-29 recipe with all three bosses in its set:
  1600 games already level off at +0.02 to +0.03 on the mean, which is
  under +0.01 two turns deep.
- The lookahead nets of 2026-11-01 against their twins on the boss replay
  (do schedule inputs help on Hexaghost with no training there): about
  1.5 thread-h and no code, but three twin pairs detect about 0.05 where
  the columns gave +0.020 on trained content, and a pass would still be a
  one-turn gain on a layout the product does not use.
- Leaving the slot empty until the review: the CPU has been idle for most
  of the day and `sequential-bursts` costs 1.5 cpu-h.

**A mismatch, pointed out.** The backlog said `hexaghost-headroom` needs
"a boss kind in `depth_probe.py`"; the code has it (`--kind boss`, bosses
entered at 50-69 HP). What is missing is a per-boss filter.

## Comparisons play one turn deep; two-turn search is the product's augment (owner, 2026-11-05)

From an `/approach` discussion. Every comparison (a net, a leaf change, a
burst, a run-layer change, a goal-1 bench column) plays one turn deep,
unless the question is about search depth itself or needs it. The
product (the 10-29 net searched two turns deep) stays the best setting we
produce and the reported headline score, but it is not the ruler a change
is judged on.

Reasons, from the record: every change read at both depths kept its sign
two turns deep at about a third of its one-turn size
(`cause/leaf-gain-third`: effects encoding +0.059 -> +0.017, ensemble
+0.021 -> +0.008, SharpHide burst +0.080 -> +0.026 and +0.066 -> +0.013);
the one net pair read at both depths agreed (10-29 over burst8hp2);
the product net itself was chosen one turn deep (`measurement/rerank@headline`);
a two-turn game costs about 100x a one-turn game, so the same CPU buys
fewer games for a smaller effect. Two-turn reads in the two lanes closed
today cost about 42 cpu-h (boss-cost-two-turn 17.9, adapted-two-turn 24.0).

Correction of the record: "with the heuristic and the two-turn product"
in `#Goal-1 yardstick: paired modifiers, measured per modifier (owner,
2026-11-02)` and the 11-03 restatement were not the owner's: the owner
agreed to paired modifiers measured per modifier, not to a depth or to
the term "product". `decision/goal1-meaning` and
`decision/burst-adapted-column` are flagged for the navigator to re-set
to one-turn columns.

What it changes (the navigator acts): goal-1 columns and adapted columns
read one turn deep; `lane/yardstick-cards`' planned two-turn columns and
its step 0 (job 0169, running, left to finish) become one-turn reads;
goal-2 candidates screen and are judged one turn deep against
`yardstick/one-turn-controls`; a two-turn read is kept for depth questions
and for the product's reported score. Alternatives: keep two-turn reads
for goal 1 (the record's earlier rule; rejected for cost and the smaller
effect); one-turn everywhere including the reported score (rejected: the
product is the best we can produce).

## Lane sequential-bursts closed (2026-11-05)

Lane worker, 2026-11-05 21:45 (session 1b8f9222), on its `done:` step.

**Outcome: go, bursts compose one turn deep** (results doc "Sequential
bursts, one turn deep"; `measurement/sequential-bursts@one-turn`). Both
orders of two 399-game bursts keep at least two thirds of the SharpHide
burst's sharp2 gain (0.74 and 1.00 of +0.080), keep its Thorns 2
transfer, and lose nothing on the one-turn cell gauntlet or the boss
replay. One training seed per order. The order matters: a second burst
without the first's games gives back about a quarter of the first's
gain. CPU: about 1.2 cpu-h of the 4 cpu-h cap (two 90-second bursts at
4 threads, six reads at 3 threads, 3-5 minutes each), on the
navigator's estimate of 1.5.

**Reopen if:** a second training seed of either order (about 1.2
cpu-h, no code) loses the sharp2 gain under two thirds or costs cell
end-HP, or a pack chain of three or more bursts is needed (goal 1's
workflow past two packs). Then the question becomes whether each burst
must replay the earlier packs' games.

**The slot is not filled from `burst-recipe`'s ready charter** (on the
owner's behalf). Its measure is a two-turn read on the 272 fresh elite
starts, and its goal is a parent cost measured two turns deep
(`measurement/adapted-two@elites`). The owner's direction of 2026-11-05
("Search depth in experiments", commit a1db77e, after the charter was
written) has every comparison play one turn deep and gives goal 1's
yardstick no two-turn column. The charter also waits for
`lane/yardstick-cards`' seed-2 read, which isn't filed yet. Re-rating a
charter is the navigator's job, so its slot goes to a navigator wake
(`lane:sequential-bursts`, "no ready charter that fits the direction")
and the lane's 15 share moves to the open lanes (yardstick-cards 60,
runtime-registry 30). Alternatives passed over: opening `burst-recipe`
as written (it would spend its 7 cpu-h on a ruler the owner has just
set aside); rewriting its measure to one turn deep myself (lane workers
copy charters, they don't write them).

## Choosing a read by its question: own picks, matched, or crossed (owner, 2026-11-05)

Same `/approach` discussion. Guidance, not a rule: a whole-player
question plays each arm with its own card picks (unmatched); a
fighting-only question is a matched read on the control's picks (cheapest,
a slight lean toward the control); crossed arms only when fighting and
picking must be split. Written as how-to in `README.md#Act-1 gauntlet`
and `how/gauntlet-read`; `decision/matched-reads` no longer limits
`--match` to screens one turn deep. Alternatives: matched reads by default
for every comparison (rejected: under the sim chooser nearly every player
change also changes picks, and on the headline picking carried most of
the gap between nets, `cause/chooser-lead`); the variant's picks
(rejected: needs the expensive own-pick run first, so no saving). With
`value-chooser` (backlog) the own-pick read gets cheap.

## After the one-turn direction: yardstick-cards re-set, burst-recipe withdrawn, value-chooser ranked (on the owner's behalf, 2026-11-05)

Navigator, 2026-11-05 22:40, on the owner's wake and the
`lane:sequential-bursts` wake.
Builds on `decision/one-turn-comparisons` (owner, 2026-11-05).

**`lane/yardstick-cards` re-set to one-turn reads.** The rung's table is
the heuristic and the net one turn deep; the two-turn column and the
two-turn adapted column are gone. Step 0 (the adapted column's seed
check) becomes a one-turn read of the seed-2 SharpHide burst net that job
0168 trained: the mutate bench at 200 starts x 8 seeds, the cell gauntlet
and the boss replay, minutes each and no code. Job 0169's two-turn games
are filed as read (paid for; a depth read that decides nothing in this
lane). The cap falls from 52 to 20 cpu-h (5.4 used; the one-turn rung
costs a few cpu-h, the rest is the build's tests). Alternatives: close
the lane and reopen it under a new name (rejected: the goal and the
build are unchanged, only the ruler is cheaper); keep the cap (rejected:
a cap sized for two-turn reads no longer bounds anything).

**`burst-recipe` withdrawn (the trade-off rule).** Its goal was the 0.60
HP the SharpHide burst loses on unchanged elites two turns deep
(`measurement/adapted-two@elites`). One turn deep that cost does not
exist: the same burst is level on the parent rows (wins within +0.007,
`measurement/adaptation-transfer`), on the cell gauntlet (paired end-HP
-0.07, `measurement/adaptation-curve`) and on the boss replay (+0.001,
`measurement/burst-bosses@replay`), and both two-burst chains play
official content as well as or better than the parent
(`measurement/sequential-bursts@one-turn`). With no parent cost on the
ruler, rehearsing the parent fights can gain nothing there, so the probe
is not run. What would give rehearsal its value: a burst that costs the
cell gauntlet or the boss replay one turn deep (on the cards rung or
generated enemies), or a chain of three or more packs where a later
burst gives back an earlier one's gain (the second burst already gives
back about a quarter); then the rehearsed games are the earlier packs'
and the parent's. Alternative: re-write its measure one turn deep and
run it (rejected: its expected effect is zero against any detectable
size).

**`value-chooser` ranked first among the candidates not open** (the
owner asked for a rank), with a ready charter for the exploration slot.
Rating **even** that it is level with the sim chooser. What it moves: a
one-turn headline read is the dearest read left under the one-turn rule
(12-33 minutes per 500 sequences, against 2-5 minutes for every other
read), and a whole-player question needs own picks (`how/gauntlet-read`),
so each such read pays the sim chooser's fights; and it is the only
goal-2 route open before Act 1's cards (open question 7: at a fixed
entry HP the decks differ by 0.2-0.3 in boss win rate, and the chooser
picks the deck). Against: the saving is machine time, which the one-turn
rule has just made plentiful (see the next entry), and `--rewards vrun`,
the closest thing tried, lost 0.044 clears. It needs a few hours of
code, so it follows the code-free probe opened below. Alternatives:
open it now in place of that probe (rejected: a lane that starts
with code sits idle, the probe does not);
rank it under `generated-enemies-bench` and `act1-content` (rejected:
both wait for the registry's stage 3, this waits for nothing).

## Lanes burst-official and test-full-memory opened; what the one-turn rule does to the queue (on the owner's behalf, 2026-11-05)

Navigator, 2026-11-05 22:45. The exploration slot is empty
(`sequential-bursts` closed go) and no ready charter fitted the direction.

**What the one-turn rule does to the queue.** Every read a lane now makes
costs minutes (cell gauntlet 2-3, mutate bench 3, boss replay 5, a burst
1.5, a headline read 12-33 per 500 sequences; `measurement/cost@gauntlet`
and jobs 0184-0191). The two lanes that closed before the rule spent 42
cpu-h on two-turn reads; `sequential-bursts` spent 1.2. So a lane's CPU
work is gone within the hour and what a lane waits on is code and specs. The CPU has been idle 79
minutes with both project lanes waiting for a spec. Filed as
`cause/one-turn-frees-cpu`. It changes three things in the ranking: a
candidate's CPU-hours hardly rank it any more (its code does);
code-free probes on existing nets and files are what fills the machine; and the full test suite, the one long job
left, has to be able to start (below).

**Lane `burst-official` opened (exploration).** Lead: the two-burst net
SharpHide then stage B gained +2.36 (0.46) paired end-HP on the one-turn
cell gauntlet 0-499 (a protocol pass, about five times the training-seed
sd of 0.4 HP, `measurement/seed-sd@gauntlet`), the stage B burst alone
+1.14, and four of five burst nets gain +0.014 to +0.032 on the boss
replay; the stat burst loses on both (`measurement/sequential-bursts@one-turn`,
`measurement/burst-bosses@replay`, `measurement/stat-burst@one-turn`).
Two readings. (a) Practice against changed mechanics makes the one-turn
net better on official content, which is a goal-2 candidate under the
owner's ruler and says first-class custom content need not cost official
play. (b) A leak: the bursts train on the mutate bench's fights from
position 200 on, and those fights are the elites and bosses of sequences
0-499 with their cell decks, which the cell gauntlet 0-499 replays; then
every burst's retention read on 0-499 flatters it, and goal 1's adapted
columns need their retention read on the held-out book. The boss replay
was checked for this (the gain holds on sequences outside the training
fights); the cell gauntlet was not. Step 1 separates the two with no
training and no code: five existing burst nets and the control on cell
sequences 500-999, about 1 cpu-h. Rated **even** that a gain of +1.0 HP
holds on the held-out book; **a long shot** that it ends as a product
net: two turns deep the SharpHide burst loses 1.21 (0.30) HP per
unchanged elite fight on two burst seeds (`measurement/adapted-two@elites`
rev 3), `decision/no-goal2-training-arms` records twelve recipe arms that
moved the run level not at all (those trained on the same official
content; this content is new, which the owner's training rule allows),
and between nets the headline detects about 2.5 HP on own picks, so step
2 is the matched read (about 1 HP). Closest technique: fine-tuning on
perturbed environments as a regulariser (domain randomisation); in this
record `jitter-training` (stat shifts; shown wrong) and "a burst as a
product step" (rejected on its two-turn parent cost, a ruler the owner
has since set aside for comparisons). Shown wrong if no burst net gains
on 500-999. About 3 cpu-h, cap 4.5. A go wakes the navigator, who then
owes the depth question before any product change: the product plays two
turns deep, where bursts have cost HP. Alternatives passed over:
`value-chooser` now (needs a few hours of code; it is the ready charter that follows); `race-price` (a long shot
that needs code; second ready charter); a second seed of the burst
chains (the reopen condition of `sequential-bursts` has not fired).

**Lane `test-full-memory` opened (project, a fourth lane while
`burst-official` is within days of its end).** The full Python suite
peaks at 9.1-9.8 GB (jobs 0072, 0076) and asks 10 GB; with other work
running, too little is free, so job 0155 has waited over 6 hours
and the suite last passed 55 hours ago, while lanes keep landing code on
their own checks. Nobody owns it: the steward queues it and does not
write code. The lane takes the first item of `throughput-fixes`: run the
suite's files one process after another (or the heavy files alone) so
the peak is the largest file's, and ask for the measured peak. Rated
**likely**. About 10 cpu-h (one full run is 130 minutes at 4 threads),
cap 15. Alternatives: leave it to the next quiet hour (rejected: the
machine is rarely idle); lower the memory ask
without a change (rejected: the peak is measured, the runner would page
other work); wait for a slot (rejected: untested landings are a
health matter, and the lane is a few lines of `scripts/test_full.py`).

Shares (`jobs/lanes.json`): yardstick-cards 35, runtime-registry 30,
burst-official 15, test-full-memory 10, main 10, filler 0.

## Lane burst-official extended: the confirm book and the two-turn matched read (on the owner's behalf, 2026-11-05)

Navigator, 2026-11-05 23:26, on the `checkpoint:burst-official` wake.

**What steps 1-2 say** (`measurement/burst-official@held-out`). No leak:
the four burst nets read on both cell books gain within 0.4 HP of each
other on 0-499 and 500-999, so burst retention reads on 0-499 stand
(`decision/burst-adapted-column` rev 4). The SharpHide-then-stage-B net
is a better one-turn net as a net: +2.36 (0.46) and +2.27 (0.47) paired
end-HP on the two cell books, +2.47 (0.53) and +0.040 (0.016) clears on
the headline setting with matched decks, most of it at the bosses (boss
deaths 107 to 89). It is not shown that the recipe makes better nets:
the five burst nets on the held-out book read +2.27, +0.75, +0.49,
+0.11 and -1.56, a mean of +0.41 (0.63) with a spread of about 1.4 HP,
three to four times the spread of seed twins of the full recipe (0.4 HP,
`measurement/seed-sd@gauntlet`). So a 90-second burst moves official
play by about 1.5 HP either way by its training seed, and this net is
the best of five draws, confirmed on a book it was not picked on. For
goal 2 a confirmed better net counts whatever made it; for goal 1 the
statement "practice on custom content helps official play" is not
supported, and a pack's burst needs its official-content check per seed.

**The extension (once; a second needs a new lane).** Step 3 (own picks
on the headline, job 0199) is running. If its paired end-HP is above
zero, the lane goes on without a navigator run in between, with two
reads that are independent of each other:
- step 4, the confirm book: the net with its own picks on headline
  sequences 500-999, one turn deep, against
  `results/gauntlet/net1029-hpb0.01-starter-simboss-500.json`, read alone
  and pooled with step 3 over the 1000 sequences (between nets one book
  detects about 2.5 HP, `cause/headline-pairing-weak`; two books about
  1.8);
- step 5, the depth question a product change owes: the net as the
  product would play it (`@hpe0.01 --two-turn --line-seed --step-line`)
  on headline sequences 0-499 with the product's own deck choices
  (`--match` the headline control), paired against that control. This
  read needs depth (`decision/one-turn-comparisons`): a one-turn gain
  reaches two turns at about a third (`cause/leaf-gain-third`), and two
  bursts lost 1.21 (0.30) HP per unchanged elite fight two turns deep
  where they were level one turn deep. Matched decks give an se of about
  0.6 HP at 500 sequences (`measurement/deck-matched@two-turn`), so a
  loss of 1.2 HP shows.
The lane then closes and wakes the navigator, who decides the product
net: by the owner's ruler a change is judged one turn deep, and the
two-turn read only has to show the product's reported score does not
fall. Cap 4.5 to 12 cpu-h (1.5 used; steps 3-5 about 6.5).

Alternatives passed over: wait for step 3 and decide then (a navigator
run to say the same thing; the machine idles meanwhile); a new lane for
the product question (a fifth lane, and the same worker would read the
same net); promote on the one-turn reads alone (rejected: the product
plays two turns deep and bursts have cost HP there; promotion is cheap
to undo, a lower reported score is not what the product is for); a
second training seed of the chain first (rejected for goal 2: the net is
what plays, and it is confirmed on a held-out book; it matters only for
the recipe claim, which this entry does not make).

**Checked and not proposed: a burst lottery** (train many burst seeds,
keep the best on 0-499, confirm on 500-999). With a spread of about 1.4
HP, the best of 20 further draws is expected about 0.5 HP above the net
in hand, with about one chance in four of +1 HP, against a detectable 1
HP on the cell books; and the owner's training rule gives CPU to
training with something new to learn, which picking a lucky seed is
not. It comes back only if step 5 shows one-turn gains of this kind
reach the product, and then as the owner's call on the rule.

## The owner's filler proposal placed: read the held-out half of existing nets, not full-size ids twins; unseen cards cost the net half its edge (on the owner's behalf, 2026-11-05)

Navigator, 2026-11-05 23:55, on the owner's wake (a proposal, not an
override: backlog `ids-effects-full-recipe` as an overnight filler).

**What existing files already say (no CPU).** The cell gauntlet marks
each sequence train or held-out by its deck's role cards; the net never
trained on the held-out ones. Read by half, paired against the
heuristic's files on the same sequences (`heuristic-bcbb0e.json`,
`heuristic-b500.json`), one turn deep, end-HP and clears with se:

| net | train half | held-out half |
|---|---|---|
| 10-29 net, 0-499 | +3.27 (0.83), +0.080 (0.025) | +1.82 (1.05), -0.004 (0.024) |
| 10-29 net, 500-999 | +4.11 (0.87), +0.100 (0.026) | +2.36 (1.03), +0.008 (0.022) |
| its seed twin s101, 0-499 | +2.71 (0.79), +0.072 (0.021) | +1.23 (1.06), +0.004 (0.026) |
| its seed twin s201, 0-499 | +2.96 (0.80), +0.056 (0.022) | +1.41 (1.11), -0.008 (0.026) |
| effects 5k, s1 / s101 / s201 | +0.00, +1.17, +0.64 HP | -2.10, -0.12, -2.26 HP |
| ids 5k, s1 / s101 / s201 | +0.89, -0.48, -1.11 HP | -6.56, -6.20, -4.01 HP |

Three things follow.
1. On decks holding cards it never trained on, the net keeps about half
   of its HP edge over the heuristic and none of its clears edge, on
   three training seeds and both books (pooled over the two books:
   clears +0.090 (0.018) on train, +0.002 (0.016) on held-out). On the
   headline setting with own picks the net's lead over the heuristic is
   +0.200 (0.038) clears on train sequences and +0.092 (0.036) on
   held-out ones. The heuristic knows every card by its rules, so here
   "beyond the heuristic" is against a player that is not new to the
   cards. This is a zero-shot cost of unseen cards, on official cards,
   and it is not small. `docs/direction.md` says "new mechanics, not new
   cards, are what hurts"; these files disagree for the fighter one turn
   deep (the line is the owner's; the mismatch goes to the owner in
   `jobs/roles.log`). Filed as `cause/unseen-cards-half-edge`.
2. The whole ids-against-effects gap sits on the held-out half (ids
   minus effects at 5k: -4.1 HP there, -0.8 on train, three seeds). An
   id net sees an unseen card as `unknown`; that gap is how the encoding
   is built, not something data size can close.
3. The cards rung of goal 1's yardstick has a zero-shot number today
   without card patches: the train edge minus the held-out edge, with
   ids as the floor.

**The proposal, placed.**
- *Full-size ids twins: not run.* Their cost is smaller than the entry
  assumed: the effects nets at 20k games exist on five seeds
  (`runs/2026-10-31-data20k-s*-r1`, 21-46 minutes each at 6 threads), so
  only five ids partners would train, about 15 cpu-h. But by point 2
  neither outcome can change the encoding or any plan: on held-out
  cards ids cannot catch up at any size, and on train cards the two are
  level at 5k. Against `decision/training-stops` (owner) they are
  training with nothing new to learn; the reading below admits controls
  of a yardstick number, and a full-size replication of a gap that is
  structural is not one. Reopen if the five-seed read below shows ids
  ahead on the train half (then the effects encoding costs official play
  and its size at the product's data matters).
- *The cheaper first part: accepted and widened, as lane work.* Reads
  cost minutes and need no training: the effects nets that exist at 5k
  (five seeds, two never read), 20k (five) and 40k (three) and the three
  ids nets, on both cell books, by half, against the heuristic. That
  gives the zero-shot card cost against training size, the number the
  proposal was after, for about 5 cpu-h. The two missing ids partners
  (`ids5k-s301`, `-s401`: 11-24 minutes each at 6 threads) train as the
  floor's fourth and fifth seed. It goes into `lane/yardstick-cards`
  as step 1 (the lane waits for its spec and had no CPU work).
- *The training rule.* `decision/training-stops` stops arms that hope
  for a gain. A twin trained only as the control of a yardstick number
  is not such an arm; the rule does not name the case, so on the owner's
  behalf: it is allowed when a decisions entry names the number it
  controls, it costs at most about 3 cpu-h, and it is never read as a
  product candidate (`decision/measurement-twins`). Alternatives: no
  training at all outside the rule's three cases (rejected: the floor
  would stay at three seeds for the lack of 40 minutes); any twin on
  idle CPU (rejected: every result needs a session to read it,
  `cause/one-turn-frees-cpu`).

**What it adds to the cards lane.** Unseen official cards are new
content the net can learn (the owner's training rule allows it), so the
lane gains the rung's adapted column on them before the card patches: a
burst from the product net on decks holding held-out cards, at about
100, 400 and 1600 games on three seeds, read on both cell books by half
(held-out half the gain, train half the retention). It needs a content
kind in `finetune.py` (the Silent kinds are the pattern), smaller than
the card-patch spec, so it goes first. Its end point
is also a goal-2 candidate: a product net that has trained on every
official card; if the held-out half gains what the train half has, that
is about +0.04 clears on the cells. Rated **even**: for, the edge is
there on trained cards on three seeds and two books, and nothing tried
so far taught the net these cards; against, a fine-tuned net is a seed
draw of about 1.5 HP (`measurement/burst-official@held-out`), so three
seeds, and the held-out half stops being that net's generalisation
read. Closest technique: retraining on train plus validation data before
shipping a model. Alternatives: a separate goal-2 lane (rejected: the
same bursts are goal 1's games-to-adapt curve on cards); wait for the
card patches (rejected: the held-out split is already built and
measured). The owner's paired modifiers stay the lane's last step
(`decision/goal1-yardstick`). Cap 20 to 35 cpu-h.

## Lane burst-official closed (2026-11-06)

Lane worker, 2026-11-06 00:35 (on the owner's behalf). Outcome: **fail**
by the extended charter (`lane/burst-official` rev 2): the pooled
own-pick read of steps 3-4 gains +1.09 (0.69) paired end-HP over 1000
headline sequences, z 1.59, under 2 se (`measurement/burst-official@own-picks`).
CPU: 4.6 cpu-h of the 12 cap (jobs 0192-0200).

What was learned:
- No leak: burst retention reads on cell sequences 0-499 stand; the four
  nets read on both books gain within 0.4 HP of each other
  (`measurement/burst-official@held-out`).
- The SharpHide-then-stage-B net fights better one turn deep, at 4-5 se on
  three reads (cells 0-499 +2.36, cells 500-999 +2.27, headline with
  matched decks +2.47 (0.53), clears +0.040), most of it at the bosses.
- With its own picks the gain is about half: +2.00 (0.98) on 0-499, +0.18
  (0.96) on 500-999. The gauntlet files keep no deck lists, so whether its
  picks are worse than the control's, or the matched read sat on the high
  side, is not separated.
- A single 399-game burst moves official play by a training-seed draw of
  about 1.5 HP either way (five nets: +2.27 to -1.56), so this net was the
  best of five draws.

Step 5 (the net two turns deep with the product's decks, job 0201) was
queued with step 4 and cancelled unrun: it could not change the outcome
once step 4 failed the pooled bar, and it held the queue's reservation for a 5.5 GB slot that was
not coming. Alternatives: leave it waiting (blocks the queue for hours);
re-queue at 2 threads (still needs 4.5 GB free). It is the cheap first
read if this net comes back.

**Reopen if:** a mode exists that takes the card picks from one net and
the fights from another (then this net's matched gain, +2.47 (0.53), is
the one that counts, and step 5 as queued, two turns deep with matched
decks against `yardstick/headline-control`, is the first read); or the
gauntlet files record deck lists, so an own-pick read can split the
picks' share from the fights' and show the picks were the cost. Not on a
re-roll of burst seeds (the burst lottery, checked and not proposed in
"Lane burst-official extended").

The charter's on-close is `wake always`: the navigator is woken; no ready
charter has a CPU job without code (`value-chooser` needs a chooser kind
in `gauntlet.py`, `heuristic-games-burst` a `player` key in
`finetune.py`), so none is queued. Shares: burst-official's 15 goes to
yardstick-cards 42, runtime-registry 36, test-full-memory 12.

## After burst-official: no product change; lane crossed-player opened (on the owner's behalf, 2026-11-06)

Navigator, 2026-11-06 00:30, on the `lane:burst-official` wake.

**The product net stays.** `burst-official` failed its bar: the
SharpHide-then-stage-B net with its own picks gains +1.09 (0.69) paired
end-HP over 1000 headline sequences, under 2 se
(`measurement/burst-official@own-picks`). The bar was set before the
read and stands; two earlier passes in this record were training luck.

**What the close leaves open.** The same net fights better at 4-5 se on
three reads (cells +2.36 and +2.27, headline with the control's decks
+2.47 (0.53), clears +0.040; `measurement/burst-official@held-out`).
Its own-pick reads (+2.00 (0.98), +0.18 (0.96)) are too wide to say
whether its picks are worse or the reads sat low: pooled, own picks
differ from the matched read by 1.4 (0.9). The lane's first reopen
condition asks for a mode that takes the picks from one net and the
fights from another. It exists: `gauntlet.py --chooser <player>` plays
the sim chooser's fights with another player (the files
`heuristic-ch-net1029-*` and `net1029-*-ch-heuristic-*` were made with
it, `measurement/chooser-vs-fighter@headline`). So the condition holds
today, without code.

**Lane `crossed-player` opened (exploration).** A player whose card
picks come from the 10-29 net and whose fights come from the burst net,
on both headline books one turn deep, against the one-turn controls.
Decks then differ from the control's only where the fighter arrives with
other HP, so the pairing is close to the matched read's (se about 0.5
per book) instead of the own-pick read's (about 1.0). Read beside the
own-pick files, the same run also says what this net's picks cost
(crossed minus own picks, same fighter), which bears on any change of
chooser (`value-chooser`). On a go, the depth read a product change owes
follows: the fighter two turns deep on the product's decks, as job 0201
was queued, at 2 threads when 4.5 GB is free. Rated **likely** that the
0-499 read holds near the matched read, **even** that the pool of both
books reaches +1.5 HP at 2 se (the net's own-pick read on 500-999 was
+0.18), **even** that the two-turn read is not below the control
(bursts have lost 1.21 (0.30) HP per unchanged elite fight there,
`measurement/adapted-two@elites`). About 7.5 cpu-h, cap 11. Closest
technique: separate policy and value models, each picked on its own
validation read; here the picker is kept and only the fighter changes.
The net was picked as the best of five on cells 0-499; the headline's
confirm book with the control's picks is a book and a setting it was
not picked on. Shown wrong if the pooled crossed read is under +1.0 HP.
The navigator decides the product at the close; a crossed product is
one more flag in `configs/product.json`, cheap to undo.

Alternatives passed over: `value-chooser` and `heuristic-games-burst`
(both ready, both start with code, so the slot would sit idle); leave the slot empty; re-read the own-pick
arms on more sequences (rejected: own picks detect about 1.8 HP on 1000
sequences between nets, `cause/headline-pairing-weak`; the crossed read
asks the sharper question for the same CPU).

Shares (`jobs/lanes.json`): yardstick-cards 35, runtime-registry 30,
crossed-player 15, test-full-memory 10, main 10, filler 0.

## Lane crossed-player closed (2026-11-06)

Lane worker, 2026-11-06 08:25 (on the owner's behalf). Outcome: **go** by
the charter's stop rule (`lane/crossed-player` rev 1). Step 1: the burst
net (SharpHide-then-stage-B) fighting with the 10-29 net's card picks
gains +1.60 (0.48) paired end-HP over 1000 headline sequences one turn
deep, clears not below the control on either book
(`measurement/crossed-player@one-turn`). Step 2: the same net as the
product plays it (two turns deep, line-seed, step-line) on the product's
decks gains +1.08 (0.47), clears -0.006 (0.014), above the -1.0 bar
(`measurement/crossed-player@two-turn`). CPU: 12.6 cpu-h of the 11 cap
(jobs 0202-0204); the cap was passed by job 0204 (two turns deep at 2
threads, 236 minutes against an estimate of 150), which was 80% done when
the cap event fired and was read rather than cancelled.

What was learned:
- Depth takes about half of the fighting gain: +2.47 matched one turn
  deep, +1.08 matched two turns deep. One turn deep the gain sat at the
  bosses; two turns deep it sits at the elites (-1.39 HP lost per run) and
  the boss share is gone.
- The elite saves do not turn into clears: runs carried through the
  second elite at low HP die in the next hallway (6 to 15 deaths), so the
  clear rate stays level (0.834 to 0.828).
- One training seed, matched decks: a lead for the product, not a
  promotion. As the charter says, the navigator decides the product (no
  `product.py set` here).

**Reopen if:** a second training seed of the SharpHide-then-stage-B burst
reads above +1.0 HP one turn deep on the headline (so the gain isn't one
lucky draw of five, `measurement/burst-official@held-out`), or the product
gains a way to turn elite HP into clears (rest or removal choices after
the second elite), which would let this net's elite gain reach the clear
rate; the first read then is this lane's step 2 on sequences 500-999.

## After crossed-player: the product stays; bursts read by content; what the nets see of Hexaghost; lane pattern-rows-burst opened (on the owner's behalf, 2026-11-06)

Navigator, 2026-11-06 08:10, on the `lane:crossed-player` wake.

**The product net stays.** The crossed player two turns deep gains +1.08
(0.47) paired end-HP on the product's decks and no clears (0.834 to
0.828, -0.006 (0.014); `measurement/crossed-player@two-turn`). The
headline's unit is clears (`decision/headline-unit`), and the protocol's
test stayed open at its 500 cap (`yardstick/protocol`), on one book, with
matched decks. So by the rules already in force this is a lead. The
confirm read on sequences 500-999 (about 8 cpu-h two turns deep) is not
queued: a pass would swap the fighter for about +1 HP and no clears and
would owe a new headline control on both books; a fail changes nothing;
the expected clears difference is about zero against a detectable 0.04
(the trade-off rule). Alternatives: promote the crossed player now
(rejected: no gain in the unit, an open test, and a product made of two
nets); run the confirm read because the CPU is idle (rejected: neither
outcome moves the reported score). What would change this: a fighter
change that lowers boss deaths two turns deep, or run choices that turn
HP after the second elite into clears (the lane's second reopen
condition). The lane's first reopen condition (a second training seed
above +1.0 one turn deep) would show a recipe one turn deep; it would
not change the product, because depth leaves about +1 HP.

**What the result says together with the record.**
- Depth takes the boss share of a fighting gain. One turn deep this net's
  gain sat at the bosses (matched +2.47 HP, clears +0.040, boss deaths
  107 to 89); two turns deep the boss share is gone (boss HP lost -0.15
  (0.46), boss deaths 62 to 61) and +1.08 HP stays, at the elites. That
  is 0.44x in HP and nothing in clears, the fifth case of
  `cause/leaf-gain-third`, and the first read on official content. It
  agrees with `cause/boss-deaths`: clears follow boss wins, and about
  +1.3 HP at the boss door moves too few runs across the Guardian's step
  to see.
- The burst lottery stays closed. Its reopen condition was that such
  gains reach the product; they reach it as about +1 HP and no clears, so
  the best of 20 further draws would be worth about 0.2 HP two turns
  deep.
- Open question 9 loses its candidate cause. Two SharpHide burst seeds
  lost 0.60 and 1.67 HP per unchanged elite fight two turns deep
  (`measurement/adapted-two@elites`); this net, a second burst on top of
  seed 1, gains 1.39 HP per run at the same depth on the headline's
  elites. So the elite cost is not a property of fine-tuning (a shifted
  value scale against the fixed HP price would cost every burst net); it
  varies by net. `cause/leaf-gain-third`'s rule stands: a net headed for
  the product owes its own two-turn retention read.
- The spread of burst nets on official play is partly content, not all
  training seed (a re-read of existing files, no CPU). One turn deep on
  the cell gauntlet against the 10-29 net, every burst whose games are
  official bosses or pattern-modified official fights reads positive:
  Guardian and Hexaghost games +1.59, +1.18, +0.78, +0.42 (400 and 1600
  games, seeds 1 and 2; `measurement/unseen-boss-burst@replay`), stage B
  +1.14 and +0.75 (the two books), stage B then SharpHide +0.38 and
  +0.49, SharpHide then stage B +2.36 and +2.27. Bursts on a power that
  punishes attacking, or on plain stat shifts, read level or below:
  SharpHide 399 games +0.11 (seed 1) and -1.56 (seed 2) on 500-999, stat
  shifts -0.85. Seed twins at the same content differ by 0.4 HP for the
  boss bursts (two pairs, the size of the full recipe's twins,
  `measurement/seed-sd@gauntlet`) and by 1.7 HP for the SharpHide burst
  (one pair). So "a training-seed draw of about 1.5 HP either way" in
  `decision/burst-adapted-column` mixed content with seed: it is re-set.
  One or two seeds per content, so a lead; it is not chased, because the
  gain it points at (official play one turn deep from a few hundred games
  on official bosses) is the one depth has just been shown to take.

**What the nets see of Hexaghost (open question 3's code read).**
`py/src/features.rs`, `scripts/finetune.py` and the saved nets' layouts:
- The product net reads 27 effect scalars and 8 triggers, its vocabulary
  of 10-29. Today's encoder has 48 and 19. Burn's cost (`damage_plain_self`,
  the damage for holding it at turn end) is one of the 21 it drops: to the
  product net a Burn is an unplayable card with no effect.
- A monster's inputs are its HP, block, powers and the intent on show.
  Divider's damage is in the intent (fixed when the move is chosen). The
  place in Hexaghost's seven-move cycle is not: Sear shows three times in
  a cycle, and only the combat turn count tells which one precedes
  Inferno. The moves after the shown intent exist as an opt-in row kind
  (`pattern`: one row per possible next move with its probability and
  effects) and as the lookahead columns; both are off in every net read
  so far. Lookahead read as no gain on 11-01, on nets that never trained
  on Hexaghost or the Guardian.
- The boss bursts of `unseen-boss-burst` (`source` configs) were widened
  to today's vocabulary, so they had Burn's cost as a new column and
  still learned nothing on Hexaghost; they had no pattern rows. Bursts on
  mutated monsters and on generated packs keep the parent's vocabulary
  (`finetune.py` `kept_vocab`). On the monsters rung that hid little:
  SharpHide and Ritual use known triggers and effects; Thorns
  (`OwnerAttacked`) and WeakOnHit (`OwnerAttackHit`) land in the one
  `unknown` trigger slot with known effects. It matters from here on: a
  pack mechanic built from the newer atoms (static, countdown,
  replacement and pattern rows, picks, expression amounts) is dropped
  from the inputs of a burst that keeps the parent's vocabulary, so such
  a bench would measure blindness, not adaptation. Filed as
  `how/burst-inputs`; `generated-enemies-bench` and the cards rung's
  generated end carry it as a precondition (widen as the `source` path
  does, a few lines in `finetune.py`).

**Lane `pattern-rows-burst` opened (exploration).** The old candidate
`rows-on-burst` was held because "which burst content uses the new rows
is unknown". It is known now: Hexaghost. It is half of the product's
boss deaths (70 of 140), is lost in the fight, gains +0.083 wins from
the second turn of search on the same decks
(`measurement/depth-by-boss@replay`) and nothing from 1600 games of its
own (`measurement/unseen-boss-burst@replay`), whose lane named "inputs
for the boss state" as its reopen condition. Those inputs exist without
code: `"row_kinds": ["pattern"]` in a fine-tune config. The probe: the
four boss bursts again (400 and 1600 games, seeds 1 and 2, the same
games) with pattern rows on, each read on the headline boss replay and
the cell gauntlet one turn deep against its plain twin (the four plain
nets exist; the new arms train on inputs the net cannot see today, which
the owner's training rule allows). What each outcome gives: a go is the
first learned change on Hexaghost, allows a training job under the
owner's rule (inputs the net cannot see today), earns a depth read (a
pattern row at a two-turn leaf shows a move the second turn does not
reach, the exit `cause/leaf-gain-third` names), and gives pack monsters
their input arm for goal 1 (a pack's pattern rows are the same rows); a
fail says a burst of this size does not learn Hexaghost from its
schedule, and the question goes back to decks and depth
(`hexaghost-headroom`). Rated **a long shot**: for, the second turn's
gain shows that seeing further pays at this boss, and the schedule is
exact; against, the lookahead columns gave nothing on the full recipe,
a few hundred games may not train a row kind the net never read, and
what the second turn adds is play with the next hand, which a row does
not give. About 3.5 cpu-h, cap 5, end 2026-11-12. Closest technique:
feeding an agent the opponent's scripted next actions (privileged
schedule inputs); here they are public information of the game (a
player can know Hexaghost's cycle), written from the engine's pattern
table. On-close: wake on go.

Alternatives passed over: `value-chooser` (ranked first among the
candidates not open, the owner's idea; it starts with a few hours of
code, so it would sit idle; it
keeps its ready charter and opens when this lane closes without a go);
`heuristic-games-burst` (code too); seed twins of the
SharpHide-then-stage-B burst (answers a one-turn recipe question depth
has made moot for the product); the two-turn confirm read (above);
`hexaghost-headroom` (about 40 thread-h and a filter in code; it waits
for this probe, which asks the cheaper half of the same question).
Four lanes are open while `test-full-memory` is within days of its end.

Shares (`jobs/lanes.json`): yardstick-cards 36, runtime-registry 30,
pattern-rows-burst 14, test-full-memory 10, main 10, filler 0.

## Lane pattern-rows-burst closed (2026-11-06)

Lane worker, 2026-11-06 09:50 (on the owner's behalf). Outcome: **fail**
by the charter's stop rule (`lane/pattern-rows-burst` rev 1): pooled over
the four twin pairs the pattern-row bursts gain +0.004 (0.002) Hexaghost
wins against their plain twins, under the +0.015 fail bar (per pair
-0.002, +0.003, +0.008, +0.008); Guardian +0.000 (0.002), Slime Boss
+0.000 (0.001); cells -0.42 (0.19) HP against the twins
(`measurement/pattern-rows-burst@replay`). Every fine-tune trained on the
rows, so the fail is the play, not a refusal. CPU: 2.37 cpu-h of the 5 cap
(jobs 0244-0255), against the opening estimate of about 3.5.

What was learned:
- A pattern row shows one move past the intent on show; for Hexaghost's
  fixed cycle that is one certain move, so the net sees Inferno one turn
  earlier and nothing beyond. That is not the play the second turn of
  search finds (+0.083 on the same decks).
- The 1600-game pairs both read +0.008, the 400-game pairs +0.000: a
  small signal that may grow with games, at about a tenth of depth's gain.
- The input path works: bursts widened to today's vocabulary train on
  pattern rows without error (useful for pack monsters in goal 1).

**Reopen if:** the inputs show more of the schedule than the next move
(pattern rows that unroll two or more moves, or the place in the cycle as
its own column), or the labels come from a deeper teacher (two-turn
games on Hexaghost, `cause/teacher-equals-student`'s exit); either read
the same way against these four plain twins, with a go only if Hexaghost
gains +0.03 pooled.

On-close: the charter says `wake on go or lead`; this is a fail, so no
navigator wake. The exploration slot goes to the backlog's next ready
charter, `value-chooser` (the ranking's note: "on a fail the exploration
slot goes to `value-chooser` (entry 3, ready charter)").

## Lane value-chooser opened (2026-11-06)

Lane worker, 2026-11-06 09:50 (on the owner's behalf). Opened in the
exploration slot `pattern-rows-burst` left, by the navigator's ranking in
`docs/backlog.md` (candidate 3, the first with a ready charter after the
open lanes; the ranking names it for this slot on a fail) and its ready
charter, copied as written into `lane/value-chooser`. Share in
`jobs/lanes.json`: pattern-rows-burst's 14. It starts with code (a chooser
kind in `gauntlet.py`), so its
spec waits, after `runtime-registry`'s stage 3
spec (the backlog's order). Alternatives: waking the
navigator instead (the charter's on-close does not ask for it, and a
ready charter exists); `heuristic-games-burst` (ranked after it, also
code).

## After yardstick-cards step 1: the unseen-card cost is one card, Demon Form, and on generated cards the powers that pay at turn start; step 2 re-aimed, step 3's first table predicted, cap extended (on the owner's behalf, 2026-11-06)

Navigator run on the wake `checkpoint:yardstick-cards@2` (step 1 passed,
`measurement/cards-by-half@cells`). The wake's two questions: the zero-shot
card cost does not shrink with training size (gap about 2 HP at 5k, 20k and
40k games), and ids nets are not ahead on the train half (five twins: ids
minus effects -1.24 HP there), so `ids-effects-full-recipe` stays closed.

**What the step-1 files say beyond the by-half table** (read inline from
the same result files, no jobs; step 1b rebuilds it as a script):

1. *The gap is one card.* The held-out half holds ten unseen cards; 174 of
   its 500 sequences (both books) have a deck with Demon Form (3 energy,
   2 Strength at each turn start). Paired edge over the heuristic, end-HP,
   se over sequences, on train decks / held-out decks without Demon Form /
   held-out decks with it: effects 5k +0.56 (0.50) / +1.74 (0.67) / -7.23
   (1.19); 20k +2.74 / +3.64 (0.69) / -6.41 (1.24); 40k +3.74 / +4.30 (0.72)
   / -3.08 (1.24); product recipe (three seeds) +3.44 (0.55) / +5.28 (0.74)
   / -4.26 (1.32), clears +0.08 / +0.08 / -0.12 (0.03). Without the Demon
   Form decks the held-out edge is above the train edge at every size
   (train minus held-out, se over seeds: -1.18 (0.22), -0.89 (0.48), -0.56
   (0.48), product -1.84 (0.08)). Both books agree (product, Demon Form
   decks: -5.16 (1.89) on 0-499, -3.25 (1.84) on 500-999).
2. *By card.* End-HP regressed on the copies of each of the 31 non-starter
   cards (upgrades and the book as covariates, robust se, 1000 sequences):
   a copy of Demon Form is worth +2.4 (1.4) HP to the heuristic and -5.2
   (1.4) to the one-turn product nets, a difference of -7.5 (1.2); the next
   card is Dropkick at -1.7 (0.7), every other card is within 2.4 HP and
   most favour the net. The other nine unseen cards: -0.9 to +3.5, none
   below zero at 2 se.
3. *Ids nets.* Without Demon Form decks the ids nets show no gap either
   (+0.61 (0.60)); their cost sits on the two unseen powers: Demon Form
   decks -12.40 (1.28), Metallicize decks -4.35 (1.38) against +0.17 (0.81)
   on decks with neither. The effects inputs carry Metallicize and part of
   Demon Form. An unseen attack or skill costs nothing even by id: the
   search plays the card in the engine and the net reads the state after it.
4. *Two turns deep.* Existing two-turn cell files (sequences 0-249 and
   500-749): the 10-29 net two turns deep minus one turn deep is +2.54
   (0.74) HP on train decks, +2.20 (1.01) on held-out decks without Demon
   Form and +8.38 (1.83) HP, +0.22 (0.04) clears on the 96 with it. Against
   the heuristic the two-turn net keeps +5.39 (1.50) on Demon Form decks
   against +8.91 (1.20) on the other held-out decks (a leftover of 3.5
   (1.9)); the burst8hp2 net over 750 sequences shows none (+5.16 (1.17)
   against +4.18 (0.85)). So the second turn of search repairs two thirds
   to all of it.
5. *A second set of content.* On the generated-power bench (elite and boss
   fights, decks with three copies of a power; `results/gen_powers/depth/`,
   10-29 net against the heuristic, one turn deep): original Demon Form
   decks -0.140 (0.024) wins; generated powers by trigger: owner's turn
   start -0.292 (0.044) on 144 fights (two turns deep the net recovers to
   0.535 against the heuristic's 0.618), turn end -0.061 (0.034), card
   played +0.005 (0.030), HP lost -0.02 to +0.13. The cost follows the
   trigger: a power whose first payoff comes at the next turn start.
6. *On the headline.* The heuristic's chooser takes Demon Form 0.68 of the
   times it is offered (its most-taken card); the net's chooser 0.19-0.25,
   its least-taken unseen card. Where the one-turn net did take it, it
   clears 0.405 and 0.480 (42 and 50 held-out sequences on the two books)
   against 0.70-0.84 elsewhere; the product 0.821 and 0.714 (39 and 42)
   against 0.86-0.89. Take rates follow what a copy is worth to the
   chooser's own fighter (correlation 0.69 over the 31 cards), so the
   chooser is right to avoid a card its trial fighter misplays.

**Why.** The heuristic prices a recurring power by rule (`hook_rates` in
`engine/src/heuristic.rs`); the net has to have learned the power's worth,
because one turn deep the payoff never fires inside the search. Content
whose effect lands inside the turn is free with search in the loop. This is
the same shape as the monsters rung (`cause/novelty-is-horizon`): what
costs is a payoff or a threat past the horizon, on either side of the
table. The owner's direction says it in its own words: new mechanics, not
new cards, are what hurts.

**Checked and not built on.** The by-card regression is observational
(decks are not randomised); it is trusted here because the same decks are
easy for the heuristic (clears 0.816) and for the two-turn net (0.865), the
two books agree, the ids nets show it larger, and the generated bench shows
it on other cards. The se over seeds in `measurement/cards-by-half@cells`
treats the sequences as fixed: over sequences the by-half gap is about 2.0
(0.8), and its agreement across sizes is one draw of decks.

**Decisions.**
- `cause/unseen-cards-half-edge` re-set to the reading above.
- `lane/yardstick-cards` re-set. Step 1b (analysis script and a code read,
  no jobs): the three-strata table, the by-card table and the two-turn
  strata in `cards_by_half.py`, filed as `measurement/cards-by-card@cells`;
  and what the net's inputs show of a turn-start power and where the
  one-turn leaf sits relative to turn-start triggers. Step 2: the bursts'
  adapted column is the Demon Form decks (headroom about 9.5 HP and 0.20
  clears there, nothing elsewhere); two more arms at 400 games, games
  played by the heuristic and by the two-turn product, each measured ahead
  of the net on these decks (the net's own games may never show the card
  paying; this is `heuristic-games-burst`'s mechanism with a teacher lead
  of 9 HP in place of 2); the best arm read on the generated bench's
  turn-start powers (does one learned turn-start power cut the cost of the
  next) and once on the one-turn headline with its own picks. Step 3 (the
  owner's yardstick, `decision/goal1-yardstick`): predicted before it runs,
  under the trade-off rule: a boon + bane pair whose parts both land inside
  the turn (cost, damage, block on Strike, Defend, Bash) costs the net
  nothing; so the first table keeps one such pair as its plain control and
  spends the other modifiers on pairs with a part that pays over later
  turns, on power parents.
- Cap 35 to 45 cpu-h (the lane's one extension; end date unchanged): 13.4
  used; step 2 adds two-turn teacher games (about 3 cpu-h), fifteen bursts
  with their reads, a generated-bench read and a headline read; step 3's
  builds bring their tests.
- A further two-turn cell read (sequences 250-499, about 8 cpu-h) is not
  queued: two nets over 1250 sequences already put the two-turn leftover
  between nothing and a third, and no decision turns on which.
- `lane/value-chooser`: its numbers are also reported without the
  sequences where either chooser took Demon Form, with both take rates.
  The one-turn control loses about 0.3 clears where it holds the card (92
  of 1000 sequences), so a chooser that only takes it less often would
  read up to +0.03 clears, more than the charter's 0.02 band.
- `heuristic-games-burst`: its first test is step 2's heuristic arm; its
  own charter is held until that reads.
- `novelty-gated-leaf` back as a candidate: its reopen condition (the
  cards rung shows a cost beyond the heuristic) holds.
- `full-inputs-retrain` retired: its probe (`pattern-rows-burst`) failed
  with validation loss inside the twins' noise.

Alternatives passed over: closing the lane's step 2 as answered (two-turn
search repairs the card, so the product has little to gain): rejected,
because games-to-learn a recurring power is goal 1's number for every
power Act 1's missing cards bring, and the bench for it exists today;
banning Demon Form from the product's offers (at most +0.01 clears);
two-turn trial fights in the chooser for such cards (same bound,
`decision/depth-family-closed`); a lane for the leaf fallback now (no free
slot; a deck-level switch to the heuristic is already known from the files
to bring Demon Form decks level, about +1.5 HP on the held-out half).

## Cards rung: nets that learned other turn-start powers already play Demon Form better; step 1c added (on the owner's behalf, 2026-11-06)

Same navigator run, after the entry above. One more read of existing
files: the three nets fine-tuned on 2026-11-01 on games with eight
generated power cards (`results/gen_powers/burst8.json`; two of the eight,
gc1_082 and gc1_095, give Strength at the owner's turn start) never saw
Demon Form. One turn deep on the cell gauntlet against the 10-29 net, by
the same three strata (train decks / held-out decks without Demon Form /
with it): burst8 s1 (0-499) +0.28 (0.65) / -1.41 (0.76) / +6.13 (1.94) HP,
clears +0.14 (0.05) on Demon Form decks; burst8hp2 s1 (both books) -2.73
(0.50) / -3.69 (0.65) / +3.79 (1.16), +0.10 (0.03); burst8hp2 s101 (0-499)
-2.03 (0.69) / -2.52 (0.92) / +4.64 (1.87), +0.12 (0.04). Against the
heuristic the Demon Form decks come level (burst8 s1 +1.75 (1.53) HP).

**What it says.** Games on relatives of a recurring power recover half or
more of its zero-shot cost (about 9.5 HP and 0.20 clears) with the other
decks kept (the plain burst) or at a cost of 2 to 3.7 HP (the HP-weighted
ones): the cards-rung twin of SharpHide carrying to Thorns
(`measurement/adaptation-transfer`). It explains burst8 s1's undecided
+0.82 HP on the cells (`measurement/rerank@cells`,
`cause/gains-from-search`): the gain is the Demon Form decks. And the
bursts' games were played by the net itself, so own games can show such a
card paying.

**Decisions.**
- `lane/yardstick-cards` gains step 1c (jobs, no code): burst8 s1 on the
  second book and burst8 s101 and s201 on both, read by the three strata:
  the transfer column on three seeds. Step 2's bursts on Demon Form decks
  are read beside it (what games on the card itself add). Rating of step
  2's pass raised from even to likely.
- `cause/unseen-cards-half-edge` carries the transfer line.
- No product read follows: two turns deep the card is already played
  (`decision/crossed-player-lead`), and burst8hp2 lost 0.148 clears on the
  headline with its own picks (`measurement/rerank@headline`).

Alternative passed over: queueing the five reads from this session; the
lane's worker queues and reads them (its idle wake is open).

## yardstick-cards step 2: one shared game set per arm and three training seeds; the decks and the Demon Form share (on the owner's behalf, 2026-11-06)

Step 2's bursts (jobs 0276-0290, configs `configs/ycards-*.json`) fine-tune the 10-29 net on elite and boss games on decks holding the held-out cards (`source.decks: "held-out"`, `selfplay.varied_held_out_deck`). The deck generator is the cells' held-out kind: starter plus 3-15 cards from the whole Ironclad pool, at least two of them held out. It runs on game seed 51, not the cells' seeds. Demon Form comes up in about 27% of such decks by chance; it replaces the first extra card in 20% of the rest, so about 40% of decks hold it (the charter asks for at least a third). Arms: the net one turn deep at 100, 400 and 1600 games per group, nested in one 1600-game set; the heuristic and the two-turn product at 400.

**Seeds.** Every arm uses game seed 51, so all arms and seeds play the same fights and pair by fight. The three seeds are training seeds (1-3), as in the unseen-boss-burst and pattern-rows-burst arms. Alternative: a game seed per training seed, so the se also covers which games were drawn. Rejected for cost: the two-turn arm's games run about 6.5 minutes per 60 fights at 3 threads (measurement/two-turn-games@j1), so three game sets would cost about 23 CPU-h against the lane's 31 left; one set costs about 6. Consequence for the read: the se over seeds understates the spread a fresh draw of games would give. A pass at 2 se is a lead for the deck kind; it does not prove the size. Reversible: three more game seeds on the winning arm is one config change.

**Order.** The cheap heuristic arm runs first (0276). Every other arm waits on it passing (`--if-passed`), so a failure in the new source path stops the chain after one job. Reads (both cell books, boss replay) are queued once the run folders exist.

## Value chooser spec confirmed (on the owner's behalf, 2026-11-06)

Lane worker, `lane/value-chooser`. Spec `docs/specs/value-chooser.md`,
confirmed under the mandate and built: `gauntlet.py play <net> --rewards
value [--value-hands K]` scores each option by the sum of three parts' mean
net values of start states (the next floor's sim draw, each elite while an
elite floor lies ahead, the own boss at the post-rest HP), no fights
played. Provisional choices: parts weighted 1:1:1 (the charter's first
cut), one dealt hand by default (K = 4 is the fallback arm). Alternatives:
weights fitted on the control's outcomes (a fit on the read's own data);
the elites part dropped (the sim chooser has none). A pre-build check on
the control's 5391 fights: start value vs. outcome score corr 0.55
hallway, 0.78 elite, 0.55 boss; boss values far too pessimistic (146 of
447 boss starts under 0.25, half of them won), so the boss part may
carry less signal than the sim chooser's boss fights.

## Runtime registry stage 3 spec: monsters from packs as process-wide kinds (on the owner's behalf, 2026-11-06)

Spec `docs/specs/monsters-from-packs.md`, confirmed under the mandate by
the lane worker of `lane/runtime-registry`. A pack's `monsters` entries
(HP, moves, pattern rows, start block and powers, split) load like cards;
`CombatState::new_vs` and Python `Combat.versus` build a combat from
monster names (official or `gen:<id>`). Choices:
- `MonsterKind` becomes a one-byte handle: official kinds keep 0-18,
  loaded pack monsters take the next numbers in load order for the
  process's life (236 at most). Alternative: per-combat monster slots in
  the binding, like generated powers (every `def()` call site would need
  the binding and the move caches a bound index). Stage 5's id widening
  lifts the cap.
- Moves referred to by index in the monster's own list. Alternative:
  names (Hexaghost repeats them).
- Generated powers on monsters refused at load in this stage.
  Alternative: bind them like a card's (one definition per monster and
  power slots); the next step if a bench needs it.
- Code-only behaviour (the lice's rolls, Lagavulin, Hexaghost, The
  Guardian) stays official-only; the round trip covers the other 13
  official monsters.
- Built (c39e365, review fixes 7277955; spec folded here and into the
  README): monster moves also refuse `Draw` and `GainEnergy` (player-only;
  `Draw` panicked in play); a pack is checked whole before anything is
  committed. Checks: cargo test green, golden identical; 13 of 18 official
  monsters round-trip and play the same 20 greedy games; series_check PASS
  (3104 states, heuristic, product net); series_speed 11 interleaved runs,
  paired new/old medians H1 1.01, search 1.02 (1 thread) and 0.99 (16),
  within +10%.

## Lane value-chooser closed (2026-11-06)

Lane worker 7cab620c (on the owner's behalf). Outcome: **go at the bar**
(`measurement/value-chooser@headline`; results doc "Value chooser: level
on the headline at a sixth of the time, as two opposite halves").
`--rewards value` with four dealt hands is level by
`yardstick/cost-savers` on all 500 sequences (+0.08 HP, +0.024 clears)
and without Demon Form (-0.99 HP, +0.000), one hand inside one se of it
(misses non-Demon-Form clears by 0.004); wall time 2.5-4.6 min against the
sim chooser's 16 min at best. The level total hides a split: train-half
decks +4 to +5 HP (3-3.7 se), held-out -4 HP (2.7 se), as the net
misvalues cards it never saw. The charter leaves the held-out book and the
default to the navigator; the split says the value chooser fits reads on
official train cards and is biased on unseen ones. CPU used: about 0.4
cpu-h (two reads at 3 threads, 7 min) of the 3 cpu-h cap. Alternatives
at close: a third arm (weights fitted, the elites part dropped) before
closing, passed over: the stop rule is reached, and what to make the
default is the navigator's.

**Reopen if:** a chooser that values unseen cards (an effects-aware net
whose held-out-half static values track outcomes as well as its train-half
ones, e.g. a burst net that closes the zero-shot gap) makes the held-out
half level with the sim chooser; or the train-half lead (+4-5 HP) is to be
built on: confirm it on sequences 500-999 at fixed n first.

## Lane act1-content opened (on the owner's behalf, 2026-11-06)

Navigator 5318d280, on the wake `checkpoint:runtime-registry@1`.
`lane/runtime-registry` passed its stage-3 checkpoint (monsters from
packs: 13 of 18 official monsters round-trip from a pack, golden
identical, series_check PASS, speed 0.99-1.02), the condition the backlog
held this lane's draft charter on. `docs/direction.md` puts it first:
Act 1 through the registry is the first interest, at a development weight
of 0.8 for goal 1 (`decision/registry-first`, `decision/parity-source`).

**Charter** (`lane/act1-content`; the backlog's draft with three changes):
- A first step that needs no engine code: an inventory of every Act 1
  monster and every Ironclad card against the engine. Each entry is
  present, writable as a pack entry today, or blocked, with the building
  block it lacks. Stage 3 already names two kinds of block: behaviour held
  in code (the lice's rolls, Lagavulin, Hexaghost, the Guardian stay
  official-only) and generated powers on monsters (refused at load). The
  count of blocked entries is goal 1's "first-class custom content" gap
  measured on real content, and the list orders the registry's next atoms.
- No edits to the engine's registry, monster or card tables until stage 4
  has landed: the `runtime-registry` lane is moving official content into
  `content/*.json` and removing the Rust tables. Until then this lane
  writes the inventory, pack files and their tests; a missing building
  block is listed and built after stage 4, rebased on it.


Rated **likely** per content kind once the registry has its atoms. About
16 cpu-h of tests and re-ranks (cap 24); end 2026-11-13; on-close: wake
always.

**Shares** (`jobs/lanes.json`): yardstick-cards 40, runtime-registry 27,
act1-content 15, test-full-memory 8, main 10, filler 0. The two lanes
whose last checkpoints passed keep the most; `test-full-memory` has the
weakest record and ends 2026-11-09.

**Alternatives passed over.**
- Waiting for stage 4, so that each file is written once in its final
  place: the inventory and the
  monsters' pack files do not depend on where official content lives.
- `generated-enemies-bench` in this slot: its enemies with unseen
  mechanics need generated powers on pack monsters, which stage 3 refuses
  (the next entry).
- An exploration lane in this slot: with `test-full-memory` open until
  2026-11-09 this is the fourth lane, the most the portfolio rule allows.
  The exploration slot stays empty until that lane closes; its ready
  charter is `turn-start-leaf` (the next entry), and the code-free
  exploration question of this run went into `yardstick-cards` as step 2b.

## After stage 3 and the value-chooser close: the transfer column is Demon Form's own row learned from other cards; step 2b added; the value chooser stays a tool; generated-enemies-bench waits for powers on pack monsters (on the owner's behalf, 2026-11-06)

Navigator 5318d280. Read: stage 3's decisions
entry and checkpoint, `yardstick-cards` steps 1b and 1c
(`measurement/cards-by-card@cells`, `measurement/cards-transfer@cells`),
the value-chooser close (`measurement/portfolio-value-chooser`), the pack
`data/bench/gen_powers_pack.json`, and the job queue.

**1. What the transfer column measures.** The three burst8 nets gain
+6.10 (1.16) HP and +0.149 clears on Demon Form decks without one game on
Demon Form, and the step-1c read explains it as a learned trigger. The
pack file is more exact: three of burst8's eight cards (`gc1_019`,
`gc1_082`, `gc1_095`) hold the row "at the owner's turn start, apply
Strength", which is Demon Form's own row at other amounts and lifetimes.
So the column shows a row learned on some cards carrying to a new card
that holds the same row. That is what effect inputs are for, and it is a
goal-1 result: a new card built from a row the net has trained on costs a
third of what it costs a net that has not. It does not show that a
trigger learned with one effect and an effect learned on another trigger
carry to their new pair. That question decides what a goal-1 base net
must be trained on: every trigger and every effect once (a sum, tens of
generated cards) or every pair (a product, hundreds). The one piece of
evidence for the sum: the effects nets close the Demon Form stratum from
-7.2 to -3.1 HP between 5k and 40k games that never held the row
(step 1b).

**Step 2b added to `yardstick-cards`** (config-only: the cards of a burst
are a list in its config). Two more bursts by burst8's recipe (4000
games, pool 10000, the net's own games, game seed 31, seeds 1, 101, 201),
each on eight cards of the same pack chosen by the powers' `keys`:
- *parts*: no card holds the pair (OwnerTurnStart, Apply:Strength); four
  hold OwnerTurnStart with other effects (16 such cards in the pack), four
  hold Apply:Strength to the owner on another trigger (20 such);
- *neither*: no card holds OwnerTurnStart or Apply:Strength (86 such),
  the control for "any burst on generated powers lifts these decks".

Read on both cell books one turn deep by the three strata against the
10-29 net, beside burst8's +6.10 (the same-row arm, which exists). What
each outcome changes: if *parts* gains at least half of the same-row arm
(3 HP) and sits 2 se above *neither*, the net composes, and
`coverage-pretrain` (backlog) gets a ready charter: a base net trained on
a generated pack that covers every trigger and every effect. If *parts*
reads like *neither*, the knowledge is per pair: an unseen pair is paid
for in games per pack (the burst) or by search (`turn-start-leaf`), and
the coverage curve of `generated-enemies-bench` is planned over pairs.
About 12 cpu-h (six bursts, twelve reads); the lane's cap of 45 holds
(14.8 used, step 2 about 6, step 3 about 5). Alternative passed over: an
exploration lane of its own (no slot, above; the question belongs to this
lane's transfer column).

**2. Corrections to `cause/unseen-cards-half-edge`** (flagged by the
lane's step 1b, all three accepted): FTL differs by +3.49 (1.33) HP in
the nets' favour, so "no other card differs by more than 2.4" becomes "no
other card costs the nets"; the generated bench's se are per cell, not
per fight (turn start -0.292 (0.049)); original Metallicize decks cost
-0.083 (0.030) wins on the bench with three copies, about 60% of Demon
Form's cost there, though nothing on the cells. The fact is re-set with
these, the three-seed transfer column and point 1.

**3. Open question 10 is answered: seen and not learned, with the payoff
outside the leaf.** The one-turn leaf is the state at the next turn's
draw, before the turn-start hooks run, so a turn-start power's first tick
never lands inside the search, while a turn-end power's does. By its own
entry, `novelty-gated-leaf` is replaced by the cheaper repair,
`turn-start-leaf`: score the leaf after the owner's turn-start hooks that
need no chance have been applied. It gets the exploration slot's ready
charter (rated even; evidence in the backlog entry).

**4. The value chooser (lane closed, go at the bar).** The lane left
three calls to the navigator:
- *The held-out book and goal-1 reads:* `--rewards value` is not used on
  any read whose offers hold cards the net never trained on. It is 4 HP
  below the sim chooser there (2.7 se): the novelty cost moves from the
  fights into the picks.
- *The default for official-card reads:* the sim chooser stays the
  default and the ruler (`yardstick/headline-setting` and its control
  files are sim-chooser files). What `--rewards value` saves, about 12
  minutes per 500 sequences, is not what limits a lane today
  (`cause/one-turn-frees-cpu`); it stays a tool for bulk reads on
  train-card sequences if wall time binds again.
- *The train-half lead (+4 to +5 HP, +0.06 clears, 3-3.7 se, one book):*
  not confirmed now. It is a chooser change, which is run-level decision
  work and waits for Act 1's cards (direction "Avoid"); those cards bring
  a new net and a new pool, so a confirm on today's net would be read
  again then. It is recorded as the first candidate of the chooser
  workstream (`decision/chooser-workstream`): a chooser by the net's
  static values where every offered card is a trained card, by trial
  fights where one is not. On today's two files that split reads about
  +2 HP and +0.03 clears overall, known without a probe.
Filed as `decision/value-chooser-use`. Alternative passed over: the
confirm read on sequences 500-999 (ten CPU minutes; no outcome changes
what is built before Act 1's cards land).

**5. `generated-enemies-bench` gets no ready charter yet.** The wake that
started this run planned one. Stage 3 as built refuses generated powers
on pack monsters, at load and in a move's effects. A bench of pack enemies
built from official powers and new move patterns holds only familiar
parts, which the record predicts to cost nothing
(`cause/novelty-is-horizon`): by the trade-off rule that bench is not
proposed. What gives it its value is binding generated powers on pack
monsters, an engine change in the registry code stage 4 is rewriting. The
bench's charter stays held with that as its first step, after stage 4
lands; widening the burst's vocabulary stays its second precondition
(`how/burst-inputs`). The navigator opens it at `runtime-registry`'s
close.

**6. `burst-recipe` comes back as a part, not a lane.** Its reopen
condition, a one-turn retention cost, holds: the burst8 nets lose 0.041
clears on train decks (3.4 se). Rehearsing official train-deck games in
the burst is the known answer; it is written into `coverage-pretrain`.

**7. What holds step 2's bursts: memory, not CPU.** The fifteen
bursts queued at 14:25 had not started by 15:00, with no other job
running; health counts 483 minutes without a job in the last day and
`cpu` red. Free memory on the dev machine stayed under what they reserve. Step 2's bursts ask for 4.5-5 GB, and need that: the burst
that builds the games peaked at 6.2 and 7.4 GB, the ones after it at
3.8-4.2 GB (jobs 0170-0173, 0244-0247), ten times a gauntlet read's 0.5-0.8
GB. The reservation of 0208 (9.5 GB) does not block them; free memory
does. So goal 1's unit of work, a burst, does not fit in the dev machine's free memory. Filed as `cause/memory-holds-bursts`; `burst-memory` enters
the backlog under `throughput-fixes` (find what holds 4-7 GB in
`finetune.py` when the search itself runs in under 1 GB). Nothing for the
navigator to change in the queue: the jobs belong to their lanes.



## Push blocker: a GitHub timeout is "can't tell", not red (owner, 2026-11-06)

At 15:15 the health check turned the `push` blocker red with nothing
unpushed (`main` = `origin/main` = 6ef16f9) because `gh auth status`
(`scripts/health.py` `gh_auth_ok`) printed "Timeout trying to log in to
github.com account <user> (keyring)" and exited non-zero. The login had not
expired: the same command passed in 1 s a few minutes later. A red blocker
stops the launcher starting any session (`scripts/roles.py`, the tick), so
one network hiccup held every role for up to a health refresh (15 min).
It was the first push-red in `jobs/roles.log`.

Decided: when `gh auth status` fails with a timeout or network error
(retry once first), the auth half of the push check reads "can't tell"
(`None`, which already keeps the blocker out of red); only a real auth
failure (not logged in, token invalid) is `False`. The unpushed-commits
half stays as it is: a commit on main unpushed for over 30 min still
turns push red, so a refused push is caught either way.

Alternatives: leave it (a timeout keeps stopping all roles until the next
refresh); drop the gh check and rely on unpushed commits alone (an expired
login would only show at the next commit, possibly hours later). Cost:
a few lines in `health.py` and a test; the risk is that a real auth
failure that looks like a timeout shows one health run later.

## Runtime registry stage 4 spec: official content as compiled-in files read by the pack parser (on the owner's behalf, 2026-11-06)

Spec `docs/specs/official-content-files.md`, confirmed under the mandate
by the lane worker of `lane/runtime-registry`. Official cards (128),
power definitions (30) and monsters (18) move to `content/cards.json`,
`content/powers.json` and `content/monsters.json` in the pack format,
loaded on first use by the pack parser; the Rust tables go once the
loaded definitions are checked equal; the fingerprint hashes the files.
Choices:
- Files compiled in (`include_str!`), parsed once on first use.
  Alternatives: read from a path at run time (every pinned snapshot,
  wheel and test would need the path); generate Rust in a `build.rs` (a
  second reader of the format). Fallback if speed fails +10%: a plain
  static copy of the loaded definitions, then `build.rs`.
- Three files, one per content kind. Alternative: one official pack.
- Code-backed monsters (the lice, Lagavulin, Hexaghost, The Guardian) go
  in the file with an official-only `code` name that attaches their
  setup and allows their code-driven effects; packs using `code` are
  refused. Alternative: keep those five in Rust.
- Kept as code, keyed by the official handles: the enums and kind
  numbers, move-id constants, setup functions, `Power::is_debuff` (the
  file's `debuff` is checked against it) and the kind-keyed special code.
- Built (19e64ce, 23b7094, 24ce05e, fccd789): readers switched to the
  file-loaded definitions (card names from the file's ids, so the load
  doesn't recurse), then the Rust tables deleted (-831 lines). Checks:
  128 cards, 30 powers, 18 monsters loaded and equal to the tables before
  they went; cargo test green in engine and solvedb (294), golden
  identical; series_check PASS on 17,361 states (heuristic, both feature
  batches, product net; `--cards` all 60 non-status kinds, base and
  upgraded; the 4 status kinds can't be played into a state, so they
  are covered by the golden games and round-trip tests, not here). series_speed on a loaded machine (old build alone ranged
  1.16-2.92 M combats/min): H1 medians -4.5% (7 runs), -16.0% and -4.1%
  (11 runs; paired new/old median 1.03 in the second); search -2.2% at 1
  thread, +10.5% at 16. Read as within the +10% budget; the fallback
  (a plain static copy) was not needed. Not settled by these reads: an
  H1 cost of a few percent from the first-use check per def lookup.

## Dashboard improvements as built (owner, 2026-11-06)

Spec `dashboard-improvements.md` (confirmed by the owner; folded here and
into `scripts/dashboard.py`'s docstring and README "Job queue"). The
owner's choices: read-only, standard library, 127.0.0.1 only and the 60 s
refresh stay; glanceable wins over complete; out of scope: controls,
results charts, live streaming of a transcript.

- **Timeline:** up to 30 days (`TIMELINE_DAYS`), opening on the last 24 h
  (also without script: a right-to-left scroller). The wheel zooms around
  the cursor (1 h to the full span), dragging or the scrollbar pans,
  buttons 6 h / 24 h / 3 d / 7 d / now. The view is kept in the URL
  fragment (`#t=<start>,<end>`, plus `&live` when it follows now); the
  page's script does the 60 s reload so the view survives it, the
  `<meta>` refresh stays in `<noscript>`. Overlapping lane and navigator
  sessions take their own tracks; a lane session names its lane (from
  `why` `idle:<lane>`, else the lane of the job in `ended:<job>`, else the
  live claim, else "lane unknown"). Job bars open their Queue row.
- **Transcripts** (was "conversation"): a tool call expands to its whole
  input (cut at 20 KB) and then its output. A log can hold several
  `result` lines (a background task wakes the session for another turn);
  each one before the last is a "turn ended" divider, and a live record
  always ends with "working", never "ok".

- **Queue:** every done job, 50 a page (`DONE_PAGE`), filtered by lane and
  status, sorted by end, duration or id, all in the query string with a
  plain form; `/queue?job=<id>` opens the page holding the row,
  highlighted. Job chips and ids show lane, threads, estimate and note on
  hover.

Commits f4c670e (spec), efc3440, 0727dee, fca8df2, b125853, 4ff7bf4,
810c3fa, bd78d8b; tests `scripts/tests/test_dashboard.py` (fixture overlay
`scripts/tests/data/dashboard/extra/`).

## Gremlin Wizard's first Blast on turn 3 (on the owner's behalf, 2026-11-06)

Lane act1-content, step 2. sts_lightspeed's Gremlin Wizard charges three
times before its first Ultimate Blast (its counter starts at 0); the wiki
says twice, and its patch history fits a game counter that starts at 1.
`decision/parity-source` takes behaviour from sts_lightspeed where it
covers it; here every other source says it covers it wrongly, so the pack
follows the wiki (Blast on turn 3, then every fourth turn). HP follows the
rule as written: the wiki's 23-25, though sts_lightspeed's 21-25 fits the
wiki's own Ascension 7 range better. Alternatives: lightspeed's three
charges (one more free turn per fight, an easier Wizard), or 21-25 HP.
Both are one-entry edits in `content/packs/act1-monsters.json`; details in
`docs/research/act1-inventory.md` "Step 2".

## Exhaust-cards spec (C1): exclusion by mechanic, count before exhaust, True Grit as chance (on the owner's behalf, 2026-11-06)

Spec `docs/specs/exhaust-cards.md` confirmed by the act1-content lane
worker: building block C1, six Ironclad cards (12 entries). Three choices,
all reversible: (1) Exhume's "not Exhume" rule is by mechanic, a card with
a `ReturnFromExhaust` pick is never a candidate (alternative: by card id
and its upgrade); (2) cards that scale with the exhausted count read
`HandCards` before their `ExhaustHand` (alternative: a count field in
`InPlay`, a codec change); the two orders give the same fight until C2's
exhaust triggers, whose spec re-checks it; (3) base True Grit's random
exhaust is a chance event (`ChanceEvent::RandomExhaust`) (alternative:
leave base True Grit blocked). Provisional until the build lands.

## The burst's memory is yardstick-cards' step 2a; the two lanes behind jobs that cannot start get a wake (on the owner's behalf, 2026-11-06)

**Read** (`jobs/health.json`, `jobs.py status`, the done records, a memory reading by hand):

- The CPU is what stands still: no job ran for 851 minutes. Sixteen jobs
  are pending and none can start. The runner admits a job when free
  memory is at least its reservation plus 1 GB; `0208-test-full` reserves
  9.5 GB and the bursts `0276`-`0290` reserve 4.5-5 GB, more than the dev
  machine had free beside the running sessions all day.
- Both lanes behind those jobs count as busy (a pending job), so
  `health.py` raises no idle wake for them: no lane worker has started on
  `test-full-memory` since 06:44 or on `yardstick-cards` since about 14:30.
  The lanes wait on jobs that wait on memory, and the fix for the memory
  is code nobody is started to write.
- What holds a burst's memory is very likely not training itself: a
  `learn.py` training on 5,000 games at 6 threads peaks at 1.2-1.6 GB
  (`0211`, `0212`), while a `finetune.py` burst on 33-1,600 games at 4
  threads peaks at 2.8-7.4 GB (`0119`-`0247`). `finetune.py` plays and
  encodes a replay pool of 10,000 games per group (`pool`, line 353-395)
  beside the new games; that pool is the first suspect.
- The pending bursts are pinned to snapshot `ba5f802`: a fix on main does
  not reach them, so they are queued again after it.

**Decided:**

1. **The burst's memory (`burst-memory`, backlog candidate 11) becomes
   `yardstick-cards` step 2a**, first in that lane: find what holds 3-7
   GB in a `finetune.py` burst and cut the peak under 2.5 GB at 4
   threads with the training result unchanged (the same config gives the
   same validation curve before and after), then cancel `0276`-`0290`
   and queue them again from the new commit at the measured peak, with
   step 2b's bursts. Step 3's card-patch spec starts beside it and does
   not wait for the bursts. That is the exit of
   `cause/memory-holds-bursts`.
2. **A wake for each lane behind a job that cannot start.** One light
   job per lane (`yardstick-cards`, `test-full-memory`) that prints one
   line and ends, moved first in its lane: its end is the event that
   starts a lane worker, who reads the re-set charter. The pending jobs
   stay; their lanes release or drop them.
3. **`test-full-memory`'s charter says what `0208` ran into:** a job
   that reserves more than the memory free beside the sessions does not
   start. The worker measures the three heavy files in pieces the runner
   can admit or finds the holder in the code; goal, stop rule, cap and
   end stay.

Alternatives passed over. For the burst's memory: a new lane (a fifth
open lane; the portfolio rule allows three, and a fourth only beside one
about to end); `test-full-memory` (the same family, but then
`yardstick-cards` would need a signal from another lane to queue its
bursts again, and no event carries one); a smaller `pool` in the configs
(no code, but another recipe than burst8's, whose +6.10 HP is the number
step 2 is read against); running the bursts at once under a low
reservation (they would push the sessions into the page file, which the
admission rule exists to prevent). For the wake: cancelling the pending
jobs (the lanes' call, and `0276`-`0290` may still start in a quiet hour
tonight); re-setting the lanes' step facts (the lane workers' facts).

A gap for whoever next changes `scripts/health.py`: a lane whose pending
jobs have all waited for hours on memory is counted as busy and gets no
lane worker. Not the navigator's code to change; the steward's 20:32
line named the same stall.

## Ideas run of 2026-11-06: the 16 new Act 1 cards get a zero-shot read with its outcome predicted; the enemies bench opens on act1-content's block M5, built after the exhaust blocks (on the owner's behalf, 2026-11-06)

What changed since the 15:11 run: `runtime-registry` landed stage 4
(official content loads from `content/*.json`); `act1-content` wrote its
inventory, four monsters and 16 Ironclad cards as pack data and specced
its first building block; no CPU result (no job ran).

**What the inventory says beyond its own count.**

- Open question 11 has its number (the navigator's count from
  `docs/research/act1-inventory.md`): of the 40 missing Ironclad cards,
  eight are powers whose payoff comes in later turns. One pays at the
  turn start (Berserk, written); seven pay on an event inside a later
  turn (Corruption, Dark Embrace, Feel No Pain, Evolve, Fire Breathing,
  Barricade, Juggernaut, all blocked). The record's rule
  (`cause/unseen-cards-half-edge`) predicts a cost for the first kind
  only.
- The 16 written cards are the first real custom content loaded from a
  file, and the product net has trained on none of them. Their cost can
  be predicted card by card before a fight is played, and five of them
  are cases the record has no answer for: three that pay now and charge
  later through a status card (Power Through, Reckless Charge,
  Immolate), two built on triggers the product net cannot read (Double
  Tap, Flame Barrier; `how/burst-inputs`).
- The inventory's block M5 (a power no official monster holds, on a
  pack monster; it blocks the Mad Gremlin) is the same code as
  `generated-enemies-bench`'s first precondition. By entries unblocked
  M5 is near the bottom of the list (one monster); with the bench it
  opens goal 1's standing number on enemies new in kind.

**Decided:**

1. **`act1-cards-zero-shot` is a candidate with a ready charter**
   (backlog candidate 3; project; cap 3 cpu-h): the generated-power
   bench takes the pack and a card list; the 10-29 net one turn deep
   against the heuristic, card by card, with the prediction written
   first (Berserk costs, eleven in-turn cards do not, five are open).
   Rated likely that the table is recorded, likely that Berserk costs,
   even that one of the five open cards does. It opens in
   `runtime-registry`'s slot when that lane closes (its close wakes the
   navigator); `turn-start-leaf` stays the first ready charter, for the
   exploration slot at `test-full-memory`'s close. Its reads run under
       1 GB.
2. **`act1-content` builds M5 right after its exhaust blocks (C1, C2)**,
   ahead of the order by entries unblocked; the charter says so.
   `generated-enemies-bench` is held until M5 lands, not until
   `runtime-registry` closes: opened earlier, it would build the same
   change in a second lane.
3. **`cause/memory-holds-bursts` re-set** with today's reading: what a
   training peaks at against a burst, the replay pool as the suspect,
   and the planning rule that a lane behind jobs that cannot start gets
   no lane worker until someone queues a wake.

Alternatives passed over. For the 16 cards: a step of `yardstick-cards`
(the same rung, but that lane now holds the burst's memory, fifteen
bursts and the card-patch spec); a step of `act1-content` (its work
    goes to building blocks, the direction's first interest); a headline
read with the 16 cards in the offer pool (a new headline pool is
run-level work, which waits for the content; direction "Avoid"); no
read at all, taking the rule's prediction as known (the rule comes from
ten official cards and one generated bench; five of these cards fall
outside what it was built on). For M5: leaving the order by entries
unblocked (the bench would wait for the bottom of a list of twenty
blocks) or building it inside the bench's lane (two lanes in the same
registry code).

Checked against the closed lanes' reopen conditions: none newly holds.
`goal1-yardstick`'s "monsters from packs land" has held since stage 3
and is what `generated-enemies-bench` carries; the four pack monsters
written today are familiar parts except the Gremlin Wizard, whose Blast
on turn 3 is a scheduled threat a 24 HP monster rarely lives to use
alone: its read waits for the Gremlin Gang (blocks E1, M5, M6).

## After the big-picture review of 2026-11-06: code first, the mechanic as goal 1's sample unit, two stored conclusions re-set, probes without lanes (on the owner's behalf, 2026-11-06)

The review is `docs/research/big-picture-2026-11-06.md` (19 agents; all
twelve skeptic verdicts "overstated", each with a corrected claim). The
navigator's reading is its first section. What is decided from it:

1. **Order of work: code goes first**: `act1-content`'s blocks, the burst's memory (`yardstick-cards` step 2a), a driver that queues a family of reads with its pass and fail rule as code (`session-free-reads`, new, ready charter), `turn-start-leaf`, the pack option of the bench (`act1-cards-zero-shot`), the card-patch spec. Trainings and reads that need no code are queued when they fit.
2. **`act1-content` builds M5 right after C1**, before C2 (this replaces
   the order of this evening's ideas run: C2 unblocks three cards, M5
   opens goal 1's bench on enemies, the one rung where a cost survives
   two turns of search). Its charter also names the steps the review
   found missing between today's packs and a deck or a character made of
   data: more than 8 pack cards and 8 pack powers per fight
   (`engine/src/registry.rs` `SLOTS = 8`, checked), upgrade links for
   pack cards, encounters as data (E1), pack content in `gauntlet.py`'s
   decks and offers, and the wider vocabulary on the pack path of a
   burst (`how/burst-inputs`). They are blocks like the inventory's,
   ordered by the lane after M5 by what they unblock.
3. **The mechanic is the sample unit of a goal-1 read.**
   `generated-enemies-bench` samples 20-30 mechanics with few starts
   each and puts its standard error over mechanics; `yardstick-cards`
   step 3 does the same over modifier pairs. No further lane step is
   designed on the Demon Form row: steps 2 and 2b stay as queued (they
   are designed, cheap, and step 2 is the owner's games-to-adapt curve),
   and step 2b's result is a lead on one pair. `coverage-pretrain` gets
   a charter only after the parts-against-neither read holds on at least
   three pairs, with the pair as the unit.
4. **Two facts re-set, two flagged.** `decision/no-goal2-training-arms`:
   the stop on label, distillation, column, ensemble, round and burst
   arms stands; the sentence that data size moved run level "not at all"
   is wrong against the files (5k, 20k, 40k games: -3.30, -1.45, -0.16
   HP against the 10-29 net on the one-turn cell gauntlet, both books;
   the curve ends level with the product net; 80k unresolved) and is
   replaced by "no data arm beats the product net". No training follows:
   more games of the same kind is not something new to learn (the
   owner's training rule). `measurement/seed-sd@gauntlet`: 0.65-0.7 HP
   pooled over 14 twin groups, not 0.4; a single-seed pair's se is about
   1.1 HP. Both numbers are the review's, recomputed alike by two
   skeptics; the ledger script reproduces them when it exists. Flagged:
   `measurement/rerank@cells` (the lean-thr and data40k rows are one
   seed). `cause/depth-saturated` was checked and stands: it already
   states that three turns were read on 48 elite fights.
5. **The headline is quoted as 0.78-0.81** (`decision/headline-quote`):
   0.834 on sequences 0-499, the book the search settings were chosen
   on, 0.780 on 500-999, 0.807 over both. The control file and the
   protocol do not change.
6. **A product net trained on all content is allowed beside the hold-out
   nets** (`all-content-net`, a candidate, not opened): both unseen
   bosses, the held-out cards and today's inputs are new content under
   the owner's training rule; the hold-out nets stay goal 1's and every
   goal-1 read uses them. It would be judged on the headline protocol
   like any product candidate.
7. **Probes without lanes.** A read that needs no code and under about 5
   thread-hours gets no lane, charter or wake of its own: the navigator
   queues it in lane `main` from the backlog's probe sheet, with its
   read rule in the job's note, and reads it at its next run. Queued
   tonight (`0296`-`0300`, about 5 thread-hours, each under 1 GB): the
   one-turn control on fresh sequences 1000-5999 as a shared control,
   its two seed twins on the same range (was the control a lucky draw on
   its own book?), and the second 80k net, never played, on both cell
   books.
8. **A lead of 2-3 se from one seed, one book or one content item opens
   nothing**; it gets a replication on fresh sequences or seeds
   (`yardstick/twin-reads` already says so for burst seeds; this widens
   it). Each candidate states its predicted effect beside what its read
   can detect with the seed spread counted, the unit its claim
   generalises over, and the error it repairs.

New candidates from the review, with their ratings in the backlog:
`session-free-reads` (likely), `all-content-net` (a long shot for the
headline), `hands-where-small` (a long shot), `ceiling-player` (a long
shot), `exact-referee` (even that it builds), `second-character-census`
(likely, no CPU). `experiment-ledger` moves up.

Alternatives passed over. Opening `all-content-net` now for the idle
CPU (a training of unknown memory peak, for a gain
predicted under what the headline detects; its config waits for a lane
slot). Dropping `yardstick-cards` steps 2 and 2b as the review advises
(they are queued and cheap, and step 2 is the curve the owner's training
rule names as goal 1's exception). Re-setting the two flagged facts
tonight (their numbers were not recomputed by a skeptic). A training on
160k games if 80k reads above 40k (not new content; the owner's rule).
The review's HP-price points on the fresh book (every price so far
moved under 1 HP).



## Role models: the navigator moves to Opus at high effort (owner, 2026-11-06)

Revises "Role models revised: the navigator stays on Fable at high
effort" for the navigator only: it runs on Opus (claude-opus-5-5) at high
effort (`scripts/roles.py` `ROLES`). The lane worker is unchanged (Opus
at medium effort). Reason: cost (launcher logs put Fable at about 3x Opus per
token). No record compares the two models on this role, so the loss
in judgment is unmeasured, not shown. The model changes for runs the
launcher starts after it restarts (`ROLES` is read once at its start).
Alternatives: keep Fable (status quo); Fable for the big-picture review
only; Sonnet at high effort (cheaper still, untested on this role).

## Runtime registry stage 5 spec: sparse piles and powers, sized from a census (on the owner's behalf, 2026-11-06)

Lane worker of `lane/runtime-registry`, session ceffddb3. Spec
`docs/specs/sparse-state.md`, confirmed under the mandate; not built
(the lane's stop rule ends at the spec; the build goes to the
navigator's ranking with the close wake).

- **Speed case, measured.** `two_turn_phases --census` (new flag) over
  1,040,766 states that 100 two-turn searches stored: distinct card ids
  per state, 4 piles summed, mean 11.1, max 17; non-zero powers over all
  creatures mean 3.1, max 8. The state is 1,292 bytes: piles 608 (148
  ids), power blocks 504 (38 powers), the rest 180. Padding the piles by
  576 bytes (same trees): `series_speed.py` 7 interleaved runs, clone
  37.7 -> 69.9 ns, random combats -6.0%, search 1 thread -17.5%, 16
  threads -20.2%; two-turn real search time ratios 1.00 / 1.13 / 1.13 /
  1.90 over 4 pairs (a gauntlet job ran throughout). Each new card id
  costs 4 bytes and each power 12 on today's layout, so Act 1's cards
  (about +100 ids, +400 bytes) would cost about 12% of one-turn search
  speed by themselves.
- **Chosen:** per-pile and per-creature sorted inline lists (capacity 40
  card ids per pile, 12 powers per creature, overflow panics), about 850
  bytes; method APIs, codec bytes, Debug text, golden, H4 unchanged.
  Expected one-turn search +15-20% games/s, two-turn about -10% time,
  less the lookup cost; the build stops at its speed check (search 1
  thread at least +5%, random combats no worse than -10%) if it does not
  pay.
- **Alternatives:** one combat-wide card table shared by the four piles
  (smaller, but every pile call needs the table: an engine-wide API
  change); heap-spilling lists (states stop being cheap to copy); a
  wider `CardId` now (no content needs it yet: 148 ids).
- Registry scope stays one per process (`decision/registry-first`): the
  spec found no need for a handle per state.

## Lane runtime-registry closed (2026-11-06)

Lane worker, session ceffddb3. Outcome: the stop rule's done branch.
Stages 2 (content identity in records and the pack store), 3 (monsters
from packs) and 4 (official content as `content/*.json`, the Rust tables
removed) landed with golden identical and the series checks green;
stage 5 is specced (`docs/specs/sparse-state.md`, decisions "Runtime
registry stage 5 spec: sparse piles and powers, sized from a census")
with its speed case measured, and not built: the build goes to the
navigator's ranking. CPU: 0.0 of the 45 cpu-h cap in queued jobs (the
builds, tests and speed checks ran in the worktree outside the queue,
a few thread-hours). Registry scope stays one per process: no stage
needed a handle per state.

**Reopen if:** a build of `sparse-state` is ranked (its own lane or a
step of `act1-content`), or content needs what this lane left out:
more than 256 card ids (`CardId` widening), content per run rather than
per process (`generated-cards` running two packs in one process), or the
code-only monsters (lice, Lagavulin, Hexaghost, The Guardian) as pack
rows.

## Lane sparse-state opened (on the owner's behalf, 2026-11-06)

Navigator, on the `lane:runtime-registry` close wake. The slot
runtime-registry left goes to the build of its stage 5 spec
(`docs/specs/sparse-state.md`) as its own lane, `kind: project`, the
fourth lane while `test-full-memory` is within three days of its end
(2026-11-09).

- **Why this, now.** The spec measured its own speed case (decisions
  "Runtime registry stage 5 spec"): padding the state by 576 bytes cost
  one-turn search 17.5% games/s at 1 thread, and the sparse layout cuts
  about 440 bytes, so on that slope one-turn search gains about 15-20%
  and two-turn about 10% time, less the lookup cost. Every search job
  gains it (machine time, `owner/machine-time`), and it makes the state
  stop growing with content: today each card id costs 4 bytes and each
  power 12, so widening the tables for Act 1's cards would cost about 12%
  of search speed against `decision/registry-first`'s 10%-per-step
  budget. It is an engine refactor held to golden, codec, H4 and
  series_check identity. Its CPU is a few thread-hours of speed checks.
- **Rated likely** to pass its bar (search 1 thread at least +5%,
  random combats no worse than -10%): for, the slope is measured on the
  same trees in both directions of size; against, a sorted-list lookup
  replaces direct indexing on every `count`/`get`, unmeasured until
  built, and the spec's own stop point drops the build if it does not
  pay. About 2 cpu-h (cap 3).
- **Alternatives passed over.** `session-free-reads` (backlog candidate
  3, the slot's named next): it
  stays the next ready charter after `turn-start-leaf`. The build as a
  step of `act1-content`: that lane is mid-C1 with M5 next, so the build
  would wait days behind it; as its own lane it runs beside it, and its
  method APIs are unchanged, so act1-content rebases over it.
  `turn-start-leaf` now (the exploration slot is empty): it stays the
  lane `test-full-memory`'s close opens, which restores the exploration
  slot within days.
- **Shares:** sparse-state 5, taken from yardstick-cards (57 -> 52),
  whose fifteen pending bursts cannot start until its step 2a cuts the
  burst's memory.

## Monster-pack-powers spec (M5): start powers only, bound after the deck's (on the owner's behalf, 2026-11-06)

Lane act1-content's block M5 (`docs/specs/monster-pack-powers.md`),
confirmed by the lane worker under the mandate. A pack monster's
`start_powers` may name a pack power; the fight's binding gains its
monsters' pack powers (split children included) after the deck's, a
shared power keeping the deck's slot, more than 8 in all an error.
Moves that apply a pack power stay refused (M5b, built when a bench enemy
needs one). Alternatives: both forms now (a per-fight resolution of the
static move tables, larger, touching intent features); a fixed slot per
monster power (collides with deck powers). Reversible: one load rule and
one binder; no format, feature or official-content change.

## Sparse state built and landed: search +17.6% (on the owner's behalf, 2026-11-06)

Lane sparse-state built `docs/specs/sparse-state.md` (results there,
"Results"). The state shrank from 1,292 to 744 bytes; against main's
build, 11 interleaved `series_speed.py` runs gave search 1 thread
+17.6% games/s (10 of 11 pairs), 16 threads +35.5%, random combats
+13.3%; golden games, codec encodings, series_check and H4 identical.
The charter's go branch (search 1 thread at least +5%, random combats
no worse than -10%, identities held) is met, so it lands with an `sts`
swap.

- **Layout change from the spec (decided here).** `Powers` holds a
  held-power bitmask and finds an entry by popcount instead of scanning
  a sorted id list: the scan cost random combats about 17%, the mask
  version gains 6% on its own (bench medians). Alternatives: the spec's
  scan with a held mask only for absent powers (still -17%: present
  lookups and inserts dominate); keeping dense powers and sparse piles
  only (`Powers` is where the size and the cost both were). Reversible:
  one struct behind unchanged methods.
- **What it changes.** Adding content no longer grows the state: Act 1's
  ~100 card ids add nothing (piles hold up to 40 distinct ids each,
  powers up to 12 per creature; more panics, naming the capacity). The
  speed slope measured for the spec now works in our favour: every
  search-based job runs about 15-35% faster per thread count.

## Lane sparse-state closed (2026-11-06)

Lane worker, session 1939d3ae. Outcome: the stop rule's go branch. The
sparse state (`docs/specs/sparse-state.md`, "Results") landed with an
`sts` swap at 342b1ce: search 1 thread +17.6% games/s, 16 threads
+35.5%, random combats +13.3%, `CombatState` 1,292 -> 744 bytes, golden,
codec, series_check and H4 identical (decisions "Sparse state built and
landed"). The spec's sorted-list `Powers` failed its own speed bar
(random combats -17%); the held-power bitmask with popcount lookup is
what passed. CPU: 0.0 of the 3 cpu-h cap in queued jobs; by hand in the
worktree, about 2 thread-hours (builds, test suites, two 11-run speed
checks).

**Reopen if:** a fight needs more than 40 distinct card ids in one pile
or 12 powers on one creature (the capacity panic fires), or card ids
pass 256 (`CardId` widened): then resize, or give `Pile` the same
bitmask-and-popcount layout `Powers` has (a 256-bit mask, 32 bytes)
and measure it the same way.

## Lane turn-start-leaf opened (2026-11-06)

Lane worker, at sparse-state's close (its `on-close: wake on fail`; the
lane went, so no navigator wake). The first ready charter in backlog
order is candidate 2, `turn-start-leaf`, which the navigator's ranking
(backlog, "Open lanes" paragraph) had named for the next free slot,
the exploration slot; `session-free-reads` (candidate 3) is now the next
ready charter. The charter is copied as written into `lane/turn-start-leaf`
(kind exploration, cap 1 cpu-h, end 2026-11-13, on-close wake on go).
Share in `jobs/lanes.json`: sparse-state's 5.

## yardstick-cards step 2a: the replay pool memory-mapped and drawn per epoch, game play in chunks of 400; the step-2 bursts queued again behind a curve check, with step 2b's (on the owner's behalf, 2026-11-07)

What held a burst's memory: the replay pool. `finetune.py` loaded the pool's encoded cache (10,000 games per group, 1.2-1.9 GB `.npz`, of which `rows` alone is 1.0 GB) whole, and `train.train` copied it again into `Dataset.concat([new, pool])`: about 4 GB before the net. Each epoch draws only about as many pool examples as there are new ones (share 0.5). Game play was the other holder: `sts.run` with `record=True` holds every recorded state of a chunk of 2,000 games.

**Decided:**
1. The pool is cached as a memory-mapped directory (`DatasetWriter`; an existing `.npz` is converted once, one array at a time), and each epoch copies only the pool examples its batches draw (`Dataset.take_unmapped`, through a fresh map dropped after, so the pages leave the working set), re-indexed so every batch holds the same examples in the same order as before. The rng draws are unchanged, so training is unchanged; `test_net` checks the batches, and job `0304` reruns burst `0276`'s config and compares its curves (`scripts/analysis/curves_equal.py`, tolerance 1e-6) and measures the peak.
2. `finetune.PLAY_CHUNK` and `two_turn_games.PLAY_CHUNK` go from 2,000 to 400 games per `sts.run` (`registry.PLAY_CHUNK` is 200): each game is played from its own spec and seed, so the games are the same; the recorded states held at once shrink fivefold.
3. `0279`-`0290` (pinned to `ba5f802`, which the fix does not reach) are cancelled and queued again from the new commit with `--if-passed 0304`: a curve mismatch parks them. `0278` (the two-turn product's games, running since 01:15) is left to finish: its games are the same under either code and its two seed twins wait on it.
4. Step 2b's card lists are fixed by rule before any read (results doc, "Step 2b's card lists"): parts takes the four test-split turn-start cards without Strength and the first four train-split cards giving the owner Strength on a trigger that does not recur each turn; neither takes the first eight test-split cards with neither key.

Alternatives passed over: a smaller `pool` in the configs (another recipe than burst8's, whose +6.10 HP step 2 is read against); keeping the `.npz` and sampling the whole pool's draws once up front (the union of 20 epochs' draws is most of the pool on the 1,600-game arm); letting `0279`-`0290` run on the old code when memory allows (they would still reserve 4.5-5 GB each and keep the CPU waiting); Strength on `OwnerTurnEnd` for parts (four such cards exist, but Strength gained at turn end acts on the next turn as Demon Form's does, so a gain would not say the net composed two parts).

## Lane test-full-memory closed (2026-11-07)

Outcome: done on memory. The full Python suite run file by file (job 0303)
peaks at 1.77 GB (test_ladder) against 9.8 GB in one process (0072, 0076)
and 8.3-9.3 GB in three files run file by file (0206); it reserves 2.2 GB. The holders were the test fixtures,
not the code under test: `fill_db` kept failed roots' subtrees (343k of
380k rows) and test_solve ran solves at budgets of 50k-100k nodes at ~21 KB
per node (`measurement/solver-memory-per-node`); both cut with every check
kept. 0303 exited 1 on two test_jobs.py tests unrelated to memory: a stale
`test_pin` expectation after b68ac7b (fixed) and `test_idle_gate`, which
fails when other heavy jobs load the machine. `test_sweep` leaves the
default run as decided on 2026-11-01 (about 53 of 0303's 169 minutes).
The stop rule's literal pass (a test-full with exit 0) is left to the next test-full run from this commit. Results doc `docs/research/test-full-memory-2026-11-06.md`,
"The full suite after the cuts (job 0303, 2026-11-07)".

CPU: 23.4 thread-hours by the job records (0205 9.4, 0295 2.8, 0303 11.3)
against the 15 cpu-h cap; the cap was reached while 0303, the deciding
run, was half done, and it was let finish (on the owner's behalf; the
alternative, cancelling it at the cap, threw away its first hour and left
the lane without its measure).

**Reopen if:** a test-full file peaks over 4 GB again (the table at the end
of each test-full log), or the runner cannot admit a test-full for 6 hours; first suspects are new fixtures that solve to a large
node budget or store unsolved subtrees. Separately, if `test_idle_gate`
fails in two test-full runs in a row, give it its own idle check (it
measures the machine, not the code).

## Lane session-free-reads opened (2026-11-07)

test-full-memory closed on its done branch, and its charter's on-close
(`wake on fail`) does not wake the navigator. Its slot goes to the next
ready charter, as the backlog's ranking says (`docs/backlog.md`, "Open
lanes" paragraph: "The next free slot opens `session-free-reads`
(candidate 3, now the first ready charter)"). The charter is candidate 3's
ready charter, copied as written into `lane/session-free-reads`.

## session-free-reads: the spec confirmed; reads find their net from the burst job's log; the first family binds to yardstick-cards' burst jobs (on the owner's behalf, 2026-11-07)

Spec `docs/specs/session-free-reads.md`, confirmed under the mandate. A
family file (`configs/families/<name>.json`) names a parent net, arms of
burst configs, reads per net, a table rule and follow-up reads;
`scripts/family.py queue` turns it into one chain through `jobs.py`
(reads `--if-passed` their burst, the table `--after` the reads with a
`--check` that passes when the rule passes, follow-ups `--if-passed` the
table), and `table` prints the result and verdict from the files.
`scripts/analysis/ledger.py` is the ledger of review 2026-11-06 direction 3.

- **How a read names its net.** A registry run folder carries a random
  hash, so a read queued before its burst cannot name the net. The read
  job runs `family.py read`, which takes the net from the burst job's log
  line `run <id>: <model_path>` when it starts. Alternatives: give
  `finetune.py` a fixed output folder (changes the registry's naming,
  off limits for this lane); queue reads only after each burst (the
  session-per-read pattern this lane removes).
- **The first family and yardstick-cards.** Steps 2 and 2b's bursts
  (0305-0322) are that lane's, now parked on 0304's curve check. The
  family binds to whatever burst jobs exist for its configs, and queues
  only their reads, in lane yardstick-cards, each note naming the family,
  so that lane's worker sees them in `jobs.py status` and doesn't queue
  them twice. If that lane re-queues its bursts, running `family.py queue`
  again re-binds the parked reads. Alternative: wait for the bursts to
  run and take the next family (act1-cards-zero-shot); kept as the
  fallback if yardstick-cards drops steps 2 and 2b.
- Checked before the build: the ledger's three numbers reproduce from
  the files on disk (mean over every (net, book) file of the paired
  end-HP edge against the 10-29 net on the same book: data5k -3.30, 10
  files; data20k -1.45, 10; data40k -0.16, 6).

## session-free-reads: built; the first family's queue waits until yardstick-cards settles 0304 (on the owner's behalf, 2026-11-07)

`scripts/family.py`, `scripts/analysis/ledger.py` and
`configs/families/ycards-step2.json` are built (spec build steps 1-4; review
fixes in be768d2). The dry run of the family binds 21 bursts (0276-0278,
0305-0322) and lists 63 reads (cell books a and b and the boss replay per
net), the table and the headline follow-up. The ledger reproduces data5k
-3.30, data20k -1.45 and data40k -0.16 (`measurement/ledger@cells`).

- **Reads cancel instead of parking when their burst fails** (review
  must-fix): the runner parks an `--after` job whose dependency is parked,
  so one failed burst among 21 would have stalled the table. A cancelled
  read is done, the table goes ahead and shows it missing; `queue` run
  again adds it again. Alternative: park and re-run `queue` by hand (the
  session-per-step pattern this lane removes).
- **The queue waits.** Bursts 0305-0322 are parked on 0304's curve check
  (largest curve difference 0.00219), which is yardstick-cards' to settle.
  Queued now, their 57 reads would be cancelled at once and the table
  would write a failing verdict from six nets. So the family is queued
  once those bursts are pending without `parked` (unparked or queued
  again): this lane's next session checks `jobs.py status` and runs
  `family.py queue configs/families/ycards-step2.json` from its worktree;
  the yardstick-cards worker should not queue those reads by hand.
  Alternatives: queue now and re-run later (a junk table and 57 cancelled
  jobs in between); take the fallback family (act1-cards-zero-shot), not
  yet written as a family file. Most reversible: wait, nothing queued.

## Lane turn-start-leaf closed (2026-11-07)

Outcome: **go**. The search flag `@tsl1` (the one-turn leaf scored on a copy
after the player's turn-start hooks that need no chance have run; draws left
out) gives the 10-29 net @hpb0.01 +7.54 (1.10) HP and +0.149 (0.028) clears
on held-out Demon Form decks, one turn deep on both cell books, with train
decks -0.02 (0.15) and the other held-out decks +0.04 (0.08)
(`measurement/turn-start-leaf@cells`). The only other sequences it moves
are Brutality decks, the one other turn-start power in the books. On the
generated-power bench (elites and bosses) generated `OwnerTurnStart`
powers gain +0.243 (0.054) wins and turn-end powers stay level, so the
repair carries to unseen powers on that trigger with no games: a goal-1
repair, zero-shot. It beats the trained repair (burst8 s1, +6.13 (1.94) on
the same decks). Results doc `docs/research/turn-start-leaf-2026-11-07.md`,
"Result: go".

CPU: 0.71 thread-hours (0324 0.23, 0325 0.20, 0326 0.28) against the
1 cpu-h cap.

Not decided here (the navigator's, woken by the charter's `on-close: wake on
go`): whether `tsl1` becomes the default leaf for one-turn screens and
goal-1 reads (it moves every one-turn comparison on turn-start powers, so
older one-turn files on such decks would need replaying), and whether it
adds anything to the two-turn product, where the first tick is already
inside the search.

**Reopen if:** turn-start hooks the flag leaves out (draws, random targets,
exhausts, effects that read the hand) show a one-turn cost against the
heuristic of more than 0.1 wins on the generated bench's elites and bosses
with `@tsl1` on, or the two-turn product with `tsl1` is read and the second
turn's turn-start tick shows the same leaf-horizon cost.

## yardstick-cards step 3: the card-patch bench as pack variants read against a pack copy; the spec confirmed and built (on the owner's behalf, 2026-11-07)

Spec `docs/specs/mutated-cards.md`, confirmed under the mandate. Choices, each provisional:
- **Variants are pack cards, read against a pack copy of the parent.** A
  card's numbers are not in the combat state (the monsters bench patches
  the state), and the per-copy overrides (`registry::Overrides`) hold only
  damage, so a variant is a generated card loaded with `sts.load_content`.
  An exact pack copy of Demon Form plays almost but not exactly like the
  official card (16 fights x 4 seeds: 54 of 64 heuristic and 57 of 64
  one-turn outcomes identical, mean end HP within 0.13), so each modifier's
  parent is its card's copy, and the official games are kept as a check
  line. Alternatives: an engine cost/amount override (engine work, off the
  lane's scope); patching `content/cards.json` per process (changes the
  rules version and the official ids every net knows).
- **Players heuristic, one (`@hpb0.01`) and tsl (`@hpb0.01@tsl1`), one turn
  deep.** tsl is the turn-start-leaf lane's go (measurement/turn-start-leaf@cells);
  it costs a third more games and tests the prediction that the turn-start
  pairs' cost is the leaf's horizon. Alternative: one only (the charter's
  "net"), leaving the horizon question to a second run.
- **Seven modifiers fixed before the first read:** the plain control
  `bash-c1-d5` and six power pairs (Inflame, Demon Form, Metallicize x2,
  Combust x2), table in the spec; prediction written there.
- **200 starts per parent x 16 seeds** instead of the charter's 200 x 8:
  the run is cheap (a 1224-game smoke run took 8 s at 3 threads), and the
  stop needs se <= 0.02. Alternative: 8 seeds and a second run if se misses.

## After turn-start-leaf: the turn-start leaf for goal-1 card reads, the product unchanged, probes on burst8 and the headline (on the owner's behalf, 2026-11-07)

What the go says (`measurement/turn-start-leaf@cells`; the navigator's read
of the same files against the heuristic, `cards_by_half.strata_row` on
`heuristic-bcbb0e.json` and `heuristic-b500.json`): one turn deep, the
10-29 net's edge over the heuristic on held-out Demon Form decks goes from
-4.12 (1.41) HP and -0.144 clears with the plain leaf to +3.43 (1.13) HP
and +0.006 clears with `@tsl1`, beside +3.67 on train decks and +5.45 on
the other held-out decks (both unchanged by the flag). So the Demon Form
half of the unseen-cards cost was the leaf's horizon, and with `@tsl1` no
unseen official card costs the net at 2 se one turn deep; the shortfall
left on Demon Form decks against the other held-out decks is about 2 HP at
about 1.4 se. On generated cards the repair is on the trigger, not the card
(`OwnerTurnStart` powers +0.243 wins). The review of 2026-11-06 predicted
this ("the one-turn card cost is mostly an artefact of where the one-turn
leaf sits").

Decided:

1. **`@tsl1` is the leaf for goal-1 reads on content holding a power with
   an `OwnerTurnStart` hook** (`yardstick-cards` step 3,
   `act1-cards-zero-shot`), with the plain leaf as a second column where
   the parent card has such a hook, so the table shows both the cost the
   search removes and the cost left. The cell controls with the flag are
   `results/gauntlet/net1029-hpb0.01-tsl1.json` and `-tsl1-b500.json`
   (0324, 0325). On decks without such a power the two leaves play the same
   sequences (469 of 500 train sequences identical, every changed one a
   Brutality deck), so older one-turn files on other content stand and
   nothing is replayed. Alternatives: the flag everywhere now, controls
   replayed (passed over: the headline setting one turn deep has never been
   played with it, and its sim chooser's trial fights change picks, so the
   whole sequence changes; job 0333 reads it first); the plain leaf
   everywhere (passed over: goal 1's number would report a cost a search
   rule removes with no games, and the owner's yardstick measures the
   player's novelty cost, `decision/goal1-yardstick`).
2. **The one-turn headline control gains an `@tsl1` twin** (job 0333, fixed
   n 500, own picks). The navigator reads it: not a protocol fail, and
   `yardstick/one-turn-controls` is re-set to the `@tsl1` files for every
   one-turn screen; a fail keeps the flag to goal-1 card reads.
3. **The product stays as it is** (`product/net`, no `tsl1`). Two turns
   deep the search already plays Demon Form's first tick (+8.4 HP over one
   turn on its decks); the flag would add the third turn's tick, on the few
   headline decks that take a turn-start power (the net's chooser takes
   Demon Form 0.19-0.25 of the times offered). Expected under 0.01 clears
   against a detectable effect of about 0.05: not proposed (the trade-off
   rule). Reopen when Act 1's Berserk joins the headline's offers, or by
   the lane's reopen condition.
4. **`yardstick-cards` charter, step 3 re-set:** it plays `@tsl1`; its
   prediction is re-written: a modifier on a turn-start power's amount or
   cost is predicted level under the flag (the first tick lands in the
   leaf), so the column now asks whether the net prices a power's later
   ticks, which the leaf shows only once. Step 2's bursts stand (their
   reads stay on the plain leaf: whether games teach a recurring power is
   a question about learning, and the plain leaf is where the cost was);
   jobs 0327-0332 ask how much of what a burst learned is the first tick.
5. **`act1-cards-zero-shot`'s charter** reads both leaves; Berserk's
   prediction splits: predicted to cost on the plain leaf, open under
   `@tsl1` (its tick is energy, which the leaf now shows).
6. **Probes queued in lane `main`** (pinned to 28c9348, the snapshot the
   0324-0326 read ran in, so the files pair byte for byte): 0327-0332, the
   three burst8 nets `@hpb0.01@tsl1` on both cell books, read by stratum
   against the 10-29 net's `@tsl1` files: Demon Form decks at least +2 HP
   at 2 se says nets learn more of a turn-start power than its first tick
   (`coverage-pretrain` keeps its case for these powers); within 2 se of
   zero says what burst8 learned there is the tick, and with the flag
   turn-start coverage needs no games. 0333, above.

Facts: `cause/unseen-cards-half-edge` and `cause/gains-from-search` re-set
from this entry; `lane/yardstick-cards` re-set (step 3).

Also read here (the navigator's probe sheet of 2026-11-06):

- **0296-0298** (`measurement/fresh-control@cells`): on fresh cell
  sequences 1000-5999 the product recipe's seed twins read -0.21 (0.15) and
  +0.25 (0.14) HP, -0.004 and +0.004 clears, against the 10-29 net. The
  s1 net's lead of 0.47 HP and 0.056 clears on 0-499 was the book's draw,
  not a better net (open question 14 answered). The control's ten blocks
  of 500 spread as independent draws (block-mean sd 0.98 HP against 1.08
  expected). A same-net read paired on this range detects about 0.4 HP.
- **0299-0300**, read through the ledger (`measurement/ledger@cells`): the
  second 80k net reads -0.50 over both books, the first -1.86 on one book;
  80k games sit level with 40k (-1.08, -0.37, +0.98 over three seeds)
  inside the seed spread. `decision/no-goal2-training-arms` re-set: the
  data curve rises to 40k and stops.

## Lane hands-where-small opened (on the owner's behalf, 2026-11-07)

The exploration slot that `turn-start-leaf` held is free, and no open lane
is `kind: exploration`. Opened: `hands-where-small` (backlog candidate,
review 2026-11-06 direction 7), exploration, goal 2, cap 9 cpu-h, end
2026-11-13. Its question: does searching again with 16 sampled hands where
the 4-hand tree is small cut the product's HP lost at elites? It is the one
in-fight knob with an exact measurement behind it (endgame regret 0.0089 at
4 hands, 0.0030 at 16, paired 0.0059 (0.0016), a figure no skeptic checked)
and it was closed on how often picks agree, never on their value. Rated a
long shot: every in-fight lever read two turns deep since the product was
set is worth under 0.03 clears, and elites lost nothing to three turns. Its
first step re-checks the regret figure in seconds, so it fails fast. A null
is still a result: then in-fight search is spent and the direction closes
with its interval. It also uses CPU on goal 2, whose CPU weight (0.4,
`docs/direction.md`) has gone unused while every open lane is goal 1.
Estimate 6 cpu-h (both elite arms two turns deep, 2.5-4.4 GB).

Alternatives passed over: `ceiling-player` (a long shot whose decisive
outcome is unlikely, since a search handed the draw order should sit far
above the product); `race-price` (code for a cost every hand-set price so
far moved by about 1 HP); `heuristic-games-burst` (its first test runs
inside `yardstick-cards` step 2, the heuristic's 400 games); `exact-referee`
(after `act1-cards-zero-shot`); `act1-cards-zero-shot` (project, the first
ready charter: it opens in `session-free-reads`' slot); and
`generated-enemies-bench` (project, the second ready charter now that block
M5 has landed).

This makes four open lanes for a few days: `session-free-reads` has only
its first family's queue command and table left, and closes when the
yardstick bursts' reads finish. Shares (`jobs/lanes.json`):
yardstick-cards 45 (was 55: its bursts are nearly done, its reads are
small), act1-content 22, hands-where-small 15, session-free-reads 8 (was
13), main 10, filler 0.

## yardstick-cards queues the step-2 family itself: its bursts are live and session-free-reads has no wake left (on the owner's behalf, 2026-11-07)

The entry "session-free-reads: built; the first family's queue waits until
yardstick-cards settles 0304" left `family.py queue
configs/families/ycards-step2.json` to session-free-reads' next session,
once bursts 0305-0322 were no longer parked. They were unparked at 05:33;
0304-0321 have ended ok and 0322 is running (the family's reads wait on it
with `if_passed`). The dry run binds all 21 bursts. No session-free-reads
session has started since: its idle wake for rev 2 is already marked woken,
so no event would start one, and the 63 reads would wait. The yardstick-cards
worker therefore runs that same command from its worktree (pinned to main's
HEAD). The family's measure is untouched: the table is still written by its
job with no session between queue and table; session-free-reads' next
session records the step and reads the checkpoint. Alternatives: wait for a
session-free-reads session (no wake would start one before the navigator's
22:15 wake); queue the 63 reads by hand (the decision forbade it, and it
would not test the family). Reversible: `jobs.py cancel` the family's jobs.

## After burst8 x turn-start leaf: what burst8 learned on Demon Form decks is the first tick; coverage-pretrain folds into the enemies bench; step-2 nets read against the turn-start leaf (on the owner's behalf, 2026-11-07)

Read (jobs 0327-0332, the navigator's probe sheet; `cards_by_half.strata_row`
on the three burst8 nets `@hpb0.01@tsl1` against the 10-29 net's `@tsl1`
files, both cell books, one turn deep; `measurement/burst8-tsl1@cells`):

| stratum | n | end-HP, pooled (se seq, se nets) | clears | per seed s1 / s101 / s201 |
|---|---|---|---|---|
| train | 500 | -0.68 (0.39, 0.52) | -0.029 (0.013) | +0.01 / -1.71 / -0.36 |
| held-out | 326 | -0.99 (0.48, 0.11) | -0.020 (0.013) | -0.76 / -1.09 / -1.12 |
| held-out DF | 174 | +0.48 (0.81, 0.67) | +0.015 (0.021) | +1.66 / -0.67 / +0.45 |

The pre-set rule (decisions "After turn-start-leaf", item 6): within 2 se of
zero, so what burst8 learned on Demon Form decks (+6.10 HP on the plain
leaf) is the first tick, which the turn-start leaf gives with no games.
Under the leaf the burst8 nets keep their cost elsewhere (about -0.7 HP on
train decks and -1.0 on the other held-out decks, -0.02 to -0.03 clears),
so with the turn-start leaf on they are net losses everywhere. Against the
heuristic they read +2.98, +4.46 and +3.91 HP on the three strata, below
the 10-29 net's +3.67, +5.45 and +3.43.

What it changes:

1. **`coverage-pretrain` is folded into `generated-enemies-bench`'s
   coverage curve.** Its evidence was this transfer on cards; on cards the
   transfer was the tick, and with the leaf no measured card cost is left
   for coverage to remove. Where a measured zero-shot cost remains is
   monster mechanics (powers that punish an action, growth;
   `cause/novelty-is-horizon`), and the bench's k-families curve is the
   coverage question asked there. Alternatives: keep it held on step 2b
   (passed over: a composition pass on the Demon Form row would now show
   nets composing a tick the search already plays); retire it (passed
   over: the coverage question stands for monsters).
2. **`yardstick-cards` step 2 and 2b run as queued** (the family
   0339-0405, plain leaf, about 10 thread-hours on an idle machine): they
   still answer how fast games teach a payoff the leaf cannot see and
   whether the net composes a trigger and an effect learned apart. But no
   step-2 or 2b net is a candidate for the chooser or the product unless
   its three seeds also read level or better than the 10-29 net with the
   turn-start leaf on all three strata (charter re-set; the best arm's
   three nets get those six reads). Alternatives: cancel the plain-leaf
   reads and read every arm with the leaf (passed over: the learning
   question is cleaner where the cost was, and the jobs are queued and
   cheap); let a plain-leaf pass reach the chooser (passed over: this read
   shows such a pass is the tick).
3. `cause/unseen-cards-half-edge`: its second exit is answered (nets
   learn no more than the tick on this row); re-set. `cause/gains-from-search`
   re-set: the one content-driven training gain on file was the tick.

## After the turn-start leaf on the one-turn headline: the one-turn controls stay plain; the chooser's horizon overpicks Demon Form (on the owner's behalf, 2026-11-07)

What the read says (job 0333, `results/gauntlet/net1029-hpb0.01-tsl1-starter-simboss.json`
against `results/gauntlet/net1029-hpb0.01-starter-simboss.json`, sequences
0-499, own picks, fixed n 500): the 10-29 net `@hpb0.01@tsl1` minus the same
net on the plain leaf reads +0.12 (0.48) HP and +0.008 (0.015) clears
(0.688 against 0.680); train -0.07 (0.26) HP, held-out +0.30 (0.93) HP.
The protocol run post hoc (H1 +1.5 HP, blocks of 50) fails at n 394: no
+1.5 HP gain. 379 of 500 sequences end on the same HP.

Underneath the level total are two parts that cancel. The sim chooser's
trial fights play the same leaf, so with the flag it takes Demon Form 120
of the 245 times offered (0.49) against 42 of 248 (0.17) on the plain
leaf; Brutality is unchanged (0.10 against 0.11). Where both arms took
Demon Form (42 sequences) the flag gains +9.93 HP and +0.286 clears, the
fighting gain the cell books showed (`measurement/turn-start-leaf@cells`,
+7.54 HP). Where only the flagged arm took it (78 sequences) it loses
-4.55 (2.27) HP and -0.115 (0.066) clears: deaths move from the boss (16
to 10) to the second elite (4 to 14) and the hallway after it (3 to 8);
boss wins given arrival rise 0.78 to 0.82. The other 380 sequences read
-0.01 (0.22) HP.

Why: the sim chooser (`scripts/gauntlet.py` `sim_choose`) scores an option
by its fights against the next floor plus fights against the boss at the
post-rest HP, the two parts weighted alike. The run's HP goes at the two
elites (`cause/boss-deaths`: 17.3 and 13.8 HP per elite), which the
horizon sees only when the next floor is one. A card that pays at the boss
and costs on the way is overpicked as soon as the trial fighter plays it
right. The product (two turns deep; its trial fights one turn deep on the
plain leaf) takes Demon Form 39 of 250 times (0.16) and clears 0.821 where
it took it against 0.835 where it did not: no sign of the cost at that
rate.

Decided:

1. **The pre-set rule holds: a protocol fail, so `yardstick/one-turn-controls`
   stays on the plain-leaf files** and `@tsl1` stays the leaf for goal-1
   card reads on the cell books (`decision/turn-start-leaf-reads`, re-set),
   where picks are fixed and the chooser does not enter. Alternatives:
   switch the controls anyway because the total is level (passed over: the
   rule set before the read said a fail keeps them, and a flagged headline
   control would carry the overpick into every one-turn screen); confirm
   on sequences 500-999 (passed over: a level total built from a +10 HP
   and a -4.5 HP part reads level at any n; the open question is the
   chooser's, not the leaf's).
2. **`cause/chooser-horizon` records the finding**: repairing the trial
   fighter does not repair the pick, because the horizon leaves out the
   elites. The chooser mismatch in backlog question 7 (trial fights rate
   Demon Form by a fighter that misplays it, "worth at most about +0.01
   clears") is worth about nothing on this pool under this horizon.
3. **A backlog candidate, `elite-horizon-chooser`** (the sim chooser's
   horizon gains a part against the next elite at the HP it would start
   at), parked under the direction's avoid list (card picks before Act 1's
   cards are in the engine) beside `value-chooser`, with the same reopen
   condition. Alternatives: probe it now on today's pool (passed over:
   direction, Avoid); drop it (passed over: it is the first chooser error
   with a measured mechanism and a sign, and Act 1 adds about eight more
   cards that pay over later turns, backlog question 11).
4. **The product stays without the flag**, in its trial fights too: there
   it would raise the Demon Form picks the same way.

## yardstick-cards step 3's adapted column: one burst recipe on the two modifiers that cost, retention on the same fights (on the owner's behalf, 2026-11-07)

Spec `docs/specs/cards-adapted-column.md`. The first card table
(measurement/mutated-cards@stage-a) has two modifiers past 2 se with the
turn-start leaf, `inflame-turn1` and `metal-c2-a5`; the charter gives each
an adapted column on three burst seeds (decision/burst-adapted-column).

1. **Recipe: step 2's net-g400** (the parent's own one-turn games, 400 per
   group, one game set per modifier, training seeds 1-3) on varied Ironclad
   setups with 1-2 copies of the variant (finetune's generated-content
   path, pack `data/bench/mutated_cards_pack.json`). Alternatives: the
   heuristic's games (passed over: step 2 reads which player teaches best,
   and this read is the size the charter names, not a player comparison);
   swapping the parent card in product-file decks (passed over: the read's
   fights would then be the training fights).
2. **Retention is the parent copy and official rows of the same 200
   fights**, not the cell gauntlet and boss replay. Alternatives: add the
   cell books (passed over: 6 more reads of about 6 minutes each for a
   question step 2's family already answers for net-g400 bursts; add them
   if a modifier is repaired and its net is read further).
3. **Prediction before the run** (spec): inflame-turn1 regains much of its
   plain-leaf cost and little of the tsl cost (games teach the first
   tick, measurement/burst8-tsl1@cells); metal-c2-a5 gains alike on both
   leaves.

## Lane hands-where-small closed (2026-11-07)

Outcome: **fail** (the stop rule's fail branch). Step 1 passed: on the 448
deeper exact puzzles 16 sampled hands cut the product's regret from 0.0063
to 0.0027, paired 0.0036 (0.0012), smaller than the review's 0.0059. Step 2
passed at its bar on the point estimate: 16 hands everywhere save 0.34
(0.16) HP per elite on the 498 floor-9 elites, two turns deep, at 1.60x the
time, no win moved (`measurement/hands16@elite-replay`). Step 3 failed: the
adaptive rule (16 hands again where the 4-hand tree is uncut and under
25,000 nodes, 25.7% of decisions) saves 0.21 (0.13) HP per elite at 1.39x
the time, against a bar of 0.3 at 2 se (`measurement/hands-adaptive@elite-replay`).
Both gains sit on starts at 60+ HP, where wins aren't at stake, and are nil
at 40-59 HP, where most fights start. In-fight search, by sampled hands, is
spent at about 0.2-0.35 HP per elite on the headline setting; the product
keeps 4 hands. Results doc `docs/research/hands-where-small.md`, "Step 3:
the adaptive rule".

CPU: 4.3 thread-hours (0342 1.71, 0343 1.06, 0344 0.01, 0345 1.48; the
puzzle screen ran in seconds) against the 9 cpu-h cap; the opening entry
estimated 6.

The charter's `on-close: wake on go` does not fire, so the slot takes the
first ready charter (`act1-cards-zero-shot`, entry "Lane act1-cards-zero-shot
opened" below).

**Reopen if:** a setting where fights start low makes HP at elites decide
wins (later acts, ascension, or a run layer that enters elites under 40 HP
more often than the headline's 17%), and 16 hands everywhere save at least
0.3 HP per elite at 2 se on fights starting under 60 HP; or a search
change makes 16-hand trees cost under 1.2x the 4-hand time (then
16-everywhere's 0.34 would clear a tighter bar on its own).

## Lane act1-cards-zero-shot opened (2026-11-07)

`hands-where-small` closed on its fail branch (entry above) and its charter's
`on-close: wake on go` did not fire, so its slot takes the first ready
charter in the navigator's backlog order: candidate 4, `act1-cards-zero-shot`
(the navigator's ranking, backlog "Open lanes (2026-11-07)": "The next free
slot opens `act1-cards-zero-shot` (candidate 4, the first ready charter)").
Project, goal 1, cap 3 cpu-h, end 2026-11-14; the charter is the backlog's
ready charter as written, now the fact `lane/act1-cards-zero-shot`. It takes
hands-where-small's share in `jobs/lanes.json` (15). The slot was the
exploration one; no ready charter is `kind: exploration`, so the portfolio
has no exploration lane until the navigator writes one.

## yardstick-cards: the cap lands mid-queue; the cell-book reads first, step 3's adapted column next, the boss replays last (on the owner's behalf, 2026-11-07)

The lane has used 35.0 of its 45 cpu-h (health.json `lane_cpu_h`, 08:49).
What is queued costs about 26 more, measured on the family's first eight
reads (0339-0348, 3 threads: book a 6.4 min, book b 6.0 min, boss replay
9.4 min, so about 0.31 and 0.47 cpu-h): 35 cell-book reads left (about
10.9 cpu-h), 18 boss replays (about 8.5), the headline read 0405 (about 2)
and step 3's adapted column 0409-0421 (about 5: its bursts reuse the
net-g400 recipe, which ran 0.5-5 min per burst in step 2). The earlier
estimates (step 2 about 6, step 3 about 5) left out the 63 family reads.
In queue order the cap would land halfway through the family, with
neither the checkpoint's strata nor the adapted column complete.

The order is now: (1) the cell-book reads of all seven arms, which are all
the checkpoint needs (the Demon Form stratum and the two retention strata,
three seeds per arm); (2) step 3's adapted column (the goal-1 number on the
owner's modifier pairs, the lane's goal); (3) the 18 boss replays
(0352-0403, every third), now `--after 0421-mutate-cards`; then the table
0404 and the headline 0405 as before. About 10.9 cpu-h sit in (1), so the
cap lands near its end; (2) and (3) then wait for the close, whose
on-close is `wake always`: the navigator sees this entry and decides
whether the rest runs (a new cap) or is cancelled.

Alternatives: keep the queue order (passed over: the cap stops the family
with every arm half read); cut the boss replay to 2 seeds (passed over:
it changes the family's design and saves about 4 cpu-h, still not enough);
step 3 first (passed over: the checkpoint and the stop rule's fail branch
both turn on step 2's reads, and they are nearly paid for). Reversible:
`jobs.py set <id> --after ""` on the boss reads.

## Exhaust-triggers spec (C2): fire after the card, owed turn-end draws (on the owner's behalf, 2026-11-07)

Spec `docs/specs/exhaust-triggers.md` confirmed by the act1-content lane
worker: building block C2, Dark Embrace, Feel No Pain and Sentinel (6
entries). Three choices, all reversible: (1) a power's `CardExhausted`
hooks fire once the card in play has been placed, once with the count of
cards it exhausted (the game's bottom-of-queue order; alternative: fire
inline per card, which can pause a draw inside `ExhaustHand`); (2) a
turn-end draw from a trigger (ethereal cards with Dark Embrace) is added
to the next turn's draw (alternative: a new stage before the monsters'
moves where the draw can pause; the two differ only when the draw pile
runs out); (3) a card's own `exhausted` effects are `GainEnergy` and
`Block` only (alternative: the full hook vocabulary, which no content
needs). C1's count-then-exhaust order is re-checked there and stays
correct. Provisional until the build lands.

## Lane act1-cards-zero-shot closed (2026-11-07)

Outcome: **done** (the stop rule: the table is recorded with the
prediction beside it), with the record's prediction shown wrong. One turn
deep with `@tsl1`, 19 of the 22 Act 1 pack cards play at no measured cost
against the heuristic with no training; three in-turn exhaust skills cost:
Disarm -0.118 (0.032) wins, Impervious -0.122 (0.034), Intimidate -0.062
(0.029), mostly in elite cells. Berserk, predicted to cost on the plain
leaf, leads instead (+0.070 (0.032)): both players lose wins with it, the
heuristic more. The status-later, unreadable-trigger and new-atom cards
are level (`measurement/act1-cards@zero-shot`; results doc
`docs/research/act1-cards-zero-shot-2026-11-07.md`, "Read"). The in-turn
rule of `cause/unseen-cards-half-edge` is flagged: it holds for damage and
cards played, not for every number in the state. Why the three cost is a
hypothesis (negative enemy Strength, Weak on all enemies and 30 block lie
outside the training range), not read.

The charter's last part, the product two turns deep on the cards that cost
under `@tsl1`, did not run: 2,004 fights at 7.2 fights per thread-minute
(`how/two-turn-games`) is about 4.6 cpu-h against the 1.4 left in the cap.
It goes to the navigator with the wake.

CPU: 1.59 thread-hours (0428 0.26, 0429 0.80, 0430 0.53, 0431 0.01)
against the 3 cpu-h cap; the opening estimate was about 1.9.

The charter's `on-close: wake if a card other than Berserk costs at 2 se
under @tsl1, or Berserk does not cost on the plain leaf` fires on both
branches: the navigator decides the next lane (wake `lane:act1-cards-zero-shot`),
and the slot stays empty; its share (15) goes to the other open lanes in
`jobs/lanes.json`.

**Reopen if:** a net that reads these numbers in range exists (a training
on new content such as the backlog's all-content net, or new inputs for
enemy Strength below zero and large block), and the three cards' lead
returns to level would show it; or a probe of the net's leaf value on
states with and without negative enemy Strength, enemy Weak and 30 block
finds the value blind to them (then the cause is read, and a fix has a
target); or two-turn reads get cheap enough (under about 1 cpu-h for 2,000
fights) to read the three cards two turns deep within a small cap.

## After act1-cards-zero-shot: the in-turn rule narrowed; lane leaf-blind-numbers opened as the exploration lane; the two-turn read of the three cards not run; simulated-effect-inputs retired (on the owner's behalf, 2026-11-07)

The read (`measurement/act1-cards@zero-shot`): one turn deep with `@tsl1`,
19 of 22 Act 1 pack cards level against the heuristic, three in-turn
exhaust skills cost (Disarm -0.118 (0.032), Impervious -0.122 (0.034),
Intimidate -0.062 (0.029) wins, mostly in elite cells), Berserk leads.

**What it says beyond its question.**
- The in-turn rule of `cause/unseen-cards-half-edge` holds for effects
  the net reads as damage dealt, HP kept or cards played; it does not hold
  for every number left in the leaf state. The fact is re-set with the
  narrowed rule.
- The eight cards that were `simulated-effect-inputs`' cheapest probe (the
  six C1 new-atom cards, and Double Tap and Flame Barrier, built on
  triggers the product net cannot read) are all level: its kill-fast rule
  fires, and it goes to "Checked and not proposed". Blindness to an atom
  costs nothing where the atom's effect lands inside the turn; what cost
  here is a number the net can read, not an atom it cannot.
- A code read (the navigator's, no CPU) gives one concrete mechanism for
  Impervious. The plain leaf is the state at the first chance event after
  EndTurn (`engine/src/search.rs` `child`; `engine/src/chance.rs`
  `request_monster_move`). When a living monster's next move is random,
  the leaf sits at `MonsterRolls`, before `StartTurn` clears the player's
  block (`engine/src/state.rs`, `Stage::StartTurn`), and the net reads that
  leftover block (`py/src/features.rs`, player scalar `block`, beside
  `pending_monster_move`); when every next move is fixed, the leaf sits at
  the draw after `StartTurn`, with block 0. The same position reaches the
  net in two forms, and leftover block is worth nothing there (no
  block-keeping effect is in play). A 30-block card leaves far more block
  than the training decks do, in exactly the first form. Disarm's -2
  Strength is permanent and real, so its question is whether the net
  prices a Strength below zero, which training never showed it.
  Intimidate's Weak 1 has already counted down at the leaf (`end_turn`
  runs the `RoundEnd` countdowns before `MonsterRolls`), so its value is
  all in HP taken during the monsters' turn and no leaf number explains
  it; with 22 cards read at 2 se about one false hit is expected, and
  Intimidate (2.1 se) is the likeliest. None of this is read yet: the
  lane below reads it.

**Two-turn read of the three cards: not run.** Trade-off: the product's
decks hold no pack content yet (`act1-content`'s list: pack content in
`gauntlet.py`'s decks and offers), so a two-turn read cannot move the
headline; for goal 1 it would show whether depth hides the cost, at about
4.6 cpu-h, where a leaf-value probe names the cause in minutes. It stays
under the close's reopen-if.

**Lane leaf-blind-numbers opened (on the owner's behalf, 2026-11-07)**,
kind exploration, in the portfolio's exploration slot (empty since
`hands-where-small` closed). It is a fourth lane: allowed because
`session-free-reads` is within days of its end (its last job, 0404, writes
the family table) and `yardstick-cards` stands at 39.9 of its 45 cpu-h.
Mechanism and rating: backlog candidate `leaf-blind-numbers`. Rated
**even** that step 2 finds a number the net misprices (for: the code
read's two leaf forms; a Strength below zero never occurs in training;
against: Shockwave's Weak and Vulnerable and Ghostly Armor's 10 block read
level, and the net has seen leftover block at `MonsterRolls` leaves
throughout its training), **a long shot** that a search-side fix brings
two of the three cards level; if leftover block is the cause, the fix
touches every leaf the product searches, so a go is read on the one-turn
headline too. About 2 cpu-h (cap 3). Alternatives passed over:
`generated-enemies-bench` (the ready project charter; it stays first for
the next project slot, which `yardstick-cards`' cap frees within the day);
the two-turn read (above); the `all-content-net` training (new content,
allowed by the training rule, but about 21 cpu-h before anyone knows the
three costs are an input-range problem; this lane's step 2 is that
evidence); leaving the exploration slot empty until `act1-content` lands
its next block (days).

Shares (`jobs/lanes.json`): yardstick-cards 46, act1-content 24,
leaf-blind-numbers 15, session-free-reads 5, main 10, filler 0.

## act1-content: next block S1, more pack cards and powers per fight (on the owner's behalf, 2026-11-07)

After C2 the charter orders the blocks by what each unblocks, counting the
review's steps to a deck or character made of data. Chosen: S1, 32 card
slots and 24 power slots per fight (spec `docs/specs/pack-slots.md`).
Alternatives: C3/C4/C5 (2, 2 and 1-3 cards each, no structural step), E1
encounters as data (4 encounters; it needs Shield Gremlin's M6 and Red
Slaver's M7 before the Gremlin Gang plays in full), upgrade links (useful
only once decks of pack cards can be played). S1 comes first because every
other structural step (pack content in `gauntlet.py`, a data character)
needs decks with more than 8 pack cards, and 25 Ironclad cards are
written as pack entries that today can't share a deck beyond 8.

Provisional, in the spec: 32/24 (alternatives 16/16, 61/34); slot 0-7 and
variant ids kept so no encoding changes (alternative: renumber); the
binding stays in the state by value unless `series_speed` breaks its bar
(then intern the slot arrays). All reversible: constants and one helper
pair.

## yardstick-cards step 2: the turn-start-leaf gate read for net-g1600 as well as two-g400, ahead of the boss replays and the headline (on the owner's behalf, 2026-11-07)

Step 2's table passes two arms (docs/research/learned-play-results.md, "Step 2,
all arms but neither's last two seeds"): two-g400 (+4.48 HP on Demon Form
decks, best) and net-g1600 (+3.77). burst8's gain of the same kind vanished
under the turn-start leaf (measurement/burst8-tsl1@cells), so the charter's
gate (the best arm's three nets `@hpb0.01@tsl1` on both cell books against the
10-29 net's `@tsl1` files) decides whether either arm learned more than the
first tick. Decided: queue the gate for both passing arms (12 reads, about 2.7
thread-hours) and run them before the 18 boss replays (which wait on step 3's
0421 anyway) and before 0405, the best net's headline read.

- Why both: net-g1600 is the goal-1 answer (the net's own games, 1.8
  thread-hours of bursts), two-g400 the stronger teacher at 7.7 times the cost;
  if only one keeps its gain under @tsl1, that is the finding.
- Alternatives: the best arm only, as the charter says (1.4 thread-hours;
  leaves the cheap arm's question open); no gate before the headline (0405
  would spend 2 thread-hours on a net the gate may rule out of the product
  path).
- The lane is at 43.9 of its 45 CPU-hours; neither's last reads and these
  gates put it about 3 over, and the close (on-close: wake always) leaves the
  boss replays, the headline and step 3's adapted column to the navigator.
  Reversible: the jobs can be cancelled before they start.

## Lane yardstick-cards closed (2026-11-07)

Outcome: **done at the cap**. The stop rule's parts are met: steps 2 and 2b
read on all seven arms and step 3's first one-turn table recorded (every
modifier's se at most 0.009 wins). What it found, goal 1's number on the
cards rung:
- **Zero-shot cost:** of the ten held-out official cards one costs, Demon
  Form (about 9.5 HP and 0.20 clears on its decks), because its value lands
  after the one-turn leaf (`cause/unseen-cards-half-edge`,
  `measurement/cards-by-card@cells`).
- **Games repair only the first tick.** Bursts on Demon Form decks raise
  them on the plain leaf (net's own games at 1,600 per group +3.77 (0.90)
  HP, the two-turn product's 400 +4.48 (0.60); 100 and 400 own games do
  not), but read with the turn-start leaf both gains vanish (-0.42 (0.94)
  and +1.19 (0.75)) and about 0.03 clears is lost on every stratum
  (`measurement/demon-form-games@cells`, `measurement/demon-form-games@tsl1`);
  burst8's transfer (+6.10) was the same first tick
  (`measurement/burst8-tsl1@cells`). The turn-start leaf gives that tick
  with no games.
- **No composition (2b):** the trigger and the effect learned on different
  cards give nothing on the pair (parts -0.13, neither -0.78, level).
- **The owner's modifier pairs (step 3, `measurement/mutated-cards@stage-a`):**
  the in-turn control is level; pooled over six power pairs level on both
  leaves; inflame-turn1 (-0.018 (0.005) wins @tsl1) and metal-c2-a5
  (-0.021 (0.006)) cost beyond the heuristic, both with value in a power's
  later ticks.
So the cost of new card content at the one-turn leaf is value that recurs
past the leaf; the search-side leaf repairs the first occurrence; the
later ticks are repaired neither by the leaf nor by games at these sizes.

CPU: 47.4 cpu-h (health.json `lane_cpu_h`) against the cap of 45 (opened
at 38, raised to 45 on 2026-11-06); the opening entry estimated about 23
more at that raise. The overrun is the twelve gate reads and neither's last
seeds, decided in the gate's entry above.

Left queued (lane `yardstick-cards`, now at the default share of a lane
missing from `jobs/lanes.json`), for the navigator to keep or cancel:
step 3's adapted column 0409-0421 (about 5 cpu-h: bursts on the two
modifiers that cost, the goal-1 number on the owner's pairs; worth keeping
if goal 1 wants the games curve on a later-tick cost), the 18 boss replays
0352-0403 (about 8.5 cpu-h; designed for a net on the product path, which
the gate ruled out: cancel is the lane's recommendation), the table write
0404 (after the boss replays) and the best net's headline read 0405 (about
2 cpu-h; the gate rules the net off the product path: cancel recommended).
Not cancelled here, because the previous entry left that choice to the
navigator and the adapted column starts first anyway (the boss replays wait
on 0421).

The charter's `on-close: wake always`: the navigator decides the next lane
(wake `lane:yardstick-cards`); the slot stays empty and its share (46) goes
to the other open lanes in `jobs/lanes.json`.

**Reopen if:** a player sees a recurring power's later ticks (a leaf that
prices a power's per-turn effect over several turns, such as a horizon
estimate from the engine's own power hooks, or a cheap two-turn read under
about 1 cpu-h per 2,000 fights), and then games could be read for what they
add beyond it; or a training target that carries value from several turns
ahead (multi-turn returns rather than one-turn labels) exists, and a burst
on Demon Form decks read @tsl1 above +2 se would show games teach the later
ticks; or the adapted column (0409-0421) shows bursts close
inflame-turn1's or metal-c2-a5's @tsl1 cost, which would make the
modifier-pair table worth widening to more pairs.

## Lane leaf-blind-numbers closed (2026-11-07)

Outcome: **done, fail** (the stop rule's fail branch, after its step 3).
Step 2 found one number mispriced with an exact search-side fix: leftover
player block at `monster_rolls` leaves, priced about -0.3 HP a point on
three sets (wrong sign) and +1 on Impervious decks
(`measurement/leaf-numbers@probe`). The fix, search option
`leaf_clear_block` (`@lcb1`, off by default, landed in 17ca500), changes
only 2-5% of fights: no card's lead moves by a third of an se (Disarm
-0.130, Impervious -0.120, Intimidate -0.072 wins @tsl1) and the one-turn
cell gauntlet is level (+0.002 clears, +0.04 HP paired, protocol fail)
(`measurement/leaf-clear-block@cells`; read in
`docs/research/leaf-blind-numbers-2026-11-07.md`). The markdown acts on
lines the search rejects anyway, and Impervious's block is mostly gone by
the leaf. So the three cards' cost is not a leaf artefact: Disarm's is
Strength below zero priced as on decks that never make it, Intimidate's
is Weak overpriced about twice, Impervious's is play. That is content the
net has not learned, evidence for `all-content-net` (new content, allowed
by the training rule). The option stays in the engine, off; nothing
promotes it, and the one-turn headline read was not run (its gate failed).

CPU: 0.55 cpu-h (jobs 0432, 0434, 0451-0453) against the cap of 3; the
opening entry estimated about 2.

**Reopen if:** a net is trained or fine-tuned so that it reads leftover
block as a quantity (step 2's block perturbations priced near 0 on every
set) and a pack card still costs it one turn deep; or a deeper search
(two-turn, the product) is shown to compare surplus-block lines it
otherwise keeps, so that `@lcb1` changes more than about 10% of
two-turn decisions on `data/bench/decisions.json` (a free count before
any fight).

## After yardstick-cards: generated-enemies-bench opened as a fourth lane; the adapted column kept, the boss replays and the headline read cancelled, the family table run on what exists; projected-leaf staged as the next exploration (on the owner's behalf, 2026-11-07)

Wake `lane:yardstick-cards` (closed at the cap, decisions "Lane yardstick-cards
closed"). Three choices.

1. **The leftover queue.** Kept: step 3's adapted column 0409-0421 (about 5
   cpu-h, 0410 running): bursts on inflame-turn1 and metal-c2-a5, the two
   owner's modifier pairs that cost @tsl1 (`decision/goal1-yardstick`); its
   result is one of the lane's reopen conditions and the first games number
   on a later-tick cost. The navigator reads 0421 (no lane owns it). Cancelled:
   the 18 boss replays 0352-0403 (about 8.5 cpu-h) and the best net's headline
   read 0405 (about 2): they were designed for a step-2 net on the product
   path, and the tsl1 gate ruled both passing nets off it (games teach Demon
   Form's first tick, `measurement/demon-form-games@tsl1`), so no outcome
   changes a decision. The table 0404 stays: its `after` list is met by
   cancelled jobs (an `after`, not an `if_passed`), and `family.py table`
   lists the missing boss reads, so `session-free-reads`' first family still
   writes its table from its own job; that lane's checkpoint reads it knowing
   the boss column was cut here, not by a session between queue and table.
   Alternatives: run the boss replays (passed over: about 8.5 cpu-h on nets no
   path uses); cancel the adapted column too (passed over: 5 cpu-h for the
   goal-1 number on the owner's yardstick, and the CPU is idle, `cpu` red at
   0.20).
2. **The slot.** `generated-enemies-bench` opens now as a fourth lane (its own
   entry below). The rule allows a fourth while another is near its end:
   `leaf-blind-numbers`' step 3 reads have run (0451-0453) and
   `session-free-reads` has only its table left. No open project lane has
   queueable CPU work (`act1-content`'s next step is code), and `cpu` has been
   red for 50 checks.
3. **The next exploration, staged, not opened:** `projected-leaf` (backlog):
   apply at the leaf, k times, the once-a-turn hooks that add a lasting power
   to their owner (Demon Form's Strength, Ritual's), on both sides. It meets
   two reopen conditions at once: yardstick-cards' ("a leaf that prices a
   power's per-turn effect over several turns") and the monsters rung's
   growth (`race-price`, `cause/novelty-is-horizon`). It opens at
   `leaf-blind-numbers`' close, whose `wake always` brings the navigator.
   Not proposed: `@lcb1` on metal-c2-a5 (the leftover-block fix for
   Metallicize's surplus block): 0452's table shows `@lcb1` leaves Impervious,
   the card with the most leftover block, where it was (-0.120 wins @tsl1
   against -0.122), and metal-c2-a5's cost sits at bosses as a rate (step 3
   table), not in leftover block.

## Lane generated-enemies-bench opened (on the owner's behalf, 2026-11-07)

Charter: the backlog's ready charter (candidate 6), with the end moved to
2026-11-13. Rated **likely** that the 24-mechanic
table is recorded within the cap, **even** that some mechanics cost one turn
deep with `@tsl1`. About 2 h of code and 6 cpu-h; cap 10. Goal 1 (weight 0.8,
`docs/direction.md`); precondition met: block M5 (pack powers as start powers
on pack monsters) landed in `act1-content`. yardstick-cards adds a prediction:
on cards the trigger and the effect learned apart did not compose (2b), so the
bench's later coverage curve is predicted flat across mechanic families unless
two families share a row (SharpHide to Thorns carried, 0.86x).

Alternatives passed over: `race-price` (a long shot, code first; growth is
folded into `projected-leaf`, staged as the exploration); `heuristic-games-burst`
(its first test, heur-g400 on Demon Form decks, raised the plain leaf +4.98 HP
but cost train decks -1.39 HP and was never read @tsl1, where every other
Demon Form gain was the first tick; stays a long shot); `all-content-net`
(waits for Act 1's content); goal 2's `ceiling-player` and `hexaghost-headroom`
(the direction's CPU weight for goal 2 is 0.4 and underspent, but neither has
a probe under the depth family's close that could change what is built; the
review at 22:10 is asked to name goal 2's next question).

Shares (`jobs/lanes.json`): act1-content 35, generated-enemies-bench 30,
leaf-blind-numbers 15, session-free-reads 10, main 10, filler 0.

## Lane projected-leaf opened (on the owner's behalf, 2026-11-07)

`leaf-blind-numbers` closed while the navigator ran (decisions "Lane
leaf-blind-numbers closed", fail: `@lcb1` changes 2-5% of fights), so the
exploration slot is empty and `projected-leaf`, staged in the entry above,
opens now rather than at the next navigator run: the CPU is idle (`cpu` red)
and the lane needs about an hour of code before its first read.

Rated **a long shot** (backlog candidate 2): for, `@tsl1` repaired Demon
Form's first tick exactly with no games (+7.54 HP), and both rungs' remaining
costs sit in value that recurs past the leaf (inflame-turn1 -0.018 (0.005)
wins @tsl1; Ritual 2 on elites); against, k ticks credited at once overvalue
a power in short fights, the card costs left are small, and every hand-set
price so far moved at most about 1 HP. About 1 h of code and 2.5 cpu-h; cap 4,
end 2026-11-13, `on-close: wake on go` (a fail closes a family nobody waits
on; a go reaches the headline and unpauses `race-price`'s question).

Alternatives passed over for the exploration slot: `race-price` (the same
growth target through a hand-set price, which every earlier price argues
against; folded in as `projected-leaf`'s monster half); `heuristic-games-burst`
(games, where `yardstick-cards` showed games teach only the first tick at
these sizes); `incremental-state-key` (machine time, a long shot whose
profile probe should come first); `hexaghost-headroom` (goal 2, depth family
closed, `decision/depth-family-closed`).

Shares (`jobs/lanes.json`): act1-content 35, generated-enemies-bench 30,
projected-leaf 15, session-free-reads 10, main 10, filler 0.

## After the cards adapted column: yardstick-cards stays closed; a copy-rehearsal probe queued; burst-adapted-column re-set (on the owner's behalf, 2026-11-07)

Read by the navigator (no lane owns it; decisions "After yardstick-cards"):
jobs 0409-0421, `measurement/cards-adapted@stage-a`, results doc "Cards
adapted column (step 3, second table)". No burst closes a modifier's cost on
the turn-start leaf (inflame-turn1 +0.001 (0.003) against -0.018; metal-c2-a5
+0.002 (0.005) against -0.021); on the plain leaf inflame-turn1's bursts win
back 56% (the first tick). Every one of the six bursts loses HP on the parent
copy and the official card at the elites (+0.36 to +2.38 HP per elite fight
by seed), with the 0.5 replay share in each.

1. **`yardstick-cards` stays closed.** Its reopen condition "the adapted
   column 0409-0421 closes a @tsl1 modifier cost" does not hold, so the
   modifier-pair table is not widened. The later ticks stay
   `projected-leaf`'s.
2. **Probe `copy-rehearsal` queued in lane `main`** (probe sheet; jobs
   0456-0460, about 1.5 thread-hours, under 1.5 GB each; read by the
   navigator from 0460's log): one burst per modifier, seed 1, whose decks
   hold the variant or the parent copy (`configs/cadapt-<mod>-copy-s1.json`,
   no code). Mechanism: the replay pool rehearses varied Ironclad decks, not
   the decks the read plays; games with the parent copy on the same decks
   teach the net what the copy is worth beside the variant, which is what the
   parent row measures. Rule in 0460's note: go if metal's parent-copy cost
   per elite fight falls to +0.90 or less and inflame's to +0.38 or less, with
   the variant wins within 2 se of the plain seed-1 burst's (then seeds 2-3,
   the copy mix becomes the adapted column's recipe, and the navigator adds a
   parent-fight share to `generated-enemies-bench`'s step 4); stop if metal's
   stays at +1.43 or more (the cost is fine-tuning drift on the product file's
   elites, not missing rehearsal); between, seeds 2-3 on metal. Alternatives
   passed over: no probe, the cost taken as part of the adapted column
   (rejected: it is 3-5 se on every seed, and retention is half of goal 1's
   number for content a pack brings); a higher replay share (rejected first:
   the pool's 0.5 did not protect the elites and its decks are not the read's;
   it is the stop branch's next question); three seeds at once (rejected: one
   seed against a cost this size and its seed spread decides go or stop).
3. **`decision/burst-adapted-column` re-set**: its sentence "no rehearsal
   ... one turn deep there is no parent cost" is wrong for card content (this
   read; the burst8 nets' -0.041 clears, decisions "After stage 3 and the
   value-chooser close", point 6); it now says card bursts cost the parent at the elites
   and that rehearsal of the read's own decks is under probe.

## act1-content: next block C4, Block and Apply amounts from a quantity (on the owner's behalf, 2026-11-07)

After S1 (built, landing waits on its speed read 0454), the lane's next
block is C4 (spec `docs/specs/quantity-amounts.md`): two effects,
`BlockOf(Amount)` and `ApplyOf`, that size block and a power from the
state, writing Entrench and Limit Break (2 of the 15 missing Ironclad
cards). Chosen over C3 (card drawn: Evolve, Fire Breathing) and C5 (cost
changes: Blood for Blood, Corruption), which unblock as many cards but each
add a new hook or per-card state; C4 is the smallest and reuses
`ScaledDamage`'s `Amount`. Provisional, in the spec: two new effects
rather than widening `Block` and `Apply` (which touches every official
card); one feature scalar each for the quantity part, not a quantity
one-hot. Reversible: pack-only effects, two named feature columns.

## Copy-rehearsal stopped: card bursts' elite cost is not missing rehearsal; no follow-up on card-burst retention (on the owner's behalf, 2026-11-07)

Read by the navigator (jobs 0456-0460, `measurement/copy-rehearsal@stage-a`,
results doc "Copy-rehearsal probe"): with the parent copy in the burst's
decks the parent-copy cost per elite fight rose to +2.61 (metal) and +1.54
(inflame) HP, against the plain seed-1 bursts' +1.43 and +0.65. By 0460's
rule, stop. The copy mix is not the adapted column's recipe, and
`generated-enemies-bench`'s step 4 stays as chartered (monster bursts were
level on their parents one turn deep, `measurement/adaptation-transfer`).

No follow-up probe: a card burst repairs nothing on the turn-start leaf
(`measurement/cards-adapted@stage-a`), so a recipe that keeps its retention
only makes a burst that gains nothing cost nothing (the trade-off rule).
Passed over: a higher replay share (it would dilute the very games that cost,
and the gain with them); card bursts on the read's own product-file fights
instead of varied setups, the one difference left from the monster bursts
(needs code; comes back if a card burst repairs a @tsl1 cost or a pack's net
is to play official decks). `decision/burst-adapted-column` re-set to say so.

## act1-content C4 build: ApplyOf takes official powers only (on the owner's behalf, 2026-11-07)

The spec (`docs/specs/quantity-amounts.md`) says `ApplyOf` applies "exactly
as `Apply`" but doesn't say whether a pack may name one of its own powers
in it. Built: a pack's `ApplyOf` of a pack power is refused at load ("ApplyOf
of a pack power ... is not supported"); Limit Break applies Strength, an
official power, and no pack entry needs more. Alternative passed over: map
a pack power to its slot at bind as `Apply` does (registry `bound`), which
also needs the features' grant rows to read `ApplyOf`'s hooks; two more
sites for no content. Reversible: the refusal is one
line, and the slot mapping can follow when a pack card needs it.

## act1-content: next block G1, pack cards in the gauntlet's offers (on the owner's behalf, 2026-11-07)

After C4 the lane's next block is G1 (spec `docs/specs/gauntlet-pack-offers.md`):
`gauntlet.py play --pack <file>` adds a pack's base cards to both halves'
reward pools, so a run drafts and plays pack content, and the charter's
headline re-rank for cards can run (one-turn net and heuristic at 500
sequences, the product at 250, each against its own control with `--vary
pack`, at fixed n). Chosen over C3 (card drawn, 2 cards) and C5 (cost
changes, 2 cards): those add cards no run can draft yet, while G1 is the
review's structural step "pack content in gauntlet.py's decks and offers",
and with S1 landed nothing blocks it; and over E1 (encounters as data), which
can't play the Gremlin Gang in full before M6. Provisional, in the spec:
every pack card in both halves (alternatives: split the pack between halves;
a pack-only pool) and uniform offers (alternative: rarity weights). All
reversible: one flag, absent from settings when off.

## generated-enemies-bench: batch 2 runs past the 10 CPU-hour cap; the close waits for its read (on the owner's behalf, 2026-11-07)

Batch 1 (0469) booked 6.5 CPU-hours, not the 5 its 100-minute estimate
implied. Batch 2 (0470, 16 mechanics plus the parent, no ladder: 17 games
per start and seed against 0469's 19) books about 5.8 more, so the lane
reaches its cap about 70 minutes into 0470 and ends near 12.3. The
24-mechanic table is the lane's measure, and step 4 (the adapted column,
about 400-game bursts on four mechanics, three seeds) does not fit the
cap at all. Decided: 0470 runs as queued; the lane-cap close waits until
0470 has ended and been read with read-gen (per parent beside the mean),
and the close's navigator wake (`on-close: wake always`) carries step 4 and
the cap as its question. Alternatives passed over: cancel 0470 and close
now (the measure stays at 8 of 24 mechanics, and 0470's 16 would have to be
re-queued later from scratch); shrink 0470 to 500 starts to stay under the
cap (half the precision, and read-gen expects every start to carry every
mechanic, so it needs a code change; step 4 still does not fit). Reversible:
the navigator can cancel 0470 while it is pending or running.

## After generated-enemies batch 1: three probe reads before step 4; all-content-net is the ready exploration charter (on the owner's behalf, 2026-11-07)

Batch 1 (`measurement/gen-enemies@batch1`) costs sit in in-turn
punishments of an action and on one parent each. The largest,
AttackLoss-Damage x Gremlin Nob (+12.8 HP, the net dying 1,077 times of
3,664 against the heuristic's 204), matches the record's one known Nob
loss: the leaf's HP price feeding Enrage ("Enemy-Strength price fails at
run level": `@esp0.04` fixed official Nob, 0.972 to 0.994 wins). And
AttackLoss-Damage is the Thorns family, which a SharpHide burst already
repaired at 0.86x (`measurement/adaptation-transfer`). Step 4 as chartered
(bursts on the four costliest mechanics, three seeds) could spend its CPU
training away a price artefact, or re-learn a family a burst on disk
already covers.

Decided: three reads in lane `main` on the probe sheet, gen batch 1 on
elites, 1000 starts x 4 seeds (the first 4 of batch 1's 16, so they pair),
about 5 thread-hours, no code:
- 0472, the 10-29 net `@esp0.04@tsl1`. If the Nob cost falls by half or
  more at 2 se, it is the HP price, not novelty: the adapted column starts
  on the next costliest mechanic (OppCard-PlainDamage x Sentries) and
  backlog `strength-by-hits-left` (the alternative passed over on
  2026-11-01) becomes a candidate with evidence. If not, the cost is in
  the net's values and step 4 takes it as planned.
- 0473, 0474, the two 399-game SharpHide bursts (seeds 1 and 2) `@tsl1`.
  If both AttackLoss-Damage and OppCard-PlainDamage are cut by half, one
  burst per family covers the bench's punish-an-action mechanics, and the
  adapted column trains per family. If only AttackLoss-Damage is cut,
  transfer follows the attack trigger and the column's bursts go to the
  others. If neither is cut, a burst on a patched power does not reach a
  pack power with the same effect (`how/burst-inputs`), which is a goal-1
  finding about custom content.
Step 4 is decided at the bench's close (its wake), with these three read,
as backlog `gen-adapted-column` (held charter, with a heuristic-teacher
arm: heuristic games where the heuristic is measured far ahead; the
former `heuristic-games-burst` folded in).

Ready charter for the exploration slot: `all-content-net` (backlog 17, a
goal-2 long shot that needs a config, not code; the CPU sits mostly
idle, health `cpu` 0.27, and goal 2's CPU weight of 0.4 is underspent).
It opens when `projected-leaf` closes and its on-close does not call the
navigator. The stale "Ready charter" text on `session-free-reads`, which is
already open, now points to its lane fact so it is not opened twice.

Alternatives passed over: step 4 straight to 12 bursts on the four
costliest (could train away an artefact; the probes cost less than a third
of it); a two-turn read of the Nob cost (about 10 thread-hours, moot if
the price or a family burst removes it); `heuristic-games-burst`, the
teacher arm alone, as the exploration charter (it needs step 4's code for
bursts on generated mechanics); `race-price` or `boss-step-hp-price` as
the exploration charter (code-first long shots; 0472 tests race-price's
mechanism on generated growth for free). Reversible: the three jobs can be
cancelled while pending; the charter is backlog text.

## act1-content: next block E1, encounters as data (on the owner's behalf, 2026-11-07)

After the G1 read (docs/research/act1-inventory.md, "G1 re-rank read":
checkpoint cards-rerank passed) the lane picks E1 next and confirms its
spec, docs/specs/encounters-as-data.md. Alternatives: C3 (card drawn: 2
cards), C5 (cost changes: 1 card alone), M6 (Shield Gremlin) or M7 (Red
Slaver) first. E1 is the largest left by entries (4 encounters with M6 and
M7) and the one goal 1 needs most: an encounter as content is what a
generator of fights composes, and the generated-enemies batch 1 read put
the novelty costs in modifier-encounter interactions. The official
encounters stay as they are (Exordium Thugs keeps its second slot; the full
one becomes a pack entry with M7), so golden and every control file stand;
reversible by keeping the handle and dropping the pack key. Then M6 and M7
complete the monster kind.

## Lane projected-leaf closed (2026-11-07)

Outcome: **fail** (the stop rule's fail branch, at step 2). At k = 2 the
projected leaf (`@pl2`, off by default, landed in 1e56863) moved
inflame-turn1's novelty cost in wins by -0.002 (0.002), 1 se away from
zero (predicted +0.008), and its boss column the wrong way (-0.006
(0.006)); the cards rung's remaining cost is boss wins and the projection
does not reach it. It does repair HP on fights every player wins:
inflame-turn1's HP cost against the heuristic falls from +0.9 to +0.2
(paired -0.61 (0.13); elites -0.74 (0.14)), df-c2-s1 elites -0.37 (0.18);
the block control metal-c2-a5 +0.14 (0.07), the plain control level
(`measurement/projected-leaf@cards-k2`; read in
`docs/research/projected-leaf.md`, "Step 2 read"). Step 3 (monsters rung,
Demon Form stratum, cell-gauntlet retention) did not run: its gate failed,
and the cap would not have covered it. The option stays in the engine,
off; nothing promotes it.

CPU: 3.4 cpu-h (job 0471 and step 1's checks) against the cap of 4; the
opening entry estimated about 2.5.

**Reopen if:** a boss-wins cost on a growth power is read with a leaf that
credits ticks by the fight's expected length (k from the enemy's HP over
the deck's damage per turn, not a fixed k), and a cheap read (inflame-turn1
boss rows, 200 starts x 16 seeds, about 1 cpu-h) moves boss wins 1 se
toward zero; or the HP column alone becomes the goal-1 measure for a
generated growth mechanic (then @pl2 is a free HP repair worth a cell
gauntlet retention read).

## Lane all-content-net opened (2026-11-07)

The `projected-leaf` slot (exploration) passes to the first backlog
candidate with a ready charter: `all-content-net` (candidate 17), which
the navigator ranked first for the exploration slot on 2026-11-07 and
staged to open when `projected-leaf` closes (backlog, the ranking note
under "Open as lanes"; decisions "After yardstick-cards"). The charter is
copied as written into `lane/all-content-net`; its share in
`jobs/lanes.json` is projected-leaf's (15).

## All-content net: configs and twin (2026-11-07)

(On the owner's behalf; lane all-content-net step 1, spec
`docs/specs/all-content-net.md`.) `learn.py` gains two dataset keys:
`bosses` (the boss group's encounters in turn: Slime Boss, Hexaghost, the
Guardian, so each gets a third of the boss games) and `deck_pool: "all"`
(extra cards uniform over the whole Ironclad pool, checks 6 and 9
held-out cards included). Both apply to training and validation sets, so
the trainer keeps the epoch that fits the content the net is for
(alternative: validation on the old pool, as `train_pool` does, which
selects for content the net is not for). Uniform full-pool decks rather
than held-out-heavy ones (`varied_held_out_deck`): the headline's decks
are reward picks. The twin stays the charter's
`runs/2026-10-31-data40k-s1-r1-72d8ced`; it reads 28 effect columns and 8
triggers against today's 56 and 20, so a gain reads as "this recipe today
against data40k", not as content alone; a today's-inputs twin (about 7
thread-hours) is the navigator's call after a go.

## Explorer v2 (provisional, spec docs/specs/explorer-v2.md, built: see "Explorer v2 as built", 2026-11-07)

- The explorer opens today's tests (gauntlet files in every setting, mutated monsters and cards, boss replays) and a content browser, replays each fight with the player and settings that played it, and lets the owner take over inside a fight and between floors while the net keeps scoring. The old solved-position views stay, shown only with a database of the current rules version (both databases hold none today).
- It stays its own server on port 8765, styled with the dashboard's stylesheet (`dashboard.CSS`, imported); the dashboard gains only a nav link.
- It imports its own copy of `sts` (`cache/explore/sts-<pyd hash>/`), so an open explorer never blocks rebuilding main's `sts` (owner). Replays run on the build current at start; a floor whose replay differs from the file is flagged, never hidden (owner: faithful to the net wins over speed).
- The drawn board comes from a new read-only binding method `Combat.board()`, not from parsing `render()`. The board hides the draw order (the net sees contents only) and shows the net's input rows (owner).
- No start-time choices (owner, 2026-11-07): the CLI keeps only `--port`; the database (from db/*.sqlite, current ones only) and the comparison nets (any run with a model.pt, settings suffixes allowed) are picked in the page and kept in its URL; every request names its players.
- Heuristic one-turn scores show beside the player's, plus each comparison net added in the page (owner). A side-by-side view of two files is not built (owner didn't pick it).
- New views carry only the solve mode's features that make sense without exact values (option table, step, reroll, back, trail, tooltips): no wrong-pick substitute, no file-wide decision list; decisions are listed only within a fight that is opened (owner).
- Bench puzzles work without a database: all 2,000 replay under today's rules with the same options (checked 2026-11-07); their exact values are labelled as solved under rules 39bfc65e541f073d. Run positions, row ids and Reopen need a database of the current rules version.


## Explorer v2 as built (provisional, 2026-11-08)

Built from docs/specs/explorer-v2.md in commits 737218f..218b9e2 (steps 1-11).

- What it is: `python scripts/explore.py [--port 8765]` serves a page in the dashboard's style (`/ui.css` is `dashboard.CSS`, imported). Top bar: Gauntlet, Mutations, Boss replays, Content, Puzzles, a link to the dashboard (which links back), the database picker and the comparison-players picker, both kept in the page's URL. Gauntlet files open as sequence lists with an 11-floor strip, a sequence as its run, a floor as its fight replayed by the file's own player; mutate and boss-replay cells open as fights the same way; the content browser lists every card, monster and power by source with links into an open gauntlet file. Each state shows the drawn board (`Combat.board()`), the net's input rows and static value, and the options with the player's own scores, the recorded action, and the heuristic's and any added nets' one-turn scores. The owner can take over inside a fight (step, reroll, back) and between floors (another card, rest choice, removal or path; the file's player plays on).
- Replays reproduce today's files. Step 5, on today's build: the one-turn headline file `net1029-hpb0.01-starter-simboss.json`, 20 sequences, 220/220 floors (win and end HP) and 200/200 events (offer and pick) match; the two-turn product file `net1029-hpe0.01-two-line-step-starter-simboss-a.json`, 5 sequences, 55/55 floors and 50/50 events.
- Memory (step 11, the explorer's process over two-turn replays): peak 1.31 GB working set, 2.0 GB commit.
- Deviations from the spec and choices the build made:
  - `depth_paired.py`: besides the new record key, `guarded_fight`'s rule for one decision is factored into `decide()` and `decision_seed()` (no behaviour change; the record pin and the callers' suites pass), so the explorer scores a state off the recorded line by the two-turn player's exact rule. The `scores` key is added only when the caller asks for it (an optional 10th job field), so `two_turn_games` partial files and datasets are unchanged.
  - `gauntlet.py`: `players(settings, threads, cells)` builds the player and hooks from a result file's settings and `play_cmd` uses it (the pinned file stays byte-identical); the choosers' scoring is split into functions the hooks choose by. `play_cmd` now loads a vrun fit when play starts, not while checking arguments.
  - Line handles: `Combat.encode` refuses states holding pack cards or generated powers, so such states are named by the replay's decision `n` plus the steps taken since (`?n=&steps=`) and rebuilt in memory; hex stays for ordinary states. Without this, pack gauntlet floors (e.g. floor 6 of `g1-heuristic-starter-simboss-pack-act1.json`), most mutated-card cells and every generated-enemy cell could not be shown.
  - Mutate cells are played by a Python search loop, as `sts.play_on`'s search agent plays them, with the engine's search-seed generator ported to Python (it matched `play_on` on every play-out tried: heuristic 48/48, one-turn net 48/48, two-turn net 12/12). Mutated-card cells search with seed 0, since their players are one turn deep, where the seed doesn't matter. After the review (2026-11-08) the result shown is the player's own: each cell runs `sts.play_on` as its script plays it, and the Python loop only lists the decisions; a loop that ends elsewhere than `play_on` raises ("stepping the recorded actions ends ..."), so drift in the port shows as itself, not as the build playing differently. REPLAY_VERSION 4.
  - The fidelity check is computed against the file's row on every read; only replays are cached (`cache/explore/replays/`, keyed by settings, sequence, floor, start spec, search settings, the sts build and `REPLAY_VERSION`, now 4).
  - `EXPLORE_STS_ROOT` moves the private `sts` copy (tests only). `/api/close_db` closes the open database ("none" in the picker).
  - `choices` is plain JSON in the query string: `{k, e: offer|extra|rest|removal|path, j, pick}` for a different choice, `{k, won, hp}` for a taken-over fight. A choice equal to the file's doesn't leave the file's line; a pick at floor k drops later choices.
  - Between-floor scores show only on the file's line; on the owner's line the page shows which choice the file's chooser made, without its scores.
  - The database views (positions, row id, Reopen, Solve) are restyled with unchanged behaviour but were not tried in the browser: no database of the current rules version exists.
- Amendment 1 (owner, 2026-11-08; built c2e6fa6..cd72667): afterstates decide the line, not decisions. `Combat.__eq__` / `__hash__` compare the engine state without the RNG. Inside a fight, a step whose state equals a recorded decision's is "as played" there again, scored from the record with no search; between floors, the owner's HP and deck (as a multiset) are compared with the row's after every fight and event, and the line rejoins the file's as soon as they match (no replay, no chooser call). Choices are one ordered history in the URL (a later entry for the same fight or event replaces the earlier one); Undo, Reset and the browser's back button step through it, and "your changes" marks entries that changed nothing. Whole rows open; the board's text/board toggle sits on the board panel. Tooltips say what their label doesn't, from the content data, long ones in hover cards; the behaviour held only in engine code (lice, Lagavulin, Hexaghost, the Guardian, Mode Shift, Split Hits) and the intent modifiers' factors are hand-written from the engine's doc comments and statics, with no test tying them to the engine (optional follow-up).
- Amendment 2 (owner, 2026-11-08; built 154a913): a description's form is fixed per kind, never by its length. Every encounter, monster, move, power and card description opens a hover card ("Gain 3 Ritual." too); headers, field notes and controls keep plain tooltips.
- Amendment 3 (owner, 2026-11-08; built adc394d..d013d78): one group-by control for every list table; a dimension that would grow columns (modifiers, HP levels, seeds) becomes rows instead (mutations by parent or modifier, boss replays by sequence or HP, puzzles by set or encounter). Content shows a sortable table per kind (cards, monsters, powers, encounters); card cost sorts numbers, then X, then Unplayable. Card, move and power text uses the game's own words: `Name · N Cost · [Rarity · Class ·] Type`, keywords stay keywords, no parenthetical explanations; keyword hover is not built (owner: probably excessive). The monster hover card shows every pick rule after a divider; hover cards stay open while the pointer is over the element or the card, and a card taller than about two thirds of the window offers "show all" in a modal.
- Amendment 4 (owner, 2026-11-08; built a4b7f6e): group headers name their grouping ("cost: 0"); a jump bar above a grouped table lists every group with its row count (a "Jump to" dropdown past 24 groups) and scrolls to one, turning the page when it starts on another (`group_page` gives each group its page).
- Amendment 5 (owner, 2026-11-08; built 8b4f278): column headers, and a grouped table's jump bar, stay under the top bar while the page scrolls; tables no longer scroll inside a box of their own.
- Amendment 6 (owner, 2026-11-08; built e02e19e): every grouped table offers "nothing": mutations list one row per (start, modifier), sorted and paged across the whole list; boss replays' per-sequence view is labelled "nothing".
- Amendments 7-8 (owner, 2026-11-09; built 95a0c23): an HP bar fills its line, with nothing beside it that changes: your energy, block, powers and result sit on a second line (a monster's were already on their own); HP numbers use fixed-width digits. A fixed 200px bar (Amendment 7) was too short.

## Lane generated-enemies-bench closed (2026-11-07)

Outcome: closed at its CPU-hour cap with the measure's main part recorded
and step 4 not run. The 24-mechanic table is filed
(`measurement/gen-enemies@table24`; docs/research/generated-enemies.md,
"Batch 2 read"): pack enemies built from atoms the net reads cost it
zero-shot, mean +1.28 (0.38) HP per elite fight over the 21 mechanics the
heuristic reads (+0.32 (0.65) over all 24; three Vulnerable/Weak-per-action
mechanics are the heuristic's collapse), 17 of 21 beyond 2 se. The cost
follows the trigger (attack HP loss +2.98, card played +1.62, monster turn
+0.4 to +0.5) and sits on one parent for most mechanics (AttackLoss-Damage
x Nob +12.80); AttackLoss-Weak costs +6 on both parents it reads on.
Checkpoints batch1 and table24 passed. Step 4, the adapted column on the
four costliest, did not fit the cap (decision "batch 2 runs past the 10
CPU-hour cap"); it is backlog `gen-adapted-column` (held charter), which
the navigator decides with probes 0472-0474 (lane `main`, 0472 running at
the close).

CPU: 15.2 thread-hours (0469 6.5, 0470 8.7) against the 10 cap and the
opening entry's 6 cpu-h; 0470 ran 173 minutes against its 100-minute
estimate. Opening rating: **likely** the table is recorded within the cap
(recorded, but at 1.5x the cap), **even** that some mechanics cost one turn
deep with `@tsl1` (17 of 21 do).

**Reopen if:** the bench is re-asked on something its table could not
see: (a) new atoms land that the product net does not read today (a
vocabulary widening; then the same 24 pairs plus the new ones measure
blindness against this table as the known-atom baseline), (b) a new
product net or leaf (a read of the costliest five pairings by worst
parent, about 1 thread-hour, says whether the cost moved), or (c) a
two-turn read of the punish-an-action mechanics is wanted (about 10
thread-hours; worth it only if the adapted column fails to cut
AttackLoss-Damage x Nob by half). The adapted column itself is not a
reopen: it is `gen-adapted-column`.

## After generated-enemies-bench: step 4 opens as lane gen-adapted-column before probes 0472-0474 are read; session-free-reads' slot goes to it; recurring-debuff-leaf is the next exploration charter (on the owner's behalf, 2026-11-07)

Wake `lane:generated-enemies-bench` (closed at its cap, decisions "Lane
generated-enemies-bench closed"). Two choices: step 4 and the slot.

1. **Step 4 (`gen-adapted-column`) opens now, as a lane; the probes pick
   its target, not whether it runs.** Probes 0472-0474 (decisions "After
   generated-enemies batch 1") were meant to be read before step 4; at the
   close 0472 has run 9 of its 40 minutes and 0473-0474 wait. Every outcome
   of the three still needs step 4's one piece of code, a burst whose
   content is a bench mechanic on its parent elite: if `@esp0.04` halves
   AttackLoss-Damage x Nob, the column starts on AttackLoss-Weak (+6 on both
   its parents, the one costly mechanic not tied to one parent); if the
   SharpHide bursts halve it, the column goes to the mechanic they leave
   costliest; if neither, it starts on Nob as chartered. So the lane opens
   now with the code as step 1 and the written rule picking step 2's
   target. The heuristic share key already exists (`configs/ycards-heur-
   g400-*`, the cards rung's heuristic-games arm: +4.98 HP on Demon Form
   decks, the best held-out gain in that family, and -1.39 on train decks,
   the worst retention), so step 1 is smaller than the backlog's 2 hours.
   Step 2 is queued as one `family.py` family, which is also the second
   family the session-free-reads driver runs. The navigator reads the three
   probes at job 0474's end for the ranking (`strength-by-hits-left` lives
   or dies on 0472); the lane worker applies the rule itself if step 1
   lands first.
2. **The slot.** `session-free-reads` has met its measure without a
   session: `family.py`'s table job wrote `results/families/ycards-step2.md`
   (verdict pass, best two-g400; the boss column cut by the navigator,
   decisions "After yardstick-cards"), and the ledger is committed. Its
   step fact is from before the table, and no event will start its worker
   (its idle wake for rev 2 is spent), so the navigator queues a one-line
   light job in its lane as the wake (backlog `throughput-fixes`, the
   standing workaround); the note asks the worker to read checkpoint
   `family-run` and close the lane. Its slot is the one `gen-adapted-column`
   takes: at that close no ready charter opens. Open lanes: `act1-content`
   and `gen-adapted-column` (project), `all-content-net` (exploration),
   `session-free-reads` until its close. Shares: act1-content 40,
   gen-adapted-column 25, all-content-net 23, session-free-reads 2, main 10,
   filler 0.
3. **Next exploration charter: `recurring-debuff-leaf`** (backlog). The
   table's one systematic cost on every parent is a debuff the monster puts
   back each turn: TurnStart-Weak +2.21 (0.16), TurnEnd-Weak +2.55 (0.17),
   Frail smaller, while the same triggers with damage cost nothing. The net
   learned Weak from official sources, where it decays; a hook that
   re-applies it makes it permanent, which the leaf state shows as one or
   two stacks about to expire. The projected leaf (`@pl`,
   `CombatState::projected_leaf`) already runs once-a-turn hooks k more
   times at the leaf for Strength and Dexterity to their owner; widening
   its kept effects to debuffs a monster's hook applies to the player is a
   few lines, and the bench's measure is HP lost per elite fight, the one
   thing `@pl2` did move (`measurement/portfolio-projected-leaf`'s second
   reopen condition: HP as the goal-1 measure on a generated mechanic). It
   opens in the exploration slot when `all-content-net` closes on a fail.

Alternatives passed over: wait for 0472-0474 before opening anything (the
code is needed in every outcome, and the lane would sit a session idle);
open step 4 as chartered on Nob regardless of the probes (it could train
away a price artefact, the reason the probes were queued); give the slot to
`race-price` or `boss-step-hp-price` (code-first long shots on costs the
bench shows are small: generated growth +0.48); `ceiling-player` (goal 2,
weight 0.2, a long shot that needs a code read first). Reversible: the lane
can be closed with its jobs cancelled while pending; the shares and the
charters are text.

(A first commit of this entry, f14dcc0, appended an older entry by mistake;
the next commit removes it.)

## Lane gen-adapted-column opened (on the owner's behalf, 2026-11-07)

Backlog candidate 8 (`gen-adapted-column`, with `heuristic-games-burst`
folded in), opened in `session-free-reads`' slot; why now and the
alternatives passed over: the entry above ("After generated-enemies-bench").
Goal 1's adapted column on generated enemies: games to adapt per mechanic,
by teacher (the net's own games or the heuristic's, the heuristic only where
it is measured ahead), on the costliest bench pairings by worst parent
(`measurement/gen-enemies@table24`). Rating: **likely** that net-game
bursts at 99 games halve the target's cost (the SharpHide family adapted at
99 games, `measurement/adaptation-curve`, and carried to WeakOnHit,
`measurement/adaptation-transfer`); **even** that the heuristic's games cut
it by 2 se more than the net's at the same size. About 10 cpu-h (bursts
minutes each; reads about 0.3 thread-h a net on the worst parent), cap 15.
Charter: the lane fact `lane/gen-adapted-column`.

## gen-adapted-column step 2: target AttackLoss-Weak on Lagavulin and Sentries; the pass read as half the cost and 2 se over nets (on the owner's behalf, 2026-11-08)

Probe 0472 (`@esp0.04`) removed AttackLoss-Damage x Nob's cost (+13.29 to
-0.06 HP, docs/research/gen-adapted-column.md "Step 2's target"), so the
written rule (decisions "After generated-enemies batch 1") puts the column
on AttackLoss-Weak on its two parents; 0473-0474 no longer decide the target
and stay the navigator's ranking read. Choices the charter left open:
- the pass ("cuts the target's cost by half at 2 se") is read as: mean cut
  over the arm's three nets at least half the zero-shot cost and at least
  2 se over nets (the family table's se, as the cards rung used); the
  alternative, cut minus half the cost beyond 2 se, needs about twice the
  effect and would fail a real halving at three seeds;
- the cost is taken against the ladder control the bench picked
  (`c-hp1.25-str1`), so the burst's change on a stat-only enemy of the same
  difficulty cancels; the parent rows' change is reported as retention, not
  gated (the charter measures it, its stop rule doesn't);
- the read plays only the mechanic, its control and the parent, one turn
  deep, 4 seeds, all 1000 starts (Nob's parent rows give retention on the
  third elite); the heuristic comes from the zero-shot file, where its
  seeds pair;
- the net teacher plays at `@hpb0.01@tsl1`, the read's player.
Alternatives passed over: Nob as chartered (the price, not novelty, was its
cost); waiting for 0473-0474 (they cannot change the target once 0472
passed). Reversible: the family's jobs can be cancelled while pending.

## Lane session-free-reads closed (2026-11-08)

Outcome: done; the stop rule's done branch. The first family
(`configs/families/ycards-step2.json`, yardstick-cards step 2 and 2b: 21
bursts bound, 63 reads, the table) was queued whole by one session (the
yardstick-cards worker ran `family.py queue`, decisions "yardstick-cards
queues the step-2 family itself"), and its own job 0404 wrote the table
`results/families/ycards-step2.md` with the verdict (pass, best two-g400)
with no session between queue and table. One caveat, not a session in the
chain: the navigator cancelled the 18 boss-replay reads mid-queue
(decisions "After yardstick-cards"), so the table lists them missing; the
table job still ran because they were an `after`, not an `if_passed`. The
ledger (`scripts/analysis/ledger.py`) is committed and, rerun at the close,
still gives effects 5k -3.30, 20k -1.45, 40k -0.16 HP against the 10-29
net; it now also lists the step-2 nets, the best ycards-net-g1600 at +0.31
(seed sd 0.39), inside seed noise like burst8's +0.26
(`measurement/ledger@cells` confirmed). Checkpoint family-run passed.
Measure: one queueing session and 64 jobs to the table (the bursts were
already queued), against `pattern-rows-burst`'s 12 jobs over several
sessions. The second family (`configs/families/gac-alw.json`,
gen-adapted-column step 2, jobs 0479-0493) was also queued from one
session.

CPU: 0.0 lane cpu-h against the 3 cap (health.json `lane_cpu_h`; the
family's reads ran under yardstick-cards' lane) and the opening rating's
about 1 cpu-h of checks. Opening rating: **likely** as code (built),
**even** that it halves the sessions per family (one queueing session;
the reads still got their sceptical look from the owning lane's sessions
afterwards, which the measure did not count).

**Reopen if:** a family's pass rule needs a look between its jobs that
`--if-passed`/`--check` cannot express (for example a read whose next arm
depends on which arm won), or the reads of a family still take as many
sessions as `pattern-rows-burst` ; then
the driver needs a branching step, not a new lane.

Not done here: no navigator wake (on-close `wake on fail`; the lane passed),
and no ready charter opens: the slot already went to `gen-adapted-column`
(decisions "After generated-enemies-bench"). Its 2 share in
`jobs/lanes.json` goes to `gen-adapted-column`.

## gen-adapted-column step 3 queued before step 2's table: four families, both teachers (on the owner's behalf, 2026-11-08)

Two of three net-g99 bursts on AttackLoss-Weak cut its cost by +6.55
(0.20 over nets), 1.09 of the zero-shot cost (docs/research/gen-adapted-column.md,
"Step 2 interim"); seed 3 cannot undo the step-3 gate (it would need a cut
below -4.1). Queued now so the CPU is not idle while the heuristic arm
runs: `gac-alw33` (33 games on the target) and 99-game families on the
next three mechanics by worst parent, OppCard-Weak x Lagavulin,
OppCard-PlainDamage x Sentries, OppCard-Damage x Sentries, each with net
and heuristic teachers and three seeds (about 4 thread-hours in all; lane
used 0.5 of 15).
Alternatives passed over: wait for 0493's table and queue only the
passing teacher (saves about 1 thread-hour, costs a session and an idle
hour; the charter measures by teacher anyway); OppCard-Frail x Sentries
(+4.26) in place of OppCard-Weak x Lagavulin (OppCard-Weak is a heuristic
collapse on Sentries, but its Lagavulin cost stands within the ladder);
AttackLoss-Damage x Nob (the HP price, decisions "After generated-enemies
batch 1"). Reversible: pending jobs cancel.

## After the family-transfer probes: the column keeps its per-mechanic families; a bench-wide retention probe queued; strength-by-hits-left and pack-pick-split carry ready charters; the review waits for the line (on the owner's behalf, 2026-11-08)

Wake `job:0474`. Probes 0472-0474 read (0472 by the gen-adapted-column
worker, 0473-0474 here: docs/research/family-transfer-probes.md,
`measurement/family-transfer@gen-b1`).

1. **The rule's outcome: both cut by half.** The two 399-game SharpHide
   bursts cut AttackLoss-Damage x Nob from +13.29 to +1.91 / +2.02 HP and
   OppCard-PlainDamage x Sentries from +5.39 to +0.31 / +0.74, so by the
   rule in decisions "After generated-enemies batch 1" one burst per family
   covers the bench's punish-an-action damage mechanics. Step 2's target was
   already set by 0472 (decisions "gen-adapted-column step 2"). Decided:
   the lane's queued per-mechanic families stay, including `gac-ocpd`
   (OppCard-PlainDamage x Sentries), which the SharpHide burst already
   repairs: they measure games to adapt from the base net on the mechanic
   itself, the charter's number, the CPU is idle (health `cpu` 0.30), and a
   99-game burst on the mechanic is the one to compare with a 399-game
   burst on a neighbour. Passed over: cancelling `gac-ocpd` (saves about one
   thread-hour on an idle machine and loses the direct comparison).
2. **New: interference on a neighbouring mechanic.** Both SharpHide seeds
   lose the zero-shot net's largest edge on the bench, OppCard-Vulnerable
   (net wins 0.841 to 0.670 / 0.707, the heuristic's 0.682; Sentries 0.765
   to 0.417 / 0.522), while the official parents' wins held (0.987). A
   pack's net read for retention on the official parents alone would ship
   this. Queued in lane `main`: 0546-0547, the column's 99-game
   AttackLoss-Weak bursts (net teacher, seeds 1 and 2) on gen batch 1, elites,
   1000 starts x 4 seeds, player one only (about 2.5 thread-hours; the read
   rule is in the jobs' notes). Go (any mechanic +2 HP at 2 se pooled or wins
   -0.05): a shipped net reads retention on the whole bench, written into
   `pack-adapt-pipeline` and `decision/burst-adapted-column` at the read.
   Level: the interference belongs to SharpHide's 399 patched games, and a
   99-game burst on the mechanic itself keeps the bench. No queued job
   waits on it: the column's measure does not change either way.
3. **strength-by-hits-left gets a ready charter (project, the next project
   slot).** 0472 confirmed its mechanism in both directions: a flat price
   on enemy Strength removed the Nob cost (the leaf's HP price feeding
   Enrage) and cost +13 to +22 HP on AttackLoss-Strength on every parent
   (attacking feeds the Strength, so a flat price stops the net attacking).
   A price scaled by the hits a monster will still land falls as attacking
   shortens the fight, which is the term the flat price lacks. Trade-off
   check: on the current setting the scaled price can gain the Nob cut
   (+13 HP on 229 starts) with no games, and the official-Nob gain `@esp`
   showed (0.972 to 0.994 wins) without its -0.020 clears at bosses; the
   zero-shot net cannot gain either without games, and the family burst
   that does costs 399 games and the OppCard-Vulnerable edge.
4. **pack-pick-split, a new goal-2 candidate with a ready charter (the
   project slot after it).** With the Act 1 pack cards in the offers every
   player loses 0.106-0.158 clears (`measurement/act1-cards@pack-offers`);
   the lane's read puts it mostly in the offers (about half as many
   original cards offered) while the sim chooser still takes 3.1-3.6 pack
   cards a sequence, the worst holders being cards that pay after its
   horizon. Those two readings are confounded (fewer originals offered
   means more pack cards offered and taken). A chooser that sees the pack
   cards but may take only originals or skip splits them: what it recovers
   is the chooser's error on the real pool, which sizes the parked
   chooser work (`elite-horizon-chooser`, `static-value-chooser`), whose
   reopen condition is Act 1's cards in the engine (27 of the 40 are). It
   is a measurement of the current chooser, not chooser work (direction,
   "Avoid").
5. **ideas#76 (drifted mutation lineages)** checked and not proposed (backlog
   line): the record puts goal 1's cost on the mechanic, not on the distance
   in stats (`difficulty-shift`, both steps failed), and stacked modifiers
   miss their parts' sum by at most about 0.04 wins (`measurement/mutated-
   stacking@stage-a`), which the idea's band guard holds down; reopen when
   pack monsters carry two generated mechanics at once.
6. **Shares:** act1-content 30 (22.5 of its 24 cpu-h used, one job pending),
   gen-adapted-column 37 (its interim read passed, 57 jobs queued),
   all-content-net 23, main 10, filler 0.


Alternatives passed over: open nothing new until a lane closes (chosen: no
slot is free, three lanes open, so the two charters wait for a close);
`race-price` ahead of strength-by-hits-left (generated growth costs +0.48
on the bench, the smaller target); a two-turn read of the Nob and
Sentries costs (`two-turn-gen-read`: the price and the family burst each
remove them one turn deep, so depth is moot there). Reversible: 0546-0547
cancel while pending; the charters and shares are text.

## After the bench-retention probes: a pack's net reads retention on the whole bench, per parent; a joint-burst probe queued (on the owner's behalf, 2026-11-08)

Wake `job:0547`. Probes 0546-0547 read here
(docs/research/family-transfer-probes.md, "Bench-retention probes";
`measurement/bench-retention@gen-b1`).

1. **Outcome: go, read at the parent.** On all elites the 99-game
   AttackLoss-Weak bursts sit just under both bars on OppCard-Vulnerable
   (net HP lost +1.23 (0.31), wins -0.049; the bars were +2 HP at 2 se or
   -0.05 wins), so the read went one level down, as a check that lands at
   its bar gets a look: on Sentries the bursts lose 6.04 (0.70) HP and 0.16
   wins (0.765 to 0.581 / 0.626, heuristic 0.501), in both seeds, the same
   place the 399-game SharpHide bursts lost it. Every other mechanic, the
   parents and the stat ladder play better (-0.35 to -4.56 HP), so the
   interference is one spot, the net's largest zero-shot edge, recurring
   across two bursts on different mechanics with a quarter of the games.
   Decided: a pack's net reads retention on every generated mechanic of
   the bench, per parent, beside the official parents (written into
   `decision/burst-adapted-column` and `pack-adapt-pipeline`). Passed over:
   reading it as level because the all-elites numbers miss the bars (the
   Sentries loss is 8.6 se in both seeds; a pack on Sentries would ship it).
2. **Also read:** the bursts' general gain on long elite fights (the
   ladder -1 to -2.6 HP) cancels in the column's cost (its control gains
   too), so the column's measure stands; and the AttackLoss-Weak games
   halve AttackLoss-Damage x Nob's cost (+13.29 to +6.88 / +4.89) with no
   Nob fights in the burst: transfer by trigger, across parents.
3. **New probe, queued in lane `main`: pack-joint-burst** (backlog
   candidate 27). One burst over all eight batch-1 mechanics at once, 50
   fights each on the three elites (400 games), net teacher, two seeds:
   0549/0551 (bursts), 0550/0552 (bench reads, gen batch 1, elites, 1000
   starts x 4 seeds), 0553 (the family table, AttackLoss-Damage x Nob);
   configs/families/pjb.json, about 2.5 thread-hours. Read rule: go if
   OppCard-Vulnerable x Sentries net wins stay at 0.72 or more pooled (the
   single bursts 0.58-0.63, zero-shot 0.765), the Nob cost falls by half or
   more (0553 passes), and no mechanic's net HP lost rises 2 HP at 2 se on
   any parent: a pack's net is one burst over the pack's mechanics, which
   becomes `pack-adapt-pipeline`'s form and charter. Fail if the Sentries
   wins fall under 0.70 with OppCard-Vulnerable's own games in the burst:
   the interference is a conflict between mechanics in one net, not
   missing rehearsal, and per-mechanic nets or a retention term become
   the question. Between: report, no follow-up. Trade-off: a per-mechanic
   burst gains the column's number (games to adapt one mechanic) and
   cannot serve a pack; the joint burst can gain the pack's repairs (Nob
   +13.3, Sentries PlainDamage +5.4) while keeping the -9.5 edge, in one
   net. No queued job waits on it; the column's per-mechanic families
   measure a different number.
4. **Unchanged:** lanes and shares (act1-content 30, gen-adapted-column 37,
   all-content-net 23, main 10, filler 0); ready charters
   (strength-by-hits-left, then pack-pick-split). 

Alternatives passed over: a retention term in the burst (distillation
toward the zero-shot net on bench positions, as in learning without
forgetting) ahead of the joint burst (it needs code, and the joint burst
tests the simpler cause, missing rehearsal, with configs only); closing
nothing and reading only (the CPU sits idle, health `cpu` 0.29).
Reversible: 0549-0553 cancel while pending; the configs are new files.

## After the pack-joint-burst probe: a pack's net is one joint burst; pack-adapt-pipeline gets a ready charter (on the owner's behalf, 2026-11-08)

Wake `job:0553`. Probes 0549-0553 read here
(docs/research/family-transfer-probes.md, "Pack-joint-burst probe";
`measurement/pack-joint-burst@gen-b1`).

1. **Outcome: between, by its read rule.** The OppCard-Vulnerable x
   Sentries edge holds (wins 0.765 to 0.787, HP -2.22 (0.53)), where the
   single-mechanic bursts lost 0.14-0.18 wins; the Nob cost falls 0.47
   (bar 0.5; 0553 fail at its bar); and TurnEnd-Frail x Lagavulin rises
   +3.25 (0.42) HP, the parent x Lagavulin +1.67 (0.37), both seeds, wins
   down about 0.01. No separate follow-up probe, as the rule said.
2. **Decided: a pack's net is one joint burst over the pack's
   mechanics**, read for retention on every mechanic of the bench per
   parent (`decision/burst-adapted-column`), and a net that fails that
   guard does not ship (the zero-shot net stays for the pack). Rehearsal
   by the pack's own games answers the interference 0546-0547 found;
   per-mechanic bursts lose a neighbour's edge and cannot serve a pack.
   The guard would stop batch 1's 50-game net on Lagavulin, so the
   pipeline's first pack run reads two arms: 99 games per mechanic (the
   dose: does the Nob cut pass and the Lagavulin leak shrink with more
   own games, or grow) and the same with the pack's unmodified parents in
   the burst (rehearsal of what the guard reads; the leak sits on the
   parent and its short ladder rows).
3. **Ranking.** `pack-adapt-pipeline` (backlog 25) gets the ready charter
   for the project slot after `strength-by-hits-left`, ahead of
   `pack-pick-split` (goal 1's "first-class custom content", development
   weight 0.8 against goal 2's 0.2; about 3 h of code). `pack-pick-split`
   keeps its charter for the slot after. Candidate 27 is answered.
4. **Unchanged:** lanes and shares (act1-content 30, gen-adapted-column
   37, all-content-net 23, main 10, filler 0). 
5. **Noted for the lane worker:** gen-adapted-column's pending bursts
   (0502 onward) ask 3.0 GB against measured peaks of 0.46-0.58 GB
   (0496, 0549, 0551), so the runner holds them back, which is most of health's idle CPU.

Alternatives passed over: a 99-game joint burst queued now in lane
`main` (the read rule said no follow-up between, and the dose read is
the pipeline's first pack run, where its answer is used); a retention
term in the burst (distillation toward the zero-shot net on parent
positions, as in learning without forgetting: code, and rehearsing the
parents tests the simpler cause first; it comes back if the parents arm
leaves the leak); calling it a go because the Nob cut misses by 0.03
(the Lagavulin leak is 7.7 se and would ship). Reversible: a backlog
order and a charter text; nothing queued or cancelled.

## Lane gen-adapted-column closed (2026-11-08)

Outcome: done; the stop rule's done branch (the column holds four
mechanics; checkpoint column4 passed), and the fail branch did not fire
(both teachers halved the target's cost at 99 games, checkpoint alw-g99).
The column (`docs/research/gen-adapted-column.md#The column (lane close,
2026-11-08)`): about 100 games adapt the 10-29 net to each of four
generated enemy mechanics, one turn deep, with the net's own games (all
four pass: 1.05, 0.56, 0.77, 0.59 of the zero-shot cost) or the
heuristic's (0.56, 0.66, 0.50 at the line, 0.56); 33 games on the target
cut 0.20 / 0.30, because this finetune overfits after one pass at that
size. Single-parent bursts cost the trained elite's plain fight 0.3-1.1
HP per fight (wins flat); OppCard-Weak bursts on Lagavulin carried to
Sentries and Nob. Facts: `measurement/gen-adapted@alw-g99`, `@alw33`,
`@ocw`, `@ocpd`, `@ocd`.

Against the opening rating: **likely** that net-game bursts at 99 games
halve the target's cost: yes, and on all four mechanics. **Even** that
heuristic games beat them by 2 se: no at 99 games (the heuristic never led
by 2 se; the net led on two mechanics, level on two); at 33 games the
heuristic's games cut more (+1.84 against +1.20, one game set each), so
the teacher arm is not shown wrong at both sizes, as its backlog test
required, only at 99.

CPU: 7.5 lane cpu-h against the 15 cap (health.json `lane_cpu_h`) and the
opening estimate of about 10.

**Reopen if:** (a) a finetune recipe that keeps improving past one epoch
at 30-50 games (a lower learning rate, a fixed small epoch count, or a
higher replay share) exists: then the 33-game point is worth re-reading,
since games to adapt below 99 is goal 1's number and today's 33-game read
measures one pass; or (b) a new batch of generated mechanics outside the
OppCard and AttackLoss triggers (turn-start, on-damage, block-based)
lands on the bench: the column has four mechanics from two trigger
families, and whether about 100 games is enough elsewhere is untested; or
(c) the trained-parent loss (0.3-1.1 HP) needs fixing for a product burst:
read two-parent or pack-rehearsal bursts on one of these families against
the single-parent tables here.

Next: the charter's on-close is `wake always`: a navigator wake with the
outcome; the slot stays empty for the navigator, and the lane's 37 share in
`jobs/lanes.json` goes to the open lanes (act1-content 30 -> 51,
all-content-net 23 -> 39, about their ratio).

## Lane strength-by-hits-left opened (on the owner's behalf, 2026-11-08)

`gen-adapted-column` closed done (its on-close `wake always` called the
navigator) and left the project slot empty. It goes to
`strength-by-hits-left` (backlog candidate 23), the backlog's first ready
charter for the next project slot since the navigator run of 2026-11-07;
the charter is copied as written into `lane/strength-by-hits-left`.

Rating (backlog, unchanged by the close): **even** that one scale keeps
half of AttackLoss-Damage x Nob's cut with AttackLoss-Strength within
1.5 HP of zero-shot (0472 showed the flat `@esp0.04` fixes Nob and stops
the net attacking where every attack feeds the Strength; a price that falls
as the fight shortens is the missing term); **a long shot** that it passes
the one-turn headline. About 2 h of engine code and about 3 cpu-h of reads
(cap 6).

Alternatives passed over:
- `pack-adapt-pipeline` (candidate 25, the next ready charter): larger (3 h
  of code, 6 thread-h) and a games answer; a zero-games price, if it holds,
  is goal 1's better answer to the same costs, and the pipeline's guard
  reads the same bench either way. It stays first for the slot after this.
- `pack-pick-split` (candidate 26): goal 2 (development weight 0.2);
  goal 2's CPU weight is served by `all-content-net` for now.
- `few-game-recipe` (new candidate 27, from this close's reopen condition
  (a)): a recipe read with no code (finetune.py already takes `lr`,
  `epochs` and `share`), so it does not need a lane's slot first; ranked
  behind the pipeline.
- Opening a fourth lane: neither open lane is within a few days of its end, so no.

Shares (`jobs/lanes.json`): act1-content 51 -> 40, all-content-net 39 ->
30, strength-by-hits-left 20, main 10. The new lane is code first; its
reads are about 3 cpu-h, so a fifth of the CPU covers them, and
act1-content's last checkpoint passed, so it keeps the largest share.

## strength-by-hits-left: step 1 built, step 2 queued (on the owner's behalf, 2026-11-08)

Step 1 of the charter is built as `@shl<k>` (docs/specs/strength-hits-price.md):
the leaf loses `k x clamp(score / 2) x H`, `H` = each living monster's
Strength x its hits per round x the rounds it still lands them, the rounds
taken from the heuristic's kill order (the round it is expected dead,
capped at the player's expected death). Off by default: golden ok,
series_check PASS, the heuristic's estimates pinned bit-identical.

Choices, with the alternatives passed over:
- Rounds from the heuristic's kill order (one definition of "rounds left"
  in the project) rather than the fight's total rounds for every monster,
  which would price a monster killed first as if it lived to the end
  (Sentries).
- Scales 0.005 and 0.01: at 0.01 a point of Strength that lands 10 hits
  costs what 10 HP cost under `@hpb0.01`; 0.005 allows for block taking
  about half, and at Gremlin Nob's opening (about 10 rounds, under one hit
  a round) about equals the flat `@esp0.04` that fixed Nob. A wider grid
  (0.0025-0.02) was passed over: the cap is 6 cpu-h and the stop rule asks
  for one scale that keeps the Nob cut, so two bracketing scales decide it.
- Step 2 as two jobs at 3 threads on the 0472 command (gen batch 1,
  elites, 1000 starts x 4 seeds, `--players heuristic,one`), so they pair
  with 0472 and the zero-shot bench seed for seed. Reversible: pending
  jobs can be cancelled; the flag is off by default.

## Lane strength-by-hits-left closed (2026-11-08)

Outcome: **fail** by the stop rule (checkpoint gen-b1-scales failed;
docs/research/strength-hits-price.md). The `@shl<k>` leaf price (enemy
Strength x the hits it will still land) cut AttackLoss-Damage x Nob's cost
by 71% at k 0.005 and 93% at 0.01, but no scale kept AttackLoss-Strength
within 1.5 HP of zero-shot on every parent: 0.005 misses on Nob only
(+2.37 (0.57)), 0.01 misses on all three (+9.38, +4.77, +1.67). It removes a
half to nine-tenths of the flat `@esp0.04`'s damage there, not all of it.
Step 3 (the headline) did not run. CPU: 3.0 of 6 cpu-h (two 31-minute
reads at 3 threads, the build's checks). The flag stays in the code, off
by default (golden and series_check unchanged).

**Reopen if:** a version prices the change in Strength a choice causes
against the fight it shortens, not the level held (for example the
difference in `strength_hits_left` from the decision's root, with the
turns-left credit of the damage dealt counted at the same rate), and an
offline check on the 0554 file's AttackLoss-Strength x Nob starts shows it
no longer ranks attacks below skills there; or a cheap read of k 0.0025
(one 31-minute job) is wanted for a goal-2 reason: the official Nob parent
improved by 0.36 HP (0.18) at 0.005, a lead that only a headline read
would turn into a result.

Next for the slot: `pack-adapt-pipeline` (the charter's on-close is `wake
on go`; this was a fail, so the lane worker opens the first ready charter
for the project slot, see "Lane pack-adapt-pipeline opened").

## Lane pack-adapt-pipeline opened (on the owner's behalf, 2026-11-08)

`strength-by-hits-left` closed on a fail (its on-close `wake on go` does not
call the navigator), leaving the project slot empty. It goes to
`pack-adapt-pipeline` (backlog candidate 25), the navigator's ready charter
"for the next project slot" (backlog summary of 2026-11-08 and decisions
"Lane strength-by-hits-left opened", where it "stays first for the slot
after this"); the charter is copied as written into
`lane/pack-adapt-pipeline`. Candidate 24's ready charter
(`recurring-debuff-leaf`) is for the exploration slot, only when
`all-content-net` closes on a fail, so it is not this slot's.

Rating (backlog): **likely** as code; **even** that one of the first run's
two arms ships under the guard with the Nob cost halved. About 3 h of code
and about 6 thread-h (cap 9). The strength-by-hits-left close adds to its
case: a zero-games price does not repair the generated punish-an-action
costs, games do.

Shares (`jobs/lanes.json`): pack-adapt-pipeline takes strength-by-hits-left's
20. Reversible: the lane can be closed at its first checkpoint; nothing is
queued yet.

## pack-adapt-pipeline step 1 built: the pack chain; gen batch 1 queued (on the owner's behalf, 2026-11-08)

Spec `docs/specs/pack-adapt-pipeline.md`, confirmed under the mandate.
`family.py queue configs/packs/<name>.json` now goes from a pack of
generated enemy mechanics to its table and, under the guard, its net
(`results/packs/<name>.json`), with no session between. Choices, each
reversible by editing `family.py`:

- A pack file is a family file with a `pack` key (one driver), not a new
  script. Alternative: a separate `pack.py` (two drivers to keep in step).
- Burst configs are written by `queue` to main's `results/packs/<name>/`,
  not committed: the pack file is their source. Alternative: commit
  generated configs (a commit between pack and queue, i.e. a session).
- Guard per net, since the shipped thing is one net; the lane's target
  (AttackLoss-Damage x Nob halved at 2 se over nets) is per arm and
  reported, not gating. "Loses 2 HP at 2 se" reads as delta >= 2 and
  delta >= 2 se, as the pjb write-up used it. Alternative: the lower bound
  delta - 2 se >= 2 (looser; would let the pjb s2 net's Lagavulin +2.38 (0.38)
  through).
- `"parent"` (no patch) joins `mutate_monsters.ALL` so a burst can rehearse
  the unmodified parents.

Check: the pack table on the two pjb nets reproduces the probe's hand
read (TurnEnd-Frail x Lagavulin +3.25 (0.42), parent x Lagavulin +1.67
(0.37), Nob cut +6.56 / +5.92 per net against cost +13.29) and refuses
both nets (s1: parent x Lagavulin +2.22, TurnEnd-Frail x Lagavulin +4.11;
s2: TurnEnd-Frail x Lagavulin +2.38). Review: no must-fix.

Step 2 queued from one command (`configs/packs/gen-b1.json`, base
`results/mutate/gen-enemies-b1.json`): bursts 0556/0558 (g99), 0560/0562
(g99 with the parents), reads 0557/0559/0561/0563, table 0564 with the
verdict check; about 6 thread-h. Read: go if the table is written with no
session and a net ships with the target passing; between if the chain runs
and no net ships (then the failing cells name the leak); fail if a session
is needed between queue and table.

## Navigator 2026-11-08 midday: a held-out read of the Strength price; stall wakes; act1-content's cap extended (on the owner's behalf, 2026-11-08)

**`cause/leaf-price-trades`** (new). Leaf changes that run the engine's
own rules further have not traded one mechanic for another: the turn-start
leaf `@tsl1` repaired Demon Form decks (+7.54 (1.10) HP) with train and
other held-out level (`measurement/turn-start-leaf@cells`), and the
projected leaf `@pl2` moved HP the right way on its target and +0.14
(0.07) on one control (`measurement/projected-leaf@cards-k2`). Leaf
changes that add a hand-set price do trade: `@esp0.04` removed
AttackLoss-Damage x Nob's cost and cost +13 to +22 HP on
AttackLoss-Strength (`measurement/esp-on-gen@batch1`); `@shl0.005` kept 71%
of that cut and cost AttackLoss-Strength x Nob +2.37 (0.57) HP, with that
cell's wins up 0.879 to 0.892 (`measurement/shl0.005@gen-b1`); `@shl0.01`
cut 93% and cost +9.38 / +4.77 / +1.67 (`measurement/shl0.01@gen-b1`). So
zero-games repairs are looked for among simulations of the rules
(`recurring-debuff-leaf` is one), and a price is read on the whole bench,
not on its target.

**Probe `shl-held-out`, job 0566** (lane `main`, probe sheet, about 3
thread-h, pinned to 3c92d1b2b8c8, which holds `@shl`). The closed lane
`strength-by-hits-left` asked for a price with no cell worse by 1.5 HP; its
reason stands: there is a trade on AttackLoss-Strength x Nob. This probe
asks a different question, which the lane did not read: is the trade
confined to that cell? `@shl0.005@tsl1` on the 16 bench mechanics outside
gen batch 1 (none of which gives a monster Strength, so the price acts
there only through Nob's Enrage, where the unmodified Nob gained -0.36
(0.18) HP). Go: no mechanic x parent row worse by 1.5 HP at 2 se or 0.03
wins, mean change over the 16 not above 0 at 2 se; then the navigator
queues the one-turn headline `@shl0.005` against the one-turn control
(the lane's unrun step 3, about 2.7 thread-h), and a pass there would make
`@shl0.005` a candidate leaf for the bench's reading player and the pack
teacher, a goal-1 gain of about a third of the bench's mean cost with no
games. Stop: any row worse by 1.5 HP at 2 se, or the mean above 0; then
`cause/leaf-price-trades` holds beyond the target and prices are dropped
as goal 1's zero-games route. Alternatives passed over: a joint grid of
`@esp` and `@shl` values tuned on the bench (about 6 thread-h, and a value
fitted on batch 1 needs this held-out read anyway); nothing (the CPU is
idle about 80% of the time, `jobs/health.json` cpu 0.19, and the read
fits beside the other work at a 1.6 GB peak).

**Stall wakes, jobs 0567 and 0568** (`cause/memory-holds-bursts`'
planning rule). 0477-learn (all-content-net, mem_gb 5, needs 6 GB free)
has waited over 12 hours for free memory; 0492-series-speed (act1-content, many threads) has waited over
11 hours for idle cores and blocks checkpoint e1-encounters. Neither lane
gets a worker while a pending job counts as busy, so each gets a one-line
light job whose end wakes its lane worker, with the stall in its note.
The re-plan is the lane's (the navigator does not touch their jobs). If
0477 has not started by the review, the navigator weighs the exploration
slot there (`recurring-debuff-leaf` is its ready charter).

**act1-content's cap: 24 to 36 cpu-h, end unchanged (2026-11-13); its one
extension.** It has used 22.5 of 24 (`jobs/health.json` lane_cpu_h), and
0492 alone is about 1.4 thread-h; what is left is mostly engine and
content code, plus one headline re-rank per kind at about 2-3 thread-h each. A cap
reached mid-block wakes a lane worker to close a lane whose work is the
direction's first interest. Alternatives passed over: let it reach the
cap and open a successor lane (a close, a charter and a session for the
same work); extend the end date (not needed: the end is five days out).
A second extension needs a new lane.

**Backlog**: the ranking paragraph rewritten to today's lanes;
`finish-faster-tiebreak` (the owner's discussion) ranked after
`pack-pick-split` as engine code; the probe sheet
carries 0566.

## all-content-net: seed 1 re-queued at 2.5 GB instead of 5 (on the owner's behalf, 2026-11-08)

The navigator's stall wake 0567: 0477-learn (allcontent40k-s1, 6 threads,
`mem_gb` 5, so 6 GB free needed) waited 12 h for free memory. The 5 GB came from the October data40k runs, which
had no measured peak. Since then the encoded datasets are written in
chunks by `DatasetWriter` and read memory-mapped (`stsnet._load_npy`,
`mmap_mode="r"`), so the 40k training data sits in the file cache, which
Windows can reclaim, not in private memory. learn.py at the same settings
(6 threads, exact_cap 50000, solve_threads 6) on 5000 games peaked at
1.18 and 1.62 GB (0211, 0212). Decision: cancel 0477 and queue the same
command at `mem_gb` 2.5 (starts at 3.5 GB free), keeping the recipe and the
twin (data40k-s1) unchanged; the measured `peak_gb` is recorded in the step
fact when it ends and sets later seeds' `mem_gb`.

Alternatives: keep 5 GB (it may not start before the lane's end on
2026-11-13); train at 20k against a data20k twin (changes the recipe and
needs a new twin replay); fewer threads (no help: the peak is not
per-worker data). Reversible: if the peak is over 2.5 GB, seeds 2-3 get
the measured peak; if it pages other processes, kill it and queue at 4.

## After shl-held-out: the Strength price's trade stays on one cell; its one-turn headline read queued (on the owner's behalf, 2026-11-08)

Job 0566 (`measurement/shl0.005@gen-rest`, `docs/research/strength-hits-price.md`
"Held-out read") went on its rule: `@shl0.005@tsl1` on the 16 bench
mechanics outside gen batch 1 breaks no row (worst +0.34 (0.12) HP,
TurnStart-Frail x Nob, wins level), the mean change is -0.41 (0.06) HP per
elite fight, Lagavulin and Sentries are identical to zero-shot (no monster
Strength, so the price is zero there), and every Nob row but the three
Frail ones gains (-0.35 to -4.55 HP, wins up by as much as 0.064). With batch 1 the
price's whole bench record is: AttackLoss-Damage x Nob -9.49, the
unmodified Nob -0.36, the 16 held-out mechanics -0.41 on average, and one
trade, AttackLoss-Strength x Nob +2.37 (wins up). The closed lane's reason
stands as written (one cell over 1.5 HP); what is new is that the trade
is confined to that cell.

Decided:
- Queue the one-turn headline read the lane never ran: job 0572, the
  10-29 net `@hpb0.01@shl0.005` on the headline setting, sequences 0-499,
  `--against` the one-turn control (pinned 3c92d1b2b8c8, about 3.5
  thread-h). Its note carries the read rule: a pass makes `@shl0.005` the
  candidate leaf for the bench's reading player and the pack teacher;
  level (no protocol fail) makes it that for goal 1 only; a protocol fail
  keeps it off. Alternatives passed over: adopt it for goal 1 now on the
  bench alone (the bench plays cell decks at fixed entry HP, not official
  runs, `yardstick/novelty-read` (c); one read settles it); reopen
  `strength-by-hits-left` as a lane (no code is left to build; a probe is
  enough).
- `pack-adapt-pipeline` keeps its teacher (`@hpb0.01@tsl1`) for gen batch
  1's queued run; whether a pack teacher takes the price waits for 0572
  and is the navigator's call then.
- `cause/leaf-price-trades` is re-set: hand-set prices trade where the
  priced quantity is what the mechanic grows (the flat price everywhere
  Strength grows; `@shl` on one cell), and a price that tracks how long
  the threat lasts can be inert or help elsewhere.

## Card-upgrades spec confirmed (block C6; owner, 2026-11-08)

Spec `docs/specs/card-upgrades.md`, from the owner's design (explorer
session, 2026-11-08) and interview; queued, built by the `act1-content`
lane worker right after M6+M7. Provisional.
- Upgrades are data in the card's entry: an `upgrade` block of paths
  beside the effects (`"effects.0.Damage.amount": 2`, `"cost": -1`,
  `"exhaust": false`). A number change is added at each upgrade, a
  constant or an expression of `n`, the level reached (integers, `n`, `+`,
  `*`; Searing Blow `"n + 3"`); a keyword is set from level 1; cost floors
  at 0. `max_level` defaults to 1, `null` is no limit. Alternative: `up`
  inside each effect (touches every effect's parser).
- Level 0 and 1 keep today's card id pair, so official play, golden, the
  rules version, encodings and feature arrays stay identical; level 2 and
  up is a per-copy variant (`Overrides` gains the level; variants allowed
  on pack cards). Names `Name`, `Name+`, `Name+N`. Search speed wins over a
  general level model (owner). Alternative: a level byte per copy.
- No net input column for the level: the card's numbers show it.
- `AddCard` gains `match_level`: the added card takes the played card's
  level, capped at its own max level (Anger; Storm of Steel, Alpha / Beta /
  Omega later). Alternative: an `AddCopy` form (Anger only).
- A unique upgrade (True Grit+) stays a separate `"X+"` entry, linked by
  its name; old-format packs mean the same.
- General upgrades (rest site, Armaments) skip statuses; only special
  effects (Hexaghost's Inferno, still code) upgrade them.
- `content/cards.json` and `act1-ironclad.json` are rewritten into the new
  form, tested equal to the old definitions. Armaments is in scope;
  Apotheosis, curses, relics and the rest-site chooser's rule are out.
- Versions: the rules version doesn't change (golden identical; the brief
  expected a change); the solved-DB fingerprint changes as for any engine
  block; the rewritten pack gets a new content hash (old records replay
  from the pack store).
- Amended the same day (owner): X-cost and Unplayable are negative costs
  (-1, -2) as the game encodes them, so a card can't be both; `CardDef`
  keeps cost private behind `cost()` (0 for both, as readers see today),
  `x_cost()` and `unplayable()`, and the net's columns are unchanged. Old
  files still load (the flags map to the sentinels). New load errors: a
  cost change on an X or unplayable card, an unplayable card with on-play
  effects or `only_attacks_in_hand`, a Power with `exhaust`. Alternative:
  keep the booleans and refuse both at load (the bad state stays
  writable). `held_out` / `proving` stay; moving card sets out of card
  definitions is its own spec (`card-sets`).

## Card-sets spec confirmed (owner, 2026-11-08)

`docs/specs/card-sets.md`, queued ahead of card upgrades (C6). Provisional:
- Card pools move out of card definitions: `CardDef` loses `held_out` and
  `proving`; the pools are named lists in `configs/card-sets.json`
  (`ironclad`, `silent`, `check9`, `proving`), built into the engine and
  read by Rust and Python alike. Alternatives: Python only (the engine's
  default pools would change), or each training config listing its pool.
- A set is a plain list of base names (the `+` card comes with it), used in
  card order, so adding content never changes a pool. Alternative: rules
  (class minus other sets), as today's flags behave.
- `sts.deck_card_names`, `class_card_names` and `held_out_card_names` keep
  their names and results; `sts.card_set(name)` is new. Alternative:
  replace every caller.
- The official loader accepts and ignores the old flags; packs keep refusing
  them. Alternative: check them against the sets file.
- The sets file is not part of the rules fingerprint. Every pin (golden,
  `GAMES_PIN`, `ARRAYS_PIN`, `TRAIN_PIN`, `rules_version()`) stays identical.
- Out of scope: the scripts' own sets (check 6, bench sets, transfer tiers),
  the `class` field, sets of pack cards.

## Lane pack-adapt-pipeline closed (2026-11-08)

Outcome: **go** by the stop rule, at its bar on retention (read in
`docs/research/family-transfer-probes.md`, "Gen batch 1 through the pack
chain (0556-0564)"). `family.py queue configs/packs/gen-b1.json` ran from
queue to table (0556-0564) with no session between. AttackLoss-Damage x
Nob's cost (+13.29) is cut by +11.50 (g99) and +9.91 (g99-parents), well
past half at 2 se. One net per arm passes the guard; the table ships
g99-parents s1 (`results/packs/gen-b1.json`). Read sceptically: that net's
TurnEnd-Frail x Lagavulin loss is +1.99 (0.40) HP against the guard's 2.0,
picked as the best of four nets on the starts the guard reads, and the
other three lose 3.0-8.4 HP there. So the chain is done, and the Lagavulin
leak stands in every net. Parents in the burst made it worse (parent x
Lagavulin +2.06 against +0.87), which points at the teacher on Lagavulin
rather than forgetting (untested). Per the stop rule's between branch,
which describes this case in substance, the leak is reported and a
retention term (or the teacher on Lagavulin, or a stricter guard: a bar on
the pooled arm or on the upper bound) is the navigator's question.

CPU: 3.8 thread-hours against the cap of 9 (health.json `lane_cpu_h`).

Not changed: the guard (the spec's), and the shipped net is not promoted
anywhere: it is the pack's net for gen-b1 only.

**Reopen if:** a retention fix (a retention term in the burst, a teacher
that plays parent Lagavulin at least as well as the zero-shot net, or a
stricter guard) is chosen. Then re-run `family.py queue
configs/packs/gen-b1.json` with it; the chain needs no new code beyond
that change. Reopen also if a second pack (gen batch 2, or real Act 1
content from `act1-content`) cannot go through the chain unchanged.

## Lane pack-retention opened (on the owner's behalf, 2026-11-08)

The project slot `pack-adapt-pipeline` left (closed go, wake always) goes
to `pack-retention`, backlog candidate 29, rewritten from
`pack-leak-retention`. Its reopen condition is met in kind: a retention fix
is chosen.

Evidence: `measurement/pack-chain@gen-b1`. GE-TurnEnd-Frail x Lagavulin
gets worse in all four burst nets (+1.16, +4.86, +1.99, +8.37 HP per
fight, per net). Putting the parents in the burst makes the Lagavulin
parent worse (+2.06 against +0.87). The net that shipped sits at the
guard's bar and was picked on the starts the guard reads. Lagavulin is
fragile under bursts elsewhere too: the OppCard-Weak bursts cost the
trained Lagavulin parent about 0.8 HP with either teacher
(`measurement/gen-adapted@ocw`), and a SharpHide burst seed lost 4.4 HP on
it (`measurement/family-transfer@gen-b1`). So two causes stay open: the
teacher's games on Lagavulin (the lane worker's reading) and forgetting
outside what the burst covers.

The lane tests both, cheapest first:
- step 1 needs no code: the same g99 arm with the heuristic as burst
  teacher, through the chain from its own pack file;
- step 2 needs code: a retention term in the burst (distillation toward
  the parent net's values on the burst's own positions, or L2 toward the
  parent's weights);
- the fix chosen gets a confirm read of its shipped net on fresh bench
  starts, which gives the guard a held-out check in place of picking on
  the starts it reads.

Rated **even**. For: the leak shows in every seed and both arms, and
distillation to the old model (learning without forgetting) is the
textbook fix. Against: a pull toward zero-shot may pull back
AttackLoss-Damage x Nob's cut as well, since both live in the same value
head, and the OppCard-Weak bursts lost Lagavulin HP with the heuristic
teacher too. The estimate is about 8 thread-h: each arm is 2 bursts and 2
bench reads, about 2.2 thread-h, plus the confirm read.

Alternatives passed over:
- `pack-pick-split` (the ready charter for this slot; goal 2, 3.3
  thread-h). Goal 2 keeps its CPU through `all-content-net`, goal 1's
  development weight is 0.8 (`docs/direction.md`), and this question came
  from the closing lane. `pack-pick-split` takes the next project slot.
- `finish-faster-tiebreak`: half a day of engine code. It stays after
  `pack-pick-split`.
- A stricter guard alone: it only refuses nets; on this pack it would
  ship none and repair nothing.
- The fresh-start re-read alone, as a probe-sheet job: with the leak at
  +1.2 to +8.4 HP in every net, a read showing it under 1 HP is unlikely,
  so it can't decide the question by itself. It is kept as the lane's last
  step instead.

Shares (`jobs/lanes.json`): act1-content 30, all-content-net 30,
pack-retention 30, main 10, filler 0. `act1-content`'s next step, M6+M7,
is code and uses little CPU.

## all-content-net: seeds 2-3 reserve 3 GB, one after the other (on the owner's behalf, 2026-11-08)

Seed 1 (0569) reserved 2.5 GB and its `peak_gb` read 5.89. That number is
the working set of the job's process tree (jobs.py samples it each poll),
which counts the memory-mapped dataset pages Windows can reclaim (decision
"all-content-net: seed 1 re-queued at 2.5 GB"), so it overstates what the
job holds privately; the run finished without a crash or a stall. Decision:
seeds 101 and 201 (`configs/allcontent40k-s101.json`, `-s201.json`, the
twins' seeds) queue at `mem_gb` 3 and 6 threads, seed 201 after seed 101,
so the two never peak together.

Alternatives: reserve the measured 5.89 (needs about 7 GB free, more than was usually free, so the seeds would miss the lane's
end on 2026-11-13); keep 2.5 (same as seed 1, but the runner then counts
the running job at its measured peak anyway); run both at once (twice the
paging risk for about 1.5 h saved). Reversible: if a seed pages other
processes or dies of memory, cancel the other and re-queue it at 5.

## Blocks M6 and M7: ally block at MonsterRolls; Entangled as a pack power (on the owner's behalf, 2026-11-08)

Lane act1-content, spec `docs/specs/m6-m7-monsters.md`. Two choices:
- **Shield Gremlin's random ally block** is picked as a chance event at
  `MonsterRolls`, after every monster has acted, just before the Shield
  Gremlin rolls its next move. Alternatives: make the monster turn
  resumable at a chance node (true to the game, which picks when Protect
  runs; the largest engine change), or roll the ally together with the
  move a turn early (shows the player the target before the game would).
  The chosen way differs from the game only when the player damages the
  protected monster during the monster turn (Thorns, Flame Barrier).
  Reversible: one function (`request_roll`) and one chance event.
- **Entangled** is a pack power with a new `forbids` field (no Attacks
  while held), applied by Red Slaver's move through `Effect::ApplyPack`.
  Alternative: an official Entangled power, which shifts the generated
  power slots, the codec masks and goldens, and adds a net column. The
  pack way keeps official content and the net's layout as they are, and
  is the goal-1 shape (any author's "can't play X" debuff).

## After seed1-bosses: the gain split by deck; the pooled read gets a second control and the split; the two-turn call needs a gain outside Demon Form decks (on the owner's behalf, 2026-11-08)

Navigator, woken by `checkpoint:all-content-net@1` (passed seed1-bosses,
`measurement/all-content-s1@boss-replay`). I split 0574's file and its
twin's (`results/boss_replay/allcontent40k-s1-hpb0.01.json`,
`data40k-s1-r1-hpb0.01.json`) by deck stratum, with the 10-29 net's
replay
(`results/boss_replay/net1029-hpe0.01-two-starter-simboss-2026-10-29-seed-check-r2-s1-1a789b2-hpb0.01-12a77a-55cb.json`)
as a second control; wins per deck averaged over the HP x seed grid,
paired by deck, se over decks. Strata: train decks, held-out decks with
Demon Form, held-out with Metallicize and no Demon Form, other held-out.
The first row covers all three bosses (235 / 36 / 73 / 130 decks); the
others the Guardian and Hexaghost only (143 / 24 / 53 / 89).

| net minus control | train | other held-out | Metallicize | Demon Form |
|---|---|---|---|---|
| all-content s1 minus its twin (all three bosses) | +0.000 (0.007) | -0.005 (0.008) | +0.167 (0.019) | +0.272 (0.040) |
| all-content s1 minus the 10-29 net | +0.024 (0.009) | -0.004 (0.010) | +0.064 (0.013) | +0.344 (0.046) |
| twin data40k s1 minus the 10-29 net | +0.007 (0.009) | -0.007 (0.010) | -0.155 (0.018) | +0.030 (0.024) |
| 10-29 recipe s101 / s201 minus the 10-29 net | -0.012 / +0.000 | -0.021 / +0.000 | -0.002 / +0.024 | +0.003 / +0.007 |
| 400-game heuristic bursts on Demon Form decks (three seeds) | -0.012 to -0.050 | -0.020 to -0.050 | -0.018 to -0.119 | +0.260 to +0.286 |

What it says:
- No boss was learned: on train decks the net gains nothing against its
  twin over the three bosses (Hexaghost +0.030 (0.012), Slime Boss
  -0.027 (0.008)).
- The Metallicize part is mostly the control's own weakness: the twin
  loses 0.155 wins on those decks to the 10-29 net, whose seed siblings
  are level there; against the 10-29 net the all-content net gains
  +0.064 (0.013).
- The Demon Form part is the first tick: three 400-game bursts on Demon
  Form decks gain the same +0.26 to +0.29 at these bosses, and the
  turn-start leaf prices that tick with no games
  (`cause/unseen-cards-half-edge`). Two turns of search already play
  Demon Form.
- Against the 10-29 net, outside the Demon Form decks, the all-content
  net gains +0.024 on train decks and +0.064 on Metallicize decks at the
  Guardian and Hexaghost: about +0.02 wins over all non-Demon-Form
  decks, one seed.

Decisions:
1. The lane's pooled read (seeds 1, 101, 201) reports, beside its
   chartered twin pairing, the same per-boss numbers against the 10-29
   net and the four strata above. The stop rule is unchanged (a fail
   against the twins is a fail against the stronger control too).
2. On a go, the two-turn headline read runs only if the gain outside
   the Demon Form decks, against the 10-29 net, pools to +0.03 wins at
   the Guardian or Hexaghost; otherwise the go is recorded as "held-out
   cards learned, mostly Demon Form's first tick", and no two-turn read
   runs (a leaf gain reaches the product at a third,
   `cause/leaf-gain-third`, and two turns already play Demon Form).
   0585, the one-turn headline against the one-turn control, still
   decides the go as chartered.
3. `measurement/all-content-s1@boss-replay` is flagged for the lane
   worker: "the gain is mostly the held-out cards entering training"
   holds for Demon Form decks; on Metallicize decks most of it is the
   twin's weakness against the 10-29 net.

Alternatives: re-set the stop rule against the 10-29 net (changes a
running lane's bar after a pass; the twin pairing controls the recipe,
and the second control is enough to read it); close the lane now as "no
boss learned" (passed over: 0585 and two seeds are queued, about 13
thread-hours, and the headline read is goal 2's real question); leave
the read as is (would send a Demon-Form-driven go to a two-turn read
worth about +0.01 clears). Reversible: a charter line and a read rule.

Ideas from it: an ensemble against seed luck on unseen cards is not
proposed: the 10-29 recipe's seeds and their three-seed ensemble are
level on these strata (ensemble +0.023 (0.009) on Metallicize decks,
plain leaf), so the spread is the data40k twin's alone. Whether the
data40k recipe is weak on Metallicize in general shows in its s101 and
s201 replays (0581, 0582), already queued.

## pack-retention step 2: an L2 anchor to the parent's weights, two weights (on the owner's behalf, 2026-11-08)

Step 1's seed 1 (0576) fails checkpoint `heur-teacher` either way: the
heuristic teacher keeps the Lagavulin cells near zero-shot but loses the
Nob cut (-2.51 against the net teacher's +11.50;
`docs/research/family-transfer-probes.md#Pack-retention step 1, seed 1
(0575, 0576): the heuristic as burst teacher`). Seed 2 and the table
(0577-0579) still run for the record. Step 2 starts now, on the net
teacher: `docs/specs/burst-anchor.md`, a config key `anchor` λ that adds λ
x the summed squared distance of the weights from the parent's to the
burst's loss. Arms λ = 0.003 and 0.03 (the gen-b1 bursts drift 9-21 at a
loss near 0.12, so λ = 0.01 makes the two equal), two seeds each, through
`configs/packs/gen-b1-anchor.json` with the zero-shot base reused: about
5.8 thread-h; the lane has used 1.5 of its 12 cpu-h.

Alternatives: distillation toward the parent's outputs on the burst's own
positions (pulls the Nob cut back as directly as the leak, and needs an
extra forward pass per batch; kept as a later arm if the anchor fails);
one weight only (cheaper, but a single miss would not say which way to
move); waiting for seed 2 first (it cannot turn the checkpoint into a go,
and the queue would idle the lane).

## After shl-headline: @shl0.005 level on the headline; goal-1 bench tables read it beside @tsl1; running chains keep their leaf (on the owner's behalf, 2026-11-08)

Job 0573 (`docs/research/strength-hits-price.md` "Headline read",
`measurement/shl0.005@headline`): the 10-29 net `@hpb0.01@shl0.005` one
turn deep on the headline, against the one-turn control, stays open at n
500: +0.95 (0.64) HP, clears +0.012 (0.016), z +0.74, Gremlin Nob -0.30
(0.40) HP per fight at the same entry HP. Level, so by the read rule of
"After shl-held-out" the price is goal 1's candidate leaf and nothing for
goal 2.

Decided:
- Goal 2: the one-turn controls stay plain (`yardstick/one-turn-controls`)
  and the product is unchanged; no two-turn read (a one-turn +0.95 HP
  predicts about +0.3 at two turns, `cause/leaf-gain-third`).
- Goal 1: a bench table started from now on (a new pack, a new batch, a
  new zero-shot base) reads `@shl0.005` as a second column beside its
  `@tsl1` reading player, as `decision/turn-start-leaf-reads` did for the
  turn-start leaf, and the price becomes the reading player only after a
  table shows it breaks no row there (no mechanic or parent worse by 1.5
  HP). Tables already queued or under way keep their leaf, so their
  pairs stay valid: `pack-retention`'s chains (gen-b1-heur, gen-b1-anchor)
  read against the reused `@tsl1` base.
- Pack teacher: `pack-retention` keeps the net teacher it has (its arms
  are paired against gen-b1's net-teacher g99). A price-teacher arm is a
  candidate for the pack chain after that lane closes, not a change now:
  the price already cuts 71% of AttackLoss-Damage x Nob's cost with no
  games (`measurement/shl0.005@gen-b1`), so a burst taught under it
  trains on a smaller gap, and that is what the arm would test.

Alternatives: make `@shl0.005` goal 1's reading player at once (breaks
the pairing of every queued table with its reused base, for a mean of
-0.41 HP per elite fight); keep it off goal 1 too (its bench record has
one trading cell, AttackLoss-Strength x Nob +2.37, and the headline now
shows no cost on official play); switch `pack-retention`'s teacher now
(confounds the lane's two running arms). Reversible: a column on new
tables.

## Element wording (owner, spec docs/specs/element-wording.md, 2026-11-08)

- Every content element has its words in `content/wording.json`, one
  family per kind of element (effect, target, quantity, pick, pile,
  trigger, condition, static condition, modifies, stage, replacement event
  and action, pattern condition and pick, encounter slot), plus the text
  for behaviour held in engine code (`code_monster`, `code_power`). The
  explorer builds all card, monster, move, power and encounter text from
  it; who uses an effect fills `{target} {to} {subject} {s} {per}`, and
  `{hits}`, `{cards}`, `{x|word}`, `{x|move}` word fields.
- Kept in explorer code (each with a plain entry): a negative or self
  Apply and ApplyOf (a monster's Apply on you sets `{to}` to " to you"), ScaledDamage's amount forms, ScaledBlock per hand
  card, a card's PlainDamage to itself, Split's named halves, Pick's "up
  to", a CardType condition's article, Window with no earlier move.
- Card counts (owner, consistency over parity with the game; spec
  Amendment 1): always copies, "1 copy of Shiv", "N copies of Burn+", a card
  adding itself "1 copy of this card". The only text change; the pin
  (`scripts/tests/data/explore/wording_pin.json`) changed for exactly the
  AddCard lines.
- Deviation from the spec, as built: no exhaustive per-family name
  functions and no `sts.element_names()` binding. `engine/tests/wording.rs`
  instead reads every content file the engine loads (official and packs)
  and fails on any element they use that `registry::element_names()`
  doesn't list or the wording file doesn't word; that is the case that
  broke the explorer (new elements arrive with the content that uses
  them). Without a binding, `sts` needs no rebuild or swap. An element
  added to a parser but used by no content file isn't caught until
  content uses it; the Python-generated packs (mutated cards, generated
  enemies) are covered by `test_explore_wording`'s unworded check, not by
  `cargo test`.
- `registry::json` (the engine's JSON reader) is public so the Rust test can
  read the content files.

## Lane all-content-net closed (2026-11-08)

Outcome: closed at its CPU-hour cap with two of the stop rule's three
seeds read, both passing the per-boss bar, and the one-turn headline not
run (docs/research/learned-play-results.md, "All-content net seed 101 on
the boss replay repeats seed 1"). Against their twins, seeds 1 and 101 gain
Guardian +0.048 (0.011) and +0.050 (0.009), Hexaghost +0.093 (0.015) and
+0.054 (0.012) wins one turn deep; pooled Guardian +0.049 (0.008),
Hexaghost +0.073 (0.012), Slime Boss level. The gain is mostly held-out
cards (Demon Form's first tick, +0.28 at the two bosses; Metallicize
+0.06 against the 10-29 net), with a small boss part on train decks
(+0.021 (0.007) against the twins, +0.028 (0.008) against the 10-29 net).
Outside Demon Form decks against the 10-29 net (the navigator's two-turn
condition, decisions "After seed1-bosses") the Guardian pools to +0.035
(0.007) and Hexaghost to +0.017 (0.008) over two seeds. Checkpoint
seed1-bosses passed; pooled-bosses not reached.

At the close (on the owner's behalf): seed 101's boss replay (0601, 0.4
thread-hours) ran past the cap so the finished learn 0583 got its read
(the generated-enemies-bench precedent); seed 201's learn (0584, 10
thread-hours, queued at `mem_gb` 3 though 0583 peaked at 6.03 GB) and
seed 1's one-turn headline (0585, 3.5 thread-hours) were cancelled, so no
CPU runs past the cap before the navigator decides. Alternatives passed
over: leave both pending (about 13.5 thread-hours past the cap with no
decision, and 0584 at half its real memory); run only 0585 (decides the
protocol half of the go but not the third seed). Reversible: both jobs'
commands are in `jobs/done/0584-learn.json` and `0585-gauntlet.json`;
re-queue 0584 with `--mem-gb 6.5`.

CPU: 31.6 thread-hours against the 30 cap (two learns of about 10 each,
four boss replays, seed 1's from-scratch work) and the opening entry's 21
for three seeds; the 40k learns ran 205 minutes against a 100-minute
estimate. Opening rating: **a long shot** that it moves the headline (not
read); **even** that the Guardian gains 0.03 wins one turn deep (it did,
on both seeds read, mostly through held-out cards).

**Reopen if:** (a) the navigator wants the go decided: seed 201 (0584 at
`--mem-gb 6.5`, 10 thread-hours) plus its twin's replay pairing (0582's
file exists) and the one-turn headline 0585 (3.5 thread-hours) finish the
charter's stop rule as written, and the Guardian's +0.035 outside Demon
Form then decides the two-turn read; (b) new content lands that no net has
trained on from scratch (the Act 1 pack cards or monsters,
`lane/act1-content`), where the same recipe with that content in its
groups is the from-scratch arm beside burst adaptation; or (c) a cheaper
learn (the exact solver out of the round, or a smaller game count with the
same boss share) brings a seed under 4 thread-hours.

## After all-content-net's close: the go stays unfinished; seed 201 and the one-turn headline are not re-queued (on the owner's behalf, 2026-11-08)

Navigator, woken by the lane's close (`lane:all-content-net`, decisions
"Lane all-content-net closed"). The lane closed at its cap with two of
three seeds read, both passing the per-boss bar, and the Guardian +0.035
(0.007) outside Demon Form decks against the 10-29 net, which meets the
two-turn condition I set (decisions "After seed1-bosses").

Decided: the go is not finished. 0584 (seed 201's learn) and 0585 (seed
1's one-turn headline) stay cancelled; the lane stays closed with its
gain filed as a lead, and the from-scratch recipe comes back through its
reopen conditions (b) and (c). Reasons:
- What finishing could buy is a product change, and none is in reach.
  The gain outside Demon Form decks is about +0.02 boss wins over the
  non-Demon-Form decks, and one-turn leaf gains reach the product at
  0.2-0.46 of their size (`cause/leaf-gain-third`): about +0.01 wins at
  the Guardian two turns deep, far under what a 500-sequence headline
  read detects (about 0.07 clears, +1.5 HP). The owner's rule: a run
  whose expected effect is below its MDE doesn't run.
- The Demon Form part, the bulk of the one-turn gain, is already free:
  the turn-start leaf prices that tick with no games and two turns of
  search play it (`cause/unseen-cards-half-edge`). A one-turn headline
  read (0585) would mostly re-measure that.
- Seed 201 can't start: its learn peaked at 6.03 GB
      (0583) and needs 7.5 GB free, more than was usually free
  (`cause/memory-holds-bursts`).
- The better use of the recipe is reopen (b): a from-scratch net with the
  Act 1 pack cards and monsters in its groups, which waits for
  `pack-pick-split`'s read (if the pack drop is dilution, goal 2's next
  gain is fighting the new cards) and for a learn that fits in memory
  (backlog `learn-memory`, added today).

Alternatives passed over: re-queue 0584 at `--mem-gb 6.5` and 0585 (13.5
thread-hours, finishes the stop rule as written, but 0584 would wait for
7.5 GB free, and neither outcome changes the product or the ranking);
re-queue only 0585 (3.5 thread-hours, fits in memory, but it reads mostly
the Demon Form tick the leaf already prices). Reversible: both commands
are in `jobs/done/0584-learn.json` and `0585-gauntlet.json`.

## Lane few-game-recipe opened (on the owner's behalf, 2026-11-08)

Exploration slot, empty since `all-content-net` closed. The ready
charter there (`recurring-debuff-leaf`) was set for a fail of
`all-content-net`; the lane closed at its cap instead, so the slot is
mine to fill. Opened: backlog candidate 27, `few-game-recipe` (goal 1's
number, games to adapt).

Why this one now: it needs no code (a family config with `finetune.py`'s
existing `lr` and `share` keys), and its bursts and reads peak under about 1.2 GB, while the CPU sits idle (utilisation 0.24,
275 minutes with no job); and it moves goal 1's headline number (games
to adapt, about 100 today, `measurement/adaptation-curve`) if the 33-game
lesson is there. Rated **even** that one recipe halves AttackLoss-Weak's
cost at 33 games for either teacher (for: every 33-game burst's
validation loss was best after one epoch, the overshoot a smaller step
answers; against: 240 states may not hold the lesson); **a long shot**
that it holds at 11 games. About 2.5 thread-hours; cap 4.

Alternatives passed over: `recurring-debuff-leaf` (even, but 1-2 hours
of engine code; it takes the
exploration slot next, charter re-pointed); `race-price` and
`boss-step-hp-price` (long shots, code, prices of the kind that has
traded one mechanic for another, `cause/leaf-price-trades`);
`ceiling-player` (a long shot that its decisive outcome appears; a code
read first); finishing `all-content-net` (entry above).

Shares (`jobs/lanes.json`): act1-content 35 (last checkpoint passed; its
last CPU job 0600 waits on memory), pack-retention 30 (heur-teacher
failed, the anchor's first arm failed), few-game-recipe 25, main 10,
filler 0.

## Lane pack-retention closed (2026-11-08)

Outcome: **fail** by the stop rule
(docs/research/family-transfer-probes.md, "Anchor a03, seed 2 (0592,
0593), the table (0594) and the anchor checkpoint";
`measurement/burst-anchor@gen-b1`, `measurement/heur-teacher@gen-b1`).
Step 1 (the heuristic as burst teacher) lost the AttackLoss-Damage x Nob
cut (-1.28 pooled of +13.29): checkpoint heur-teacher failed. Step 2 (an
L2 anchor toward the parent's weights, 0.003 and 0.03, two seeds each)
fixes forgetting outside the burst (parent x Lagavulin within 1 HP in all
four nets, the parents better than zero-shot overall) but trades the
TurnEnd-Frail x Lagavulin leak against the Nob cut: a003 keeps the cut
(+10.84 pooled) and leaks +2.76 at seed 2; a03 holds the leak to +0.32 /
+1.22 and keeps +7.59 of the cut (6.89 at seed 1), under the 8.0 bar.
Each arm meets a fail condition; checkpoint anchor failed. Step 3 (fresh
starts) confirms a go and was not run. The leak is in a cell the burst
plays itself, so it is what the burst's games teach there, not forgetting.

At the close (on the owner's behalf): no third weight and no distillation
arm. Alternatives passed over: a middle weight 0.01 (2.6 thread-hours;
by the two weights' trend it lands between them on both numbers, so it
misses the 1 HP bar or the 8.0 cut); distillation toward the parent's
values on the burst's positions (code; it pulls on the Nob positions as
directly as on the leaking cell, so the same trade, as the anchor spec
argued). Reversible: `configs/packs/gen-b1-anchor.json` takes another arm
and `family.py queue` runs it. The pack table's own rule (half the
target's cost) passes a03 and ships a03-s2 as gen-b1-anchor's net; that
ship file stands as the family table's output, not as this lane's go.

CPU: 7.5 thread-hours against the 12 cap and the opening entry's about 8.
Opening rating: **even** (against: a pull toward zero-shot may pull back
the Nob cut as well, both in the same value head; that is what happened).

**Reopen if:** a burst can change what it teaches on one cell without the
target's: (a) a per-cell retention term (hold the positions of cells the
guard names, say TurnEnd-Frail x Lagavulin, to the parent's values while
the target's positions train free), or (b) the burst teacher's games on
Lagavulin are shown wrong (a read of the burst teacher alone on
TurnEnd-Frail x Lagavulin against the heuristic) and a fix for them exists;
or new content makes the leak matter on the headline (a pack whose
shipped net loses 2 HP or more on a cell the gauntlet plays).

## Lane pack-pick-split opened (on the owner's behalf, 2026-11-08)

Project slot, empty since `pack-retention` closed on a fail (decisions
"Lane pack-retention closed (2026-11-08)"). Opened from the ready
charter: backlog candidate 26, `pack-pick-split` (goal 2, and goal 1's
own-pick reads on custom cards). With the 27 Act 1 pack cards in the
offers every player loses 0.106-0.158 clears
(`measurement/act1-cards@pack-offers`); the lane splits that drop into
dilution (fewer original cards offered) and choice (the sim chooser's
horizon overpicks cards that pay later, `cause/chooser-horizon`) with a
chooser that sees the pack cards but may take only originals or skip.
Rated **even** that it recovers half the drop for either player. About
30 lines of code (a gauntlet.py flag), then 3.3 thread-hours of one-turn
reads at about 1 GB each. Cap 5 cpu-h,
end 2026-11-13, on-close wake always: either outcome moves the ranking
(a choice result reopens the parked chooser work with a target near 0.07
clears; a dilution result points goal 2 at fighting the new cards,
`learn-memory`'s pack net).

It also restores a goal-2 lane: none was open since `all-content-net`
closed, against goal 2's CPU weight of 0.4.

Alternatives passed over: `finish-faster-tiebreak` (the owner's, machine
time; half a day of engine code, and its value grows once the CPU is
busy; next project slot); `learn-memory`
(about 3 hours of code; its first use waits on this lane's read);
reopening `pack-retention` (its reopen conditions need a per-cell
retention term or a teacher fix, neither ready; backlog
`per-cell-teacher`, added today, a long shot on value: the leak is 1-3
HP on one generated cell).

Shares (`jobs/lanes.json`): act1-content 35 (its last CPU job 0600 waits
on memory), few-game-recipe 30 (23 small jobs queued), pack-pick-split
25 (code first), main 10, filler 0.

## Curriculum modifiers reviewed: player growth exposure and Fickle queued, sleeping enemies wait for M2, run modifiers parked (owner, 2026-11-08)

From an `/approach` review of the owner's five modifier ideas, with a
sceptic subagent on the record (the facts cited in backlog candidates
32-34).

1. **Player growth exposure is queued** (backlog `player-growth-exposure`,
   rated even): Ritual forced on the player at 0-2 stacks per fight, to
   remove the gate where a net that undervalues a growth card never
   reaches positions holding it. Its first step is a near-free count of
   how often the player held Demon Form in the earlier Demon Form bursts.
   The aim is an accurate price of growth, higher or lower. Alternatives:
   Ritual on everyone as the owner first put it (passed over: enemy Ritual
   blurs the player's lesson and was tried, 0.38x at 534 games); force
   Demon Form itself (passed over: it spoils the held-out Demon Form
   decks the read needs); park it on the Ritual 2 burst's result (passed
   over: that burst had no gate to remove, so it does not answer the
   owner's mechanism).
2. **Fickle enemies are queued** as a bench modifier (backlog
   `fickle-enemy`), first as a fixed Skill -> Attack -> Power cycle, a
   random choice later when hooks may run chance.
3. **Sleeping enemies ("-vulin") wait for block M2** (backlog
   `sleeping-enemy`): waking is Lagavulin's code today.
4. **The run modifiers (Spire-wide Ritual, Slow Start, Fickle Opposition)
   are parked.** The bench already gives a modifier to every enemy of a
   fight; a run adds the chooser's error and spreads one parent's cost
   over hallway fights (`cause/chooser-horizon`, `cause/novelty-is-horizon`),
   and run-level work waits for content (`docs/direction.md`, Avoid).
   Reopen: a chooser whose horizon holds the elites, or Act 1's run
   content in the engine.
5. **Ascension levels are a candidate** (backlog `ascension-levels`): the
   engine plays ascension 0; enemies get an upgrade form for the
   ascension tiers, after `act1-content`'s monsters are data.

## Turn-start leaf in fights, plain leaf in trial fights (owner, 2026-11-08)

`@tsl1` gains where the player holds a turn-start power and changes
nothing elsewhere (`measurement/turn-start-leaf@cells`); it failed the
headline only because the sim chooser's trial fights play the same leaf
and overpick Demon Form, whose cost sits at the elites the chooser does
not simulate ("After the turn-start leaf on the one-turn headline").
That decision did not weigh splitting the two. Decided: the fights a
player plays use `@tsl1` and the trial fights keep the plain leaf, adopted
for the one-turn controls after a level-or-better read on the headline
(backlog `fight-leaf-tsl1`: non-inferiority, since the expected gain of
about +0.8 HP is under the protocol's +1.5). Until that read passes,
`decision/turn-start-leaf-reads` stands as written. Alternatives: keep
the plain leaf everywhere (passed over: every one-turn comparison on
turn-start content carries the artefact, and Act 1 adds more such cards);
`@tsl1` everywhere (failed, job 0333); wait for `elite-horizon-chooser`
(passed over: parked behind Act 1's cards). The product stays as it is
(two turns deep already plays the first tick, backlog `tsl1-two-turn`).

## Lane few-game-recipe closed (2026-11-08)

Outcome: **go** (stop rule met through the net teacher). In family gfr-33
(`docs/research/few-game-recipe.md#Step 1 result: both teachers (table
0626, 2026-11-08)`), 33-game bursts at replay share 0.8 (the default lr)
cut GE-AttackLoss-Weak's +6.03 HP cost by +4.77 with the net's games
(0.79 of the cost, +3.57 over the default share 0.5 at about 5 se, parent
change -0.41 against the default's -0.24) and +3.13 with the heuristic's
(0.52, +1.29 at about 10 se, but its parent change is 0.57 HP worse than
its default's, just over the 0.5 guard). lr at a third of train.LR lost
for both teachers (+0.41 and +1.15 against +1.20 and +1.84).

Why: `share` is the replay share (`train.replay_batches`), so share 0.8
gives each pass over the new states 2.5 times the gradient steps, each
padded with replay. The 33-game default was under-trained, not
over-stepped; the candidate's overshoot mechanism is contradicted, its
replay-dilution half holds. The recipe closes about two thirds of the gap
between the 33-game and 99-game defaults on this mechanic.

CPU: 3.5 thread-hours over 24 jobs, cap 4.

On-close: `wake on go`, so the navigator decides the slot: the
games-to-adapt number (`measurement/adaptation-curve`, about 100 games,
measured at share 0.5) may now overstate the games needed; a curve at
share 0.8 (and 0.9) at 11, 33 and 99 games, and a split of step count
from replay anchoring (more epochs or smaller batches at share 0.5), are
the obvious next reads. `measurement/adaptation-curve` flagged for it.

**Reopen if:** (as a follow-up, not a reopen of this read) the recipe
question is wanted at 11 games or on another mechanic: the go here is one
mechanic on two elites, in-distribution, one share point, so a share
sweep (0.8, 0.9) at 11 and 33 games on a second mechanic (a held-out
SharpHide or Ritual-kind cost) would say whether "share 0.8 adapts in 33
games" is general.

## Lane share-curve opened (on the owner's behalf, 2026-11-08)

In the exploration slot `few-game-recipe` left (its close, `wake on go`).
Its go (`measurement/few-game-recipe@gfr-33`: replay share 0.8 cut 0.79 of
GE-AttackLoss-Weak's cost at 33 games, 0.20 at the default share 0.5) says
the 33-game default was under-trained, so goal 1's standing number,
"about 100 games to adapt" (`measurement/adaptation-curve`, flagged), was
measured with a recipe that starves small sets. The lane re-measures it:
net-teacher bursts at share 0.8 and 0.9, 11 and 33 games, on
AttackLoss-Weak and on a second mechanic the recipe has not seen,
GE-OppCard-Weak x Lagavulin (cost +7.36, 99-game default cut 0.56,
`measurement/gen-adapted@ocw`), with its 33-game default as the baseline,
and one retention read on the one-turn cell gauntlet. No code, about 6.5
thread-hours; the bursts peak under 1.3 GB. Backlog candidate 37.

Rated likely that a recipe arm at 33 games beats OppCard-Weak's 33-game
default by 2 se; even that it reaches half that mechanic's cost or its
99-game cut; a long shot that 11 games pass on both. Shown wrong if no
OppCard-Weak recipe arm beats its default by 2 se.

Alternatives passed over: `recurring-debuff-leaf` (the ready charter for
this slot; rated even, but it needs 1-2 h of engine code before any CPU,
while the CPU sits idle; it takes the next exploration slot); the heuristic
teacher's arms (its share-0.8 arm missed the parent guard, and the net is
the teacher the pack chain ships); a share sweep at 99 games (the 99-game
default already cuts 1.05 of AttackLoss-Weak's cost, nothing to gain);
a fourth lane for `recurring-debuff-leaf` beside this one (passed over for
the same build reason).

Shares (`jobs/lanes.json`): act1-content 35 (one job left, 0600, waiting
on memory), pack-pick-split 25 (two reads queued), share-curve 30, main
10, filler 0.

## Lane pack-pick-split closed (2026-11-08)

Outcome: **fail** by the stop rule (docs/research/act1-inventory.md,
"Pack-pick split read (0627-0630, lane pack-pick-split)";
`measurement/pack-pick-split@headline`). With the Act 1 pack offered and
the chooser barred from the pack cards, both players lose more than with
the pack: heuristic 0.304 clears against 0.428 (-0.124, se 0.025), the
one-turn net 0.382 against 0.522 (-0.140, se 0.027); the share of the
pack drop recovered is -1.17 and -0.89, far under the quarter. Barred,
the chooser takes about 2 fewer cards a sequence and the extra deaths sit
at the floor-9 elites; boss deaths barely move. The pack drop is
dilution; the pack cards the sim chooser takes, the late-paying holders
included, are worth 0.12-0.14 clears against its alternatives, so the
parked chooser work (`elite-horizon-chooser`, `static-value-chooser`)
gets no target from the real pool. Checkpoint split failed.

At the close (on the owner's behalf): no follow-up read. Alternative
passed over: a chooser that must take the best original even below skip,
to separate "fewer cards" from "which cards" (about 2 thread-hours); the
charter's question is answered without it, since barring the pack picks
took clears away instead of giving them back.

CPU: 2.1 thread-hours against the 5 cap and the opening entry's 3.3.
Opening rating: **even** that it recovers half the drop for either
player; it recovered less than nothing for both.

**Reopen if:** a chooser change (a longer horizon, learned card values)
is shown to gain on the plain headline setting, so that a pool with late-
paying cards could hold an error of that chooser's kind; or a pack whose
cards the chooser takes more often than 4 a sequence, where the
originals-only read (`gauntlet.py --pack-picks originals`, already built)
costs one run per player.

## Lane finish-faster-tiebreak opened (on the owner's behalf, 2026-11-08)

In the project slot `pack-pick-split` left (its close, `wake always`: a
fail, the Act 1 pack drop is dilution and the chooser's pack picks help,
`measurement/pack-pick-split@headline`). It opens the ready charter
written for the next project slot, backlog candidate 28 (the owner's idea
from the 2026-11-08 discussion): exact ties in the search broken toward
the line that ends the fight sooner, then toward lower enemy HP plus kept
block, behind an option that is off by default, judged by
`yardstick/cost-savers`. Rated even that it cuts a measurable share of
easy-fight turns; half a day of engine code, under 1 thread-hour of
replays, then about 3.5 thread-hours of two-turn reads if the replays cut
3% of the nodes or more. Nothing else in the project slot
could use the CPU sooner (the project candidates with queueable CPU and no
code are spent or waiting on another lane's result).

Alternatives passed over: `learn-memory` (code too; `pack-pick-split`'s
dilution reading raises it, since a from-scratch pack net is goal 2's next
gain on the pack read, but it only frees memory for from-scratch learns,
not for the bursts and reads waiting now; it gets the ready charter for
the next project slot, when `act1-content` closes after job 0600);
reopening `elite-horizon-chooser` or `static-value-chooser` (passed over:
the split gave the chooser no target, the reopen condition the close
named); `fight-leaf-tsl1` (a goal-2 ruler change worth about +0.8 HP, under
the protocol's detectable effect, and its trial-fight player string is
code as well); a fourth lane.

Shares (`jobs/lanes.json`): act1-content 40 (one job left, 0600, waiting
on memory), share-curve 40 (its bursts and reads 0631-0674 queued),
finish-faster-tiebreak 10 (code first), main 10, filler 0.

## Lane act1-content closed (2026-11-09)

Lane worker 70f6f749, on the wake `lane-cap:act1-content`, after reading
its last job (0600, the product's monsters re-rank).

**Outcome.** Closed at its CPU-hour cap: about 36.8 cpu-h used against
36 (extended once from 24). Charter predicted "likely per content kind
once the registry has its atoms", about 16 cpu-h.
- Step 1 (inventory) done; the monsters kind done: all 7 missing Act 1
  monsters load from `content/packs/act1-monsters.json` with their checks
  (golden identical, series_check PASS, speed read 0580), and the
  headline re-rank (G2) passed checkpoint monsters-rerank: on the real
  Act 1 hallways every player pays the same (-0.056 heuristic, -0.048
  one-turn on 0-499; one-turn and product both -0.080 on 0-249), the
  order heuristic < one-turn < product holds and the product's lead over
  the one-turn net is unchanged (+0.148 on pack and control;
  `measurement/act1-monsters@rerank`, `measurement/act1-monsters@product`,
  `docs/research/act1-inventory.md` "G2 re-rank, product read").
  No zero-shot gap for the net or the search on these monsters.
- The cards kind is unfinished: 27 of the missing Ironclad cards written
  as pack entries (blocks C1, C2, C4, S1, G1 built), 13 blocked on C3
  (a card-drawn trigger), C5 (cost changes in combat) and C6-C14, one card
  each. Relics and potions (step 4) not started.
- Open, not run: the pack's Exordium Thugs cost about 3 HP more than the
  official `exordium_thugs` for all three players; arrival HP differs, so
  a one-encounter replay of both on the same decks would settle parity.

**Reopen if:** the cards kind gets building blocks cheaply enough to
finish within a new cap: C3 and C5 together unblock 4 of the 13 cards
(Evolve, Fire Breathing, Blood for Blood, Corruption with C1), and the
other nine need one block each, so a reopen pays when a general
mechanism (e.g. a `new-mechanics-workflow` that writes a block from a
card's text) makes a block cost hours rather than a spec and build each;
or when relics and potions gain registry atoms (step 4). The Thugs parity
replay is a sub-hour probe any lane can run first.

**Next.** On-close is `wake always`: the navigator decides the slot
(the backlog's ready charter for this project slot is `learn-memory`).
The closed lane's share (40) moves to the open lanes in
`jobs/lanes.json`: share-curve 40 -> 60, finish-faster-tiebreak 10 -> 30
(on the owner's behalf; the navigator re-sets shares when it fills the
slot).

## Act 1 is finished; act1-content reopens now (owner, 2026-11-09)

The owner: finishing Act 1 is essential. It is now a standing goal: a lane on Act 1 stays open until
every official Act 1 monster and encounter and every Ironclad card, relic
and potion loads and plays, and a cap or end date only reopens it in the
next free project slot with a new cap.

- `act1-content` takes the project slot its own close freed (2026-11-09),
  ahead of `learn-memory`. The close's "Reopen if" conditions no longer
  apply: blocks are built one at a time.
- Order inside the lane (navigator may re-order with a reason): C3 and C5
  first (they unblock Evolve, Fire Breathing, Blood for Blood and
  Corruption), then the other nine card blocks, then relics and potions
  (step 4), and the sub-hour Thugs parity replay whenever a slot of CPU
  is free.
- `learn-memory` moves to the next project slot that frees (likely
  `finish-faster-tiebreak`'s, about half a day of code).
- The navigator writes the new charter and cap and sets the lane shares
  in `jobs/lanes.json`.

## Lane act1-content reopened (on the owner's behalf, 2026-11-09)

Navigator, on the wake `lane:act1-content@2026-11-09T02:47`, writing the
charter, cap and shares the owner's decision "Act 1 is finished;
act1-content reopens now (owner, 2026-11-09)" asks for
(`decision/act1-finish`).

- **Charter** (fact `lane/act1-content`, rev 5): what is left of Act 1 in
  the owner's order: blocks C3 (card-drawn trigger: Evolve, Fire
  Breathing) and C5 (cost changes in combat: Blood for Blood, and
  Corruption with C1) first; then the other card blocks (C6 card upgrades
  and its forerunner card-sets are specs the owner confirmed on
  2026-11-08, so they build next without a new spec; then C7-C14, one
  card each); then relics and potions (step 4); the sub-hour pack Exordium
  Thugs parity replay goes first on the CPU, which is idle now.
- **Re-order, with its reason:** step 4 starts with an inventory of the
  Act 1 relics and potions against the engine (no code, as step 1 was for
  monsters and cards), written whenever a session waits on a build or the
  CPU. The code shows almost nothing to start from: no relic type in
  `engine/src/` (only a Red Skull power, `powers.rs`, and the character's
  starting relic in a doc comment, `character.rs`), and potions only as a
  reserved `UsePotion` action number (`codec.rs`, "4 UsePotion") and a
  `Potion:` action text (`scripts/action_text.py`). This disagrees with
  `docs/direction.md`'s interest line "Resources that carry across fights
  (potions, gold, max HP, relic counters) are in the engine but off": the
  code has no potions or relic counters to turn off. The direction is the
  owner's file, so it stays as written; the mismatch goes to the digest.
  Sizing step 4 early keeps the lane from discovering at the last block
  that relics are the larger kind.
- **Stop:** done when every official Act 1 monster and encounter and every
  Ironclad card, relic and potion an Act 1 run can meet loads and plays,
  with its checks (`docs/research/act1-inventory.md` keeps the count). No
  fail close (the owner's goal): a block that breaks golden identity or
  series_speed by more than +10% is fixed or reverted and re-specced inside
  the lane; at the cap or end date the lane closes and reopens in the next
  project slot with a new cap.
- **Cap 42 cpu-h** from an estimate of about 28 (x 1.5): series checks at each
  landing about 1 cpu-h each (0492, 0570, 0580: 14 threads for 3-4
  minutes, plus series_check and golden) over about 11 card blocks and
  about 5 relic and potion landings (about 16); one re-rank for the cards
  kind when its blocks are in (about 11: the monsters re-rank 0598, 0599
  and 0600 cost 0.5, 3.6 and 7.1 thread-hours); the Thugs replay under 1. **End 2026-11-13**; at that date it closes and reopens with a new cap (the owner's rule).
- **On-close: wake always** (the navigator writes each reopen's cap).
- **Rating: likely** per block. For: every block built since 2026-11-06
  landed with golden identical and series_check PASS (C1, C2, C4, S1, G1,
  E1, M5, M6, M7, G2), and the monsters kind finished. Against: C3-C14 are
  one card each, so each costs a spec and a build for one card; relics and
  potions need new atoms and an action kind (potions), which no block so
  far has been.
- **Shares** (`jobs/lanes.json`): act1-content 40, share-curve 35,
  finish-faster-tiebreak 15, main 10, filler 0. act1-content carries the
  owner's standing goal and the series checks and re-ranks; share-curve
  keeps the bursts (its AttackLoss-Weak half passed); the tiebreak's next
  step is code and its replays are under 1 thread-hour, so it needs little
  share.
- **Alternatives passed over:** `learn-memory` in this slot (the owner put
  it in the next project slot that frees); closing `finish-faster-tiebreak`
  to give learn-memory a slot now (it is the owner's, opened yesterday,
  and costs half a day); a fourth lane (the rule allows one only while a
  lane is within a few days of its end, and three lanes fill the slots).

## Draw triggers: once per Status card (on the owner's behalf, 2026-11-09)

Lane act1-content, block C3 (`docs/specs/draw-triggers.md`, confirmed under
the mandate). A power hook `CardDrawn` (condition `CardType Status` only)
fires once per Status card drawn, unscaled, where the stage machine reaches
the player's turn; the drawn Statuses are counted only while such a power is
held, so official states and encodings are unchanged. Alternatives: C2's
scaled firing once with the count (fewer chance events, but Fire Breathing's
hit count against per-hit hooks such as Angry would differ from the game);
counting every draw by type (general, but changes official states). Both
reversible: the hook and its counter are pack-only vocabulary.

## Lane finish-faster-tiebreak closed (2026-11-09)

Outcome: **fail** at step 2 (the stop rule's kill-fast: under 3% of the
search nodes cut). The tie break (`SearchConfig::tie_break`, player
setting `@tb1`, off by default) was built and checked identical off
(golden, `series_check` PASS, 254 two-turn searches identical). On 330
replayed headline fights (control sequences 0-29, every floor; the off arm
reproduces all 330) it cut search nodes by -0.003% (none) and turns by
2.6%, with end HP and wins identical in every fight
(`measurement/finish-faster-tiebreak@replay`,
`docs/research/finish-faster-tiebreak-2026-11-09.md`). The turns it saves
are the near-free last turns of won fights; 98.7% of the nodes sit in hard
hallways, elites and bosses, where top options rarely tie exactly. Step 3
(the 250-sequence read) did not run. The option stays in the engine, off.
The two-turn policy (`depth_paired.decide`) now plays each search's own
root pick, identical to `np.argmax` with the flag off. CPU used: about 1.0
of the 7 cpu-h cap.

**Reopen if:** a setting where exact ties are common in costly fights
appears: a score that no longer separates lines by HP (a survival or
win-only score, or a capped heal on every floor), or content whose hard
fights have many equal-value lines; check first with the same replay
(`depth_probe.py play --kind all`, both arms, one read), go only if it cuts
3% or more of the nodes.

## Lane learn-memory opened (2026-11-09)

In the project slot `finish-faster-tiebreak` left (its close, a fail;
`on-close: wake on go`, so no navigator wake). It opens the ready charter
the navigator wrote for the next project slot after `act1-content`
reopened (`docs/backlog.md`, the ranking paragraph: "the next project slot
that frees after that takes `learn-memory`"; candidate 30): `learn.py`
trains from its example cache in chunks or a compact form, so a 40k-game
from-scratch learn peaks at 3.5 GB or less (`cause/memory-holds-bursts`).
Code first. Shares
(`jobs/lanes.json`): learn-memory takes finish-faster-tiebreak's 15.

## act1-content's cap counts from its first opening; step 4 starts from the relics and potions survey (on the owner's behalf, 2026-11-09)

Navigator, on the owner's wake of 2026-11-09 15:47.

- **Cap.** `health.py` counts a lane's CPU-hours from the first revision
  of its `lane/<name>` fact (`charters()`, "opened"), and the reopened
  `lane/act1-content` (rev 5) keeps the history from 2026-11-06, so the
  reopen's cap of 42 cpu-h already stood at 36.9 used
  (`jobs/health.json` `lane_cpu_h`): about 5 cpu-h left, two series
  checks and a re-rank, where the reopen meant 42 new. Mismatch between
  the reopen entry ("Cap 42 cpu-h from an estimate of about 28") and the
  code; the code's count stands. The charter's cap becomes **79 cpu-h**
  (36.9 used before the reopen + 42), end unchanged (2026-11-13).
  Alternatives: retire the fact and set a fresh one so "opened" restarts
  (loses the charter's history in kb, and the lane worker's step facts
  hang off the old one); leave 42 and let the lane close at its cap within
  a day and reopen (the owner's rule allows it, but a close and reopen
  cost two sessions for nothing). The cap is a number in the charter:
  reversible by the next reopen.
- **Step 4's first part.** The navigator's research survey
  (`docs/research/relics-potions-survey-2026-11-09.md`, from sts_lightspeed's
  code and the wiki's lists) sizes it: of the 109 relics in the pools an
  Act 1 Ironclad run meets, 25 fit a permanent player power with today's
  hook kinds, 15 more with one counter carried across fights (sts_lightspeed
  keeps 7 such counters), 39 act only out of combat, 30 need a new hook or
  rule; of the 33 potions open to the Ironclad, 18 are card effects of
  today's vocabulary and 7 more need one "choose a card" effect; a potion
  is not a card play in sts_lightspeed (`drinkPotion` leaves the card
  counts alone) and only 4 take a target. So the step's order, by entries
  unblocked: R1 a relic kind in content files as a permanent player power
  plus the run's relic list (about 25), R2 a counter carried across fights
  (about 15), P1 potion slots and the reserved `UsePotion` action with card
  effects (18), P2 a choose-a-card effect (7); the out-of-combat relics go
  with the run layer's blocks (gold, rest, shop, rewards, map: the owner's
  scope note); the new-hook relics one block per hook kind (shuffle, enemy
  death, death prevention, damage and heal modifiers, rule changes).
  Exhaust (C2) and draw (C3) hooks may already cover some of the survey's
  "new" ones (Dead Branch, Charon's Ashes); the inventory checks each entry
  against the engine and against the wiki and sts_lightspeed
  (`decision/parity-source`): the survey's effect lines came from the
  agent's own knowledge, not a page. Carried resources stay off or unpriced
  in every fight measured (`docs/direction.md`).

## share-curve gains the one 11-game arm its quote needs (on the owner's behalf, 2026-11-09)

Navigator. `lane/share-curve`'s stop rule quotes games to adapt "as 11 if
an 11-game arm meets the same bar on both" mechanics, but step 1 gave
GE-OppCard-Weak only an 11-game arm at share 0.8, while AttackLoss-Weak's
11-game pass came at share 0.9 (`measurement/share-curve@alw`: g11 sh0.8
0.27 of the cost, fail; g11 sh0.9 0.58, pass). Table 0674 (written
03:27, not yet read by the lane) puts OppCard's g11 sh0.8 at 0.34 of the
cost and its 33-game arms rising with share (0.40 / 0.56 / 0.61 at 0.5 /
0.8 / 0.9), so the arm the quote lacks is OppCard-Weak at 11 games share
0.9. What each outcome gains: a pass makes goal 1's number 11 games
(a third of 33) on both mechanics read; a fail fixes it at 33. Neither is
known from the files (AttackLoss-Weak's step from 0.8 to 0.9 at 11 games
doubled its cut; OppCard's 33-game step from 0.8 to 0.9 added 0.05).

- **Charter change** (`lane/share-curve` rev 2): step 1b, after the
  recipe-tables checkpoint and only if step 1 goes: GE-OppCard-Weak x
  Lagavulin at 11 games share 0.9, three burst seeds, read and judged as
  step 1's arms (`family.py`, the sc-ocw setup); the 11-game quote needs
  it to pass. Cap 10 to **12 cpu-h** (9.0 used; the arm is about 0.9 as
  g11 sh0.8 cost, step 2's retention read about 0.7). End unchanged.
- **Alternatives:** a new lane for it (a lane for one arm; the slot rule
  keeps three); a probe in lane `main` (the family config is lane work,
  and the navigator does not write configs); skip it and quote 33 (the
  charter asks for the 11-game answer and the arm costs under an hour of
  CPU that sits idle). Reversible: the lane worker drops it if step 1
  fails.

## After the big-picture review of 2026-11-09: act1-content puts relics and potions before the one-card blocks; queue-throughput opens; a random-world bench is the next exploration (on the owner's behalf, 2026-11-09)

Navigator, from `docs/research/big-picture-2026-11-09.md` (its reading
and the twelve skeptic verdicts, all "overstated").

- **act1-content re-ordered** (`lane/act1-content` rev 7): after C3, C5,
  card-sets and C6 (the owner's first items and confirmed specs), step
  4's R1 (relics as permanent player powers in content files, about 25
  entries), R2 (a counter carried across fights, about 15) and P1 (potion
  slots and the reserved `UsePotion` action with card effects, 18) come
  before C7-C14 (one card each); the inventory part of step 4 goes first
  as before. Reason: blocks that unblock 15-25 entries before blocks that
  unblock one, and relics and potions are what level 1 of the arena
  needs (`decision/goal2-arena`) and may move where runs are lost (the
  headline plays with no potions and a 30% heal before the boss). The
  owner's decision "Act 1 is finished; act1-content reopens now" lets
  the navigator re-order with a reason; the work to finish Act 1 is the
  same. Alternatives: the owner's order unchanged (one-card blocks first,
  relics last); relics before C3 and C5 (those are specced and building).
- **Lane queue-throughput opened** (the fourth lane: `share-curve` is
  within four days of its end and its step 1 tables are in): the queue
  booked 0.18-0.21 of the threads, and in 21.9 of 29.8 idle hours since
  11-06 a runnable job was pending behind admission (a reservation, a
  14-thread job waiting for 14 idle threads, memory) or sleep; 154 of 213 lane wakes were job
  ends. Charter in the lane fact:
  an offline replay of the runner's log through a backfill rule first
  (kill if it recovers under 2 of the 21.9 hours), then the rule, peak-
  based `mem_gb`, and lane wakes on a family's decisive job only. Rated
  **likely** to build, **even** that the replay recovers 5 hours; about 2
  cpu-h (cap 3), end 2026-11-13, on-close wake on fail. It rewrites
  candidate 13 (`throughput-fixes`). Alternatives: wait for the four-day
      slot; fold it into
  `learn-memory` (another subsystem); leave admission alone and fill the
  idle hours with filler (filler cannot start while a reservation holds
  the machine). Shares: act1-content 35, share-curve 25, learn-memory 15,
  queue-throughput 15, main 10, filler 0.
- **Next exploration slot: `random-world-bench`** (candidate 39, ready
  charter), ahead of `recurring-debuff-leaf` (second). Goal 1 has 0.8 of
  the development weight and every goal-1 bench so far holds one novelty
  at a time; a world of k novel items per fight (k 0-8, cards and enemies
  together, the world as the unit) is the first read on random content,
  and as a resumable family it runs without sessions. The review's stop
  list names projected-leaf variants among "net features that read new
  structure"; `recurring-debuff-leaf` simulates the rules rather than
  adding inputs, so it stays, second.
- **Not adopted from the review:** the arrival score as a ruler (it
  misses about a third of the two-turn edge and flips sign on one pair;
  `measurement/boss-replay-score@one-turn` was not adopted for the same
  kind); the own-boss sim chooser probe now (run-level decision work
  before the content it chooses between, the direction's Avoid; it stays
  in `static-value-chooser`, which reopens with `act1-content`'s cards);
  a fresh-book SPRT programme (cheap only one turn deep, and controls on
  fresh ranges come first). New candidates: `aivat-reads` (a long shot),
  `character-as-data` (after Act 1), `pack-net-scratch` (the project
  charter after `learn-memory`'s go).
- **Facts:** `decision/headline-quote` quotes the pack-content level
  beside the curated number (the curated headline ranks players the same
  with pack content, so it stays the ruler); `cause/unseen-cards-half-edge`
  narrowed: the 10-29 net (effects) pays nothing on the nine other unseen
  cards against the heuristic, but an id-only net does (effects minus ids
  +3.02 (0.54) HP over five 5k twins, a skeptic's recompute).


## Lane queue-throughput opened (on the owner's behalf, 2026-11-09)

Navigator; reasons, rating, alternatives and shares in "After the
big-picture review of 2026-11-09" above. Project lane, the fourth while
`share-curve` is within four days of its end. Rated **likely** to build,
**even** that the offline replay recovers 5 of the 21.9 idle hours with a
runnable job pending; about 2 cpu-h of checks (one test-full, the jobs and
roles tests), cap 3, end 2026-11-13, on-close wake on fail. Code first. Charter: fact `lane/queue-throughput`.

## Lane queue-throughput closed (2026-11-09)

Outcome: **fail** at step 1 (the charter's kill-fast). The offline replay
(`scripts/queue_replay.py`, `docs/research/queue-throughput.md`,
`measurement/queue-backfill-replay`) found 19.8 h from 2026-11-06 to
2026-11-09 16:00 with the
    machine awake, no queue job running and a
    runnable job pending (plus 6.6 h of machine sleep, which no rule recovers). A
backfill rule recovers 0.0 h when it must agree with what the runner
really refused, and at most 1.1 h trusting a free-core and free-memory
model alone: under the 2 h kill-fast in every variant. There was almost
never a small job to backfill: the smallest pending job needed 4 threads
in 15.6 h and 3.5 GB or more in 14.7 h. The idle hours were held by
memory reservations above the job's real peak (0276-finetune 5.0 GB,
peak 3.81; 0204-gauntlet 3.5, peak 2.47; 0565-test-full 4.0, peak 0.97;
0208-test-full 9.5, cancelled) and by 14-thread `series_speed` jobs
waiting for 14 idle cores (4.2 h). Step 2 (backfill, peak-raised
`mem_gb`) was not built: the backfill doesn't pay, and raising `mem_gb`
to the last peak goes the wrong way for these cases. Step 3 landed as
the fail branch says: a lane's `ended:` wake now fires only for a
decisive job (a `check`, not ok, or the lane's last), the other ends ride
along with it (`health.py wake_events`; spec `operating-model.md` and
`docs/roles/sts-lanes.md` amended). Step 4 (sessions per filed result
and zero-job minutes, three days after against three before) is left as
a read for the navigator. CPU used: about 0.05 of the 3 cpu-h cap (the
replay and two test runs, outside the queue).

**Reopen if:** the queue fills with small jobs behind a big one (a
reservation holder waiting while jobs of 2 GB or less and 3 threads or
fewer are pending); check first by re-running `scripts/queue_replay.py
--since <date>` on the new window and go only if it recovers 2 h or more
under `--consistency necessary`. The two causes it found are separate
questions for the navigator: reserving memory from a command kind's
measured peak (downward as well as upward), and letting a timing job
(`series_speed`, alternating old/new runs) start with fewer than its
idle cores. `throughput-fixes`' leftover (a small-size flag for the slow
suites, ideas#69) was outside the lane and stays an idea.

## After queue-throughput's close: speed checks reserve 4 threads; reserving memory from measured peaks becomes a candidate; the slot stays empty (on the owner's behalf, 2026-11-09)

Navigator, on the wake `lane:queue-throughput@2026-11-09T16:50`
(decisions "Lane queue-throughput closed (2026-11-09)",
`measurement/queue-backfill-replay`). The replay left two causes of the
19.8 idle hours with a runnable job pending; ranked:

1. **14-thread speed checks waiting for 14 idle cores (4.2 h; 0492 waited
   725 min).** First, because each one gates an `act1-content` landing,
   the owner's essential goal, and the fix needs no code. `series_speed.py`
   already runs the two builds interleaved with the order swapped every
   other run so that a steady background load hits both alike, and the
   landing gate reads its median per-run ratios (1-thread search and
   random combats; one 25-run read has se about 4-5% against the +10%
   bar, `measurement/series-speed@order`). So `lane/act1-content` (rev 8)
   queues its series_speed checks at `--threads 4` (the runner starts them
   with 4 idle cores), reads the 1-thread and random-combat ratios as the
   gate and the 16-thread row as information only, and re-queues once at
   14 threads only if a ratio lands within 2 se of the bar. Alternatives:
   keep 14 (hours of waiting per landing, nothing gained in a ratio built
   to cancel load); drop the 16-thread arm from the script (code, and the
   row still tells something). Reversible in the charter.
2. **Memory reserved above the job's real peak** (0565 4.0 GB against a
   0.97 peak, 0204 3.5 against 2.47, 0276 5.0 against 3.81; an oracle bound
   of about 3.9 h). Candidate 43 `reserve-from-peak` (backlog): `jobs.py
   add` warns and records `mem_gb_high` when `--mem-gb` is over 1.5x the
   same command kind's last peak, symmetric with today's `mem_gb_low`, and
   the runner may admit a job that waited an hour on memory at 1.25x that
   peak. Not opened now: the bound is about an hour a day, an
   under-reservation risks paging other processes, and
   the review measured that the CPU idles more from sleep and job size than
   ordering. Its cheapest probe re-runs `scripts/queue_replay.py` with
   reservations at 1.25x the kind's peak; open only if it recovers 2 h or
   more. 

- **Slot:** three lanes stay open (`act1-content`, `learn-memory`
  projects; `share-curve` exploration), inside the 2-3 rule. A fourth would
  be a lane on the 3.9-hour bound above, which doesn't rank. The next
  slots stay as ranked: `random-world-bench` when `share-curve` closes,
  `pack-net-scratch` after `learn-memory`'s go. Shares as the closing lane
  set them (act1-content 41, share-curve 29, learn-memory 20, main 10).


## share-curve: the parent-change bar is one-sided (on the owner's behalf, 2026-11-09)

The charter's go asks for a parent change "within 0.5 HP of its 33-game
default's". On GE-OppCard-Weak the share 0.8 and 0.9 arms change the
unmutated Lagavulin by +0.15 and -0.04 HP, the 33-game default (share 0.5)
by +1.53 (docs/research/share-curve.md, second half). Read as two-sided,
the arms would fail for keeping the parent better than the default does.
Decided: the bar is one-sided, at most 0.5 HP worse than the default's
parent change; the bar exists to catch a recipe that buys its cut by
forgetting the parent. Alternatives: two-sided (fails a recipe for
retaining better, against the bar's purpose); drop the bar (loses the
forgetting check before step 2). Reversible: the numbers are in the table.
Checkpoint recipe-tables passed on it; step 1b and step 2 queued.

## Lane share-curve closed (2026-11-09)

Outcome: **go** by the stop rule (docs/research/share-curve.md, "Step 1b
and step 2"; `measurement/share-curve@alw`, `@ocw`, `@retention`). On
both mechanics a 33-game net-teacher burst at replay share 0.9 reaches
half the zero-shot cost or the 99-game default's cut: GE-AttackLoss-Weak
1.24 of its cost, GE-OppCard-Weak 0.61 (at its 99-game cut, +4.51 against
+4.13); share 0.8 passes both too. The unmutated parents are spared (the
high shares change them by -0.04 to +0.17 HP; OppCard-Weak's share-0.5
default cost its parent 1.5 HP), and the hardest-trained seeds keep the
one-turn cell gauntlet (+0.06 and +0.31 HP paired, clears up). Goal 1's
games-to-adapt quote becomes **33 games at share 0.9** (from about 100 at
share 0.5); 11 games at share 0.9 meet the same bar, on OppCard-Weak at
the edge (0.50 of the cost, one seed of three at 0.33). The parent-change
bar was read one-sided (decisions "share-curve: the parent-change bar is
one-sided"). Predicted at opening: likely / even / a long shot (11 games
on both); all three came true, the long shot at its bar.

CPU: 9.85 cpu-h of the 12 cap (jobs/done, threads x wall time; the
opening estimate was 6.5 thread-h before step 1b and the OppCard default).

Follow-ups for the navigator (not decided here): `measurement/adaptation-curve`
still quotes about 100 games at share 0.5 and points at this lane; the
finetune default share (0.5) under-trains every small burst; candidate
`pack-dose-33` (38) waited on this go.

**Reopen if:** the quote is challenged on a third kind of mechanic (a
card or power the player holds, or a payoff past the one-turn horizon such
as Ritual 2, which the 99-game default never repaired) or two turns deep:
then re-read g33 sh0.9 and g11 sh0.9 there, three seeds, with this lane's
table and retention read; or if the 11-game number matters for a pack
dose, a share above 0.9 or a second epoch at 11 games on OppCard-Weak.

## After share-curve's close: few-game bursts set replay share 0.9; two probes queued on main (on the owner's behalf, 2026-11-09)

`share-curve` closed on a go (decisions "Lane share-curve closed
(2026-11-09)"): 33 games at replay share 0.9 adapt as far as about 100 at
the default 0.5, with the parents spared. Its three follow-ups:

- **The recipe.** A burst of under about 100 games per mechanic sets
  `"share": 0.9` in its config (`decision/burst-share`). The code default in
  `scripts/finetune.py` stays 0.5 for now: changing it would change what
  every old config without a `share` key means on a rerun, and code is
  not the navigator's. Alternatives passed over: change the default now
  (a lane's code edit; the next lane that edits `finetune.py` may do it,
  with old configs given an explicit 0.5); leave the recipe to each lane
  (the share-0.5 under-training already cost two lanes a wrong quote).
  Reversible: one key per config.
- **The quote.** `measurement/adaptation-curve` (a closed lane's fact,
  the navigator's) and `cause/novelty-is-horizon` quoted about 100 games;
  both now give 33 at share 0.9 beside 100 at share 0.5.
- **`pack-dose-33` (38)** needs no code and about 2 thread-h, so it runs
  from the probe sheet, not as a lane: `configs/packs/gen-b1-dose33.json`,
  gen batch 1's pack chain at 33 games per mechanic and share 0.9, one arm,
  two burst seeds (jobs 0697-0701, lane `main`). Read against gen-b1's g99
  arm (share 0.5; `results/families/gen-b1.md`): go if the pooled
  TurnEnd-Frail x Lagavulin leak is under +1.5 HP (g99: +3.01 (0.39)),
  both nets pass the guard and the target cut stays at half the cost or
  more; stop if the leak is not under +3.01. A go answers
  `measurement/portfolio-pack-retention`'s reopen with a dose, not a
  retention term, and makes the chain's default arm g33-sh9.
- **`card-burst-share` (45, new)**, the close's own reopen case "a card
  or power the player holds": the two card modifiers' bursts of
  `yardstick-cards` (inflame-turn1, metal-c2-a5; 400 games at share 0.5
  cost the parent copy +0.76 and +1.79 HP per elite fight,
  `measurement/cards-adapted@stage-a`) again at 33 games and share 0.9,
  three seeds each (configs `cs9-*`, jobs 0702-0714, lane `main`, about 2
  thread-h). Go if the parent copy, pooled per modifier, is under +0.5 HP
  on both and inflame-turn1's plain-leaf win gain is at least +0.012 (half
  the 400-game bursts'); stop if the parent cost is not below the
  share-0.5 bursts' on both. A go extends the 33-game quote to a card
  mechanic and makes g11 sh0.9 on cards the next read (the close's reopen
  rule); a stop says the high share's parent saving is a monster-bench
  effect.

No pending job is made worthless by either probe (no lane has jobs
queued).

## Lane random-world-bench opened (on the owner's behalf, 2026-11-09)

The exploration slot `share-curve` freed (on-close: wake always). Opened
from its ready charter, candidate 39 (`docs/backlog.md`; the review of
2026-11-09, claim 3): goal 1 on random content, k novel items in one
fight, the world the sample unit. Rated **likely** to build (both
generators exist and the registry loads pack powers on monsters),
**even** that 20-40 worlds per k read a slope, **a long shot** that costs
compound. About 6 cpu-h one turn deep plus half a day of code; cap 9
cpu-h, end 2026-11-13, on-close: wake always (either outcome re-ranks
goal 1's work: additive lets the per-mechanic benches and bursts stand
for random content, compounding moves goal 1's work onto combinations).
Since `share-curve`'s go, an adapted column on worlds costs little (a
33-game share-0.9 joint burst per world, about 0.2 thread-h); the charter
adds it as an optional last step within the cap.

Alternatives passed over:
- `recurring-debuff-leaf` (24, even, cap 3): a zero-games repair of the
  two recurring-Weak mechanics; second in line for the exploration slot.
  It repairs one family on one bench, where the random-world bench says
  whether the per-mechanic picture holds at all.
- `pack-dose-33` (38) and `card-burst-share` (45): no code and about 2
  thread-h each, so they run from the probe sheet (the entry above)
  instead of holding a slot.
- `pack-net-scratch` (42): a project lane, after `learn-memory`'s go.
- A third project lane: `act1-content` and `learn-memory` already hold
  the project kind; a fourth lane only while one is within days of its
  end.

Shares (`jobs/lanes.json`): act1-content 40 (its CPU is landing checks),
random-world-bench 35 (the pilot and the grid), learn-memory 15 (cap 3
cpu-h), main 10 (the two probes above), filler 0.

## A third share-0.9 probe: share-quote-widen (on the owner's behalf, 2026-11-09)

`measurement/portfolio-gen-adapted-column`'s reopen ("a finetune recipe
that improves past one epoch at 30-50 games exists") holds since
`decision/burst-share`. Its two damage-trigger mechanics (OppCard-Damage
and OppCard-PlainDamage x Sentries: 99 games at share 0.5 passed, 33 too
few) run at 33 games and share 0.9 on that lane's tables, three seeds
(families `sc-ocd33`, `sc-ocpd33`; jobs 0715-0728, lane `main`, about 3
thread-h; candidate 46). Go if both pass the table's rule (cut at least
half the zero-shot cost at 2 se over nets) with the trained parent's
change no worse than the 99-game default's (+0.62, +1.08 HP); stop if
either misses half its cost. A go widens goal 1's quote to four
generated mechanics and two trigger kinds; a stop bounds it to debuff
mechanics. Alternative passed over: reopen `gen-adapted-column` as a
lane (it needs no code and no session between the jobs, so a lane slot
would hold nothing a probe does not).

## random-world-bench: paired read on the singles (on the owner's behalf, 2026-11-09)

Step 1's sizing (docs/research/random-world-bench.md, "Step 1") shows the
charter's literal read (k-item worlds' mean cost against 1.5 x k x the
k=1 worlds' mean) can't reach either branch of the stop rule at 20-40
worlds per k: the spread between items enters twice, and additive sits
0.7-2.4 se from the 1.5x line. Decided:
- **Paired read.** Each world's additive prediction is the sum of its own
  items' single costs on its own starts and seeds, already measured in
  `results/mutate/gen-enemies-b1.json` (675 elite starts x 16 seeds, the
  charter's net and depth). The stop rule's test becomes the mean over
  worlds of (cost_w - 1.5 S_w) at 2 se: go above 0 at k 4 or 8,
  additive below 0 at every k. Same threshold as the charter; additive
  sits 5-16 se from it at 20 worlds per k on the 21-item pool.
- **k 0 and k 1 are not replayed:** the parent and the singles are in the
  file; the pilot plays k 2, 4 and 8 only.
- **Enemy pool of 21:** the three mechanics where the heuristic collapses
  (OppCard-Weak, OppCard-Vulnerable, AttackLoss-Vulnerable, as table24's
  headline sets them aside) are a side read, not drawn into the main
  worlds; with them, additive sits 2.7-5.7 se from the line.
- **Unsaturated starts:** a world's starts are drawn among those the
  singles predict to survive (parent loss + summed raw single costs under
  the start HP), since dying caps HP lost and would read as additive
  whatever the truth; deaths are reported beside the cost.
- **Cards second:** card items join once their singles are measured on
  the same starts and seeds (they exist only on starts whose deck holds
  the parent card; `cards-a.json` used other seeds).
Alternatives: the literal read with 100+ worlds per k (about 3x the CPU
and still near 2 se at k 2); replaying k 0 and k 1 per world (pairs on
fewer games than the file has); worlds on all starts (saturation biases
toward additive). Reversible: the sampler records each world's items and
starts, so any of these reads can be computed from the same games.

## random-world-bench: sampler as a standalone script (on the owner's behalf, 2026-11-09)

The charter asks for the world bench "as a resumable family (family.py)
with an automatic table". A family is built around burst nets and their
reads; this bench has no burst until step 5. Decided: a standalone
`scripts/analysis/random_world.py` (spec `docs/specs/random-world-bench.md`)
queued as a resumable play job and a read job with `--check` (exit 0 when
the stop rule reaches go or additive with at least 10 worlds per k),
which gives the same session-free table. Alternatives: a new family kind
in `family.py` (more code in a shared script for one bench; worth it only
if step 5's adapted column needs bursts in the chain); one job per world
(more queue entries, no gain: the play job resumes per world and k).
Reversible: the script and its file format stand alone.

## learn-memory step 1: the 40k peak is round 0's pool, not the training set; step 2 streams the pool (on the owner's behalf, 2026-11-09)

Lane worker. The charter's "train from the example cache in chunks" was
built already: since curriculum Amendment 1 (`aa7f9e5`) the training set
is a view over the memory-mapped caches (about 200 bytes per example in
RAM, training measured at 1.07-1.51 GB up to 502k examples); the 12.8 KB
per example it cites is the step-7 model from before that (mismatch
between the backlog entry, `docs/backlog.md` 30, and the code; the code
stands). What grows with a 40k-game pool is `registry.selfplay`, which
held all 120,000 games' results and their records in memory before
writing (`docs/research/learn-memory.md#Step 1`). Step 2 instead streams
round 0's pool to disk a chunk at a time, the same bytes and dataset id;
step 3's "5k-game learn with and without" is replaced by that byte
identity (same data, same nets) plus one probe of the real config's round
0 at 40k games (`memprobe.py --config`, one epoch, about 2 cpu-h of the
3). Alternatives: keep the charter's step 2 (nothing left to build there);
a compact in-memory form of the results (still grows with the pool);
streaming the branch rounds too (their games are 1,048 per group, small;
left for later if a probe shows them high).

## random-world-bench: no-death worlds for step 4 (on the owner's behalf, 2026-11-09)

The pilot's read (docs/research/random-world-bench.md, "Step 3") said
additive, but the HP cap decided it: at k 8 the net dies in 78% of fights
(24% predicted), so HP lost is squeezed to the start HP while the summed
singles aren't; capping the prediction instead biases toward go (main
k 8 at exactly z +2.0). Raw costs compound for both players (+30% at k 8).
Decided: step 4 plays the parent, each of the 24 mechanics alone and the
worlds (40 main of 21 mechanics, 10 side of 24; k 2, 4, 8) in the engine's
no-death mode (decisions "No-death HP-loss target"; the player's HP may
go below 0, a win ends the fight with the HP left, a loss only at turn
50) on one shared set of 50 elite starts x 4 seeds, read paired against
the file's own parent and singles with the same g and verdict rule (spec
`docs/specs/random-world-bench-nodeath.md`). Its verdict replaces the
pilot's. HP lost then measures how hard a world is without a ceiling;
the price: players play without a death cliff (no desperate lines), so
the cost is that of minimising HP lost, not of surviving.
Alternatives: starts with HP headroom (prediction under 0.8 x start HP
keeps a median of 60 of 675 starts at k 8, minimum 28, and worlds exceed
their prediction by 13 HP, so the cap still binds); raising start HP (out
of the net's training range, and its HP inputs shift for every game);
reading the pilot against capped singles (biased toward go); dropping k 8
(the charter's go branch reads k 4 or 8). Reversible: the pilot file and
its read stay; the no-death file is a separate result.

## Candidate 44 ranked against the open lanes; pack-dose-33 read (on the owner's behalf, 2026-11-09)

The owner's `/approach` on pile prices (commits b6bc95b, d676ab4, ab236d0;
`docs/research/pile-prices-2026-11-09.md`) asked to rank
`shown-card-numbers` (backlog 44) against the open lanes.

- **The open lanes keep their slots.** `act1-content` is the owner's
  standing goal until Act 1 is finished (`decision/act1-finish`).
  `random-world-bench` keeps the exploration slot: its pilot (0731) read
  additive on the main pool with 20 worlds per k, goal 1 at development
  weight 0.8, and it is the record's only read of more than one novelty in
  a fight. `learn-memory`'s last read (0732-memprobe) is running; it
  closes within hours.
- **44 is the next project slot's ready charter, whatever `learn-memory`'s
  outcome, ahead of `pack-net-scratch` (42).** Its cost is 1-2 h of
  engine code and about 4 cpu-h (cap 6, end 2026-11-13, on-close: wake
  always); it is the owner's proposal with zero-shot evidence on two
  measures (`measurement/shown-numbers@pairs`,
  `measurement/exhaust-hidden@pairs`); and it decides the input layout of
  42's 40-60 thread-h from-scratch learn: a net trained on printed numbers
  needs a new learn to adopt shown ones, while a net trained on shown
  numbers carries them to every pack (a generated attack's shown damage
  follows from the rules, not from games). Its read also plays the shown
  arm on the generated bench's recurring Weak and Frail rows, the rows
  `recurring-debuff-leaf` (24) targets, at no extra code; if that halves
  both Weak rows, 24 narrows to Frail and Vulnerable before it opens.
  Rated even on the Strength stratum one turn deep, a long shot on the
  headline and on the Weak rows; the evidence against it now includes the
  Pummel timing oracle's bound (about +0.002 headline clears,
  `measurement/pummel-timing@replay`): a better price moves play only
  where lines differ in what they leave in the piles or in Strength at the
  leaf. The trade-off rule holds: the flag-off arm is today's play, and
  the flags can lose through inputs the net never saw.
- **24's charter end moves to 2026-11-18**: the exploration slot frees on
  2026-11-13 at the earliest (`random-world-bench`'s end).
- **pack-dose-33 (probe sheet, 0697-0701; `measurement/pack-dose-33@gen-b1`):
  between.** The Lagavulin leak is gone (+0.54 (0.33) against g99's
  +3.01), but Nob's cut falls to a third (+4.24 of +13.29) and both nets
  lose the OppCard-Vulnerable x Sentries edge (+7.06 HP, wins -0.213), so
  the guard fails on both. The single-mechanic quote of 33 games at share
  0.9 (`decision/burst-share`) does not carry to a pack of eight mechanics
  in one burst. Second read queued (jobs 0734-0738,
  `configs/packs/gen-b1-dose99s9.json`): 99 games per mechanic at share
  0.9, the same rule. A go makes g99-sh9 the pack chain's default arm and
  answers `measurement/portfolio-pack-retention`'s reopen with a dose; a
  stop keeps g99 at share 0.5 and the leak as that lane's trade.

Alternatives passed over: open 44 now as a fourth lane (learn-memory
closes within hours; two lane workers would hold three code streams for
an hour's gain); make 44 the exploration slot's next charter ahead of 24
(that slot frees on 11-13 at the earliest, and 44 gates a project lane);
rank 44 behind 42 (42's learn would bake printed numbers in for 40-60
thread-h before the read); not propose 44 (both arms can gain or lose).
For pack-dose-33: stop on the first read (the leak criterion was met and
the dose question is unanswered between 33 and 99), or a 66-game arm (one
point between two that each failed one clause says less than the dose
that passed the cut at share 0.5). Reversible: a ready charter and a
probe on lane `main`.

## After card-burst-share: between, no larger card dose (on the owner's behalf, 2026-11-09)

The probe-sheet read of `card-burst-share` (backlog 45; jobs 0702-0714;
`measurement/card-burst-share@stage-a`; read rule in "After share-curve's
close") is between: at 33 games and replay share 0.9 the parent copy's
cost per elite fight falls to +0.52 (0.15) HP on inflame-turn1 (bar 0.5;
400 games at share 0.5: +0.76) and to -0.33 (0.18) on metal-c2-a5 (was
+1.79), while inflame-turn1's plain-leaf win gain is +0.010 (0.004)
against the +0.012 bar (400 games: +0.024); with the turn-start leaf
nothing is closed, as at every size before.

- Not a go, so g11 at share 0.9 on cards is not read and the card
  column's recipe is not changed; both recipes stay on file, and a card
  column quotes the share-0.9 burst's retention beside the share-0.5
  burst's gain.
- No larger card dose follows (backlog, Checked and not proposed,
  *card-burst-dose*): with @tsl1 no burst has closed any card cost, and
  the best plain-leaf burst only matches what @tsl1 gives with no games,
  so a bigger plain-leaf dose cannot gain over the leaf the cards are read
  with (the trade-off rule).
- Together with `measurement/pack-dose-33@gen-b1` the picture is the same
  twice: share 0.9 keeps the net near its parent, and the target's gain
  follows its own games; 33 suffice for one monster mechanic and for
  Metallicize, not for Inflame's recurring tick or for eight mechanics in
  one burst. A cause fact waits for share-quote-widen (0728) and the
  pack's 99-game read (0738).

Alternatives passed over: count the narrow misses as a go (inflame's
parent and win gain miss their bars by under a fifth of an se, and
"a check that passes at exactly its bar gets a look"; a miss at its bar
is no better evidence); a 99-game card arm (above). Reversible: no
recipe or default changed.

## random-world-bench: bounded read of the no-death worlds (on the owner's behalf, 2026-11-09)

The step-4 read job (0740) printed go from the mean of uncapped no-death
HP lost, which runaway fights to the 50-turn limit dominate (main k 8:
2932 HP raw net loss, 46% turn-limit games). Decided: the lane's verdict
comes from HP lost bounded per game, as play bounds it (docs/research/random-world-bench.md,
"Step 4"): at every bound tried (start HP, +30, 100, 150) and against
both the plain and the bounded sum of singles, g sits 10-37 se below zero (main pool; side pool 1.4-14 se)
at every k: **additive**; the lane's step is done: additive. Alternatives:
take the job's go at face value (it measures runaway length, not play);
rerun with a shorter turn limit in no-death mode (more CPU for the same
answer, since every bound already agrees); keep the lane open for step 5
(an adapted column; optional, and the stop rule is reached). Reversible:
both files and the caps script stay; a reader preferring another bound
reruns `scripts/analysis/rwb_nodeath_caps.py`.

## Lane learn-memory closed (2026-11-09)

Outcome: **go** by the stop rule (docs/research/learn-memory.md, "Step
3/4 read"; `measurement/learn-memory@40k`). Round 0 of a from-scratch
40k-game learn (`allcontent40k-s101`, 120,000 games, 417k examples) peaks
at **1.01 GB commit** against the 3.5 GB bar, with the pool's
`games_sha256` equal to 0583's, so the examples and the net are today's.
Two fixes did it: round 0's pool streams to disk a chunk at a time (step
2; 0.92 GB at 120,000 games), and the solve step reads only the games it
solves (`puzzles.dataset_games` had decoded the whole pool before cutting
it: 3.72 GB and 43 s for a step that solves 0 games; now 0.25 GB, 0 s).
The charter's premise was out of date (the training set has been a view
over memory-mapped caches since curriculum Amendment 1), so no chunked
trainer was built and no second learn was run (byte-identical data, so
"nets level" holds by construction; minutes per round not slower: the
training code is unchanged and the solve step lost 33-43 s). Predicted at
opening: likely that it builds, even that training time stays within
15%; both held, the second trivially.

CPU: about 1.8 cpu-h of the 3 cap (`jobs/health.json` `lane_cpu_h`; one
26-minute probe at 4 threads, plus a few seconds by hand).

Follow-ups for the navigator (not decided here):
- The job runner's `peak_gb` is the working set of the job's process
  tree, which counts memory-mapped feature-cache pages (6.06 GB for this
  probe against 1.01 GB commit). `jobs.py add` suggests `mem_gb` from the
  last `peak_gb` of the same command, so a learn would reserve about
  7 GB and wait for memory it doesn't need; set a learn's `mem_gb` from
  commit (about 1.5 GB at 40k games). 0583's 6.03 GB, which
  `cause/memory-holds-bursts` and candidate 30 cite, was measured the
  same way; that fact's numbers for bursts may be part mapped cache too.
- `pack-net-scratch` (42) waited on this lane ("once `learn-memory` has
  gone").

**Reopen if:** a learn with branches in its later rounds (the path step 2
left unstreamed, 1,048 games per group) or a config with a solve step
over many games peaks above 3.5 GB commit, or the mapped cache's reads
make an epoch more than 15% slower when less than its size is free:
then measure that round's phases with `scripts/memprobe.py --config`.

## Lanes shown-card-numbers (exploration) and pack-net-scratch (project) opened (on the owner's behalf, 2026-11-09)

Woken by `learn-memory`'s close on a go (`measurement/learn-memory@40k`:
a 40k-game from-scratch learn's round 0 peaks at 1.01 GB commit). At the
same time `random-world-bench` reached done (additive,
`measurement/random-world@nodeath`; its close is in progress and wakes
the navigator), so both its exploration slot and learn-memory's project
slot are free. This changes the order set two hours earlier ("Candidate
44 ranked against the open lanes": 44 in the next project slot, 42
after it):

- **`shown-card-numbers` (backlog 44) opens in the exploration slot**,
  ahead of `recurring-debuff-leaf` (24). It is cheap (1-2 h of engine code,
  about 4 cpu-h), a new input approach with zero-shot evidence, and its
  read plays the shown arm on the generated bench's recurring Weak and
  Frail rows, which 24 targets: 24 waits for that read, then opens
  narrowed or whole. Rated even on the Strength stratum one turn deep, a
  long shot on the headline. Charter as the backlog's ready charter, with
  kind exploration.
- **`pack-net-scratch` (backlog 42) opens in the project slot now**,
  instead of after 44 closes. Three things changed: the learn fits
      in memory (learn-memory's go); the CPU stands mostly idle
  (`cpu` red since 2026-11-06, 0.16 of the machine) while act1-content
  writes code, so seed 1's learn costs CPU nothing else would use; and
  44's question does not decide 42's first answer (does a net learned
  on the Act 1 pack fight the pack better), since 44's flags are
  zero-shot and play on any net. If 44 closes on a go before 42's step 3,
  seeds 2 and 3 learn with its flags and seed 1 gets a flags twin; else
  the recipe stays. Rated even that seed 1 beats the 10-29 net on the
  pack-offers headline by 2 se. About 40-60 thread-h for three seeds;
  cap 60, end 2026-11-14 (seed 1 and its read fit; a pass extends once).
  The learn's `mem_gb` is set from commit (about 1.5 GB at 40k games),
  not from the runner's `peak_gb`, which counts the mapped feature cache
  (6 GB); if the runner then holds other jobs out by a running learn's
  working set (`how/job-admission`: a running job reserves its measured
  peak when higher), the lane's first code step makes the runner count
  commit.
- Shares (`jobs/lanes.json`): act1-content 35, pack-net-scratch 30,
  shown-card-numbers 15, random-world-bench 10 until its close, main 10.
- `cause/memory-holds-bursts` re-set: its exit holds (bursts now peak
  0.5-1.1 GB, jobs 0697-0712; a 40k learn 1.01 GB commit), and its 6 GB
  learn figure was the mapped cache.

Alternatives passed over: keep the order of two hours ago (44 first in
the project slot, 42 after it; leaves the CPU idle about a day and the
exploration slot to 24, which 44's read may narrow); open 24 in the
exploration slot and 44 in the project slot (24 might be answered in
part by 44's read; 42 would wait again); open 42, 44 and 24 together
(four lanes after random-world-bench closes, beyond 2-3). Reversible:
42's seed 1 is one queued learn; either lane closes early on a decisions
entry.

## Lane random-world-bench closed (2026-11-09)

Outcome: **additive** by the stop rule (docs/research/random-world-bench.md,
"Step 4"; checkpoint `passed nodeath-read`). For k generated enemy
mechanics (pack powers from the enemies bench) on the official elites,
one turn deep, the 10-29 net's cost beyond the heuristic is about +5.5 HP
at k 2, +6.5 at k 4 and +5-10 at k 8 with HP lost bounded per game, far
below 1.5 x the sum of its singles at every k and every bound (main pool,
40 worlds per k: z -10 to -37; side pool -1.4 to -14). The net loses to
novelty about once per fight, not once per item. Raw difficulty does
compound, for the heuristic as much as for the net (the pilot, Step 3).
So the per-mechanic benches give an upper bound for random enemy worlds:
goal 1's random-content cost, as far as this bench reaches, is at most the
sum of its parts. One sign kept: at k 8 the net reaches the 50-turn limit
more often than the heuristic (0.46 against 0.35) in no-death fights both
players lose in real play.

Predicted at opening: likely that it builds (held), even that 20-40 worlds
per k read a slope (held, at 40 worlds with paired starts), a long shot
that costs compound (they did not, beyond the heuristic). Not covered:
card items (a card variant exists only on starts whose deck holds its
parent, and their singles were never measured on these starts), bosses,
two turns deep, and the optional adapted column (step 5; the stop rule
was reached first).

CPU: about 3.7 cpu-h of the 9 cap (`jobs/health.json` `lane_cpu_h`).

On-close: wake always; the navigator is woken with the outcome. Its slot
was already filled (decisions "Lanes shown-card-numbers (exploration)
and pack-net-scratch (project) opened"), so its share of 10 went 4 to
act1-content, 4 to pack-net-scratch and 2 to shown-card-numbers.

**Reopen if:** card items' singles are measured on shared starts (a deck
pool where each card variant's parent is present), so worlds can mix
cards and enemies; or a two-turn or adapted player is the one goal 1
quotes and its per-mechanic costs differ from the one-turn net's; or the
k 8 turn-limit stalls (0.46 against 0.35) show up in fights the net can
win in real play (with-death mode, a boss world). Then rerun
`scripts/analysis/random_world.py` nd-play/nd-read on that pool and
`scripts/analysis/rwb_nodeath_caps.py` for the bounded read.

## After share-quote-widen: the 33-game quote widens on the cut, not on the parent (on the owner's behalf, 2026-11-09)

The probe-sheet read of `share-quote-widen` (backlog 46; jobs 0715-0728;
`measurement/share-quote-widen@sentries`; rule in "A third share-0.9
probe: share-quote-widen") is between: both damage-trigger mechanics pass
`gen-adapted-column`'s cut rule at 33 games and share 0.9 (OppCard-Damage
0.64 of its cost, OppCard-PlainDamage 0.69), and OppCard-Damage's trained
parent is spared (-0.02 HP), but OppCard-PlainDamage's loses +1.68 (0.26)
HP per fight, more than the 99-game share-0.5 default's +1.08.

- Goal 1's quote becomes: 33 games at replay share 0.9 cut half or more
  of the cost on four generated mechanics, two trigger kinds, one at a
  time; the trained parent is spared on three of the four and loses
  about 1.7 HP on OppCard-PlainDamage x Sentries. `decision/burst-share`
  and `measurement/adaptation-curve` are re-set to say so.
  `measurement/pack-dose-33@gen-b1` stays the limit: eight mechanics in
  one burst need more than 33 games each.
- No change to the recipe: share 0.9 at 33 games stays the default for a
  single mechanic's burst; a burst whose mechanic punishes playing cards
  reads its parent row before it ships (the pack chain's guard already
  does).
- The share-0.9 cause fact waits for 0738 (the pack chain at 99 games and
  share 0.9), as planned: two of three reads so far say the parent is
  spared, this one says a burst can still teach its parent's encounter a
  costly lesson.

Alternatives passed over: count it a go (the rule says no worse; the
difference is about 1.5 se, so "worse" is a lead, not a result, but the
rule was written before the read); a 99-game share-0.9 arm on
OppCard-PlainDamage to see whether the parent cost follows the share or
the mechanic (the pack read 0738 holds the same mechanic and parent at 99
games and share 0.9 in a joint burst, so read that first). Reversible: no
recipe changed.

## pack-net-scratch: pack learn design (on the owner's behalf, 2026-11-09)

Spec `docs/specs/pack-learn.md` confirmed under the mandate. `learn.py`
takes `packs` (pack files); every game, training and validation, draws its
extra cards uniformly over the official Ironclad pool plus all pack cards
(upgrades included), and each group's pack encounters join it at
added / (added + official) per spec, a pack version replacing its official
namesake (the gauntlet's `pack_hard` rule). Seed 1 learns on both Act 1
packs (`configs/packnet40k-s1.json`, otherwise `allcontent40k-s1`). The
one-turn pack control is rebuilt at the learn's pin, since the pack grew
from 27 to 29 cards after the old control (`g1-net1029-hpb0.01-...`).
Alternatives passed over: pack cards in a share of decks only, like
`content_share` (would under-train the pack against the read, where the
cards fill half the offers); pack encounters in training only (validation
would not match training); reading against the old 27-card control with
`--vary pack` (loses pairing on the offers). Reversible: a config key.

## C5 cost changes: one HP-loss counter and two power fields (on the owner's behalf, 2026-11-09)

Lane act1-content, spec `docs/specs/cost-changes.md` (confirmed under the
mandate). Provisional, all reversible:
- A combat-wide counter of HP-loss events (counted only when the binding
  holds a card with `cost_less_per_hp_loss`, capped at the largest such base
  cost) instead of a cost per card copy. Alternative: per-copy costs as
  sts_lightspeed keeps them (changes every pile's representation; C11 will
  need it for "costs 0 this turn"). Known difference: an Exhumed Blood for
  Blood gets losses from while it was exhausted.
- Corruption as two pack power fields (`sets_cost`, `exhausts_played`),
  like `forbids`. Alternative: a `CardCost` static with a type condition
  plus a hook exhausting the card in play.

## act1-content parked; the owner leads Act 1 content (owner, 2026-11-09)

The owner: the lane system is too slow for adding Act 1 content, so the
owner leads that work in their own session.

- `act1-content` is parked: no lane worker claims or works it, and it
  queues no new jobs; jobs already running finish. The navigator parks
  it (charter, `jobs/lanes.json` share) on its next run. Reopening it is
  the owner's call.

- State at parking (`lane/act1-content/step`, `measurement/act1-cards@files`):
  monsters done; 31 of 40 missing Ironclad cards from the pack, 9 blocked;
  relic and potion inventory written (`docs/research/act1-relics-potions.md`),
  no relic or potion code.
- Why: per block the lane runs spec, confirm, build, review, speed read, sanity pair and checkpoint (C3: about 3.5 h for two cards).
- Alternatives: keep the lane and split by kind (the owner on some kinds,
  the lane on others); keep the lane as it is.

- Addendum (owner, 2026-11-09): the lane worker that had started before
  the park keeps coding card-sets (`docs/specs/card-sets.md`) without
  waiting on any job, lands it and stops there; no later block, and the
  lane stays parked.

## Headline card pool and choosers after Act 1 (owner, 2026-11-09)

The owner: the headline's card pool (offers drawn uniformly from 21 train
and 31 held-out cards, `scripts/gauntlet.py` `reward_pools`) is small and
artificial, and limits how much gain a net trained on new content can
show: such a gain shows only where the new cards are offered
(`measurement/portfolio-all-content-net`: gains on held-out cards, +0.02-0.03
on train decks).

- After Act 1 is done, the headline's pool widens to the cards the
  engine holds, and its controls are built once then. Not before: the
  pool still changes and new controls cost about 10 thread-h (jobs
  0463-0465). The `--pack` reads already on file stay side reads.
- Reads of nets trained on new content on it use cross comparison
  (deck-matched `--match` or crossed arms, `how/gauntlet-read`) for the
  noise between nets (`cause/headline-pairing-weak`).
- The value chooser is the chooser there once a net has trained on the
  pool (`decision/value-chooser-use`'s reopen), changed first as
  backlog `value-chooser-path`: every encounter the sequence can still
  meet, and no card-draw evaluation (states valued before the opening
  hand).
- Rejected: a chooser that averages exactly over every opening hand. The
  value chooser is meant to be cheap, and the owner sees no place for
  such a chooser; the long-run aim is the AI making run decisions.
- Open: what the held-out half becomes on the wider pool.
- Alternatives: make the `--pack` setting the ruler now; keep the
  curated pool as the only ruler (`decision/headline-quote`).

## Card sets as built (on the owner's behalf, 2026-11-09)

Lane act1-content, spec `docs/specs/card-sets.md` (confirmed by the owner,
2026-11-08; built under the mandate). Provisional, all reversible:
- Card pools live in `configs/card-sets.json`, compiled into the engine
  (`card_sets` module) and read by Rust and Python alike. Alternatives:
  Python only (the engine's default pools would change), or each training
  config listing its own pool.
- A set is a plain list of base names, used in card order (a name brings
  its `+` card); adding content never changes a pool. Alternative: rules
  (class minus other sets).
- The old helpers (`deck_cards`, `class_cards`, `held_out_cards`;
  `sts.deck_card_names`, `class_card_names`, `held_out_card_names`) stay as
  the default sets' names. Alternative: replace every caller with
  `sts.card_set`.
- The official loader accepts and ignores the old `held_out` / `proving`
  flags; packs still refuse them as official-only. Alternative: check them
  against the sets file.
- Built before C6 (card upgrades), whose fixture is taken from the
  flag-free `cards.json`.
- The sets file is not part of the rules fingerprint (`solvedb`) or the
  golden games, so editing a pool invalidates no stored solve and no
  rules version. Alternative: fingerprint it like the content files.

## Shown card numbers and exhaust hidden as built (on the owner's behalf, 2026-11-10)

Lane `shown-card-numbers` step 1 (spec `docs/specs/shown-card-numbers.md`):
two encoder flags, off by default, `@sn1` (card damage + Strength x hits,
x0.75 rounded down under Weak; block + Dexterity, x0.75 under Frail) and
`@xh1` (exhaust pile counts as 0). Parity with the zero-shot scripts is
exact (`scripts/shown_numbers_parity.py`: batches equal on pairs.jsonl's
states; correlations 0.218 / 0.203 / 0.221 as zs_noex.py). Both off:
series_check PASS, encoder time within noise.

- **Weak rounds the whole total, not each hit** (zs.py's arithmetic, so the
  zero-shot evidence carries; the game floors per hit). Alternative: per
  hit, closer to the game, differs by at most hits-1 on multi-hit cards;
  reversible (one line in `show_numbers`).
- **series_speed not run:** it times engine-only binaries and the engine
  crate is untouched; the encoder's own time stands in.
- **Step 2 plays at fixed n 500 without `--against`** (no early stop), read
  by `scripts/analysis/shown_strata.py` against the control file by
  stratum; the protocol's verdict is computed there. 436 of the 500 cell
  decks hold a stratum card, so "the rest" is 64 sequences and its se is
  wide.
- **Bench rows:** no plain `@tsl1` file covers the Weak rows (batch 1 has
  TurnEnd-Frail only), so step 2 plays both arms (0760 control with the
  heuristic, 0761 shown) on the four Weak/Frail turn rows, 8 seeds.


## Lane shown-card-numbers closed (2026-11-10)

Outcome: **fail** by the stop rule (docs/research/shown-card-numbers-2026-11-10.md;
checkpoint `failed step2-read`). Today's 10-29 net one turn deep @hpb0.01
on the one-turn cell gauntlet (sequences 0-499, fixed n 500, against
`results/gauntlet/net1029-hpb0.01.json`) is level with every arm: shown
numbers `@sn1` -0.24 (0.21) HP, exhaust hidden `@xh1` -0.24 (0.22), both
-0.34 (0.26); clears within +0.005; the Strength / multi-hit stratum (436
of 500 decks) reads the same. The flags change about a third of the
sequences, so the net reads them; it does not play better zero-shot. On the
generated bench's Weak and Frail turn rows (675 elite starts x 8 seeds,
@tsl1), `@sn1` recovers part of the recurring-Weak cost (+0.006 (0.002)
and +0.005 (0.001) win rate, cuts 0.54 and 0.40) with parents unchanged,
but halves neither Weak row at 2 se; Frail rows are within noise. So
`recurring-debuff-leaf` (backlog 24) opens whole, and `pack-net-scratch`'s
seeds 2-3 learn without the flags.

Predicted at opening: even on the Strength stratum one turn deep, a long
shot on the headline, about 4 cpu-h. Actual: level on the stratum, no
headline read (step 3 not reached).

CPU: about 2.0 cpu-h of the 6 cap (`jobs/health.json` `lane_cpu_h`).

The flags stay in the engine, off by default (`@sn1`, `@xh1`; parity script
`scripts/shown_numbers_parity.py`).

On-close: wake always; the navigator is woken with the outcome and the
exploration slot stays empty for it. The lane's share of 17 goes to
`pack-net-scratch` (34 -> 51), the one lane a worker runs (act1-content is
parked with the owner).

**Reopen if:** a net is trained with `@sn1` on (shown numbers as a training
input, the training rule's second reason: something the 10-29 net cannot
see), e.g. as a `pack-net-scratch` seed or a fine-tune burst, and that net's
own `@sn1`-off read shows the inputs matter; or the Weak rows' partial cut
grows on a stronger-debuff bench (Weak plus Strength-scaling enemies) to a
halving at 2 se. Then rerun `scripts/analysis/shown_strata.py` against that
net's own control.

## Lane recurring-debuff-leaf opened (on the owner's behalf, 2026-11-10)

Woken by `shown-card-numbers`' close on a fail (`measurement/portfolio-shown-card-numbers`):
the exploration slot is empty. Its bench read settles the open clause of
backlog 24's charter: shown numbers cut the two recurring-Weak rows 0.54
and 0.40 (win rate), not halved at 2 se, so **`recurring-debuff-leaf`
opens whole** (Weak, Frail and Vulnerable put back each monster turn), as
the backlog's ready charter, kind exploration. Two changes to the charter:
the end moves from 2026-11-18 to 2026-11-13, and
step 2's control is the 10-29 net `@tsl1` on the bench's first 8 seeds
(as 0760 played it), the same arms the shown-numbers read used, so the two
reads sit side by side. Rated **even** that one k halves both Weak rows at
2 se (for: the cost is systematic across parents, shown numbers already
recover half of it zero-shot, so the net does misprice Weak's lasting
effect; the leaf kind simulates rules rather than adding a price, the kind
that has not traded; against: projected Strength left boss wins unmoved).
About 1-2 h of engine code and 2 cpu-h of reads; cap 3 cpu-h.

Alternatives passed over: `aivat-reads` (40; a long shot, 3-4 h of engine
code for a read tool, and the paired sd it would cut matters most for
goal 2, weight 0.2); `race-price` (9; a long shot, growth's cost was not
moved by projected Strength); `exact-referee` (20; its reach is short on the
one class with a measured cost); the new `generated-pack-scratch` (47) as
exploration (it needs a learn per seed, 12+ thread-h, so it is project-sized;
it is the next project slot's ready charter instead).

Shares (`jobs/lanes.json`): pack-net-scratch 45, recurring-debuff-leaf 25,
act1-content 20 (parked with the owner, whose own jobs may run in it),
main 10, filler 0.

## Probe pns1-gen-bench queued (on the owner's behalf, 2026-11-10)

`pack-net-scratch`'s seed 1 (0749 r1) passed its checkpoint well above its
bar: on the 31-card pack headline one turn deep +3.25 (0.94) HP and +0.084
clears against the 10-29 net's matched control, and on the one-turn cell
gauntlet (official content, the retention read) +1.61 (0.58) HP, +0.014
clears (0753's check log; a single seed: a lead until seeds 101 and 201
read). A from-scratch learn on wider content does not cost official play
and may gain on it. What it says beyond its own question is about goal 1:
does breadth of training content carry zero-shot to novel mechanics? Job
`0762` (lane main, about 3.5 thread-h) plays that net on the generated
bench's eight costliest or edge rows (the reopen form of
`measurement/portfolio-generated-enemies-bench`: a new candidate base net
re-reads the costliest pairings), read against `results/mutate/gen-enemies-b1.json`
by `mutate_monsters.py compare`. The read rule is in its note: breadth
carries if 3 or more of the 7 costly rows are cut 0.3 or more at 2 se with
the OppCard-Vulnerable edge kept; a level read says official breadth buys
nothing on generated mechanics, which leaves `generated-pack-scratch` (47)
its own rating, since the Act 1 pack holds no generated mechanic. No
pending job is affected. Alternatives: wait for seeds 101 and 201 (the
probe runs now on otherwise idle threads and repeats on them only if it
reads a cut); the whole 24-row bench (about 10 thread-h; the eight rows
hold the costs and the edge).

## After pack-dose 99s9: pack chains train 99 games per mechanic at share 0.9 (on the owner's behalf, 2026-11-10)

The probe sheet's second pack-dose read (jobs 0734-0738,
`configs/packs/gen-b1-dose99s9.json`, `results/families/gen-b1-dose99s9.md`;
read late, at this run): gen batch 1's pack chain at 99 games per mechanic
and replay share 0.9, two nets, against the zero-shot 10-29 net (HP lost
per elite fight, 675 starts x 4 seeds, pooled per start). Pooled, the
TurnEnd-Frail x Lagavulin leak is gone (-0.16 (0.28) HP; g99 at share 0.5
+3.01 (0.39)), Nob's AttackLoss-Damage cut is +12.18 (se over nets 0.59) of
+13.29 (g99: +11.50), the OppCard-Vulnerable x Sentries edge is kept and
grows (-4.31 (0.50) HP, wins +0.106), OppCard-PlainDamage x Sentries is cut
+5.13 of +7.36 with the Sentries parent at -0.04 (0.21), and the parent
over all encounters moves -0.12 (0.14). Net s1 passes the guard (mean cut
+1.64); net s2 fails it on GE-OppCard-Vulnerable x Lagavulin, +2.97 (0.57)
HP (pooled +0.78 (0.42)).

By its written rule (go needs both nets to pass the guard) this is not a
go. Decided anyway: **new pack chains use 99 games per mechanic at share
0.9** (the arm `g99-sh9`), because the rule's stop branch kept g99 at share
0.5, which fails the same guard on one net of two by more (+4.86 HP on
TurnEnd-Frail x Lagavulin) and is worse on every row the rule names (leak,
Nob cut, Sentries edge; mean cut 0.85-0.99 against 1.33-1.64). The chain
already ships only a net that passes the guard, so a failing seed is
dropped, not shipped. Reversible: arms are per pack config; no code
default changes. The share-0.9 question that waited on this read ("After
share-quote-widen") is answered for joint bursts: at 99 games each, share
0.9 spares the parents, OppCard-PlainDamage x Sentries included.

Alternatives passed over: keep g99 at share 0.5 (dominated, above); a third
seed of g99-sh9 to settle the guard (about 1 thread-h; both arms fail the
guard on one seed of two, so a third seed would not change the choice
between them).

## Probe pns-twin and pns-official queued; the pack net's two-turn read waits on the three-seed check (on the owner's behalf, 2026-11-10)

The navigator woke on `lane/pack-net-scratch/checkpoint` (seed 1's
checkpoint, set after the last run had read it); the three-seed read
(0766-0769) is still queued. Three gaps in what that read can say, each
closed by a read that needs no code, queued in lane `main` on the pack
lane's snapshot (pin 2af5b30, the same `sts` bytes as 0766-0769):

- **pns-twin** (0770-0773). The pack net's recipe (`configs/packnet40k-s1.json`)
  differs from the 10-29 net in four ways at once: 40k games, one round,
  `deck_pool: all` (it trains on the cells' held-out half too) and the
  pack. The all-content nets of 2026-11-08 (`allcontent40k-s1`, `-s101`)
  are the same config minus `packs`, same seeds, never read on the cells
  or the pack headline. So they split the gain: twin against the controls
  is the recipe (and zero-shot play of the pack cards by effect inputs,
  open question 17 on cards); pack net minus twin, per sequence, is what
  training on the pack adds. Reading note: the results doc's hint that
  the held-out halves gaining more "is a hint that all-content training
  generalises better" does not follow, because with `deck_pool: all` the
  held-out cards are in its training; the twin shows how much of it that is.
- **pns-official** (0774-0776). The lane reads the pack headline and the
  cells, not the ruler: goal 2 judges a change on the headline setting one
  turn deep against the one-turn control (`yardstick/headline-setting`,
  `yardstick/one-turn-controls`). Three seeds, pooled per sequence.
- **pns-two-turn** (0777 control, 0778 seed 1), each `--if-passed
  0769-gauntlet --on-fail cancel`: the product on the 31-card pack,
  sequences 0-249, and pack net seed 1 (named before seeds 101 and 201
  were read, so no selection) two turns deep against it. It asks whether a
  gain from knowing the content survives depth better than a leaf gain
  (`cause/leaf-gain-third`: 0.2-0.46x; its exit names payoffs past both
  horizons, as the pack's setup powers are). About 12 thread-h.

What each outcome does. pns-twin: if the pack net beats its twin by 2 se
pooled over seeds 1 and 101 and by over half its gain on the pack, the pack
content pays and `generated-pack-scratch` (47) keeps its rating; if the
twin carries more than half, the gain is the recipe, 47's comparison base
stays the pack net (unchanged), and the all-content recipe becomes the
goal-2 fighter question (a twin read on the official headline next).
pns-official: pooled +1.5 HP at 2 se (clears not z <= -2) makes the pack
recipe a goal-2 fighter gain on the ruler; a two-turn read on the official
headline against `yardstick/headline-control` follows only if the gain is
outside the bosses or at least about 3.9 HP (three times that read's
detectable effect). pns-two-turn: ratio >= 0.6 with the two-turn gain 2 se
above zero means content gains survive depth, and the pack-capable net is
the product's fighter candidate once the headline pool widens
(`decision/headline-pool-after-act1`); <= 0.46 means it behaves as a leaf.

The slot question this wake was set for is decided now rather than at the
three-seed read: the next project slot takes `generated-pack-scratch` (47)
as chartered, whatever the three-seed read says; the pack net's product
reads run as the probes above, not as a lane. The exploration slot gets a
ready charter (`fickle-enemy`, backlog 33, the owner's idea), so a fail of
`recurring-debuff-leaf` opens it without a navigator round.

No pending job is made worthless by these; none is reordered. About 20
thread-h, on threads that would otherwise idle (health `cpu` 0.28, `ready`
2.66 h). Alternatives passed over: wait for the three-seed read before any
of it (costs a navigator round and idle CPU); the official two-turn read
now (about 12 thread-h for 500 sequences, earned only by pns-official);
500 sequences for pns-two-turn (twice the CPU for the ratio question,
whose two cases differ by about 3 se at 250).

## Probe pns1-gen-bench read: the pack net loses generated-bench play zero-shot; 47 also bars against the 10-29 net (on the owner's behalf, 2026-11-10)

Job 0762 (`docs/research/pns-probes.md#pns1-gen-bench (0762): the pack net
loses generated-bench play zero-shot`, `measurement/pack-net-gen-bench@seed1`):
pack net seed 1 one turn deep on the generated bench's eight costliest or
edge rows loses more HP than the 10-29 net on five of the seven costly
rows (+1.6 to +3.2 HP per elite fight) and turns the OppCard-Vulnerable
edge into a loss (+11.67 HP, wins -0.304); unchanged elites +0.62 (0.16);
only the two Weak-on-action rows gain (-2.06, -2.24). By the probe's rule
this is the guard branch: the pack net is not a goal-1 base for generated
packs, and the "breadth carries" branch (47 to likely) did not happen.

Decided:
- **47's charter gets a second bar.** Its go compared the held-out rows
  with pack net seed 1 only; seed 1 now sits well below the 10-29 net
  there, so a 0.4 cut could be catching up. The go now also needs the
  held-out rows' pooled cost not worse than the 10-29 net's
  (`results/mutate/gen-enemies-b1.json`) at 2 se. Step 3's pack-net-seed-1
  file exists (`results/mutate/gen-pns1-tsl1.json`, eight of the 24 rows),
  so step 3 plays only 47's net and the 16 rows that file lacks for seed 1.
  47 stays **even**: against it, breadth of official content cost
  transfer; for it, 47's mechanism is variety inside the generated family
  (each trigger with many effects), which the pack lacked (its one
  OwnerLostHp-from-Attack example is Angry on a gremlin).
- **Attribution probes queued** (lane `main`, pin 2af5b30): 0779 the
  all-content twin (the pack net's config minus its packs) and 0780 pack
  net seed 101 on the same rows. If the twin loses as the pack net does,
  the recipe (40k games, one round, every card) is weaker off its content,
  and 47's learn should not use it unchanged: the navigator re-sets 47's
  step 2 before its learn is queued (47's step 1 is about 2 h of code, so
  the read lands first). If the twin stays near the 10-29 net, the pack's
  few powers did it, which is 47's own argument.

No pending job is made worthless; none is reordered. Alternatives passed
over: drop 47 (the read tests official breadth, not generated breadth,
which is 47's question); delay 47's opening until 0779 (its code step
needs no learn recipe, and the slot would idle); read seeds 101 and 201
both (seed 101 alone says whether seed 1 is an outlier, at half the CPU).

## Lane recurring-debuff-leaf closed (on the owner's behalf, 2026-11-10)

Outcome: **fail** at its one read (checkpoint `weak-rows-halved`, jobs
0764 and 0765; `measurement/recurring-debuff-leaf@elites`;
`docs/research/recurring-debuff-leaf.md#Result (read 2026-11-10): fail`).
With `@pd1`, the 10-29 net one turn deep cuts the HP cost of the two
recurring-Weak rows by 0.12 and 0.14 at k 2, and by 0.19 and 0.23 at k 4
(se about 0.05). Half was the bar. The win-rate cut reaches 0.71 and 0.50
at k 4, but on a cost of about 1 point of win rate its error is wide; the
HP measure decides. Parents moved less than 0.1 HP. At k 4 the Frail rows
got 0.3 HP worse. By encounter, the projection works on Gremlin Nob
(TurnEnd-Weak cut 55%), partly on Lagavulin (about 30%), and hurts on
Three Sentries, where k applications per living sentry over-count a debuff
whose stacks add duration. CPU: 1.2 of the 3 cpu-h cap.

**Reopen if:** a projection that counts a duration debuff once per turn
(the player Weak or Frail for the next k turns, however many monsters
apply it), instead of k applications per monster, is built and cuts the
Nob row on one-monster fights. Or the net's inputs show a debuff's
duration together with its re-application source, so a projection is not
needed. Check first on the bench's one-monster elites (Gremlin Nob,
Lagavulin) against `results/mutate/gen-wf-tsl1.json`.

On-close `wake on go`: a fail, so no navigator wake. The exploration slot
goes to the backlog's next ready charter, `fickle-enemy` (33), as the
backlog's ranking says ("a fail of `recurring-debuff-leaf` opens it
without a navigator round").

## Lane fickle-enemy opened (on the owner's behalf, 2026-11-10)

Opened in `recurring-debuff-leaf`'s exploration slot at that lane's close
on a fail, from the navigator's ranking (`docs/backlog.md`, "Ready
charters, in order": "The next exploration slot takes `fickle-enemy` (33,
the owner's idea; ready charter in its entry)"). The charter is the ready
charter of entry 33, copied as written into `lane/fickle-enemy`: kind
exploration, cap 2.5 cpu-h, end 2026-11-13, on-close wake on go. Rated
**even** by the navigator that an opening costs the net beyond the stat
control. Share in `jobs/lanes.json`: the closed lane's 25.

## Fickle enemy built as three paired openings (on the owner's behalf, 2026-11-10)

Lane `fickle-enemy`, step 1 (spec `docs/specs/fickle-enemy.md`). The
charter's first form picks the cycle's opening per fight from the start
seed. The bench instead plays every elite start with each of the three
openings as its own modifier (`FE-Attack`, `FE-Power`, `FE-Skill`), paired
by start and seed. Why: the measure is per opening, and three paired
modifiers read each opening on all 675 starts, where a seeded pick would
give each a third of them; the seeded form is the average of the three
rows. Cost: four variants (parent included) of 675 x 16 seeds, about 1.5
cpu-h, inside the 2.5 cap. Alternatives: the seeded pick (one variant,
a third of the cost, no per-opening read at useful n); both (more CPU,
no new question).

Engine changes the cycle needed (reversible, golden identical): a `Heal`
atom; a pack power's hook may apply another pack power (forward names in
one pack allowed; binding a pack power binds what its hooks apply); a
pack power applied during one pass of an owner's hooks first fires on the
next pass, so the cycle moves one step per monster turn start. Amounts:
one power per HP amount n (n = 5% of max HP, rounded up, n 1-20), because
a power's stacks scale every amount of its hooks. Known effect, not
corrected: an Attack or Skill opening's HP loss wakes Lagavulin at its
first turn start (any HP loss wakes it, as in the game); read per parent.

## Lane pack-net-scratch closed (2026-11-10)

Outcome: **go.** Three from-scratch all-content nets with the 31 Act 1
pack cards (seeds 1, 101, 201), one turn deep @hpb0.01 on sequences 0-499
at fixed n 500, beat the 10-29 net on the pack-offers headline by +3.33
end HP pooled (se 0.83, z 3.99; clears +0.065; every seed alone z 2.7-3.8)
and keep official-cell play (+1.58 HP pooled, seeds +0.86 to +2.26)
(`measurement/pack-net-scratch@three-seeds`,
`docs/research/pack-net-scratch.md#Three-seed read 0767-0769: checkpoint
three-seed-read passed (go)`). The opening entry rated it even that seed 1
would beat the 10-29 net by 2 se, at about 40-60 thread-h; it used 51.9
of its 60 cpu-h. Not settled here: whether the gain survives two turns
deep in the product (the navigator's `pns-two-turn` probes 0777-0778,
gated on 0769 and now released), and the pack net's worse zero-shot play
on generated content (`measurement/pack-net-gen-bench@seed1`; 0779-0780
attribute it). On-close `wake always`: the navigator decides the slot.

**Reopen if:** content lands that these nets never trained on (the
owner's Act 1 work adding relics, potions or a new batch of cards or
monsters to the pack, `docs/research/act1-inventory.md`), so a fresh
three-seed learn has something new to learn; or the two-turn product read
(0778) passes and the product's successor needs more seeds or a second
round of self-play from the two-turn teacher.

Shares: pack-net-scratch's 45 went to fickle-enemy (now 70), since act1-content is parked with the owner and queues nothing; the navigator re-sets shares when it fills the slot.

## Probe pns-twin read: the all-content recipe carries the pack net's gain; twin official reads queued (on the owner's behalf, 2026-11-10)

Jobs 0770-0773 (`docs/research/pns-probes.md#pns-twin (0770-0773): the
all-content recipe carries the pack net's gain; the pack costs official
cells`, `measurement/pack-net-twin@one-turn`). On the pack headline the
pack net beats its no-pack twin by only +0.38 (0.73) HP pooled over seeds 1
and 101, and the twin carries 87% of the gain (+2.59 of +2.97). On the
official cells the pack costs -1.09 (0.39) HP (z -2.8): dilution. By the
rule written before the read, this is the "recipe" branch: the
all-content recipe (from scratch, 40k games, one round, every card) is the
goal-2 fighter question, and a twin read on the ruler comes next.

Queued: **pns-twin-official**, jobs 0782-0783 in lane `main` (pin 2af5b30):
twin seeds 1 and 101 one turn deep on `yardstick/headline-setting` against
`yardstick/one-turn-controls`, about 4.5 thread-h. Go: pooled +1.5 HP at 2
se, clears not z <= -2. The read sits beside pns-official 0774-0776
(the three pack nets, same sequences). A two-turn read on the official
headline follows only if the gain sits outside the bosses or reaches
about 3.9 HP (`cause/leaf-gain-third`).

Not changed: pns-two-turn 0777-0778 keeps pack net seed 1. It was named
before any seed was read. Swapping in twin seed 1, the best player on
the pack, would pick a winner after seeing the results. It reads the same
question for the family: whether a gain from training on more content
survives depth. 47 keeps its base (pack net seed 1). Alternatives: drop the
official twin read and let 0774-0776 stand for the family (cheaper, but
the twin is the better official fighter by +1.09 HP, so it is the
candidate a product swap would use); a two-turn read of the twin now
(about 12 thread-h, before the one-turn ruler says it gains).

## Lane generated-pack-scratch opened (on the owner's behalf, 2026-11-10)

Opened in pack-net-scratch's project slot at that lane's close (on-close
`wake always`), from the backlog's "Ready charters, in order": "the next
project slot ... takes `generated-pack-scratch` (47) whatever the
three-seed read says". Charter: entry 47's ready charter, with one line
added from today's pns-twin read: the pack costs official cells -1.09
(0.39) HP against its twin, so the generated pack takes a bounded share
of the monster fights (proposed: at most half of the hallway and elite
fights carry a generated mechanic). Kind project, cap 80 cpu-h, end
2026-11-13, on-close `wake always`. Rated **even** that the held-out
rows' pooled cost falls by 0.4 or more at 2 se. For: transfer across
triggers inside a family is measured (`measurement/family-transfer@gen-b1`),
and effect inputs carry new cards zero-shot (pns-twin). Against: on cards
a trigger and an effect learned apart did not compose, and the pack net
plays the generated bench worse than the 10-29 net
(`measurement/pack-net-gen-bench@seed1`). About 18 thread-h for seed 1,
54 for three. Its step 1 is code, so 0779 (the twin on the generated
bench, moved to the front of the queue) lands before the learn and can
re-set step 2's recipe.

Passed over: `player-growth-exposure` (32, even; Demon Form's later
ticks, about 10-15 cpu-h, but its kill-fast step 1 is a count with no
lane); `fight-leaf-tsl1` (36; goal 2 at an expected +0.8 HP, under the
protocol's reach); `aivat-reads` (40, a long shot, read tooling);
`value-chooser-path` (45) and the other choosers (run-level work before
Act 1's content, the direction's Avoid); the all-content net as a
product lane (its one-turn ruler read runs as probes 0782-0783 first);
reopening `act1-content` (parked with the owner, `decision/act1-owner-led`).
Shares (`jobs/lanes.json`): generated-pack-scratch 45, fickle-enemy 25
(its 2.5 cpu-h cap needs no more), act1-content 20 (parked; it queues
nothing), main 10.

## Lane fickle-enemy closed (2026-11-10)

Outcome: **fail** at its one read (job 0781; checkpoint `fickle-table`
failed, `measurement/fickle-enemy@table`). Over all elite fights the
fickle enemy (cycle Attack -> Power -> Skill, Strength on a played card
of the named type, 5% max HP lost or healed) costs the net beyond the
heuristic and the ladder control +0.32 (0.20) on the Attack opening,
+0.16 (0.15) on Power, +0.70 (0.17) on Skill: none reaches the 1.0 HP go
bar. Per parent, Attack x Lagavulin +1.75 (the turn-1 HP loss wakes it)
and Skill x Sentries +1.57 are the only rows over 1 HP. The enemy is
mild: about one to two Strength on the ladder. Read in
`docs/research/generated-enemies.md`, "Fickle enemy read".

CPU: 3.8 cpu-h against the 2.5 cap (the build decision estimated 1.5;
0781 ran 76 minutes against its 45-minute estimate). The cap was passed
inside the one queued job, so the read finished.

**Reopen if:** the fickle enemy punishes with an effect the net already
pays for (Weak or Damage on the punished card type: table24's card-played
Weak and Damage rows cost +1.8 to +7.2 on some parents), or hooks may run
chance and the random form can be read beside this one at the same
effect (then the read prices unpredictability alone, and the bar is the
seeded form's +0.39 plus 1.0 HP).

Next slot (on-close `wake on go`; a fail opens the next ready charter):
`player-growth-exposure` (backlog 32), the navigator's "next exploration
slot" charter.

## Lane player-growth-exposure opened (2026-11-10)

Opened in `fickle-enemy`'s exploration slot at that lane's close on a
fail, from the navigator's ranking (`docs/backlog.md`, "Ready charters,
in order": "the next exploration slot (fickle-enemy's close on a fail,
any day to 2026-11-13) takes `player-growth-exposure` (32, the owner's
idea; ready charter in its entry)"). The charter is entry 32's ready
charter, copied as written into `lane/player-growth-exposure`: kind
exploration, cap 22 cpu-h, end 2026-11-13, on-close wake on go. Rated
**even** by the navigator. Share in `jobs/lanes.json`: the closed lane's
25.

## player-growth-exposure step 1: the heuristic arm read @tsl1 decides (on the owner's behalf, 2026-11-10)

Step 1's count (`docs/research/player-growth-exposure.md`, "Step 1"): the
player held Demon Form in 8.2% of net-g1600's Demon Form-deck training rows,
32.5% of two-g400's and 51.9% of heur-g400's. The stop rule ("a third or more
of the positions on Demon Form decks") assumes the arm with that exposure was
shown to learn the first tick only; that holds for two-g400, which sits at the
bar (32.5%, under one se from it), and heur-g400, far over it, was never read
@tsl1. Chosen: read heur-g400's three nets @hpb0.01@tsl1 on both cell books
(six jobs, about 0.5 cpu-h) and decide step 1 on its Demon Form stratum
(+2 se above the 10-29 net @tsl1 passes; less fails). Alternatives: fail now
on two-g400 at the bar (cheapest, but a call at exactly the bar, against the
reading rules); go to step 2 on net-g1600's 8% (ignores that two-g400's 48%
on bosses taught nothing past the first tick). The read is the reversible
choice: it costs half a cpu-hour of the 22 and either branch stays open
until it lands.

## Probe pns-twin-official read: the all-content gain on the ruler is Demon Form; twin-tsl1 and pns-twin-matched queued (on the owner's behalf, 2026-11-10)

Jobs 0782-0783 (`docs/research/pns-probes.md#pns-twin-official (0782-0783):
the all-content gain on the ruler is Demon Form; outside it the twin loses
1.5 HP`, `measurement/pack-net-twin@one-turn`, its ruler part). The all-content twins one
turn deep on the ruler, own picks, pool to +0.76 (0.87) HP, clears +0.028,
against the +1.5 HP at 2 se bar: fail. Candidate 48
(`all-content-product`) retires by its kill-fast rule. The split says
why: the gain is Demon Form (both players took it: +19.2 and +15.6 HP;
the twins pick it 0.62-0.69 against 0.19), and on the 347 sequences where
no player took it the twins lose -1.50 (1.00) HP with second-elite deaths
21 to 30. Two turns deep the product already plays Demon Form's first
tick, so a swap is predicted level or worse.

Corrected: `cause/chooser-horizon` is narrowed to the leaf repair (re-set
from this entry). Where only the twins took Demon Form they gain (+3.23 and
+0.41 HP, clears +0.118 and +0.086), where `@tsl1`'s extra picks lost
-0.115 clears; a net that learned the card from games carries its extra
picks under the same chooser. The parked `elite-horizon-chooser` loses the
evidence it rested on and folds into `value-chooser-path` (45), whose
path part already holds every elite ahead.

Queued in lane `main` (the navigator reads both):
- **pns-twin-matched**, 0791-0792 (pin 2af5b30): the twins on the
  control's own picks (`--match`). It splits the -1.50 HP outside Demon
  Form into fighting and picks. Go (pooled +1.5 HP at 2 se, clears not
  z <= -2) makes the recipe a fighter gain on the ruler's decks; the
  outcome changes no product decision (48 is retired either way); it
  says whether the one-round from-scratch recipe's own-pick reads carry a
  chooser cost, which `generated-pack-scratch`'s pack-headline reads use.
  The two jobs' notes name an earlier draft of this heading and read the
  shortfall as the chooser's horizon; their read rule stands, the reading
  is this entry's. About 0.6 thread-h.
- **twin-tsl1**, 0793-0796 (pin 4056504, the pin of
  `player-growth-exposure`'s 0784-0789): the twins @hpb0.01@tsl1 on both
  cell books against the 10-29 net @tsl1, with the lane's tools and rule.
  Go: Demon Form decks +2 se above zero with train decks within -0.9 HP
  and the other held-out stratum under it by 2 se, so 40k from-scratch
  games with Demon Form in the pool taught more than its first tick. That
  answers open question 16 in part and tells the lane its mechanism works
  by dose. Fail: the ruler's Demon Form gain is the first tick. About 1.2
  thread-h.

Held on twin-tsl1: **pns-two-turn**, 0777-0778 (now `--after`
0793-0796; about 12.7 thread-h). Its ratio asks whether a content gain
survives depth, and today's split says the content gain behind the pack
and all-content nets is Demon Form. On a twin-tsl1 fail it is the first
tick, which two-turn search already plays, so the ratio is predicted at a
leaf's or below and the navigator cancels 0777-0778. On a go the nets
learned more than depth finds, and the navigator releases them as queued.

Alternatives passed over: read 48 two turns deep anyway (13 thread-h
against a predicted level read); run 0777-0778 as queued (12.7 thread-h
whose answer the cheap probe may settle); a crossed arm (the twin fighting,
the 10-29 net picking; about 1 thread-h): `--match` answers the same
fighting question at a tenth of the cost with 2.4-4.2x lower variance
(`measurement/deck-matched@one-turn`), and the owner names both for reads
of nets trained on new content (decisions "Headline card pool and
choosers after Act 1").

## player-growth-exposure on-close: wake always (on the owner's behalf, 2026-11-10)

`lane/player-growth-exposure`'s on-close goes from `wake on go` to `wake
always`. Its step 1 (heur-g400 @tsl1, 0784-0789) and the navigator's
twin-tsl1 probe (0793-0796, decisions "Probe pns-twin-official read")
read the same question, whether games teach Demon Form more than its
first tick, on the same books against the same control. The two can
disagree: heur-g400 level and the twins above it would say the variable is
the dose of a from-scratch learn, not the exposure share the lane tests,
and the next exploration slot would then go to candidate 49's dose read
rather than to `race-price`. A fail with no wake would open `race-price`
before that is weighed. Charter otherwise unchanged. Alternatives: keep
`wake on go` (cheaper by one navigator round, and it risks opening the
slot on the wrong candidate); hold the lane's close on twin-tsl1 (not the
navigator's to do: the lane's step and its close are the lane worker's).

## Probe twin-tsl1 read: from-scratch games taught Demon Form past its first tick; 0777-0778 released; 49 gets the next exploration charter (on the owner's behalf, 2026-11-10)

Jobs 0793-0796 (`docs/research/pns-probes.md#twin-tsl1 (0793-0796):
from-scratch games taught Demon Form more than its first tick`). The two
all-content twins @hpb0.01@tsl1 against the 10-29 net @tsl1 on both cell
books: Demon Form decks +3.30 (0.95) HP (se over nets 0.35), train +0.56
(0.43), other held-out -0.04 (0.60). Go by the rule in decisions "Probe
pns-twin-official read". It is the first learned value past a power's
first tick on file: bursts of up to 1.6k games learned the first tick
only, and heur-g400 @tsl1 (52% exposure, `player-growth-exposure` step 1)
reads -1.20 on the same stratum with two of three nets in.

Decided:
- **0777-0778 released** (`--after` cleared), as that entry set: the
  content gain goes past the first tick, so whether depth keeps it is open.
- **Candidate 49 (`from-scratch-later-ticks`) goes to even** and takes the
  first ready charter for the next exploration slot, ahead of `race-price`
  (9). It asks what made the difference: the game count (40k against at
  most 1.6k), the start (from scratch against a trained net) or both. That
  is goal 1's number for powers that pay over later turns. Charter in its
  backlog entry: two 10k-game arms, from scratch and the Demon Form burst
  recipe at 10k, about 10 cpu-h, cap 15.
- **`cause/unseen-cards-half-edge`** gains the result (re-set from this
  entry): what games taught on Demon Form was the first tick for bursts,
  and more for a from-scratch learn.

Alternatives passed over: open 49 now as a fourth lane (the portfolio
rule allows a fourth only near a lane's end; `player-growth-exposure` is
reading its step 1 and its close wakes the navigator); fold 49 into
`player-growth-exposure` (that lane tests exposure share by a player
start-power patch, whose premise these numbers weaken; its step and
close are the lane worker's); a 20k from-scratch arm instead of 10k (half
the steps to 40k; 10k shows more if it passes, and a fail still bounds
the dose); keep 0777-0778 held until 49 reads (it asks a goal-2 question
49 does not answer).

## pns-gen-attribution read: the recipe loses the generated bench; 47's step 2 keeps it and gains a round-2 branch (on the owner's behalf, 2026-11-10)

Job 0779 (`docs/research/pns-probes.md#pns-gen-attribution, twin (0779):
the recipe, not the pack, loses the generated bench`): the no-pack
all-content twin loses the generated bench's OppCard-Vulnerable edge
(-0.267 wins) and its OppCard damage rows as pack net seed 1 does, so the
one-round 40k recipe is weaker than the ten-round 10-29 net on mechanics
neither trained on. `generated-pack-scratch`'s charter asked the navigator
to re-set step 2's recipe on this outcome before its learn is queued; the
lane has no step yet and no learn queued.

Decided: step 2 keeps the recipe (pack-net-scratch's config plus the
generated pack). The cut bar compares with pack net seed 1, the same
recipe, so it reads the generated pack alone, which is 47's question. Added
**step 2b**: if seed 1 passes the cut bar and fails the 10-29 bar, a
second self-play round of that net (the 10-29 recipe's form, about 12
thread-h) is read the same way before any other seed. It asks whether the
deficit is rounds. The cap (80 cpu-h) holds it. Seed 101 of the pack net
(0780) still reads whether seed 1 is typical.

Alternatives passed over: the 10-29 recipe throughout (ten rounds, about
120 thread-h a seed: over the cap, and it changes two things at once);
fine-tune the 10-29 net on the generated pack (a burst, the pack pipeline's
known route, not 47's zero-shot-from-breadth question); drop the 10-29 bar
(47's go would then allow a net worse than the product's on held-out
mechanics, which no goal-1 base can be).

## Card upgrades as built (C6, owner-led session, 2026-11-10)

Spec `docs/specs/card-upgrades.md` (confirmed by the owner, 2026-11-08),
built in the owner's Act 1 session. The spec's provisional decisions stand
as written; where the build departs from it:
- `max_level: null` means "as far as the card's numbers stay in the
  engine's range": Searing Blow's damage (12 + n(n+7)/2) passes i16 at
  level 253, so it stops at 252. An explicit `max_level` past the range is
  a load error. Alternative: widen damage numbers (state and every column).
- `AddCard`'s `match_level` covers official cards only (`AddCard` can't
  name a pack card), so the spec's level-2 test case doesn't exist.
- FTL keeps its `X+` entry (its upgrade changes a row condition's number;
  paths don't name conditions). Alternative: a `rows.<r>.condition` path.
- A pack card held only at level 1 or above builds its slot's level-0 id
  as level 1 (that id never appears: upgrades only go up), so a counter
  capped by the bound cards' costs (Blood for Blood+'s HP losses) keeps its
  cap.
- An `X+` entry loaded by a later pack than `X` links at bind time.
- The gauntlet's rest site keeps the old upgradable rule for official
  cards (a `+` in `sts.deck_card_names()`), so official rest choices are
  identical; pack cards use `sts.upgrade_name`. Held-out `check9` cards
  are never upgraded at the rest site, as before C6; whether they should
  be is open (it would change headline reads).
- Armaments' pick with one distinct candidate resolves at once in the
  engine (sts_lightspeed's `ArmamentsAction`); Armaments+ skips statuses
  (wiki), where sts_lightspeed would upgrade a Burn.
- An upgrade block's changes are stored in path order (packs pass through
  key-sorted JSON).

## Rest-site upgrades of held-out cards wait for the headline change after Act 1 (owner, 2026-11-10)

Found while building C6: the gauntlet's rest site (`upgradable()`, from
the rest-site spec of 2026-11-02) upgrades only cards whose `+` is in
`sts.deck_card_names()`, the training set, so held-out `check9` cards
(Go for the Eyes, FTL, Metallicize, Demon Form, Rage, ...) and proving
cards are never upgraded at a rest; nothing in the spec meant it. Owner:
the fix goes in with the rest of the planned headline change after Act 1
content is mostly finished (decision "Headline card pool and choosers
after Act 1"), with the controls built once then, not before. Until then
the rule stays as it is, so headline reads stay comparable.

## Lane player-growth-exposure closed (2026-11-10)

Outcome: **fail** at step 1 (checkpoint `step1-exposure` failed; read in
`docs/research/player-growth-exposure.md`, "Step 1 read: heur-g400 @tsl1
fails"). The heuristic's 400 Demon Form games held the power in 52% of
their Demon Form-deck rows (63% on bosses), and its three nets @tsl1 play
those decks -0.73 (0.87 / 1.06) HP against the 10-29 net @tsl1 (train
-1.12, past the -0.9 guard): the +4.98 they show on the plain leaf is the
first tick the turn-start leaf already prices. With two-g400 at 32.5% the
same, exposure inside a burst does not teach later ticks, so the start-power
patch (step 2) and its bursts (step 3) are not built. CPU: about 1.2 of
22 cpu-h (six one-turn cell reads; step 1's count was free).

**Reopen if:** a burst recipe is shown to teach any growth power's later
ticks @tsl1 (for example the from-scratch count or start that backlog 49
tests: if 49 finds the 40k from-scratch gain comes from early-training
exposure, forcing the power into the first rounds of a from-scratch learn
is this lane's mechanism at a different stage), or a leaf that prices later
ticks lands and bursts still undervalue growth.

## Lane from-scratch-later-ticks opened (on the owner's behalf, 2026-11-10)

Opened by the navigator in the exploration slot `player-growth-exposure`
freed (its close: exposure inside a burst does not teach later ticks,
`measurement/portfolio-player-growth-exposure`). Backlog 49, the ready
charter named next, with one change found this run: the all-content
twins' +3.30 (0.95) HP @tsl1 on Demon Form decks
(`measurement/pack-net-twin@one-turn`) was read against the 10-29 net,
which differs from them in two ways, Demon Form in the training pool
(`deck_pool: all`) and a second self-play round. The data-curve nets
`data40k` s1 and s101 round 1 are the exact twins of `allcontent40k` s1
and s101 without the pool change (configs differ only in `deck_pool` and
`bosses`), so reading them @tsl1 on both cell books separates the two in
about 1.2 thread-h and comes first: if they gain on Demon Form decks too,
the gain is the recipe, not games with the power, and the dose-or-start
question is moot. The data-curve twins at 5k and 20k (`data5k-s1`,
`data20k-s1` round 1) make step 2 a dose curve with a twin at each point,
replacing the charter's single unpaired 10k arm, whose general weakness
(a 5k-20k net reads -3.30 to -1.45 HP on cells, `decision/no-goal2-training-arms`)
would have failed the train guard on its own. The burst arm (the start
question) moves to step 3, at the smallest from-scratch dose that passed.
Training rule: each learn has new content to learn (Demon Form and the
held-out half in the pool), and a games curve is goal 1's number
(operating.md, "Training").

Charter (`lane/from-scratch-later-ticks`): see the kb fact. Rating
**even** (for: the twins' go is 3.5 se on two seeds that agree; against:
1.6k-game bursts learned nothing past the first tick, and step 1 may
show the recipe, not the games). About 15 cpu-h (step 1 1.2, step 2
about 10 with two learns, step 3 about 4); cap 23, end 2026-11-13,
on-close wake always.

Alternatives passed over: `race-price` (9, a long shot, 2 h of code; stays the next exploration charter); 49 as written (a
single 10k arm per mechanism, unpaired against a twin and confounded
with the second round); leaving the slot empty until the
generated-pack-scratch learn (no: the CPU is idle, `cpu` red 87 runs).
Shares: generated-pack-scratch 55, from-scratch-later-ticks 25,
act1-content 10 (parked with the owner, whose session may queue),
main 10, filler 0.

## Probe pns-official read: the pack nets' ruler gain is Demon Form; no two-turn official read (on the owner's behalf, 2026-11-10)

Jobs 0774-0776 (`docs/research/pns-probes.md#pns-official (0774-0776): the
pack nets' ruler gain is Demon Form; outside it they lose 2.1 HP`): the
three pack nets one turn deep on the ruler pool to +0.78 (0.89) HP, clears
+0.011, against the +1.5 HP at 2 se written before the read: fail. The
gain is Demon Form (+17.7 to +20.2 HP where both players took it); on the
345 sequences where no player took it they lose -2.14 (0.97) HP, deaths
moving from the boss to the second elite, as the twins did (-1.50). With
pns-twin-matched (twins level on the control's decks outside Demon Form)
that loss is the one-round net's picks through the sim chooser.

Decided: no two-turn official read of the pack recipe (its condition, a
gain outside the bosses or about 3.9 HP, does not hold); the product stays
the 10-29 net (`decision/crossed-player-lead`). Kept: pns-two-turn
0777-0778 (the pack headline two turns deep, a different question: whether
a content gain survives depth) and 0780 (pack net seed 101 on the
generated bench, 47's base). No job is made worthless; none reordered.
`all-content-r2` stays checked and not proposed: the picks loss is real,
but the owner's plan retrains on the widened pool after Act 1
(`decision/headline-pool-after-act1`). Alternatives passed over: a
two-turn official read anyway (about 12 thread-h for a gain two turns
deep already plays); a second-round arm now (trains for a pool that will
change).

## After the big-picture review of 2026-11-10: read floors for charters; counterfactual pricing, product-depth worlds and wider generators ranked; 0780 cancelled; generated-pack-scratch's reroute written in advance (on the owner's behalf, 2026-11-10)

From `docs/research/big-picture-2026-11-10.md` (its "Navigator's reading";
all twelve skeptic verdicts "overstated").

- **Read floors.** Filed as `yardstick/read-floors` from the skeptics'
  recomputes: the headline one turn deep between nets on own picks has a
  paired end-HP sd of 20-24 HP (floor about 2.5 HP or 0.07 clears at n
  500), deck-matched 10.6-15 (about 1.0-1.3 HP), the cells about 1.0 HP;
  training-seed sd 0.65-0.7 HP; a cell gain reaches the headline at about
  0.5x and a one-turn gain the two-turn product at 0.2-0.46x. The
  navigator's charters and probes state their predicted effect on their
  ruler beside that floor, seeds counted, and do not open below it. The
  synthesis's "a cell gain needs about 11 HP to show" is refuted (the ruler
  is one turn deep; matched reads see about 2.6 HP). Alternatives passed
  over: a hard gate in `jobs.py add` (code, not the navigator's; candidate
  54); no rule (the record's 36% of CPU inside noise argues against).
- **0780 cancelled** (pack net seed 101 on 0762's eight rows, lane main,
  not started). The pns-official entry kept it as 47's base, but 47's step
  4 reads seeds 101 and 201 on the 24-row format of 0797 (675 starts x 8
  seeds), not 0762's (1,000 x 16), and its "is seed 1 typical" question
  changes no bar: 47 reads against pack-net-scratch seed 1 itself, and
  0779 already put the loss on the recipe. Under the review's stop list:
  no follow-up reads of a failed net unless a stop rule names them. About
  2.8 thread-h and a heavy slot freed. Alternatives passed over: keep it
  (a fourth read of nets that failed the ruler); make it wait on 47's read
  (its format still would not serve step 4).
- **Kept:** 0778 (running; pns-two-turn's second half), from-scratch-later-ticks
  as chartered, step 3 included (conditional on step 2, inside its 23
  cpu-h cap; the counterfactual price that would moot it is unbuilt and a
  long shot).
- **generated-pack-scratch's reroute, written before seed 1 reads**
  (0809-0811, running): on a **go** (held-out pooled cut 0.4+ at 2 se and
  not worse than the 10-29 net), training on a space of mechanics becomes
  goal 1's base recipe for custom enemy mechanics: step 4 (seeds 101 and
  201, the same 24-row reads, pooled) runs, and wider generators (53) get
  the next project slot so the space can widen to attacks, skills and
  monsters; on step 2b (cut passes, 10-29 bar fails), the round-2 read runs
  before any seed; on a **fail** (cut under 0.2 or not 2 se), goal 1's
  zero-shot route for enemy mechanics is the simulator plus leaf pricing
  plus a burst of 33-100 games per mechanic: no lane asks a net trained
  from scratch on more content for zero-shot transfer to new enemy
  mechanics until a new input or teacher exists, and the freed project
  slot opens `random-world-product` (52), goal 1's standing number at
  product depth; between 0.2 and 0.4, the lane's own rule (one read, no
  go) holds and the slot goes as on a fail.
- **Ranked** (backlog): counterfactual-state-price (51, long shot, goal 1;
  `race-price` 9 folded in as its Ritual 2 target) takes the next
  exploration ready charter; random-world-product (52, likely to read,
  goal 1) the next project charter; wider-generators (53, even, goal 1);
  read-preflight (54, tooling); chooser-noise (55, a ruler check, goal 2);
  aivat-reads (40) and reserve-from-peak (43) move up with the review's
  evidence (mutate_monsters took 30% of CPU since 11-03; memory waits come
  from cache-inflated reservations).


## Parity source: the game's own code (owner, 2026-11-10)

Supersedes "No StS1 install; content parity from the wiki and
sts_lightspeed" (2026-11-04). The real game is the final testing ground
and nets must learn in its environment, so the game itself decides both
content values and behaviour: its code, read from decompiled copies of
the game's Java on GitHub (`com/megacrit/cardcrawl/...`; for example
`Li-Binghui/MySlayTheSpire` and `aeubanks/sts`, which agree where both were
read). A claim cites the file and line it comes from, and where copies
could differ, two copies are compared. sts_lightspeed and the wiki are
leads (where to look, what a number probably is), never the deciding
source: where either disagrees with the game's code, the code wins and the
difference is noted. The game is still not installed and level 2 of the
arena ladder (the real game through a mod bridge) stays dropped; only the
source of truth changes. Why now: the turn-start timing (before or after
the draw, and turn 1's different order) was settled by the game's code
where sts_lightspeed has its own turn-1 handling and the wiki says
nothing (`docs/specs/turn-start-draw.md` on lane/act1-content). Content
already written from the wiki or sts_lightspeed stays until a check
against the code finds a difference.

## Probe pns-two-turn read: the pack net's gain grows two turns deep; seeds 101 and 201 queued (on the owner's behalf, 2026-11-10)

Jobs 0777-0778 (`docs/research/pns-probes.md#pns-two-turn (0777-0778):
the pack net's gain grows two turns deep`): pack net seed 1 two turns
deep on the 31-card pack, sequences 0-249, against the product there:
+4.67 (1.40) HP, clears +0.080 (0.033); one turn deep on the same
sequences +2.80 (1.37); ratio 1.67 (0.86). By the probe's rule (decisions
"Probe pns-twin and pns-official queued") the branch is "content gains
survive depth". The gain sits at the bosses (boss-floor deaths 60 to 37)
and is not Demon Form alone (+3.10 (1.48) where neither player took it).

Decided:
- **Replicate before re-setting the rule.** A single-seed pass is a lead
  (operating.md, "Reading results"). Seeds 101 and 201 two turns deep on
  the same pack, snapshot and sequences, against 0777's file: jobs 0819,
  0820 (lane `main`, about 9.3 thread-h on threads the queue leaves idle:
  health `cpu` 0.42). Read pooled with seed 1: go if the pooled ratio is
  0.6 or more with the pooled two-turn gain 2 se above zero (se the larger
  over sequences and seeds); fail if seeds 101 and 201 pool to 0.46 or
  less. Go: `cause/leaf-gain-third` is re-set to cover gains on content
  whose payoff is past both horizons as carrying whole, and goal-1
  content reads stop applying the one-third discount to such content.
  Fail: seed 1 was luck and the rule stands.
- **`cause/leaf-gain-third` now carries this read as a lead** (its exit
  named, one seed), and the corollary "a one-turn gain at the bosses
  predicts no clears two turns deep" is limited to in-fight threats the
  second turn sees, its source.
- **`decision/headline-quote`** gains the 31-card pack level: the product
  0.636 clears on 0-249 against 0.836 curated (-8.56 (1.50) HP).
- **No two-turn read on the curated ruler.** One turn deep there the pack
  nets pool to +0.78 (0.89) HP and lose 2.1 HP outside Demon Form by
  their picks; at 1.67x that is about 1.3 HP two turns deep, under that
  read's floor (`yardstick/read-floors`).
- **No lane or charter change.** The result supports the owner's plan
  (retrain on the widened pool after Act 1, `decision/headline-pool-after-act1`)
  rather than asking for new work before it.

Alternatives passed over: re-set the rule on one seed (the record has two
seed-luck passes); 500 sequences per seed (twice the CPU; the go and fail
cases differ by about 3 se pooled at 250 per seed); a matched read
splitting picks from fighting two turns deep (about 4.5 thread-h; it
would refine the fighter question, which waits for the widened pool).

## Generated-pack seed 1 go: genpack-reach probes queued, wider-generators re-scoped and readied (on the owner's behalf, 2026-11-10)

Woken by `lane/generated-pack-scratch`'s checkpoint `passed seed1-read`
(`measurement/genpack-transfer@seed1`): held-out pooled cut 0.81 (0.02)
against a 0.4 bar, 10-29 bar held, cells +0.40 (0.52), pack headline
+0.17 (1.13). The lane goes on to step 4 (seeds 101 and 201) by its
charter; nothing in it changes.

- **What the read says beyond its own question.** Split by parent from the
  two existing files (`docs/research/genpack-host-split-2026-11-10.md`):
  on Lagavulin, which the generated pack never carried a mechanic on, the
  held-out cost goes from +1.40 to -0.04 HP (gain 5.8 se) and the
  training mechanics' from +2.02 to -1.26 (12.6 se). On seed 1 the net
  learned a value per mechanic that moves to a new host. With
  `from-scratch-later-ticks`' 5k dose go (`measurement/later-ticks-dose@5k`),
  both goal-1 lanes now say that a pool holding a space of content
  teaches what bursts on a trained net did not.
- **Probes queued (lane `main`, pin 33fd633): genpack-reach**, the backlog's
  probe sheet. 0842-0843: random worlds k 4 (40 worlds, no-death),
  pack-net-scratch seed 1 and the generated-pack net seed 1 @tsl1, each
  with its own base file: whether the cut composes when k mechanics share
  one fight (the pack showed one per encounter). 0844-0845: the 24
  mechanics on the official bosses (325 fights x 4 seeds), a host kind
  the pack never carried. About 6 thread-h. Outcomes: a go on both makes
  the pooled net goal 1's base for enemy mechanics with bosses and stacks
  included, and 52's product-depth question becomes one for that net; a
  boss fail puts bosses into 53's pack before its learn; a stacks fail
  keeps the cut per mechanic and makes the random-world bench 53's guard.
  None of the queued lane jobs waits on them.
- **wider-generators (53) re-scoped and readied** as the next project
  charter, as the reroute in "After the big-picture review of 2026-11-10"
  set for a go: the widening goes first to the enemy-mechanic grid (4
  triggers x 7 effects today, 19 triggers and 48 effect scalars in the
  engine), with held-out pairs and one whole trigger and one whole effect
  held out, cap 40 cpu-h, end 2026-11-13. It opens on 47's pooled go; on a
  pooled fail, `random-world-product` (52) takes the slot as written.
  Alternatives passed over: 53 as first written (generators for attacks,
  skills and whole monsters first): in-turn content has read free (19 of
  22 Act 1 cards; no fickle opening cost 1 HP), so those generators wait
  behind a d=1 zero-shot check; opening the reach reads as a fourth lane:
  they need no code and fit the probe sheet; putting them into 47's
  charter: they answer a question beyond 47's stop rule, and the lane
  should close on its own.
- **New candidate 56, generated-card-space-scratch** (47 x 49, a long
  shot): the card analogue of 47, behind a no-training probe of what is
  left to gain (the residual @tsl1 cost of held-out generated recurring
  powers) and behind 49's step 3.
- **Shares unchanged** (55 / 25 / 10 / main 10): both active lanes passed
  their last checkpoints; the parked act1-content's share carries the
  owner's own jobs.

## Golden games record an ended fight by what outlasts it (owner, 2026-11-10)

The golden games (`engine/tests/golden.rs`) wrote the whole state after
every step, the step that ends a fight included. In the real game, what is
left after a fight-ending effect depends on how the developers split that
effect into actions: the action running finishes all its code, and of the
queued ones `GameActionManager.clearPostCombatActions` keeps only heals,
block gains, card-use bookkeeping and damage-type actions (aeubanks/sts
`actions/GameActionManager.java` 119, Li-Binghui/MySlayTheSpire 143). Poison
is one action (`PoisonLoseHpAction`: HP loss, then the stack drops), so a
monster it kills keeps its stack lowered; an effect split into two actions
would lose its second part. No rule over effects matches that, so stacks on
a corpse, block and piles after the end are noise to the golden check.

- An ended fight (`Stage::Over`) is recorded as `over(won) hp/max_hp`, what
  the run reads after a fight (`gauntlet.py` `run`). Mid-fight lines are
  unchanged. Anything the engine later carries past a fight (gold, deck
  changes, relic counters, potions) joins that line, its leftover checked
  against the game's code per effect.
- `golden.txt` and `golden_proving.txt` were re-recorded with the engine
  unchanged; the new hash `e9c10f64df68a215` maps to the rules version
  `7042d1d6a6149ba0` in `registry.SAME_RULES`, so runs, datasets, the
  solved DB and pinned jobs replay as before. Only a re-recording with no
  rule change goes in that map; a real rule change makes a new version.
- Lane workers: nothing to do. A branch that re-records golden does it
  after rebasing onto this change.
- Alternatives passed over: swapping Poison's effects to the written order
  (moved the rules version over a corpse's stack); finishing a hook's
  effects after the fight ends (matches Poison only because it is one
  action).

## Hook effects scale by the stacks they see (owner, 2026-11-10)

Replaces the first point of decisions.md line 304 ("A hook's effect amounts
use the stacks the power had when the hook fired"). Each effect in a hook
now scales by the power's stacks at that moment, so a hook's effects act in
their written order; once the power is gone (removed, or lowered to 0) its
remaining hooks do nothing that pass (`run_hooks_scaled`, hooks.rs `Hook`).

- Poison is written in the game's order, `LoseHp(1), ReduceSelf(1)`
  (`PoisonLoseHpAction`: HP loss, then the stack drops), and the explorer
  words it that way. The old order was kept only so a lethal tick left the
  corpse a stack lower in the golden games; since "Golden games record an
  ended fight by what outlasts it" that leftover isn't recorded, and the
  golden games pass unchanged (rules version 7042d1d6a6149ba0).
- Hooks that removed themselves before applying the next power (the fickle
  cycles in `engine/tests/fickle.rs` and `mutate_monsters.fickle_pack`) put
  `RemoveSelf` last; each applies a different power, so they act as before.
- The solved DB fingerprint changes (state.rs and content/powers.json are
  rule files): rows of the old fingerprint are kept, not current. The DB is
  0.8 GB of its 5 GB cap, so nothing is pruned.
- Alternatives passed over: keeping the early read and only rewording the
  explorer (the written order would still not be the order of meaning).

## Relics as content (R1), spec decisions (owner, 2026-11-10)

Provisional, from `docs/specs/relics.md` (interview 2026-11-10):
- Relics reach fights only through the fight constructors (`sts.Combat`,
  `Combat.versus`) and `sts.run`'s dict specs for now; the run layer
  (gauntlet) gets them with the headline change after Act 1's content is
  mostly done. Nothing in this spec changes a headline read.
- The combat-end heal is a general amount the fight holds (`win_heal`),
  set from the character's starter relic, raised by relics and by a
  `WinHeal` effect, and read by every heal reader (fight end, bounds,
  heuristic, net value input, Python columns): Meat on the Bone and Self
  Repair do it too, and the net must value it.
- A fight's kind for a relic's `fights` comes from the encounter's group;
  `Combat.versus` takes `group` (default hallway).
- Shared relics sit in their own pack, `content/packs/act1-relics.json`;
  Burning Blood is official, in `content/relics.json`.

## Turn start before and after the draw, spec decisions (owner, 2026-11-10)

Provisional, from `docs/specs/turn-start-draw.md` (interview 2026-11-10;
the game's order from its decompiled code, `decision/parity-source`):
- Two triggers with the game's names: `OwnerTurnStart` runs before the
  turn's draw (the game's `atStartOfTurn` / `atTurnStart`),
  `OwnerTurnStartPostDraw` after it (`atStartOfTurnPostDraw` /
  `atTurnStartPostDraw`).
- Turn 1 follows the game: the opening draw, then the post-draw hooks
  (where the start-of-combat relics sit), then the turn-start hooks. A
  fight built with `turn1_pre_draw` runs turn 1 like every other turn.
- Generated turn-start powers move to pre-draw: the generator keeps
  writing `OwnerTurnStart`, which now means before the draw.
- Old files keep their meaning by pack version: in a `"version": 1` file
  `OwnerTurnStart` reads as `OwnerTurnStartPostDraw`; files the repo
  writes from now on are version 2.
- One net input column for both triggers (owner: the split is mostly a
  logic matter for effects that need cards in hand, and a second column
  would mostly distract the net, as the exhaust pile's did).
- No front-of-queue field for hooks until one needs it: today's
  front-of-queue hooks (Brimstone, Lantern) only add Strength or energy,
  which land the same on either side of the draw.

## pns-two-turn-seeds read: past-horizon content gains carry whole; cause/leaf-gain-third re-set; twin-two-turn-matched queued (on the owner's behalf, 2026-11-10)

Jobs 0819-0820 (`docs/research/pns-probes.md#pns-two-turn-seeds (0819-0820): the gain carries whole two turns deep on three seeds`):
pack net seeds 101 and 201 two turns deep on the 31-card pack, sequences
0-249, against the product: +4.42 (1.42) and +4.62 (1.49) HP, clears
+0.096 and +0.116. Pooled with seed 1: two turns deep +4.57 (1.19) HP,
clears +0.097 (0.030); one turn deep on the same sequences +3.38 (1.21);
ratio 1.35 (0.50); seeds 101 and 201 alone 1.23 (0.46). Boss deaths 60 to
a mean of 41.7. By the probe's rule (decisions "Probe pns-two-turn read"):
go.

Decided:
- **`cause/leaf-gain-third` re-set: its content exit is a rule.** A gain
  on content whose payoff lands past both search horizons (powers paying
  over later turns, setup) reaches the two-turn product whole (about 1x;
  whether it grows past 1 is not shown, 0.7 se). The one-third discount
  stays for gains against threats the second turn sees (the SharpHide and
  stat bursts it came from). Planning: a leaf candidate earns a two-turn
  read when its one-turn gain is three times that read's detectable effect
  for in-horizon content and once that effect for past-horizon content.
  `yardstick/read-floors`' transfer line follows.
- **`measurement/pack-net-scratch@two-turn`** is re-set to the three seeds.
- **Goal 1:** one-turn reads of past-horizon content (later ticks, setup
  powers; `from-scratch-later-ticks`, 56) stand for product depth, so
  their gains count whole for goal 2 as well. Enemy-mechanic costs that
  punish an action this turn are in-horizon threats: there the discount
  applies, which is `random-world-product` (52)'s question.
- **Probe twin-two-turn-matched queued (job 0846, lane `main`, pin
  2af5b30, about 4.3 thread-h on idle threads: health `cpu` 0.41).** The
  all-content twin seed 1 two turns deep on the headline control's decks,
  sequences 0-249. Why it can gain on the current setting (the trade-off
  rule): on the control's decks one turn deep the twins gain +13-14 HP on
  the 41 Demon Form decks (past-horizon, now expected to carry whole: about
  +1.1 HP over 500) and, outside them, trade second-elite deaths (25 to
  32-33) for boss deaths (93 to 73-81) at level HP
  (`measurement/pack-net-twin@one-turn`). If the boss side carries and the
  second turn repairs the elite side (in-horizon), the fighter lowers boss
  deaths two turns deep, which is the condition `decision/crossed-player-lead`
  sets for a promotion read; best case about +2 HP and +0.03 clears.
  Fighting only, so a matched read (the owner's "Choosing a read by its
  question", 2026-11-05). Predicted +1.1 to +2.5 HP against a se of about
  0.66 at 250 (0204's 0.47 at 500). Go (+1.2 HP and 8 fewer boss deaths,
  clears not below -0.01): extend to 500 and queue seed 101; stop (under
  +0.6 HP or boss deaths within 4): the fighter waits for the widened
  pool. Rated even.
- **three-turn-content-leaf stays not proposed.** Its reopen's first half
  holds; the second (a boss read of about 300 fights in memory) is
  unmeasured since `sparse-state` cut the state 42%, and its other reason
  stands: a plausible third-turn gain of +0.03-0.05 boss wins is under
  even a 300-fight read's floor (about 0.06).
- **No lane, charter or share change.** The result is the strongest
  evidence yet for retraining the product's net with the all-content
  recipe on the widened pool after Act 1
  (`decision/headline-pool-after-act1`); nothing in it asks for work
  before the owner finishes Act 1.

Alternatives passed over: twin seeds 1 and 101 at 500 sequences each at
once (about 16 thread-h; the 250-sequence seed-1 pilot decides whether the
second seed is worth it); an own-pick two-turn read of the twins on the
ruler (floor about 2.5 HP against a predicted +1, and their picks cost
about 1.5 HP); keeping the rule as it stood (three seeds agree, the fail
line is 1.7 se below the low seed's ratio on seeds 101 and 201 pooled).

## genpack-reach (a) stacks read: the cut composes; the k-4 world bench joins wider-generators' reads (on the owner's behalf, 2026-11-11)

Jobs 0842-0843 (`docs/research/genpack-reach-2026-11-11.md#Stacks (0842-0843): the cut composes, about half of the cost at the death cap`):
random worlds of 4 generated enemy mechanics on official elites, the
generated-pack net seed 1 against pack-net-scratch seed 1, both @tsl1.
The net's cost beyond the heuristic with each game's HP loss capped at
its start HP (a death counts whole): +3.16 (0.18) against +6.16 (0.23),
paired by world -3.01 (0.18), ratio 0.51; with looser caps 0.17-0.22.

Decided:
- **Read as "composes".** The probe's rule (under half at 2 se) holds by
  far at the looser caps and sits on its line at the death cap; the cut
  is 17 se there, and a 4-mechanic world keeps about four fifths of the
  singles' cut (61% on singles, 49% on worlds). So the generated pack's
  zero-shot price holds when unseen mechanics share a fight, and the
  stacks half of genpack-reach's outcome is the go branch: once 47's
  seeds pool, the generated-pack net is goal 1's base for enemy mechanics
  with stacks included (bosses wait for 0844-0845).
- **The k-4 world bench joins `wider-generators` (53)'s step-3 reads**
  (both branches of the probe had it cheap: about 0.7 thread-h a net,
  paired se 0.18 HP at the death cap), read at the start-HP cap against
  the 47 net, descriptive. Its charter in `docs/backlog.md` gains the
  line; nothing else in it changes.
- **Measures:** reads of this bench quote the start-HP cap first (the
  play-like measure) and the looser caps beside it, never the uncapped
  no-death number alone.

Alternatives passed over: calling it a fail on the death cap's 0.51 (the
rule's line was set for a cut that composes or does not; a 17-se cut that
keeps four fifths of the singles' share is composition); more worlds or a
second seed now (47's pooled read gives the seeds, and 53 reads the bench
again on its own net).

## genpack-reach (b) bosses read: the cut reaches the official bosses; both reach probes went (on the owner's behalf, 2026-11-11)

Jobs 0844-0845 (`docs/research/genpack-reach-2026-11-11.md#Bosses (0844-0845): the cut reaches the official bosses, on a small base cost`):
the 24 generated mechanics on the 325 official boss fights x 4 seeds,
the generated-pack net seed 1 against pack-net-scratch seed 1 @tsl1.
Held-out pooled novelty cost +1.21 (0.26) to +0.23 (0.26) HP, cut 0.81
(0.19), wins +0.030 (0.009); training rows cut 0.86 (0.13); parents
level. By the probe's rule: go (0.43 at 2 se, base above 1 HP).

Decided:
- **Both genpack-reach probes went** (stacks: decisions "genpack-reach
  (a) stacks read"). On seed 1 the generated pack's price per mechanic
  moves to hosts it never carried (Lagavulin, the bosses) and holds when
  four mechanics share a fight. Once 47's seeds pool, its net is goal 1's
  base for enemy mechanics, bosses and stacks included.
- **Bosses do not join `wider-generators` (53)'s pack** before its learn;
  its step 2 keeps the boss reads off, as its charter set for this branch.
- **`random-world-product` (52)** keeps its charter for 47's pooled-fail
  branch. On 47's pooled go it waits behind 53, and when it opens it reads
  the pooled generated-pack net two turns deep beside the product, since
  that net is then goal 1's base (the reach probes' "go on both" outcome).
- **The boss gain is small in HP** (about 1 HP per boss fight, a quarter
  of the elites' base cost): the generated enemy mechanics are not where
  boss deaths come from, so this result does not move goal 2's boss work.

Alternatives passed over: a second seed of the boss read now (47's
step 4 brings seeds 101 and 201; their bench reads can add the boss
group for about 0.6 thread-h each, left to the lane's choice); reading
bosses two turns deep (base costs of 1.2 HP one turn deep predict about
0.4 HP at that depth, under any boss read's floor).

### genpack learns re-queued at an admissible mem_gb (on the owner's behalf, 2026-11-11)

0817-learn (genpack40k-s101, 6 threads) was queued with mem_gb 5.5. The runner admits a job only when free memory is at least mem_gb + 1 GB, which was rarely free, so 0817 could never start. It held the queue's reservation for 258 minutes and kept every other lane's heavy jobs waiting. Earlier 40k learns of the same script ran with mem_gb 2.0 and peaked at 5.0-6.4 GB without trouble (0749, 0754, 0755, 0803). 0817 and 0818 were cancelled and queued again on the same pin (ed467ac) with mem_gb 2.5, as 0847 (s101, given the reservation with `first`) and 0848 (s201, `--after 0847` so two 5-6 GB learns never start together). Once a job runs, the runner reserves its measured peak, so nothing else is admitted on top of it.
Alternatives: keep mem_gb 5.5 and wait (it never fits); lower threads (the memory comes from the 40k-game data, not the threads); let both learns run at once (two ~6 GB peaks would page). Reverse: cancel 0847/0848 and queue them with a higher mem_gb.

## twin-two-turn-matched read: between; extended to 500 on seed 1 (on the owner's behalf, 2026-11-11)

Job 0846 (`docs/research/pns-probes.md#twin-two-turn-matched (0846): the twin fighter gains two turns deep outside Demon Form; between, extended to 500`):
the all-content twin seed 1 two turns deep on the headline control's
decks, sequences 0-249: +1.53 (0.64) HP, clears +0.024 (0.020), boss
deaths 33 to 28. Demon Form decks +4.38 (1.65) (n 21; one turn deep
+11.40), the rest +1.38 (0.69) (one turn deep -0.10 (1.00)). By the
probe's rule (decisions "pns-two-turn-seeds read"): between, since boss
deaths fell by 5 (go needs 8, stop is 4 or fewer).

Decided:
- **Extended to 500 on seed 1 (job 0854, lane `main`, pin 2af5b30, the
  same snapshot as 0846 so the file holds one build; about 9 thread-h
  at 2 threads).** Read at fixed n 500. Go: +1.0 HP or more, boss deaths
  at least 10 fewer than the control's, clears not below -0.01: queue
  twin seed 101 (allcontent40k-s101-r1-ce824da) the same way on 0-499
  toward a promotion read (`decision/crossed-player-lead`'s condition:
  fewer boss deaths two turns deep). Stop: under +0.6 HP or boss deaths
  within 6: the fighter waits for the widened pool
  (`decision/headline-pool-after-act1`). Between: no second seed; the
  twin stays a lead. The 500 bars: +1.0 HP is about 2 se at 500
  (0846's se 0.64 at 250 gives about 0.45), and 10 fewer boss deaths is
  2% of sequences where the 250 bar asked 3%.
- **No change to `cause/leaf-gain-third` yet.** Its Demon Form part kept
  0.38 (0.17) of the one-turn gain, which fits the in-horizon third (the
  product's second turn plays the first tick); its exit (a past-horizon
  gain under 0.6x) is 1.3 se away on 21 decks. The rest grew with depth
  (level to +1.38), a kind of gain the fact does not name. Both wait for
  the 500 read, which doubles the Demon Form decks.

Alternatives passed over: queue seed 101 now beside the extension (the
rule said one seed on a between, and free memory fits one two-turn job beside the lanes' bursts, not two); stop
here (the HP side passed its go bar; a between is what the extension is
for); a one-turn re-read on the product's decks to pair the two depths
(about 1 thread-h; it would make the depth difference paired, but the
500 read decides the next step either way, so it waits for that read).

## Probe twin-depth-paired queued (on the owner's behalf, 2026-11-11)

0846 showed the twin level one turn deep outside Demon Form and +1.38
(0.69) HP two turns deep, but on different decks (each depth's control
picked its own), so the growth with depth is unpaired. Jobs 0855-0857
(lane `main`, pin 2af5b30, 3 threads, about 0.3 thread-h together) play
twin seeds 1 and 101 and the 10-29 net one turn deep on the product's
decks (`--match` the headline control), sequences 0-499.

Mechanism: if the second turn of search fixes tactical errors the twin
makes one turn deep while its values for long fights stay better, the
twin's gain grows with depth on the same decks; then a one-turn screen
misses part of a fighter's product gain, which matters for every goal-2
fighter read (`decision/one-turn-comparisons` keeps the product as the
augment). Closest technique: evaluation functions tuned at the depth they
are searched at (chess engines tune their evaluation through the search,
and a net trained for shallow play can rank wrong at depth); this project's
own `cause/leaf-gain-third` names gains that shrink or carry, not ones
that grow. Trade-off: one-turn screening gains speed (minutes against
hours per read) and loses nothing if gains never grow; two-turn reads for
fighters gain the cases where they do.

Read with 0854 (the two-turn file at 500): per sequence, (twin two turns
minus product) minus (twin one turn minus 10-29 net one turn), outside
the product's Demon Form decks. Go (gains can grow): +1.0 HP or more at
2 se: `cause/leaf-gain-third` gains a clause, and fighter candidates
whose one-turn deaths move to elites get a two-turn matched read before
they are dropped. Stop: under 2 se: the 0846 growth was deck noise, and
one-turn screens stand. Seed 101's file is for 0854's go branch (its
two-turn read pairs with it). Predicted: even (for: 0846's +1.5 over the
one-turn level on 221 sequences; against: about 1.2 se, one seed).

Alternatives passed over: waiting for 0854 alone (it doubles n but stays
unpaired across depths); playing the product's decks two turns deep with
the 10-29 net (that is the headline control itself).

## Card rules the net can read, spec decisions (owner, 2026-11-10)

Provisional, from `docs/specs/card-rules.md` (decided in chat, 2026-11-10):
- Entangled's `forbids` and Corruption's `sets_cost` and `exhausts_played`
  become something the net learns, as one opt-in row kind `rule` (owner:
  "add entangle and forbid as another thing the net has to learn";
  Corruption "has the same problem").
- `only_attacks_in_hand` leaves the card format for a general play
  condition (`playable_if`); existing nets keep the column as a special
  read for their version (owner: "just preserve it as a special read for
  this net version").

## Red Skull as real Strength, spec decisions (owner, 2026-11-10)

Provisional, from `docs/specs/red-skull-strength.md` (owner in chat
2026-11-10: "Also fix red skull"):
- Red Skull gives real Strength at the game's times instead of the
  `RedSkull` damage static: +3 at combat start if HP is at most half, +3
  when HP loss crosses down to half or below, -3 when a heal crosses back
  above (the game's `relics/RedSkull.java` with `isBloodied` from
  `AbstractPlayer.damage` / `heal`, decompiled copy `aeubanks/sts`), so
  Heavy Blade and Limit Break count it.
- The crossing is two general triggers (`OwnerBloodied`,
  `OwnerUnbloodied`) any power can use; the static condition
  `OwnerHpAtMostHalf` stays for generated statics.

## twin-two-turn-matched at 500: between; no second seed; the fighter plateau has two nets (on the owner's behalf, 2026-11-11)

Job 0854 (`docs/research/pns-probes.md#twin-two-turn-matched at 500 (0854): between; the fighter is worth about 1 HP outside Demon Form`):
the all-content twin seed 1 two turns deep on the product's decks,
sequences 0-499: +1.41 (0.45) HP, clears +0.014 (0.015), boss deaths 62
to 54 (paired 28 against 20, z 1.15). The product's 39 Demon Form decks
+6.46 (1.41) HP; the other 461 +0.98 (0.47), clears level. The protocol
(H1 +1.5) passes at n 500; by the probe's rule (decisions
"twin-two-turn-matched read: between; extended to 500 on seed 1"):
between, since boss deaths fell by 8 (go 10, stop 6 or fewer).

Decided:
- **No second seed, no promotion read.** The rule's between branch: the
  twin stays a lead. The protocol pass does not override it: the read is
  matched (fighting only, on the product's picks), so a promotion would
  owe an own-pick read, where the one-round recipe's picks cost about 1.5
  HP (`measurement/pack-net-twin@one-turn`), and
  `decision/crossed-player-lead`'s condition (fewer boss deaths two turns
  deep) is not shown at 1.2 se. And the twin trained on every card
  (deck_pool all), the ruler's held-out half included: as the product's
  net it would turn that half into training content, which is open until
  the pool widens after Act 1 (`decision/headline-pool-after-act1`: "what
  the held-out half becomes is open").
- **`decision/crossed-player-lead` gains the twin as its second net**:
  two recipes (a fine-tuned burst net and a from-scratch all-content net)
  each fight about +1 HP better two turns deep on the product's decks
  outside new content and move no clears; the twin's elite saves die on
  the next hallway (floor 9: 13 against 6). So a fighter swap on the
  curated ruler is about +1 HP, and the ruler's clears wait for the deck
  side (the chooser and the widened pool after Act 1,
  `decision/headline-pool-after-act1`).
- **`measurement/pack-net-twin@two-turn`** is re-set to the 500 read.
- **0856 (twin seed 101 one turn deep on the product's decks) stays
  queued**, read descriptively as a second seed of the twin's one-turn
  fighting on those decks. Its stated use was this read's go branch; the
  navigator's cancel was refused by the session's permission check, and at
  about 0.25 thread-h the job is cheaper to run than to chase.
- **twin-depth-paired (0855, 0857) reads as queued**, with one addition:
  the Demon Form decks' paired ratio (two turns over one turn, the same
  39 decks) is read beside it; under 0.6 at 2 se would meet
  `cause/leaf-gain-third`'s past-horizon exit, except that the product's
  second turn plays Demon Form's first tick, so the read reports it and
  re-sets the cause only if the ratio stays under 0.6 after the first
  tick's in-horizon part is set apart (the twin-tsl1 split: +3.30 of the
  one-turn gain is past the first tick).

Alternatives passed over: queue seed 101 two turns deep anyway on the
protocol pass (about 9 thread-h for a swap the matched read can't promote
and clears don't follow); an own-pick two-turn read of the twin (its picks
cost about 1.5 HP against a +1 HP fighter edge, so its prediction is level
and a level read decides nothing); a confirm on 500-999 (the protocol's
finalist step, but a confirmed +1 HP fighter with level clears changes
nothing under `decision/crossed-player-lead`).

## twin-depth-paired read: stop; one-turn screens stand; leaf-gain-third gains the mixed-content case (on the owner's behalf, 2026-11-11)

Jobs 0855-0857 with 0854 (`docs/research/pns-probes.md#twin-depth-paired (0855-0857 with 0854): stop at 1.8 se; Demon Form splits by tick as predicted`):
on the product's decks, sequences 0-499, outside Demon Form the twin
seed 1 is -0.40 (0.62) HP one turn deep against the 10-29 net and +0.98
(0.47) two turns deep against the product: growth +1.38 (0.76), 1.8 se
(seed 101 one turn deep -0.92 (0.60)). Demon Form decks: +11.49 one turn,
+6.46 two, ratio 0.56. By the probe's rule: stop (go needed 2 se).

Decided:
- **One-turn screens stand** (`decision/one-turn-comparisons`). The
  growth is filed as a lead with its mechanism (the second turn repairs
  the twin's second-elite deaths: 33 one turn deep against the 10-29
  net's 26, 8 two turns deep against the product's 13); no replication
  now. A fighter screened one turn deep whose losses there are elite
  deaths gets that noted in its read, not a two-turn read by rule.
- **`cause/leaf-gain-third` gains the mixed case**: a gain on content
  whose payoff is partly inside the second turn splits by part. Demon
  Form's first tick (inside the product's horizon) at a third plus its
  later ticks whole (+3.30 past the first tick, twin-tsl1) predict about
  +6.0 HP two turns deep; measured +6.46 (1.41). The 0.56 ratio is that
  mix, not the past-horizon exit.
- **`measurement/pack-net-twin@two-turn`** gains the paired depth read.

Alternatives passed over: twin seed 101 two turns deep to replicate the
growth (about 9 thread-h; it would settle a screening rule for fighters,
and the next fighter headed for the product, the net trained on the
widened pool after Act 1, is read two turns deep anyway, so the rule
would decide nothing soon); calling it a go at +1.38 (the rule asked for
2 se, set before the read).

## Lane from-scratch-later-ticks closed (2026-11-11)

(on the owner's behalf) Closed by the lane worker at its stop rule: go,
then count. Step 1 took the pool branch (data40k, the twins without Demon
Form in the pool, lose on Demon Form decks); step 2 went at 5k and 20k
from scratch, each against its data-curve twin
(`measurement/later-ticks-dose@5k`, `@20k`); step 3's three bursts of
5000 games per group on the 10-29 net gain +2.69 (0.91 sequences / 0.51
nets) HP on held-out Demon Form decks against the 10-29 net @tsl1, other
held-out +0.19, train +0.08 (`measurement/later-ticks-count@burst5k`;
`docs/research/from-scratch-later-ticks.md`, "Step 3, count or start").
Outcome: a later-ticks power is learnable by a burst on a trained net
once the dose is large enough; the dose lies between 1.6k (taught the
first tick only, `measurement/portfolio-player-growth-exposure`) and 5k
games per group, about 3.5k games with the power. No fresh start and no
shrink-and-perturb needed. Caveat: other held-out clears -0.033 (0.012)
with their HP level; one turn deep only.

CPU-hours: about 10.6 of the 23 cap (`health.py` lane use), against the
opening's estimate of about 15. Rating at opening: even; it went.

Alternatives at the close: keep the lane open for a dose point between
1.6k and 5k (pins goal 1's games number tighter, about 4 cpu-h), or a
two-turn read of the bursts; both left to the navigator's ranking
(on-close: wake always), since the charter's stop rule is met.

**Reopen if:** goal 1 needs the games number for a later-ticks power
tighter than "1.6k to 5k per group" (a 2.5k-3k burst point, three seeds,
same read), or a different later-ticks form (a stacking attack, a
generated power from the pack) fails at 5000 games per group, or a
two-turn or headline read of these bursts shows the other held-out
clears loss growing past -0.04.

## After from-scratch-later-ticks: lanes counterfactual-state-price and card-later-ticks-burst opened (on the owner's behalf, 2026-11-11)

Lane from-scratch-later-ticks closed on a go, then count
(`measurement/later-ticks-count@burst5k`): three bursts of 5000 games per
group on the 10-29 net gain +2.69 (0.91) HP on held-out Demon Form decks
@tsl1, so a trained net learns a power's later ticks once the dose is
1.6k-5k games per group. Two closed lanes' reopen conditions hold on it:
`measurement/portfolio-yardstick-cards` ("a leaf or training target sees a
recurring power's later ticks") and `measurement/portfolio-player-growth-exposure`
("a burst ... shown to teach a growth power's later ticks @tsl1"); the
second's question (exposure share) is answered by the dose, so it merges
into the first.

Decided:
- **Lane counterfactual-state-price opened** (backlog 51, the ready
  exploration charter; end 2026-11-18 by "Lanes opening from 2026-11-12
  end 2026-11-18"). Rated a long shot; about 4-6 hours of engine code and
  about 3 thread-h (cap 5). The count result sharpens what it would win:
  the burst needs about 3.5k games with the power (and costs other
  held-out clears -0.033 (0.012)); a leaf term that prices persistent
  state needs none and learns nothing to forget. 
- **Lane card-later-ticks-burst opened** (backlog 58, revived from
  yardstick-cards; a fourth lane while generated-pack-scratch is within
  two days of its end). The two power modifiers that still cost the net
  @tsl1 on the owner's card yardstick (`decision/goal1-yardstick`):
  inflame-turn1 -0.018 (0.005) and metal-c2-a5 -0.021 (0.006) wins
  (`measurement/mutated-cards@stage-a`); 400-game bursts closed neither
  (`measurement/cards-adapted@stage-a`). Mechanism: both are values that
  recur past the leaf, which 400-1.6k-game bursts teach only for the
  first tick and a 5k burst taught for Demon Form. Rated even (for: the
  same kind of value, the same recipe that went; against: the costs are
  small, about 0.02 wins, and card bursts lost 0.5-1.8 HP per elite fight
  on the parent copy at 400 games, which a burst twelve times larger may
  raise). About 16 thread-h (six bursts at about 1.7 each, reads about 6),
  cap 24; no code (configs). It fills the queue now (health `ready` red at
  2.3 queued hours, `cpu` red).
- **Shares** (`jobs/lanes.json`): generated-pack-scratch 55,
  card-later-ticks-burst 15, counterfactual-state-price 10, act1-content
  10, main 10, filler 0.

Alternatives passed over: a dose point between 1.6k and 5k for Demon
Form (about 4 cpu-h; narrows goal 1's games number from "1.6k-5k" when
nothing yet needs it tighter); a two-turn read of the 5k bursts (their
clears caveat is one turn deep, -0.033 at 2.75 se; it matters once a
burst heads for the product, which none does); 56
generated-card-space-scratch (a long shot whose precondition, count or
start, now says a burst carries one power, so its value is the zero-shot
case only; its cheap residual probe stays its first step); 57
mechanic-count-curve (waits for generated-pack-scratch's pooled read);
opening only one of the two (the exploration slot takes 51 by its
charter, and 58 needs no code while the queue runs dry).

## card-later-ticks-burst: the 5000-game card bursts use the 400-game pack recipe (on the owner's behalf, 2026-11-11)

The charter asks for the fslt-step3 burst recipe with the variant in the
decks as 0409-0421 had it; fslt's `source` games (held-out decks) can't
hold a pack card. Chosen: the 400-game configs (`configs/cadapt-*`) with
`games` 5000 per group (`configs/clb-*`), so dose is the only change from
0409-0421. Alternatives: a pack option in `two_turn_games` decks (code,
and a teacher change with the dose change); about 1200 games per group to
match fslt's count of games with the new card. Reversible: configs only.
Plan and reads: `docs/research/card-later-ticks-burst.md#Plan (2026-11-11)`.

## generated-pack-scratch: the cap close waits for the seed-201 reads (on the owner's behalf, 2026-11-11)

The lane has used 77.5 of its 80 CPU-hours (health.json `lane_cpu_h`); the
seed-201 reads 0885 (rows), 0886 (cells) and 0887 (pack headline), queued
at pin e54c5ba, add about 6 more, so `lane-cap:generated-pack-scratch`
fires while some of them still run. Step 4's verdict is the three seeds
pooled (the charter), and seeds 1 and 101 pass every bar with room (cut
0.75 pooled; docs/research/generated-enemies.md#Seed-101 read): the reads
decide whether that holds across seeds. So a lane worker woken by the cap
before 0885-0887 have ended leaves the lane open and lets them finish;
the close then follows the pooled read (go or fail), about 84 of 80
CPU-hours. Alternatives: close on two seeds now (the charter asks three;
a two-seed go is weaker evidence for goal 1's headline transfer claim);
cancel the seed-201 reads (saves ~6 CPU-hours, loses the same). Reversible:
`jobs.py cancel 0885-mutate-monsters 0886-gauntlet 0887-gauntlet` and close.

## counterfactual-state-price step 1: greedy windows, sampled chance, rollout worths (on the owner's behalf, 2026-11-11)

Spec `docs/specs/counterfactual-state-price.md` (lane worker). The term
`cf_price` (engine `cf.rs`) prices each held power by playing the greedy
policy one window forward with it and without it. Choices, each the most
reversible (a probe-only function, no search flag yet):
- **Policy: greedy** (`agent::greedy_action`), not a one-turn heuristic
  search, which would cost a search per element per leaf. Alternative:
  `SearchAgent<Heuristic>`.
- **Chance: k = 4 sampled windows with shared seeds**, not exact: draws
  have too many outcomes to list. Alternative: listed outcomes where small.
- **Growth** (the owner's Strength gap widens over the window: Ritual,
  Demon Form) plays one more round to find the per-round gain, since
  Ritual's first tick lands after the window's monster attack. Alternative:
  the charter's plain one-window form, which prices Ritual at 0.
- **Worths for Ritual 2 and Demon Form 2: a greedy rollout to the fight's
  end** (4 seeds, at most 30 rounds); Strength -2 and Weak +1 keep the
  leaf-numbers probe's worths. Alternative: an upper-side formula, which
  needs the deck's hits per turn.
- **"Inside" = not mispriced (the leaf-numbers probe's half-to-twice rule
  by 2 se) and precise (se at most a quarter of the worth) on every set.**
  The charter's strict ranges are printed beside it. Alternative: the
  strict ranges alone (a noisy per-leaf estimator would almost never land
  in a 3-HP window) or the mispriced rule alone (a 3-cell smoke run passed
  it with se up to 20 HP, so it can't fail a noisy term).

## Lane counterfactual-state-price closed (2026-11-11)

Lane worker, at its stop rule (on the owner's behalf). **Outcome: fail at
step 1** (`docs/research/counterfactual-state-price.md#Step 1 read
(2026-11-11, job 0889; diagnostic re-run with own prices)`): none of the
four perturbations is priced inside its worth on every set (charter: three
needed). The term change is noise (se 3-95 HP; Weak +1 negative on three
sets); the edited element's own price, a diagnostic, fails too: Strength -2
and Weak +1 at about half their worth or less (greedy blocks, so a weaker
hit saves block, which the window prices at 0), Ritual 2 and Demon Form 2
overpriced 10-25 times by the growth sum over the heuristic's remaining
rounds. Step 2 not built. CPU: about 0.15 thread-h of the 5 cpu-h cap
(job 0889 and one 1.5-minute diagnostic run). On-close `wake on go`: a
fail, so no wake for the outcome; the slot has no ready charter (52 and 53
wait on generated-pack-scratch's pooled read and are written for the
project slot), so the navigator is woken for the slot. Share 10 moved to
card-later-ticks-burst (the other lane with queued work besides
generated-pack-scratch, which is at its cap).

**Reopen if:** a counterfactual price per element is shown, on the same
probe (`scripts/analysis/cf_price_probe.py`, 2 minutes), within half to
twice its greedy-rollout worth for three of the four perturbations with se
at most a quarter of the worth, which needs both (a) a policy whose play
turns a weaker hit into HP rather than spare block, or a window that
prices spare block, and (b) a horizon read from play (a rollout's own
length, or a learned fight-length estimate checked against rollouts)
instead of `turns_left_estimate`; or a cheap exact rollout to the end at
leaves replaces the extrapolation altogether (the rollout leaf was +0.67
HP worse on elites, `measurement/rollout-leaf@elites`).

## After counterfactual-state-price: lane luck-corrected-labels opened, probe gen-powers-later-ticks queued (on the owner's behalf, 2026-11-11)

Lane counterfactual-state-price closed on a fail at step 1
(`measurement/cf-price@probe`): greedy-window prices miss every worth, so
the leaf route to a power's later ticks is closed for now, and the route
that works is games, at a dose of 1.6k-5k per group
(`measurement/later-ticks-count@burst5k`). The exploration slot it left
had no ready charter (52 and 53 wait on generated-pack-scratch's pooled
read).

Decided:
- **Lane luck-corrected-labels opened** (backlog 40, re-scoped from
  `aivat-reads`; exploration; cap 18 cpu-h, end 2026-11-18, on-close
  wake always). The question under "games teach later ticks only at a
  dose": a training label is the fight's final score, and most of its
  spread is luck (draws, move rolls) after the labelled decision; a later
  tick's worth is a few HP inside that spread. The dose numbers fit a
  noise limit: Demon Form-holding rows at about 130 games (net-g1600, 8%
  exposure) taught +1.19 (0.75) HP @tsl1, at about 400 (the 5k bursts)
  +2.69 (0.91) (`measurement/growth-exposure@ycards-step2`,
  `measurement/demon-form-games@tsl1`). Subtracting at each chance event
  the value of the outcome drawn minus the mean over outcomes (AIVAT,
  Burch et al. 2018, a control variate) keeps each label's expectation and
  removes the luck the value function sees; if it removes a fraction f of
  the label variance, a burst needs 1-f of the games. Its first step also
  measures the same correction on reads (40's original question: both
  reviews since 2026-11-09 ranked it, never opened), which would cut the
  CPU of goal 1's benches. Rated a long shot (for: the dose evidence, the
  correction is unbiased for any value function, AIVAT's poker results;
  against: the net values the post-draw states the correction needs off
  its training range, so it may remove little, and the dose gap may be
  optimisation steps rather than noise). About 12 thread-h, 3-4 hours of
  engine code.
- **Alternatives passed over.** `generated-card-space-scratch` (56): a
  learn of about 18 thread-h for a cost of about -0.06 wins; its cheapest
  probe needs no code and goes on the probe sheet instead (below).
  `chooser-noise` (55): goal 2 at 0.2 of the development weight, a
  probe-sheet read once its flag exists. `incremental-state-key` (22) and
  `reserve-from-peak` (43): machine-time tooling, while the CPU stands
  idle for want of queued work, not for speed. `ceiling-player` (19) and
  `hexaghost-headroom` (10): goal 2, waiting on Act 1's content.
  `specialist-teacher-burst` (50) retired: it opened only if 49 landed on
  start, and 49 landed on count.
- **Probe gen-powers-later-ticks queued** (job 0890, lane main, about 0.5
  thread-h): the seven nets that learned Demon Form past its first tick
  (the all-content twins at 40k s1/s101, 20k and 5k s1, the three 5k
  bursts) @tsl1 on the generated-power bench, zero-shot on generated
  power cards no game held, against the 10-29 net @tsl1. Today the 10-29
  net @tsl1 sits -0.049 (0.040) wins below the heuristic on generated
  OwnerTurnStart powers and -0.072 (0.052) on OwnerTurnEnd ones (from the
  0326 file and the heuristic's elite+boss file, computed this run).
  What each outcome does: a gain of +0.04 wins or more at 2 se in either
  family says the later-ticks value carries through the effect inputs to
  unseen recurring powers, and 56 rises to even; under +0.02 in both, 56
  is retired; between, 56 stays a long shot.
- **Shares** (`jobs/lanes.json`): generated-pack-scratch 40 (one read
  running, its close two days out), card-later-ticks-burst 25,
  luck-corrected-labels 15, act1-content 10, main 10, filler 0.

## Relics as their own entity, spec decisions (owner, 2026-11-11)

Provisional, from `docs/specs/relic-entity.md` (interview 2026-11-11):
- A relic is its own entity: a list on the player, each relic with its
  own hooks and a counter (the owner chose this over powers marked "from
  a relic").
- Relic fights may change toward the game: game parity wins conflicts
  with today's relic behaviour; each difference is named with the game's
  line.
- The net reads relics as opt-in rows with their counter; relic id
  columns only in ids mode.
- At most 16 relics per fight (`RELIC_CAP`).
- Out of scope: the run layer, counters carried between fights, relics
  beyond today's 23, potions.

## Lane generated-pack-scratch closed (on the owner's behalf, 2026-11-11)

Closed at its CPU-hour cap (82.4 cpu-h used against 80) with the stop rule's
**go** reached on the pooled read the cap close waited for (decision
"generated-pack-scratch: the cap close waits for the seed-201 reads").
Outcome over three from-scratch seeds (1, 101, 201; pack-net-scratch's
recipe with a generated pack of 18 training mechanics as start powers on
at most half the hallway and elite fights): the zero-shot cost on the six
held-out mechanics is cut by 0.76 pooled (starts se 0.02, seed spread
0.04; per seed 0.81, 0.68, 0.78), held-out cost +1.28 (0.11) HP per elite
fight against the 10-29 net's +4.21 (0.16); training rows cut 1.29;
official cells +0.52 (0.30) HP pooled and the 31-card pack headline
+0.41 (0.63) HP pooled against pack-net-scratch, so the generated pack costs official
play nothing measurable. Results: `docs/research/generated-enemies.md`,
"Seed-201 read and the pooled verdict". Predicted at opening: even that
the cut reaches 0.4 at 2 se, about 54 thread-h for three seeds; it went
well past the bar. No net was promoted (one turn deep; the product is a
two-turn net trained without the generated pack).

On-close `wake always`: the navigator decides the slot (a navigator wake
`lane:generated-pack-scratch`); the lane's share in `jobs/lanes.json`
moves to card-later-ticks-burst (+30, to 55) and luck-corrected-labels (+10, to 25).

**Reopen if:** (a) mechanics outside the 24-cell trigger x effect grid
exist to hold out (a new trigger or a new effect, not a new pairing of
seen ones): the held-out rows here are unseen pairings only, so the next
transfer question is a held-out trigger or effect, read the same way
against these three nets; or (b) a genpack-trained net is to be read at
product depth (two turns, the headline setting) as a product candidate,
which needs a two-turn round on this recipe; or (c) the residual held-out
cost (+3.0 HP on OppCard-PlainDamage, +2.0 on TurnEnd-Weak) is the target
of a leaf or input change, read against these files.

## Lane wider-generators opened (on the owner's behalf, 2026-11-11)

Lane generated-pack-scratch closed on a go (`measurement/genpack-transfer@three-seeds`:
held-out cut 0.76 over three seeds, official play level). The reroute
written in advance (decisions "After the big-picture review of
2026-11-10") opens `wider-generators` (backlog 53) on that go, and the
close's reopen condition (a) asks the same question: a held-out trigger
or effect, not only unseen pairings of seen ones.

Decided:
- **Lane wider-generators opened** in the project slot generated-pack-scratch
  left, with 53's ready charter: widen the generated enemy-mechanic grid
  to every trigger and effect an enemy power can carry in the engine,
  hold out pairs plus one whole trigger and one whole effect, read the
  generated-pack seed-1 net (the best seed, cut 0.81) zero-shot on the
  new rows, then one from-scratch learn on the wide pack. Rated even on
  the held-out pairs (for: 47's cut at about 20 se over its bar, three
  seeds; against: at 40k games each mechanic gets about a third of 47's
  games, and status cards into the player's piles act through the deck),
  a long shot on the whole held-out trigger or effect. About 26 thread-h,
  cap 40, end 2026-11-18, on-close wake always.  Bosses stay out of the
  pack: genpack-reach (b) went (`measurement/genpack-reach@bosses`).
- **Alternatives passed over.** `random-world-product` (52): its charter
  was the pooled-fail branch; with the go, 52 waits behind 53 and its
  player becomes the generated-pack net two turns deep beside the
  product. `mechanic-count-curve` (57): the same family at about 18
  thread-h; it stays a candidate for the next slot (or an extra arm of
  53's step 3, which the lane worker may add if the cap allows), so the
  portfolio does not hold two lanes on one recipe.
- **A fourth open lane.** act1-content is parked with the owner
  (`decision/act1-owner-led`): no lane worker works it and its jobs are
  the owner's. The lanes a worker runs stay three: card-later-ticks-burst
  (project, its last jobs queued), luck-corrected-labels (exploration)
  and wider-generators (project).
- **Shares** (`jobs/lanes.json`): wider-generators 30,
  card-later-ticks-burst 35, luck-corrected-labels 15, act1-content 10,
  main 10, filler 0. card-later-ticks-burst has about 2 queued CPU-hours
  left, which its share still covers first.

## luck-corrected-labels step 1: luck from the net on the post-event state, the fail-fast on replayed noise (on the owner's behalf, 2026-11-11)

Spec `docs/specs/luck-corrected-labels.md` (lane luck-corrected-labels,
step 1). Decided:
- **V of a chance outcome is the luck net (the 10-29 net, unpriced) on the
  state the outcome reaches**, the engine's score on a finished one; the
  mean is exact over at most 64 listed outcomes, else over 16 sampled with
  the logger's own RNG (the game's RNG untouched, so plain and corrected
  arms train on the same games). Alternative passed over: the agent's root
  search value per outcome (a search per listed outcome, tens per draw,
  over ten times the games' CPU); decision and paused states are the net's
  own training rows, so it is in range.
- **The fail-fast reads `noise_share`**: the noise variance removed,
  Var(y) - Var(c), over the label noise E[Var(y | state)] measured by
  replaying 600 rows per deck slice 8 times each with fresh chance seeds.
  Alternatives: `label_share` = 1 - Var(c)/Var(y), the charter's words
  read literally, which also counts the spread of true values across
  states that no correction removes; `bound_share`, the removed variance
  over the residual around the net's value, a lower bound that also holds
  the net's own error (half of the residual in a 200-game smoke run).
  All three are reported. Reversible: the read prints all three.

## After the big-picture review of 2026-11-11: two charters amended, genpack-product-depth readied, 56 answered, pick book started (on the owner's behalf, 2026-11-11)

The review (`docs/research/big-picture-2026-11-11.md`, run `wf_2b643c12-8da`)
found the same split as the last three: what paid let a decision see a
consequence it could not see before, and refinements of the same axis are
flat; goal 1's one strong result is transfer to unseen pairings of seen
atoms. All six key claims came back overstated; the corrected forms are in
the review file. This run's probes 0890 and 0891 (control 0893, identical to
the 11-07 file on all 7,824 fights) add one goal-1 result: every one of ten
nets that learned a power's later ticks from games (from-scratch twins at
5k-40k, the three 5k bursts, the three generated-pack nets) gains +0.03 to
+0.09 wins on generated recurring powers no game held, and none on the other
generated powers (`measurement/gen-powers@later-ticks`).

Decided:
- **Candidate 56 (`generated-card-space-scratch`) answered, not opened.**
  Its mechanism holds (a pool's later-ticks value reaches unseen recurring
  powers through the effect inputs), but the nets on file already close the
  10-29 net's gap to the heuristic on that bench (-0.05 to -0.07 wins), so a
  learn with generated power cards in the pool has no measured cost left to
  cut there (the trade-off rule). Reopen if a bench shows those nets still
  losing to the heuristic on recurring player powers.
- **`lane/wider-generators` amended**: a step 2b, the column ablation the
  review proposed (the trigger column, then the effect column, of the 6 old
  held-out rows zeroed for the generated-pack seed-1 net @tsl1, about 1.5
  thread-h; descriptive): how much of the 0.76 cut rides on the atom's
  name, which says whether a name-free atom description is worth a
  candidate. The spec states, for each whole held-out atom, which content
  trains its column (its spec on the lane branch picks Attacked and Wound,
  both trained elsewhere on purpose); the step-3 learn lists the row kinds
  it turns on. Stop rule unchanged.
- **`lane/luck-corrected-labels` amended**: the read-sd ratio is step 1's
  main result (the review's direction 8: the read use is the likely payoff,
  the label use the long shot); a ratio at most 0.75 makes the correction an
  opt-in of `gauntlet.py --against` and the mutate benches, and is the
  lane's go on its own; step 2 still runs only if the label variance falls
  by half. The offline stronger-teacher check (direction 9) reads the same
  step-1 data: the one-turn root values against outcomes, descriptive.
- **Ready charter `genpack-product-depth`** (backlog 60, merging 52
  `random-world-product`): the generated-pack nets two turns deep with the
  product's flags on the 6 held-out rows and the k-4 random-world bench,
  against the product. Mechanism: both of today's goal-1 transfers (enemy
  pairings, recurring player powers) are one turn deep; the product plays
  two, where the second turn already repairs part of in-horizon novelty
  (`cause/leaf-gain-third`) and leaves past-horizon gains whole. Rated even
  (for: the pack nets' 1.35x ratio on past-horizon content; against: the
  punish-an-action rows are in-horizon threats, which kept a third to a half
  two turns deep). About 12 thread-h, cap 18. It takes the next project slot
  (card-later-ticks-burst, whose queue has about 2 CPU-hours left).
- **Pick book** for matched reads: block 1000-1499 queued (0895, lane main,
  about 3 thread-h); blocks to 2999 follow if it runs in its estimate. Under
  `decision/matched-reads` (owner, 2026-11-05) fighter questions are read
  matched; more recorded picks lower that read's floor.
- **Tooling entries** (backlog 59 control-arm cache, 61 sparse feature
  cache) for lane workers while their lanes wait on CPU, beside 54 and 43;
  the two-heavy-slot cap, which held back three times as many jobs as memory
  since 11-03, goes in 43's entry (runner code, a lane worker's).
- **Not adopted.** "No more bursts on the frozen net for later ticks": the
  5k bursts carried their later-ticks value to unseen powers as well as the
  twins (+0.078 against +0.076), so `card-later-ticks-burst` finishes on the
  record. A change to goal 1's standing number and the chooser's own-boss
  exception to the Avoid item are the owner's (`decision/goal1-yardstick`,
  docs/direction.md); listed as notices for the digest.
- **Alternatives passed over** for the ready charter: `mechanic-count-curve`
  (57; same recipe family as the open wider-generators, whose step 3 can
  carry it as an arm), `chooser-noise` (55; goal 2 at 0.2 of development
  weight, stays a probe-sheet read once its flag exists), the Hexaghost
  three-turn probe (10; 8.2 GB peak, more than the dev machine had free).

## wider-generators step 1: the 100-mechanic grid, its whole held-out trigger and effect, and a sparse wide pack (on the owner's behalf, 2026-11-11)

Spec `docs/specs/wider-generators.md`, built on `lane/wider-generators`;
results doc `docs/research/generated-enemies.md#Wider grid (lane wider-generators)`.

Decided:
- **The grid:** 9 triggers x 12 effects on a monster owner, minus the pairs
  an official power's hook holds: 100 mechanics, the old 24 unchanged, 76
  new. Left out: OwnerDied (a kill that ends the fight drops its effect;
  probe on Cultist, 0 of 6 seeds changed), OwnerBloodied, Heal and
  BlockAlly (no input column in the seed-1 generated-pack net: a read would
  measure blindness), and player-only triggers. Alternative: add those
  columns first, which changes the feature layout for a question the
  columns we have can already ask.
- **Whole held-out trigger Attacked, whole held-out effect Wound** (one
  Wound into the discard pile): atoms whose input columns other content
  trains (Flame Barrier's `OwnerAttacked` on the player; Sentry's and the
  slimes' status cards into the discard pile) but no generated enemy power.
  Alternatives: AttackHit and DexDown, whose columns no content trains; a
  read of them would measure an untrained column, an answer known in
  advance (operating.md, "A probe needs a trade-off").
- **A sparse wide pack.** The engine holds at most 236 pack monsters
  (`MonsterKind` is a u8), so 58 training mechanics x 10 bases (580) don't
  fit. Every mechanic rides both elites and one of the four single-base
  hallways; the slime and mixed hallways stay official (174 copies;
  generated share 4/18 of hallways against the old pack's 8/22, elites 2/5
  as before). Alternatives: widen `MonsterKind` (an engine and codec change
  outside the lane's scope); fewer training mechanics (narrows the very
  space the lane widens). The charter asks for at most the old pack's
  shares, which this keeps.
- **Queued (pin 1abac89):** 0896 and 0897 (the seed-1 generated-pack net and
  pack-net-scratch seed 1 on the 76 new rows, 675 elite starts x 4 seeds),
  0898 (the read; its check is the charter's fail-fast, the generated-pack
  net's new held-out pairs pooled cost under 1 HP fails it), 0899 (the
  wide-pack learn, `configs/widepack40k-s1.json`, if 0898 passed).

## Lane luck-corrected-labels closed (2026-11-11)

Lane worker, at its stop rule (on the owner's behalf). **Outcome: fail on
both of step 1's reads** (charter rev 2, `docs/research/luck-corrected-labels.md`).
The read-sd ratio, the main result, is 1.41 (se 0.50) against the bar of
0.75 (`#Step 1b read (2026-11-11, job 0900)`): on 100 one-turn cell
sequences the luck-corrected paired end-HP sd is 12.05 HP against 8.53
raw, and the unpaired sds are 37.7 against 25.3. A sequence's summed luck
(sd about 26 HP) is uncorrelated with its end HP (r -0.08). The label
read gated step 2 and failed too (`#Step 1a read (2026-11-11, job 0894)`):
the correction removes 1% (se 10%) of the label noise on Demon Form decks
and 13% overall. Luck is a fifth of label variance, and the 10-29 net's
error around the labels is twice the luck. The net's values of a chance
event's outcomes swing but carry almost no information about the fight's
end. Step 2 did not run. CPU: about 0.6 cpu-h of the 18 cpu-h cap (jobs
0894, 0900 and the smoke runs). Built and kept: `runner::play_luck`,
`sts.run(luck=)`, `two_turn_games --luck`, `scripts/analysis/luck_share.py`
and `scripts/analysis/luck_read.py`. None of them change a game played
without `luck`. On-close `wake always`: the navigator is woken. Share 15
moved to wider-generators (4 jobs pending, the most queued work of the
open lanes, with card-later-ticks-burst's 6 waiting on memory).

**Reopen if:** a luck valuer passes step 1a on the same read
(`luck_share.py`, about 5 minutes) with at least half of the replayed
label noise removed on Demon Form decks. Then `luck_read.py` (about 2
minutes) gives a ratio at most 0.75. That needs values that tell a chance
event's outcomes apart and track the fight's end: a net whose label error
is well under the label noise (today 0.165 against 0.072), or a search or
rollout value per outcome cheap enough to log on a read. The cheapest
first check is luck_share.py's `residual_ms` against `noise_var`.

## Lane mechanic-count-curve opened (on the owner's behalf, 2026-11-11)

Lane luck-corrected-labels closed on a fail (`measurement/portfolio-luck-corrected-labels`:
the 10-29 net's luck correction adds noise to reads, ratio 1.41, and
removes 1% of the label luck on Demon Form decks), leaving the exploration
slot empty.

Decided:
- **Lane mechanic-count-curve opened** (backlog 57; exploration; cap 27
  cpu-h, end 2026-11-18, on-close wake always). The question: how wide a
  generated training pool must be for zero-shot transfer to unseen
  pairings. The generated-pack recipe trained on 18 mechanics and cut 6
  held-out pairings by 0.76 over three seeds
  (`measurement/genpack-transfer@three-seeds`). Thinning the training split
  to 6 mechanics that still contain every trigger and effect of the
  held-out pairs (AttackLoss-PlainDamage, AttackLoss-Frail, OppCard-Weak,
  OppCard-Frail, TurnEnd-Damage, TurnEnd-PlainDamage), with the same 40k
  games, separates the two explanations: transfer from seen atoms (the
  6-arm, with three times the games per mechanic, cuts as much) or from the
  count of combinations seen (the cut falls, Procgen's curve). The answer
  sets what a custom mechanic needs in the pool and whether
  wider-generators' thinner games per mechanic are a risk. Rated even (for:
  the held-out cut is close to the training rows' and moved whole to hosts
  the pack never carried; against: Procgen needs hundreds of levels, and
  with 6 mechanics each trigger meets only two effects). About an hour of
  code (a mechanic subset for the generated pack writer) and about 18
  thread-h (the learn about 12, the rows read about 6), while the CPU is
  underbooked (`cpu` red, three pick-book blocks the only main-lane work).
- **Alternatives passed over.** `genpack-product-depth` (60) is project
  work and has the next project slot (card-later-ticks-burst, its queue
  nearly done). `chooser-noise` (55): goal 2, a measurement only (choosers
  wait for Act 1 under "Headline card pool and choosers after Act 1"), a
  probe-sheet read once its seed flag exists, not a lane. `name-free-atoms`
  (62) waits for wider-generators' step 2b. `incremental-state-key` (22):
  machine-time tooling while CPU waits on ready work, not on speed. Goal 2
  has no lane while its levers wait on Act 1's content; the pick book
  (0901-0903) is its infrastructure meanwhile.
- **Shares** (`jobs/lanes.json`): wider-generators 35,
  card-later-ticks-burst 25, mechanic-count-curve 20, act1-content 10,
  main 10, filler 0.

## Lane card-later-ticks-burst closed (2026-11-11)

Lane worker, at its stop rule (on the owner's behalf). **Outcome: fail**
(`docs/research/card-later-ticks-burst.md#Step 2 read: fail (2026-11-11)`,
`measurement/card-later-ticks@5k`). Three 5000-game-per-group bursts per
modifier (family clb-step1, jobs 0859-0882, verdict 0884) close neither
card variant's win cost at the turn-start leaf: inflame-turn1 +0.001
(0.004) of a -0.018 cost, metal-c2-a5 +0.003 (0.004) of -0.021; the go bar
was half the cost at 2 se. Twelve times the 400-game dose changes almost
nothing (inflame one turn +0.029 against +0.024; @tsl1 the same +0.001),
though the bursts do teach the net inflame-turn1's value one turn deep
(+0.075 of the -0.108 boss cost). So dose is not the lever for the card
column at the turn-start leaf; what that player still loses on these
variants isn't fixed by the net's value. Inflame's parent-copy retention
missed too (+1.13 HP lost per elite fight @tsl1 against the 400-game
bursts' +0.76), and every arm lost clears on the cell guards (0883). The
only lead: metal-c2-a5 at the bosses @tsl1, +0.020 (0.010) wins, -1.47
(0.41) HP, as at 400 games. CPU: 5.3 cpu-h of the 24 cpu-h cap. No code
was built (configs only). On-close `wake always`: the navigator is woken.
Share 25 moved to wider-generators (+15, to 50) and mechanic-count-curve
(+10, to 30), the two open lanes with queued work.

**Reopen if:** a read shows the variants' @tsl1 cost is something a
burst can reach. Two checks would show it. First, the cost read two turns
deep (the product's `--two-turn --line-seed --step-line` on
`results/mutate/cards-a.json`'s starts) is at least 0.02 wins, and a
400-game burst closes half of it there. Second, a training target changes
the turn-start leaf player's line choice on the variant decks (not only
its value) and moves at least 0.01 wins @tsl1 at 2 se. Today's bursts
showed neither, at 400 or 5000 games.

## Lane genpack-product-depth opened (on the owner's behalf, 2026-11-11)

Lane card-later-ticks-burst closed on a fail
(`measurement/portfolio-card-later-ticks-burst`: 5000-game card bursts
close neither variant's @tsl1 win cost, the same as 400 games), freeing a
project slot; its on-close `wake always` woke the navigator.

Decided:
- **Lane genpack-product-depth opened** (backlog 60, the ready charter
  from "After the big-picture review of 2026-11-11"; project; cap 18
  cpu-h, end 2026-11-18, on-close wake always). The question: whether the
  generated-pack recipe's zero-shot pricing of unseen enemy pairings
  (`measurement/genpack-transfer@three-seeds`, cut 0.76 one turn deep)
  holds where the product plays, two turns deep, and what k generated
  enemy mechanics cost the product there. Every goal-1 transfer on record
  is one turn deep; the second turn repairs part of in-horizon novelty and
  leaves past-horizon gains whole (`cause/leaf-gain-third`), so the
  answer is the baseline every later goal-1 change at product depth needs.
  Rated even (for: the pack nets' 1.35x two turns deep on past-horizon
  content, the one-turn cut 20 se over its bar; against: punish-an-action
  rows are in-horizon threats, which kept a third to a half two turns
  deep, and two-turn elite reads are noisy per fight). About an hour of
  code and about 12 thread-h. The card-later-ticks fail does not touch it:
  that lane read card variants with official enemies, this one enemy
  mechanics.
- **Alternatives passed over.** `genpack-burst-base` (new this run, 63):
  exploration-shaped and waits on wider-generators' step 2 (0896-0898) for
  its target rows; readied as the next exploration charter. The card
  column's two-turn read (the closed lane's reopen check (a)): checked and
  not proposed (backlog), the residual @tsl1 card costs are small and
  pooled level over six power pairs (`measurement/mutated-cards@stage-a`:
  -0.006 (0.005) wins), and the direction says new mechanics, not new
  cards, are what hurts. `chooser-noise` (55): goal 2, a measurement of
  the ruler, a probe-sheet read once its seed flag exists.
  `name-free-atoms` (62): waits for wider-generators' step 2b. Tooling
  (54, 59, 61): no lane of its own; lane workers build it while CPU waits.
- **Shares** (`jobs/lanes.json`): wider-generators 35,
  genpack-product-depth 25, mechanic-count-curve 20, act1-content 10,
  main 10, filler 0 (the closed lane's 25 goes to the new lane, as the
  shares stood before the close moved it).

## genpack-product-depth step 1: the product player on the mutate bench, 200 starts x 2 seeds (on the owner's behalf, 2026-11-11)

Spec `docs/specs/genpack-product-depth.md`. `mutate_monsters.py` gains a
`product` player (two turns deep, line seed and stepped line, through
`depth_paired.run_guarded` from the patched start state); `genpack_cut.py
--player product` reads it.

- **200 elite starts x 2 seeds instead of x 4.** A smoke ran stepped
  two-turn fights at about 15 a thread-minute; x 4 would be about 6 thread-h
  a player, 12 for step 1 alone against the 18 cpu-h cap. Halving the seeds
  keeps every start, and starts pair across files. Alternatives: 100 starts
  x 4 (fewer distinct starts at the same cost); x 4 without step 2 (no seed
  spread for the go rule). Reversible: a rerun with more seeds adds them.
- **The random-world rows wait** until step 2 is read, and run only if the
  cap leaves room (descriptive in the charter).

## After 0898: the generated-pack net prices enemy mechanics built on atoms it never trained on; two charters amended (on the owner's behalf, 2026-11-11)

Job 0898 (wider-generators' fail-fast, `jobs/done/0898-genpack-cut.json`,
files `results/mutate/gen-wide-pns1-tsl1.json` and
`results/mutate/gen-wide-gp1-tsl1.json`, 675 official elite starts x 4
seeds, one turn deep @tsl1) passed: the seed-1 generated-pack net's pooled
cost on the 17 new held-out pairs is +1.59 (0.14) HP beyond parent, over the
1 HP bar, so the learn 0899 runs. The lane worker files the measurement; this
entry is what the navigator takes from it.

What the read says beyond its question. The generated-pack net trained on 18
mechanics over 4 triggers and 7 effects. None of the 76 new mechanics is in
its pool, and each carries a trigger or effect no generated enemy power in
its pool had. Against pack-net-scratch seed 1 (the same recipe without the
generated pool) it still cuts their cost: new held-out pairs 0.60 (0.03),
the 40 future training pairs 0.75 (0.03), the whole held-out trigger
Attacked 0.81 (0.03), close to the 0.76-0.81 it cuts on recombinations of
atoms it did see (`measurement/genpack-transfer@three-seeds`). The cut
fails on one kind of effect: Wound into the discard pile -0.11 (0.17) over
its 8 rows, Dazed into the draw pile 0.31-0.56, the Artifact rows -0.09 to
0.65 (OppCard-Artifact costs both nets about +10 HP). Effects that change a
number in the fight (Strength or Dexterity down on the player, Weak,
Vulnerable, Damage, Block) are cut 0.65-2.1. The wide grid's inputs describe
these atoms through columns other content already trains (Attacked's
trigger column by Flame Barrier, Wound's columns by the status cards Sentry
and the slimes add; spec `docs/specs/wider-generators.md`, Amendment 1), so
"never trained on" means never on an enemy power, not an empty column.

So the mechanism candidate 57 (`mechanic-count-curve`) was framed around,
"transfer to a new pair comes from having seen its atoms", does not explain
this: the transfer reaches atoms the pool never held. Two readings are left,
and they predict different things. (a) The net reads the enemy's power row
through its shared columns (owner, amount, the descriptive trigger and
effect columns): the generated pool taught it that such rows matter, so it
reads any row. (b) The net does not need the row: one-turn search plays the
power in the engine, and what the generated pool taught is to price the fight
states the powers lead to (a player with Dexterity below zero, stacked
debuffs, a monster that grew mid-turn), states official training never shows
(the same gap `leaf-blind-numbers` found for Strength below zero). Under (b)
deck effects stay uncut because their cost lands on later draws, past the
horizon, which is what the read shows. Zeroing the whole power row separates
the two: under (a) the cut falls, under (b) it stays.

Decisions:
- **wider-generators' step 2b gets a third ablation**: the whole generated
  power row zeroed, for the seed-1 generated-pack net only, on the 6 old
  held-out rows and 4 new number-effect rows (GE-Attacked-DexDown,
  GE-OppAttack-DexDown, GE-Attacked-Vulnerable, GE-TurnStart-StrDown),
  against its unablated files; the cut under ablation is read against
  pack-net-scratch's unablated file (the question is what the
  generated-pack net uses; pns as it plays stays the base). About 1 thread-h more.
  Read: the cut keeps two thirds or more of itself, reading (b); falls under
  a third, reading (a). Descriptive, like the rest of 2b.
- **wider-generators' cap 40 -> 48 cpu-h.** The charter's own plan costs
  more than 40: steps 2 reads 0896-0897 about 15.5 thread-h, the learn 0899
  about 16, step 3's reads on 100 rows plus cells, the pack headline and the
  k-4 worlds about 13, step 2b about 2.5. Extended once; end unchanged.
- **mechanic-count-curve's go is re-read, not re-scored.** Its rule stands
  (go at a held-out pooled cut of 0.6 or more at 2 se). A go now reads
  "6 generated mechanics give the cut", not "atoms carry it"; a fail reads
  "the count of mechanics matters". Added, descriptive and inside the cap
  (learn about 15, 0905 about 4, this about 3, of 27): the 6-arm on the wide
  grid's 17 held-out pairs and 11 Attacked rows with their parents at 675
  starts x 4 seeds, the starts and seeds of `gen-wide-pns1-tsl1.json`, cut
  against that file: does a 6-mechanic pool give the same reach to new
  atoms as the 18?
- **Candidate 63's step 1 is answered** (no CPU, from 0897-0898): rows with
  a trigger or effect outside the 18-mechanic grid that cost the
  generated-pack net 2 HP or more beyond parent exist (Attacked-DexDown
  +5.06, OppAttack-DexDown +3.71, Attacked-Damage +3.04, OppCard-Wound
  +3.03, Attacked-Artifact +2.82). Its two burst rows: GE-Attacked-DexDown
  (a number effect) and GE-OppCard-Wound (a deck effect), so the read also
  says whether a burst's head start from the generated base differs by kind.
- New candidates 64 (`state-coverage-scratch`) and 65
  (`genpack-product-net`) in the backlog.

Alternatives passed over: ablating both nets in 2b (doubles its cost and
asks what pns uses, a different question); opening a lane for reading (b) now (its probe
is the 2b arm; a learn before it would spend 15 thread-h on a guess);
closing mechanic-count-curve as superseded (its pool-size number is still
the cost of a custom-content recipe, and its learn is queued); leaving the
cap at 40 (the lane would close at the cap with step 3 unread).

## Candidate 63's burst rows: level at zero shot (on the owner's behalf, 2026-11-11)

The entry above ("After 0898") named GE-Attacked-DexDown and GE-OppCard-Wound
as candidate 63's burst rows. Replaced before any lane opened on them: on
Attacked-DexDown pack-net-scratch pays +26.34 HP beyond parent against the
generated-pack net's +5.06, and on OppCard-Wound +1.75 against +3.03, so a
cut of each base's own cost would compare bases that start far apart, and
the go rule's pooled cut would be one row's. The rows now chosen cost both
bases about the same zero-shot, so what differs after a burst is how fast
each adapts: GE-RoundEnd-Damage (a number effect on a trigger outside the
18-mechanic grid; pns +2.48, generated +2.26) and GE-Attacked-Wound (a deck
effect; pns +2.24, generated +2.44), one of each kind 0898 split on.
Alternatives: AttackLoss-Wound (+2.01 / +2.05, the generated cost on the 2
HP line); Attacked-StrDown (+6.35 / +2.08, apart like DexDown). The ready
charter in `docs/backlog.md` (entry 63) carries the rows.

## wider-generators step 3 reads queued within cap 48: new rows at 2 seeds, old rows at 4, seed-1 controls re-run (on the owner's behalf, 2026-11-11)

Step 2 passed its fail-fast (0898; `docs/research/generated-enemies.md`,
"Step 2 read"), so the learn 0899 runs and step 3's reads are queued behind
it. At 17.3 cpu-h used, the learn (about 14.5 thread-h at its earlier
siblings' pace) and step 2b (about 2.5) leave about 14 thread-h for step 3
under the cap of 48. So:
- **New rows (100-mechanic grid) at 2 seeds per start**, not step 2's 4
  (about 4.8 thread-h instead of 9.5). The go cut is read against the
  seed-1 generated-pack net's +1.59 (0.14) HP; at 2 seeds its se is about
  0.12, so 2 se stays under the 0.4 bar. `genpack_cut.py` means each
  start's seeds, so 2-seed and 4-seed files pair by start.
- **24 old rows at 4 seeds**, not 0809's 8 (about 1.7 thread-h).
- **Seed-1 controls re-run** for the one-turn cells and the pack headline
  (both @hpb0.01, as 0810 and 0815): `content/packs/act1-ironclad.json`
  changed after 0815 (turn-start split, pack version 2) and the rules with
  it, so 0815's file is no longer the same setting. The new net is read
  `--against` the re-run files.
- The k-4 random worlds take the new net's 24-row file as `--base`, as
  0843 took the seed-1 net's; compared descriptively with
  `results/mutate/rw-nd-gp1-k4.json`.
- `gauntlet.py play` now takes a glob in the net path (as
  `mutate_monsters.py --net` does), so these reads can be queued before
  the learn names its run folder.

Alternatives: 4 seeds on the new rows (the lane would pass its cap before
the headline read); skip the control re-runs and read against 0810/0815
(a rules change between the files would show up as the new net's effect);
ask for a higher cap (the navigator just set it).

## genpack-product-depth: step 1's real pace; step 2 on 100 starts (on the owner's behalf, 2026-11-12)

0907 (the product on the step-1 bench) ran far slower than its 90-minute
estimate. Its three workers run at 100% CPU and play about 22 fights a
minute. That is half the smoke test's pace (14 stepped fights a minute on
one thread; 7.3 per thread here), so step 1 costs about 13.4 CPU-hours,
not ~6.

Decided:

Step 2 (seeds 101 and 201, 0910/0911) re-queued at `--two-starts 100`
   (the first 100 starts, about two thirds elite) instead of 298: at the
   real pace the 298-start version costs another ~13.5 CPU-hours and the
   lane would end at ~27 against its cap of 18; at 100 starts step 2 costs
   about 4.5 and the lane about 18. The pooled read (genpack_cut) uses
   only the starts every file shares, so 0912 pools three seeds over those
   ~67 starts (se about 1.7x seed 1's on 200); 0909's seed-1 read keeps
   all 200. Alternatives: keep 298 starts and let the cap close the lane
   before 0912 (no verdict); one more seed instead of two (the go rule
   asks for three seeds); ask the navigator for a higher cap (charters are
   theirs; the wake at close says what was short). The 0909 reader re-sizes
   step 2 again if 0908's pace differs much from 0907's.

## Fractional amounts, spec decisions (owner, 2026-11-11)

Provisional, from `docs/specs/fractional-amounts.md` (interview
2026-11-11, confirmed with /build the same day):
- A fractional `k` goes in its own spec, built before potions.
- Fractions are written `"k": "a/b"`; whole numbers stay plain numbers.
- Game parity wins: truncation toward zero, as Java's `(int)` (the game's
  share-of-max-HP heals, read in the decompiled game; a negative fraction
  has no game case, so its rounding is our choice).
- Amounts resolve when their effect runs; amounts fixed when a monster's
  intent is chosen (Hexaghost's Divider) are out and kept as an idea.
- No net column for the new quantity or heal now.

## Potions, spec decisions (owner, 2026-11-11)

Provisional, from `docs/specs/potions.md` (interview 2026-11-11, confirmed
with /build the same day):
- Potions in the fight only; the gauntlet holds none (P2, the run layer,
  later).
- Game parity wins conflicts.
- Sacred Bark is in scope.
- Holding a potion is worth nothing for now (the heuristic and existing
  nets give it nothing); nets can read potions as opt-in rows.
- A potion is written in the card row format.
- Held potions are a list in one fixed order, at most 5; copies give one
  action.
- `potency` is the game's number, 0 for none; effects keep written amounts;
  Sacred Bark (`potion_potency: 2`) runs potions with potency above 0 at
  double.
- The net's potion rows show effective amounts and potency (Fire Potion
  reads 40 under Bark), and Bark's relic row shows `potion_potency`, so a
  start-state value can tell a Bark start from a plain one (owner: the run
  decision-maker must be able to value Bark).

## act1-content out of the active lanes; its jobs run at the default share (owner, 2026-11-12)

The owner (wake note, 2026-11-12 08:00): act1-content stays owner-led
(decision/act1-owner-led); the owner keeps the lane and builds it in owner
sessions. Take it out of the active lanes, so the launcher no longer starts a
lane worker for it (it started one at 07:39 on `idle:act1-content:rev59`, and
one at 07:24 on `ended:0925-series-speed`, both of which only marked the wake
handled). Owner sessions still queue jobs under lane `act1-content`, and those
jobs keep running without a share.

How it is done (on the owner's behalf, 2026-11-12; no code change):

- **The charter `lane/act1-content` is retired.** `health.py` lists as open
  lanes only active `lane/<name>` facts (`charters()`), and every lane-worker
  wake for a lane (`ended:`, `idle:`, `lane-cap:`, `lane-end:`, `lane-done:`)
  and the launcher's 4-hour lane backstop come from that list. With the
  charter retired, none of them fires for act1-content, and its jobs no longer
  count in the `ready` metric or lane CPU-hours. The retired value stays
  readable with `kb get lane/act1-content` for the owner's sessions.
  `lane/act1-content/step` and `/checkpoint` stay active: the owner's sessions
  write them, and without a charter `health.py` ignores them (except as
  progress for the stagnation metric, which is right).
- **`jobs/lanes.json` drops act1-content.** The runner gives a lane missing
  from lanes.json `DEFAULT_SHARE` 10 (`scripts/jobs.py`), and `jobs.py add`
  accepts any job of a lane with share above 0, so owner jobs queue and run as
  before, at the same weight they had. Its 10 points go to wider-generators,
  the one open lane whose last checkpoint passed (`step2-failfast`):
  wider-generators 45, genpack-product-depth 25, mechanic-count-curve 20,
  main 10, filler 0.
- **Lane workers leave it alone at closes too.** No lane worker closes or
  reopens act1-content: the operating.md rule that the next free project slot
  reopens an unfinished Act 1 lane stays suspended while the owner leads it
  (decision/act1-owner-led); reopening it as a role lane is the owner's call.

Alternatives passed over: share 0 in lanes.json (makes it a filler lane:
`jobs.py add` then refuses non-resumable jobs over 20 minutes, which breaks
the owner's queueing); keeping the charter and marking its step `done` (fires
`lane-done:` and a lane-worker close); changing `health.py` to skip parked
lanes (code, not the navigator's to edit, and not needed).

## Learns 0899 and 0904 re-queued at mem_gb 2.5 (on the owner's behalf, 2026-11-12)

The machine ran no job from 07:08 to 08:30 on 2026-11-12 (cpu red), and
only one 8-minute job since 06:53, while 18 jobs waited. Every lane's chain
was headed by a job that could not start: 0904-learn (mechanic-count-curve)
and 0899-learn (wider-generators) reserved mem_gb 5.5, so the runner wanted
6.5 GB free, which was rarely free; 0908 (genpack-product-depth,
mem_gb 4.0) and 0822 (test-full) wanted 5.0. This is the same trap as
decisions "genpack learns re-queued at an admissible mem_gb" (2026-11-11):
`jobs.py add` warns `mem_gb_low` against the last learn's `peak_gb` (6.63),
but that peak is the working set with the mapped feature-cache pages, and a
40k learn commits about 1 GB (`measurement/learn-memory@40k`); 0749-0848
ran at mem_gb 2.0-2.5 without trouble.

Done: 0899 re-queued as **0926-learn** (same command, pin 1abac89e, if
passed 0898, mem_gb 2.5, given the reservation with `first`); 0904
re-queued as **0927-learn** (same command, pin 3e258d99, mem_gb 2.5,
`--after 0926` so two 5-6 GB working sets never start together); 0899 and
0904 cancelled before they ever ran; their dependents re-pointed (0905
`--if-passed 0927`; 0916, 0917 `--after 0926`; 0918 `--after 0926,0914`;
0919 `--after 0926,0915`). The wide-pack learn goes first: wider-generators
holds the larger share (45) and its only passed checkpoint, and has the
longer chain behind its learn (0916-0921, about 4.5 h at 3 threads). Once a
learn runs, the runner reserves its measured peak, so nothing heavy is
admitted on top of it.

Alternatives passed over: wait (never fits); the 0904 learn first (the runner's tie-break by lane name, no
value reason); both learns at once (two 6 GB working sets would page);
fewer threads (the memory comes from the 40k-game data and its cache, not
the threads). Reverse: cancel 0926/0927 and queue them again at a higher
mem_gb. The cause in the tooling (a `peak_gb` that counts file-backed
pages, and the `mem_gb_low` warning built on it) is backlog candidate 43,
re-rated in this run.

## genpack-product-depth: seed-1 cut at the bar, step 2 at 1 thread; the stalled 0908 hours left out of the cap (on the owner's behalf, 2026-11-12)

Read of 0907 (`results/mutate/gpd-product.json`, generated-enemies.md
"Product depth"): the product's held-out pooled novelty cost two turns deep
is +1.46 (0.33) HP over 200 elite starts x 2 seeds, +2.05 (0.59) on the
first ~67, which step 2 shares. The fail-fast (under 1.0) does not fire.

1. **Step 2 re-queued at 1 thread: 0929 (seed 101), 0930 (seed 201),
   `--two-starts 100`, pin d2e6eb5.** I first judged step 2 unable to
   decide (a resampling guess put the cut's se at 0.35-0.5 on ~67 starts)
   and planned to drop it. The seed-1 read (0928) showed otherwise: cut
   0.87 (se 0.23), gain +1.77 (0.48) HP, parents -0.10 (0.41), so cut - 2
   se = 0.399, right at the go bar, and 0.51 (0.17) without AttackLoss-Weak
   (genpack -3.74 (1.40) there). A result at its bar needs the other seeds,
   and they fit the real budget. 1 thread each (peak 0.88 GB at 1 thread,
   3.1 at 3) so both fit in the free memory; ~130 min
   each, ~4.5 CPU-h together. The pooled read is by hand (the fixed
   `genpack_cut.py`; 0922-0924's pin has the old one). Alternatives: drop
   step 2 and close on a single-seed lead (a single seed is a lead, never
   a result); 3 threads (waits for more free memory); all 200 starts (~13 more CPU-h, past the cap).
2. **0908's rest at `--two-starts 100` (job 0928, 1 thread).** 0908 played
   fights 0-931 of 2800 (about the first 67 elite starts, start-ordered)
   by 09:39, then wrote nothing until the 12:08 reboot killed it. 0928
   resumes from the partial file, so only a few fights play. 0909 failed on
   0908's heuristic-only file (KeyError 'product'); `genpack_cut.py` now
   reads files whose deep player played fewer starts (commit 46dd525, test
   `test_product_player_fewer_starts`); without it 0924 would have failed
   the same way.
3. **The cap.** `health.py` books 17.7 of the lane's 18 CPU-h. 7.4 of
   them are 0908's 09:39-12:08 stall at 3 threads, no fight finished (0927-learn ran beside it at up to 5.2 GB, likely paging). The real use is about 10.3. I
   marked `lane-cap:genpack-product-depth` handled (`health.py woke`) so
   that 0928 crossing 18 does not start a session to close the lane over
   hours that did no work; real use at the end of step 2 is about 15 of 18. Alternatives:
   let the cap wake close it (no verdict, the cap spent on a stall);
   teach `health.py` to leave out stalls (needs log-quiet history it
   doesn't keep). Reverse: delete that key from `jobs/wakes.json`.

## After the big-picture review of 2026-11-12: wider-generators closes after step 2b; three probes queued; machine-throughput and wide-recipe-confirm readied (on the owner's behalf, 2026-11-12)

The review (`docs/research/big-picture-2026-11-12.md`) and the navigator's
early look at `wider-generators`' step-3 files (0916, 0917; the lane's own
read 0921 is still pending, so nothing here files a measurement): one seed
of the wide recipe leaves +0.25 (0.15) HP beyond parent on the new held-out
pairs (cut 0.94 (0.04) against pack-net-scratch s1) and +0.10 (0.15) on the
old 6 held-out pairs.

1. **`lane/wider-generators` amended: the lane closes only after step 2b's
   reads**, on the seed-1 generated-pack net (as chartered) and on the wide
   net (the same three ablations on the same rows), whatever step 3's
   verdict. Why: candidates 62 (`name-free-atoms`) and 64
   (`state-coverage-scratch`) are each decided by that ablation, the review
   found nothing scheduling it, and the lane holds the code and the files.
   About 2.5 thread-h inside the cap (38.6 of 48 booked). Alternatives: a
   separate probe after the close (a second session has to re-learn the
   ablation code); leave 2b optional (it has stayed unbuilt since 11-11).
   Reverse: re-set the charter without the sentence.
2. **Probes queued in lane main** (the backlog's probe sheet): 0931-0933,
   `genpack-yardstick`, the wide net, pack-net-scratch s1 and the 10-29 net
   @tsl1 on the owner's yardstick rows (stage A singles and boon + bane
   pairs, 675 elite starts x 2 seeds, about 3.5 thread-h): no
   generated-pack net has been read on `decision/goal1-yardstick`'s own
   rows; 0934, the wide net on the generated-power bench (about 0.2
   thread-h), the review's first check for a player-side generated pool
   (candidate 67). Alternatives: wait for the lane's close and charter the
   yardstick read (the CPU is idle now, cpu red 111 runs); fold it into 65
   (it decides whether 65 carries the yardstick). Reverse: cancel the jobs.
3. **Ready charters, in order**: 66 `machine-throughput` for the first free
   project slot (its parts were filed by three reviews as "a lane worker
   builds it while its lane waits" and never built), then 65
   `wide-recipe-confirm` for the next (seeds 101 and 201 of the wide
   recipe: a single seed is a lead); 63 `genpack-burst-base` stays the
   exploration slot's, with the wide net as a third base on
   GE-RoundEnd-Damage (the one row no recipe cuts) and cap 20.
   Alternatives passed over: 65 first;
   67 player-side generated pool (a long shot until a cost shows, by the
   trade-off rule); 69 clears statistic as a lane (no CPU, and no goal-2
   candidate is in flight to decide).
4. **Not adopted from the review:** recording that goal 2's product may
   train on all official content (direction 9) touches "Headline card pool
   and choosers after Act 1", an owner decision (2026-11-09);
   left as a notice for the owner. Lending goal 2's CPU share to goal 1
   is a `docs/direction.md` change, the owner's; a notice too.

## mechanic-count-curve: 0927-learn re-queued as 0935 at the same pin (on the owner's behalf, 2026-11-12)

0927-learn (the 6-mechanic seed-1 learn) ended at 12:13 with exit
1073807364 (terminated) at effects epoch 2: the 12:08 reboot killed it, as
    it killed 0908. Its epochs had slowed
from 4.5 to 1.9 batches/s beside 0908 at 3.2 GB, which
    looks like paging. Re-queued as **0935-learn**: same command, same pin
3e258d9 (main's engine and features have moved since, so the old pin keeps
the net comparable with the pack-net-scratch and 18-mechanic nets it is
read against, and with 0905/0906, which are pinned there too), mem_gb 2.5,
6 threads. Its dataset (7997b07edf15) is cached, so only training reruns.
0905 now waits on `--if-passed 0935` and is unparked with 0906.
Alternatives: pin to main's HEAD (a new engine under one arm only, the
read would mix two changes); fewer threads (the slowdown was memory, not
threads). Reverse: cancel 0935 and park 0905.

## Words: "pool" for the game's lists, "set" for ours (owner, 2026-11-12)

A *pool* is a list the game itself draws from (a class's card pool by
rarity, the colorless pool, the potion pool, the boss pool); a *set* is a
list chosen for training or testing (a training set, a held-out set, the
gauntlet's offer set). A list that copies a game pool whole is that pool.
Rule in `docs/extending.md` "Pool or set"; `configs/card-sets.json`
already says "sets". Scope: new writing now; live docs where they define
the word (`docs/extending.md`, README "Card sets"); code names when a
change touches them; logs and past results stay as written. Alternative
passed over: one rename of every doc and code name now (about 500 code
uses, many in CLI flags and cached data keys, for no change in behaviour).

## After genpack-yardstick: the wide pool moves the owner's yardstick; 70 joins 65, 67 retired (on the owner's behalf, 2026-11-12)

The navigator read 0931-0933 (`docs/research/genpack-yardstick.md`,
`measurement/genpack-yardstick@wide-s1`): on the owner's yardstick
(`decision/goal1-yardstick`) the wide net's pooled novelty cost over
sharp2, thorns2, ritual2 and weakhit1 is +0.92 (0.19) HP against
pack-net-scratch s1's +4.03 (0.28): the probe's go. What is left is
Thorns 2 (+4.20, level with the 10-29 net), on Attacked, the trigger the
wide pack holds out whole.

1. **65 `wide-recipe-confirm`'s charter** carries the yardstick rows in
   every seed's reads and as a go and fail condition (pooled cost at most
   half pns1's at 2 se). Alternative passed over: the yardstick as a
   descriptive column only; it is the owner's standing number for goal
   1, so a recipe that loses it should not be confirmed as the base.
2. **New candidate 70 `wide-full-triggers`** runs as step 2 of 65's
   charter: one seed-1 learn of the wide pack with the Attacked and Wound
   mechanics trained, read on the yardstick and the 23 held-out pairs; it
   picks the recipe 65's last seed trains. Cap 48 -> 60 cpu-h (estimate
   about 43), end 2026-11-19. Alternatives passed over: 70 as its own lane
   (it shares 65's controls
       and reads), and 70 instead of a wide seed (seed 101 of the wide recipe
   is still the confirmation every held-out-trigger number needs).
3. **67 `player-genpack-scratch` retired** on its own no-CPU probe, run
   this session: every net is level with or ahead of the heuristic on the
   52 non-recurring generated player-power cells, so no cost to cut.
   0934 (the wide net on that bench) stays queued as a descriptive
   retention read (0.2 thread-h).
4. **Probe queued** in lane main: 0939-0941, the yardstick for the three
   18-mechanic generated-pack nets at the same pin (c5bf088), about 2.5
   thread-h on an idle CPU: whether the gain replicates over seeds
   without the wide grid. It makes no pending job worthless.
5. `measurement/genpack-transfer@seed1` retired as superseded by
   `@three-seeds` (STATUS.md was over its cap); the facts citing it were
   re-pointed or confirmed.

## Lane mechanic-count-curve closed (2026-11-12)

Lane worker, at its CPU-hour cap (on the owner's behalf). **Outcome:
capped before its checkpoint read finished; no result yet.** Step 1 (the
6-mechanic training pack, `docs/specs/mechanic-count-curve.md`) was built.
Step 2's learn 0935 finished (exit 0; net
`runs/2026-11-12-genpack6-40k-s1-r1-2d5163e/model.pt`, val MSE 0.172). The
checkpoint read was still running when the cap fired: 0905 (the 6-arm
@tsl1 on the 24 GE rows, out `results/mutate/gen-gp6-1-tsl1-all24.json`)
at 366 of 1000 starts, slowed to about 0.06 starts/s by a full CPU, with
0906 (genpack_cut against `gen-pns1-tsl1-all24.json`) queued after it.
CPU: about 29 cpu-h of the 27 cap at the close, about 18 of them spent by
0927, the first learn, which the 12:08 reboot killed after 3 hours
(decisions "mechanic-count-curve: 0927-learn re-queued as 0935"). 0905
adds about 8 more by its end, about 37 in all. The descriptive wide-grid
read (charter rev 2) did not run.

Decided:
- **0905 and 0906 run to their end after the close.** The learn's CPU is
  spent, and the read is what it was for. Alternatives: cancel 0905 and
  close with no number (saves about 8 cpu-h, throws away the learn); keep
  the lane open past its cap until 0906 (the cap is the navigator's). The navigator is
  woken on `job:0906-genpack-cut` (on-close `wake always`) and reads 0906
  against the charter's rule: go if the held-out pooled cut is 0.6 or
  more at 2 se (6 generated mechanics give the cut), fail under 0.4 (the
  count of mechanics matters), between: a seed-101 learn of the 6-arm
  decides. The 18-arm's cut on the same split is 0.81 (0.02).
  It then files `measurement/mechanic-count@six-arm` from 0906's record.
- **Share 20** moves to genpack-product-depth (2 jobs running; it rises to
  45). wider-generators keeps 45 and has nothing queued.

**Reopen if:** 0906's pooled held-out cut falls between 0.4 and 0.6 (one
seed-101 learn of the 6-arm, about 9 thread-h at the 0935 pace, decides),
or under 0.4 (a 12-mechanic arm on seed 1 reads the curve's middle), and
the count of mechanics a custom-content pool needs is still an open
question then (wider-generators' width result may answer it first). On a
go there is nothing to reopen; the wide-grid descriptive read
(the 6-arm on `gen-wide-pns1-tsl1.json`'s rows, about 3 thread-h) is the
only part left, worth it only if 53's width question is still open.

## Lane genpack-product-depth closed (2026-11-12)

Outcome: **between**, on its one pooled read (jobs 0928, 0937, 0938;
`docs/research/generated-enemies.md`, "Step 2 pooled read and verdict").
Two turns deep, both players with the product's flags, the generated-pack
nets (seeds 1, 101, 201) cut the product's held-out novelty cost of +2.05
(0.59) HP by 0.60 (starts se 0.20, seed spread 0.15), gain +1.23 (0.47)
HP, parents -0.39 (0.48) HP; without the noisy AttackLoss-Weak row the
cut is 0.27 (0.19). Go needed cut - 2 se >= 0.4 (0.20 here); fail a cut
under 0.2 or under 2 se (3 se here). So the recipe's transfer survives the
second turn at about half its one-turn strength (0.76), on a cost the
second turn already shrank from about 4 to about 2 HP; OppCard-PlainDamage
stays uncut at both depths. The k-4 random-world rows did not run.

Reading of "0.4+ at 2 se" (on the owner's behalf): the lower bound,
cut - 2 se >= 0.4, as `genpack_cut.py` and the step-1 read ("at the bar",
0.399) applied it. Alternative: a mean of 0.4 or more and 2 se from zero
(as decisions "cuts the target's cost by half at 2 se" read a halving),
which would call this a go; not taken, since the rule was applied as a
lower bound all through the lane and the read without AttackLoss-Weak
fails by either reading.

CPU-hours: `health.py` books 32.8 against the cap of 18; about 7.4 of
them are 0908's stall and about 2 the stuck last hour of 0929/0930
(decisions "genpack-product-depth: seed-1 cut at the bar, ..."), so
about 23 did work: over the cap, mostly from step 2 running at 1 thread
beside paging learns.

**Reopen if:** (a) a read on more starts (all 200 elite starts, or 1000
at one turn's starts count, about 13+ CPU-h) is cheap enough, e.g. after
machine-throughput's caches land, and would settle 0.27 against 0.60; or
(b) a recipe or feature aimed at OppCard-PlainDamage (damage per card
the player plays), the one row neither search nor the recipe cuts,
exists to be read two turns deep; or (c) the wide net (wider-generators)
or a later pack net is the candidate for the product's fighter on new
content (`decision/crossed-player-lead`), when this bench is its
two-turn check.

## After 0906 and genpack-product-depth's close: lanes machine-throughput and genpack-burst-base opened (on the owner's behalf, 2026-11-12)

Navigator, woken by genpack-product-depth's close (on-close `wake always`),
with mechanic-count-curve's left-over read 0906 finished during the run.


1. **mechanic-count-curve's read: go on one seed.** 0906: the 6-mechanic
   pack's net cuts the 6 held-out pairs' cost 0.88 (0.02), against the
   18-arm's 0.81 on seed 1 (`measurement/mechanic-count@six-arm`,
   `docs/research/generated-enemies.md`, "Mechanic count"). The lane's
   reopen conditions (a cut of 0.4-0.6 or under 0.4) do not hold; its
   portfolio fact is re-set with the read. What it changes: a generator
   has to cover atoms, not supply many pairings, so the wide recipe's
   worry that each mechanic gets a third of the games carries little
   weight (65 stays likely), and a new atom, which no covering pack can
   supply, is where goal 1's zero-shot cost now sits (whole held-out
   trigger Attacked +0.52, GE-RoundEnd-Damage +2.30 on every recipe):
   that is 63's question. Alternative passed over: a seed-101 6-arm learn
   to confirm (about 6 thread-h): the wide net's 0.98 on the same rows
   already says count barely matters from 6 to 58; nothing waits on the
   difference.
2. **Lane machine-throughput opened** (project; candidate 66's ready
   charter, as written; first free project slot). The CPU booked about 28%
       of the machine's threads this evening (`cpu` red for 114 health runs), 0929/0930
   died beside a paging learn, the learn's dense feature cache (6.8 GB
   peak) keeps learns out of the queue while two reads run. Rated likely to build
   (a)-(c) and (e), even on (d); about 10 thread-h, cap 15, end
   2026-11-16. On-close `wake on fail` (a go changes no ranking; the
   parts that land are used by every lane).
3. **Lane genpack-burst-base opened** (exploration; candidate 63's ready
   charter, as written; the exploration slot, empty since
   mechanic-count-curve closed). Rated even, about 15 thread-h, cap 20,
   end 2026-11-20, on-close `wake always`. Goal 1's own number (games to
   adapt) has had no lane since share-curve (11-09), and 1. puts the
   remaining zero-shot cost on new atoms, which only games teach.
4. **Shares** (`jobs/lanes.json`): wider-generators 40 (its last
   checkpoint passed and step 3's reads wait on its session),
   genpack-burst-base 30 (bursts and reads, CPU-bound), machine-throughput
   20 (mostly code, one confirming learn), main 10, filler 0.

Alternatives passed over for the two slots: 65 `wide-recipe-confirm` (its
charter opens on wider-generators' close with a step-3 go, and that lane
still owes step 2b; opening it now would run two lanes on the same nets);
68 `multi-hook-zero-shot` (waits for a recorded wide base); 69
`clears-statistic` (no CPU, goal 2's ruler; stays on the list for a slot
with nothing queueable); a seed-101 6-arm (see 1.). Only two lanes open
beside wider-generators: three is the portfolio's upper end.

End dates past 2026-11-14: both charters keep the dates they were written
with (11-16, 11-20). 
Reverse: close either lane with a decisions entry; the charters' backlog
entries stay.

## genpack-burst-base amended before its first session: GE-OppCard-Artifact in place of GE-RoundEnd-Damage (on the owner's behalf, 2026-11-12)

Navigator, the same run as the entry above. Checking 63's rows against the
wide pack's split (`mutate_monsters.WIDE_SPLIT`): the wide pack trains nine
RoundEnd mechanics, GE-RoundEnd-PlainDamage among them, yet every RoundEnd
row costs about 2 HP on all three nets, trained or not (from
`results/mutate/gen-wide-{pns1,gp1,wp1}-tsl1.json`, HP beyond parent:
RoundEnd-Damage +2.48 / +2.26 / +2.30, RoundEnd-PlainDamage +2.57 / +1.88 /
+1.90, RoundEnd-Weak +2.89 / +2.24 / +1.72, RoundEnd-Dazed +2.72 / +2.15 /
+1.52). The search sees the round end in the engine (`search.rs` takes the
leaf after the monster phase; `state.rs` runs RoundEnd hooks before the
monster rolls), so the cost is not blindness to the trigger: it is damage
that comes back every round, priced past the turn
(`cause/novelty-is-horizon`), which 40k games of nine RoundEnd mechanics
moved by 0.2-0.7 HP. A burst of 11 or 33 games is then unlikely to cut it
on any base, and the lane's fail rule ("within 0.1") would fire for that
reason, not for the base comparison it was built to make.

Decided: the row GE-RoundEnd-Damage is replaced by **GE-OppCard-Artifact**
(pns1 +9.92 (0.61), the 18-mechanic net +10.82 (0.56), the wide net +0.29
(0.26) HP beyond parent): Artifact is an effect no generated power in
either base's pool carried (a new atom for both as a hook's effect; Three
Sentries start with Artifact, so its status column is trained, as Flame
Barrier trains Attacked's), both bases pay about the same
zero-shot (no head start), the wide net's cut shows games can teach it, and
its 10 HP cost reads with more power than a 2 HP one. GE-Attacked-Wound
(the deck effect on a new trigger) stays. The wide net's third-base arm
goes (it existed only for GE-RoundEnd-Damage, and the wide net already cuts
OppCard-Artifact zero-shot): about 10 thread-h, cap 20 -> 15 cpu-h.
Alternatives: keep RoundEnd-Damage beside it as a third row (about 3
thread-h more for a row that probably reads level on both bases;
descriptive at best); GE-OppAttack-DexDown (pns1 +26.81 against the
18-mechanic net's +3.71: a head start of 23 HP would decide the read before
any burst); GE-Attacked-Damage (+9.34 against +3.04, the same problem). The
RoundEnd family goes to the backlog as a finding (open question 2), not a
lane. Reverse: re-set the charter with the old row.

## The real-game bridge and the showcase site (owner, 2026-11-12)

Owner, in session:

- A bridge between the real game (StS1 with ModTheSpire, BaseMod and
  CommunicationMod) and the engine is written and tested offline, against
  the mod's documented state format, with no game running while the queue
  is busy. Scope: the AI plays fights and card rewards; the human clicks
  the map, events, shops and rest sites; content the engine doesn't load
  (most relics and potions) hands that fight to the human instead of
  guessing. The player for the real game is picked by one read on the
  real-content setting (the product net against the pack-trained net),
  queued as an ordinary job.
- Live contact with the real game happens with the job runner stopped:
  the machine can't run the game and the automated setup at once (CPU and
  memory).
- A showcase website for StS players, written by hand. Not generated from
  the repo: results from different periods used different rulers (rules
  versions, yardsticks, controls), so each period is told in its own terms
  and every number is quoted beside the setting it was measured on. If the
  bridge isn't ready, the site ships without its real-game section.
- After that: the final training run, then whatever is left of the bridge.

## After genpack18-yardstick: 65 re-chartered without 70; 70 a long shot (on the owner's behalf, 2026-11-12)

Navigator, woken by job 0941 (the last of 0939-0941). Read
(`docs/research/genpack-yardstick.md`, "The 18-mechanic nets on the
yardstick"; `measurement/genpack-yardstick@18-seeds`): the three
18-mechanic generated-pack nets pool +0.96 / +2.27 / +2.01 HP on the
owner's yardstick against pns1's +4.03 and the wide net s1's +0.92: the
probe's verdict is between (only seed 1 at most half pns1's at 2 se; all
far from pns1). Three things follow.

1. **Seed 1 was the best seed of both recipes**, so the wide grid's
   yardstick edge over the 18 mechanics is not shown. 65
   (`wide-recipe-confirm`) stays the next project charter, rated likely on
   the grid and even on the yardstick's go bar, and now reads the wide
   seeds' yardstick against the 18-mechanic three-seed pool too
   (descriptive).
2. **Thorns 2 is seed noise at one learn.** The 18-mechanic seeds spread
   2.45 / 6.28 / 4.62 HP on thorns2, so 70's pick rule (one learn of the
   full-trigger pack, thorns2 at most half the wide s1's +4.20 at 2 se)
   would be decided by the seed. Decided: 70 leaves 65's charter and falls
   to a long shot; 65 trains seeds 101 and 201 of the wide recipe (about
   34 thread-h, cap 60 -> 50, end 2026-11-19 -> 2026-11-20, no code step).
   Alternatives: keep 70's arm with three seeds (about 27 thread-h more,
   for a row whose gap is not shown); keep it at one seed as descriptive
   (about 9 thread-h for a number inside the noise). Reverse: re-add the
   step to the charter.
3. **Ritual 2 is repaired by every 40k from-scratch net** (pns1 -0.22,
   the 18-mechanic seeds -0.33 to -1.02, the wide net -1.07, against the
   10-29 net's +1.68 (0.35)). `cause/novelty-is-horizon` is re-set: its
   "Ritual 2 stays unrepaired by games" held for the 10-29 net only. Which
   part of the recipe does it is not proposed as a probe (every later base
   uses the recipe; backlog, *ritual-repair-source*).



Facts: `measurement/genpack-yardstick@wide-s1` merged into `@18-seeds` and
`measurement/queue-backfill-replay` retired into its portfolio fact
(STATUS.md over its cap).

## wider-generators closes at step 3, 2b leaves it; the RoundEnd fix becomes 65's step 0 (on the owner's behalf, 2026-11-13)

Navigator.

1. **wider-generators closes on step 3's checkpoint (0945), without step
   2b.** 2b (trigger, effect and whole-row zeroing on both nets) needs an
       evaluator option not yet built, and its reads (about 5 thread-h) pass the lane's cap (44.6 of 48 cpu-h).
   Its only consumers are candidates 62 and 64, both long shots. It moves
   to the backlog's probe sheet as `column-zeroing`, read when the option
   exists. Alternatives: extend the cap to 54 and hold the lane open until
   the build (keeps the slot from 65 for a descriptive read); drop 2b
   entirely (loses 62/64's decider). Reverse: re-add the step and the cap.
   `lane/wider-generators` re-set without 2b.
2. **A generated `RoundEnd` power is invisible to every net**
   (`docs/research/generated-enemies.md`, "RoundEnd rows: the power is
   invisible to the net"; `cause/roundend-blind`): the encoder writes
   `RoundEnd` hooks only as the opt-in `countdown` kind, which no net
   turns on. That's why nine trained RoundEnd mechanics cut nothing and
   every RoundEnd row costs about 2 HP, as untrained turn-trigger damage
   does on pns1. Decided: candidate 71 (`roundend-rows`: write a
   `RoundEnd` hook that isn't a pure `ReduceSelf` countdown as a
   `triggered` row, and count it in `is_hook_power`; no official input
   changes, the product net's bytes the same by `series_check`) becomes
   step 0 of 65 (`wide-recipe-confirm`), so the base net every later
   goal-1 step builds on can see every power it trains on. 65's step 0
   relearns seed 1 with the fix (about 6 thread-h) and reads it on the
   wide grid's rows (about 4); seeds 101 and 201 then train on the fixed
   encoding if step 0 passes, else on the old one. 65's cap 50 -> 66,
   end stays 2026-11-20. Alternatives: turn `countdown` on in the
   learn's `row_kinds` (no code, but +2.8 rows per state from the
   official debuffs, the memory cost that made the kind opt-in); keep 65
   as chartered and test 71 later as its own lane (the base net
   confirmed would be one that can't see a twelfth of its pack). Reverse:
   65's charter without step 0; the code change is one filter.


## Correction to the entry above: 65 with step 0 is about 51 thread-h, cap 76 (on the owner's behalf, 2026-11-13)

The entry above counted step 0 at about 10 thread-h (the learn and the
grid read) and left out that a passing step 0 makes seed 1's remaining
reads (old rows, yardstick, cells, headline, about 7) part of the
three-seed pool. With step 0 passing 65 is about 51 thread-h (three
fixed seeds at about 17 each), 44 if it fails; cap = 51 x 1.5 = 76, not
66. The backlog's ready charter carries cap 76. Reverse: as above.

## Lane wider-generators closed (2026-11-13)

Lane worker, on 0945's end.

- **Outcome: go** (checkpoint `step3-go`, `lane/wider-generators/checkpoint`
  rev 2; `docs/research/generated-enemies.md`, "Step 3 headline and
  verdict"). A from-scratch net trained on the 100-mechanic wide pack
  (seed 1) cuts the zero-shot novelty cost against the seed-1
  generated-pack net: unseen pairings 0.84 (0.09), the whole held-out
  trigger Attacked 0.51 (0.16), the whole held-out effect Wound 0.95
  (0.15). Official play within the bars: old 24 rows not worse, one-turn
  cells -0.25 (0.55) HP, post-C6 pack headline -0.80 (1.05) HP at n 500.
  One seed; the headline's held-out half loses 8.4 points of clears
  (boss deaths), a lead for candidate 65's seeds, not a finding.
  RoundEnd rows stay uncut (`cause/roundend-blind`, now 65's step 0).
- **CPU:** 46.7 of 48 cpu-h (opened at about 26 thread-h predicted, cap
  40, raised to 48 for step 3's reads). Step 2b (column zeroing) left the
  lane unrun (decisions "wider-generators closes at step 3"); it is the probe sheet's
  `column-zeroing`.
- **Reopen if:** candidate 65's seeds 101 and 201 on the wide recipe
  lose on the pack headline's held-out half at 2 se pooled (then the
  wide pack's price on official play is real, and a lane on its shares of
  generated fights against official ones has a question); or
  `column-zeroing` shows the whole held-out trigger's remaining cost
  (0.52 HP) sits in the trigger's name column (then a wider trigger set,
  or trigger features by effect instead of by name, is the next block).
- **On close:** the charter says `wake always`: the navigator is woken;
  the slot stays empty for it (65's ready charter names this slot, the
  navigator opens it). The lane's share 40 moves to genpack-burst-base
  (30 -> 54) and machine-throughput (20 -> 36), in proportion.

## Lane wide-recipe-confirm opened (on the owner's behalf, 2026-11-13)

Navigator, woken by `wider-generators`' close on a go (decisions "Lane
wider-generators closed (2026-11-13)"). 

- **Opened:** candidate 65 (`wide-recipe-confirm`) with 71
  (`roundend-rows`) as its step 0, from its ready charter in
  `docs/backlog.md` (decisions "wider-generators closes at step 3" and its
      correction): the RoundEnd encoding fix and a seed-1 relearn on it, then
  seeds 101 and 201 of the wide recipe, read on the grid, the old rows,
  the owner's yardstick, cells and the pack headline. Rated likely on step
  0 and on the grid, even on the yardstick's go bar. About 51 thread-h
  (44 if step 0 fails), cap 76, end 2026-11-20, kind project, on-close
  wake always. The close's reopen condition (the headline's held-out half
  at 2 se over seeds 101 and 201) is read from this lane's headline reads.
- **Passed over:** 68 `multi-hook-zero-shot` (even; it builds on the wide
  base this lane records); 72 `blind-row-kinds` (an audit in code, no CPU;
  a lane worker can take it while this lane's learns run); 69
  `clears-statistic` (no CPU, goal 2's ruler, the fallback for a slot
  with nothing queueable).

- **Shares** (`jobs/lanes.json`): wide-recipe-confirm 40,
  genpack-burst-base 30, machine-throughput 20, main 10, filler 0 (the
  shares before the close's proportional split; the new lane holds the
  goal-1 base every later step builds on). Reverse: close the lane and
  restore 54/36.

## wide-recipe-confirm: three-seed control pool first, step 0 waits for the line (on the owner's behalf, 2026-11-13)

- **Situation.** Step 0
      (the RoundEnd row: code, a spec and a build) waits.
  The charter reads the wide recipe's three seeds against pack-net-scratch
  s1 "and its s101/s201 files where they exist"; on the wide grid only the
  s1 file exists, so every seed's cut would carry pns1's own seed luck.
- **Decision.** Queue the two missing controls now (0960, 0961: pns s101
  and s201 @tsl1 on `gen-wide`, the command of 0897, about 8 thread-h
  each), pinned to 817da2e, before the RoundEnd fix, so they match
  `gen-wide-pns1-tsl1.json`. Step 0 is specced and built later.
- **Alternatives.** Leave the CPU to the other lanes and wait (the ready
  check is red, the machine would sit part-idle); queue seeds 101 and 201
  of the wide recipe on the old encoding now (pre-empts step 0's verdict,
  which decides their encoding). Reverse: cancel 0960/0961 while pending;
  once run, the files only add to the control pool.

## Lane genpack-burst-base closed (2026-11-13)

Lane worker, on 0959's end.

- **Outcome: go** (checkpoint kill-fast 11-game read,
  `lane/genpack-burst-base/checkpoint`; `docs/research/generated-enemies.md`,
  "Pack-net-scratch base, 11 games, and the checkpoint";
  `measurement/gbb@g11`). Joint 11-game bursts (share 0.9, @tsl1, three
  seeds) on GE-OppCard-Artifact and GE-Attacked-Wound: the generated-pack
  s1 base cuts 0.60 (0.12) of its pooled zero-shot cost, pack-net-scratch
  s1 0.10 (0.06); gap 0.49 (0.14), parents +0.14 and +0.25 HP. All of the
  gap is Artifact (a new effect on an old trigger): gp cuts +5.29 HP,
  pns gets worse (-1.59, every net); on Sentries, where both bases pay
  about the same, gp +4.98 to +12.31 against pns -3.57 to +3.20. Wound (a
  deck effect on a new trigger) is level: both cut all of it. One base
  seed per recipe: a lead for goal 1's games-to-adapt quote, not yet a
  result. The 33-game arm was for the between case and is not run.
- **CPU:** 2.5 of 15 cpu-h (predicted about 15 thread-h, rated even; the
  backlog's open-lanes line says cap 20, the charter and `health.py` 15).
- **Reopen if:** a second base-seed pair (generated-pack s101 against
  pns s101, the same two rows and reads, about 2.5 cpu-h) is wanted to
  turn the lead into goal 1's quote; or 65's step 0 makes RoundEnd rows
  visible, so GE-RoundEnd-Damage (dropped from this lane as blind) becomes
  a new-atom row a burst can be read on; or a custom mechanic on a new
  effect costs a recorded base 2 HP or more after a short burst.
- **On close:** the charter says `wake always`: the navigator is woken
  with the outcome; the slot stays empty for it. The lane's share 30
  moves to wide-recipe-confirm (40 -> 60) and machine-throughput
  (20 -> 30), in proportion. Neither lane has a job queued (both wait on
      code); the first ready candidate (72,
  blind-row-kinds) starts with a test, no CPU job, so none is queued.

## After genpack-burst-base's close: lane blind-row-kinds opened; 65's seeds 101 and 201 queue now on the current encoding (on the owner's behalf, 2026-11-13)

Navigator, woken by genpack-burst-base's close on a go (decisions "Lane
genpack-burst-base closed (2026-11-13)", `measurement/gbb@g11`). 

1. **What the go says beyond its question.** A base trained across
   generated enemy mechanics binds a known effect column on a new pairing
   (GE-OppCard-Artifact) in 11 games; the same recipe without the pool
   gets worse. The base the project is moving to already has it zero-shot:
   on the same 675 starts the wide net s1 pays +0.29 (0.24) HP beyond
   parent on GE-OppCard-Artifact (gp1 +10.82, pns1 +9.92, pns101 +9.59,
   pns201 +6.69) and -0.55 to +0.67 on every other Artifact row (computed
   from `results/mutate/gen-wide-*-tsl1.json` this run). So a burst from
   the wide base on these rows has nothing to cut and is not proposed
   (backlog, *wide-base-artifact-burst*). Goal 1's open few-game case is
   an atom no content trained, a fresh input column (candidate 73), and
   the replication of the 11-game lead on a second base seed is
   candidate 74.
2. **Lane `blind-row-kinds` opened** (exploration; candidate 72, its ready
   charter in `docs/backlog.md`): an input-coverage test over
   `registry::element_names()` that names every content element writing
   no row under the default kinds, and a fix for each blind one. Rated
   even that it finds a blind element beyond RoundEnd; about 3 thread-h,
   cap 5 cpu-h, end 2026-11-20, on-close wake on go. It is code first and holds the
       exploration slot without CPU. Passed over: 74 `gbb-second-seed` (likely, about 3 cpu-h, no
   code, but a replication of a lead whose base is not the one the
   project builds on); 68 `multi-hook-zero-shot` (waits for 65's base);
   69 `clears-statistic` (goal 2's ruler, no CPU); 73 (code and a burst
   vocabulary change; follows 72's audit).
3. **65 (`wide-recipe-confirm`) re-sequenced: seeds 101 and 201 of the
   wide recipe train now on the current encoding; step 0 (the RoundEnd
   row) and its seed-1 relearn follow when code is allowed.** The charter
   had seeds 101 and 201 wait for step 0's verdict, which decided their
   encoding. Changed since that choice (decisions "wide-recipe-confirm:
   three-seed control pool first"): every open lane is waiting on code and the CPU has had no job since 06:35, so step 0 may wait days. The question the seeds answer, whether the wide recipe's
   cut is seed luck, doesn't depend on the RoundEnd rows: they are read
   apart in every pool (nine of the pack's mechanics, invisible on the
   current encoding, `cause/roundend-blind`). Step 0's verdict now decides
   the encoding of the final training run and later base nets, not these
   seeds'.  CPU about the same as before
   (about 51 thread-h with step 0), cap 76 and end 2026-11-20 unchanged.
   Alternatives: keep the order (the CPU idles through the last research
   day and the seeds wait on code for an unknown time); drop step 0 (the
   final base would stay blind to a twelfth of its pack). Reverse: cancel
   the seeds' jobs while pending and restore the charter's order; once
   run, the old-encoding seeds stay valid as the recipe's seed check.
4. **Shares** (`jobs/lanes.json`): wide-recipe-confirm 60,
   machine-throughput 20, blind-row-kinds 10, main 10, filler 0. The
   only queueable CPU is 65's, and the two code lanes need little CPU
   until they build. Reverse: 60/30.

## End-HP bonus scales with max HP (owner, 2026-11-13)

ideas#75 (survival worth a fraction of max HP) was parked on 2026-11-03
with the survival-score arms, but it doesn't depend on them: every HP
price sets how many HP a win is worth, the product's `@hpe` included.
Decision: `@hpe<c>` now prices `c x 80 / max HP` per HP (search's
`end_hp_scale`, leaves and finished combats alike), so c is quoted at
80 max HP and a win keeps its worth as a share of the HP bar at any max
HP. Every fight measured so far is at 80 max HP, where the scale is
exactly 1.0, so scores are bit-identical and no result moves
(`engine/tests/end_hp_scale.rs`, golden unchanged). Left fixed: the
engine's own score, `2 - HP lost / 100`, which the nets are trained on,
also prices HP at a fixed 0.01; scaling it changes the training target
and needs a retrain, so it waits for training on fights with other max
HPs. Alternatives: a new suffix beside `@hpe` (the product would keep
the fixed price when max HP varies, the opposite of the goal); scale by
start HP (brings back the drift the issue rules out). Reversible: one
function.

## Level and more general is a pass (owner, 2026-11-13)

The protocol (`yardstick/protocol`) tests for a +1.5 HP gain, so a level
pair reads as a fail (`measurement/protocol-replay`); only cheaper changes
had a level rule (`yardstick/cost-savers`). A review of the closed lanes
found four changes that are more correct or more general, closed on that
fail while level: `@tsl1` (headline +0.12 (0.48) HP), `@lcb1` (+0.04
(0.07) HP on cells), `@tb1` (end HP identical) and `@sn1` / `@xh1`
(zero-shot -0.24 HP, se about 0.25). Decided: such changes pass on a
level-or-better read (docs/direction.md "Level and more general is a
pass", the thresholds of backlog 36), and the four go to backlog 75
`level-defaults`. Not re-opened (a real cost beside the tie):
`@shl0.005` (AttackLoss-Strength x Nob +2.37 HP), `@pl2` (control worse),
`@pd1` (Frail 0.3 HP worse). The scan covered the closed lanes' portfolio
facts and kb facts pairing a tie with a fail; probes recorded only in this
file or the results doc may be missed. Alternatives: a per-change
non-inferiority rule as for 36 (passed over: the same miss repeats on the
next such change); lower the protocol's H1 for every read (passed over:
it would also pass ties for changes that add cost or complexity).

## Level-defaults reads queued; how the level rule's bars are read (on the owner's behalf, 2026-11-13)

After the owner's rule "Level and more general is a pass"
(`docs/direction.md`) and backlog 75 `level-defaults`. The CPU had been
idle for about three hours (no lane had queueable work), and 75's parts
(a) and (b) are reads with no code, so they run as probe-sheet reads in
lane `main`, read by the navigator; no lane opens for 75.

Queued (0966 and 0967 pinned 872a7bbe4925):
- **0966** (75(a), backlog 36's read): the 10-29 net `@hpb0.01@tsl1` in
  played fights with plain `@hpb0.01` trial fights (`--chooser`; 36's
  step 1 is that existing option, so no code was left), headline
  setting, fixed n 500, `--against` the one-turn control.
- **0967** (75(b)): the 10-29 net `@hpb0.01@lcb1`, the same read.
- **0969** (75(b)'s goal-1 rows): the 10-29 net `@tsl1@lcb1` on the
  yardstick modifiers, the same snapshot (c5bf088), starts, seeds and
  mods as 0933 (`results/mutate/yard-n1029-tsl1.json`), so the
  heuristic's games are identical, paired per modifier.

How the bars are read (the rule's wording leaves two points open):
- **Clears on the point estimate, end HP at 2 se.** The headline's paired
  clears se is about 0.015 at n 500 (`measurement/turn-start-leaf@headline`),
  so a 2-se bound at -0.02 would need a point estimate of +0.01 or more:
  an exact tie would fail, against the rule's "level is a pass". The HP
  bar names 2 se itself (se about 0.48, so a tie passes). Alternative
  passed over: 2 se on both.
- **A goal-1 row fails** when its paired difference is -1 HP or worse
  and more than 2 se below zero. Alternative passed over: a lower bound
  below -1 HP fails a row (with eleven modifiers at se 0.3-0.6, noise
  alone would fail a level change).

What each outcome does:
- 0966 passes: `yardstick/one-turn-controls` is re-set to its file and
  the cell twin `results/gauntlet/net1029-hpb0.01-tsl1.json`;
  `decision/tsl1-fight-leaf` takes effect. Fails: `decision/turn-start-leaf-reads`
  stands.
- 0967 and 0969 pass: `@lcb1` joins the controls' price. With 0966 also
  passing, the navigator queues one combined `@tsl1@lcb1` control
  (headline and cells, about 4 cpu-h) and the controls move to it;
  either alone moves them to its own file. Fails: `@lcb1` stays off.

(c) **`@tb1` is adopted as the default.** The owner's condition (a
replay showing values bit-identical) is already met: 0680/0681 replayed
330 product fights with end HP and wins identical in every fight, and the
tie break never changes a value by construction
(`measurement/portfolio-finish-faster-tiebreak`). It takes effect when
the search default flips in code (one line; check: rerun 0680/0681's
replay with the flag's default on); that waits for a code session on
main (backlog probe sheet). Until then strings without `@tb1` stand: no
file or read changes. Alternative passed over: write `@tb1` into every
player string now (every control and product read would differ in its
price string and need `--vary price`, for no change in play).

(d) **`@sn1` / `@xh1` ride on the next from-scratch net that isn't a
replication twin**, most likely Act 1's widened-pool net
(`decision/headline-pool-after-act1`), read against a twin without them
under the level rule. Not `wide-recipe-confirm`'s seeds 101/201 or its
step-0 relearn: both are twins of the current encoding, and the flags
would confound their reads.

Re-read scan beyond the owner's four (closures resting on a protocol
fail for a change of the rule's kind): `pattern-rows-burst` (cells
-0.42 (0.19) HP against its twins, a cost beside the tie like `@pd1`)
and `burst-official` (a trained net, not a change of the rule's kind;
its own-pick gain was read under `decision/crossed-player-lead`) are not
re-opened. Job 0333 (`@tsl1` with flagged trial fights, +0.12 (0.48) HP,
+0.008 clears) would meet the bars, but its closure rested on the
chooser's overpick too (Demon Form 0.49 of offers against 0.17, deaths
moved to the second elite), so 0966's plain-trial arm is the read.

Ranking: 75 sits first while its reads run; 68 and 73 keep their ready
charters. Reversible: the controls are fact pointers, the tie break one
default.

## Level-defaults part (e): `@hpe` one turn deep (on the owner's behalf, 2026-11-13)

Since 1d9c3cca the end-HP bonus `@hpe` scales with max HP; the one-turn
controls' `@hpb` does not, prices no finished combat, and leaves out the
win heal (`py/src/lib.rs`: `@hpe` prices `min(HP + win heal, max HP)`).
So the one-turn ruler misprices HP wherever max HP moves (relics, Act 1
content) and differs from the product's price for no gain: a change of
the level rule's kind. One turn deep it played level before (run-HP 0037
against 0023: -0.05 HP, se 0.04; decisions "End-HP bonus built and
read"), never on the headline.

Queued: **0970**, the 10-29 net `@hpe0.01` one turn deep on the headline
setting, fixed n 500, against the one-turn control (pinned 872a7bbe4925,
about 3.5 cpu-h), read under `decision/level-pass`. Pass: `@hpe0.01`
replaces `@hpb0.01` in the one-turn controls, joined with 0966's and
0967/0969's outcomes in one re-recorded control (headline and cells,
trial fights plain `@hpe0.01` if 0966 passes). Fail: `@hpb` stays and the
max-HP misprice is recorded as open for content that changes max HP.
Alternatives passed over: scale `@hpb` the same way in code (the
navigator doesn't edit code, and it would leave the finished-combat and
win-heal gaps); wait for content with other max HPs (the read is cheap
now, with the CPU idle).

## Level-defaults read: `@tsl1` and `@lcb1` pass, `@hpe` one turn deep fails; the one-turn controls move (on the owner's behalf, 2026-11-13)

Backlog 75's four reads under `decision/level-pass`, each paired against
the one-turn control (`results/gauntlet/net1029-hpb0.01-starter-simboss.json`,
0.680 clears) on the headline setting at fixed n 500 (bars: end HP
minus 2 se at least -1 HP, clears at least -0.02 on the point estimate):

- **0966, `@tsl1` in played fights, plain `@hpb0.01` trial fights:
  pass.** End HP +0.56 (0.19), clears 0.696 (+0.016, 0.006). Only 30
  sequences differ, 22 of them held out (held out +1.15 (0.37) HP,
  +0.032 clears; train -0.03 (0.11), clears identical); boss deaths 107
  to 100. Demon Form taken at 0.19 of 249 offers, as the control (0.19
  of 248): the plain trial fights remove the old overpick (0.49, job
  0333).
- **0967, `@lcb1`: pass.** End HP +0.15 (0.45), clears 0.700 (+0.020,
  0.012); deaths at the second elite 31 to 24. **0969**, its yardstick
  rows (the 10-29 net `@tsl1@lcb1` against 0933's `@tsl1`, same snapshot,
  1,350 games per modifier): every modifier within 0.05 HP of zero (worst
  thorns2-hp0.9 -0.05 (0.04)), parent -0.00 (0.01): no row fails.
- **0970, `@hpe0.01` one turn deep: fail.** End HP -1.74 (0.75), lower
  bound -3.23; clears 0.660 (-0.020, 0.020, at the bar); train -2.78
  (1.08), held out -0.69 (1.04); deaths before the boss up (floors 5-8:
  7 to 18). The play differs almost only in fights that start near full
  HP: of fights both arms start on the same deck and HP, 322 of 1,670
  differ at 74-80 HP against 26 of 538 below, and there `@hpe` loses
  +0.19 (0.05) HP more per fight. `py/src/lib.rs` `add_prices` prices
  every leaf, unfinished ones too, at `min(HP + win heal, max HP)`: in a
  fight still running, HP within the heal of max HP looks free, though the
  rest of the fight's damage comes before the heal. Backlog 76 takes this
  up (the product prices the same way).

Decided:
- The one-turn price is `@hpb0.01@tsl1` with plain `@hpb0.01` trial
  fights now, and `@hpb0.01@tsl1@lcb1` with `@hpb0.01@lcb1` trial fights
  once the combined control is recorded: jobs **0972** (headline,
  `results/gauntlet/net1029-hpb0.01-tsl1-lcb1-starter-simboss.json`) and
  **0973** (cells, `results/gauntlet/net1029-hpb0.01-tsl1-lcb1.json`),
  both pinned d08ef5a4, about 2.6 thread-h. 0972 is read
  under the same rule as a check on the pair's interaction; a fail
  leaves the controls on 0966's file and `@lcb1` off. (0972's note calls
  its cell twin 0974; it means 0973.)
- Until then `yardstick/one-turn-controls` points at 0966's file and the
  `@tsl1` cell twin `results/gauntlet/net1029-hpb0.01-tsl1.json` (both
  read level or better). `decision/tsl1-fight-leaf` is in force;
  `decision/turn-start-leaf-reads` loses its "until" clause.
- `@hpb` stays in the one-turn controls; the max-HP misprice of `@hpb`
  stays open for content that changes max HP. Part (e) reopens if 76's
  fix makes `@hpe` one turn deep level against `@hpb`.
- Reads against the new controls of a player with another price or
  chooser add `--vary price` / `--vary chooser`, as before.

Alternatives passed over: wait for 0972/0973 before moving the controls
(screens queued meanwhile would pair against a ruler already known to
misprice turn-start powers); adopt `@lcb1` without the combined read (its
pass was measured beside a plain leaf, not beside `@tsl1`; 2.6 thread-h
on an idle CPU settles it); count 0970's clears at the bar as a pass (the
HP bar fails on its own). Reversible: the controls are fact pointers.

## wide-recipe-confirm: seeds 101 and 201 queued without the pack headline (on the owner's behalf, 2026-11-13)

Lane worker, under charter rev 4 (seeds 101 and 201 first, current
encoding). This session only queued jobs already designed: the learns 0975/0976
(`configs/widepack40k-s101.json`, `-s201.json`, made the same way as
genpack40k-s101/s201), then for each seed the wide grid rows, the 24
old rows, the yardstick rows and the one-turn cells, copied from seed
1's jobs 0916, 0917, 0931 and 0918 (0977-0984). Cells are paired
against the same seed's pack-net-scratch file; the raw per-sequence
files allow pairing against wp1 offline.

Left out: the pack headline. `content/packs/act1-ironclad.json`
changed after seed 1's headline (commit 8a171705, Havoc joins the
pool, 13 Nov 02:44), so every pack-headline control on file was played
on an older pack. A paired read would need `--vary pack` (mixing
content into the comparison) or new controls (wp1 and pack-net-scratch
replays, about 2.3 h at 3 threads each). Alternatives: queue the
headline with `--vary pack` (cheap but confounded); queue the control
replays now (about 14 thread-h for six files, before step 0, which may
change the encoding anyway). Reversible: the next lane session queues
the headline reads with fresh controls once the rows have read.

## Combined one-turn control `@tsl1@lcb1` read; the controls move to it; the product read with both flags queued (on the owner's behalf, 2026-11-13)

Jobs 0972 and 0973 (entry above), read under `decision/level-pass`:
- **0972, headline**: the 10-29 net `@hpb0.01@tsl1@lcb1`, trial fights
  `@hpb0.01@lcb1`, against the old one-turn control: end HP +0.76 (0.47),
  lower bound -0.19; clears 0.716 against 0.680 (+0.036, 0.013); train
  -0.05 (0.61) HP, +0.012 clears; held out +1.57 (0.73) HP, +0.060
  clears. The parts add: against 0966's file (`@tsl1` alone) +0.20
  (0.45) HP, +0.020 clears; against 0967's (`@lcb1` alone) +0.62 (0.23)
  HP, +0.016 clears. Demon Form taken at 0.17 of 250 offers. Deaths at
  the second elite 31 to 24, at the boss 107 to 101. The protocol stays
  open at n 500 (no +1.5 HP gain shown), as a level change should.
- **0973, cells**: +1.56 (0.33) HP, clears 0.670 against 0.634 (+0.036,
  0.009) against the plain cell control, the `@tsl1` cell gain
  (`measurement/turn-start-leaf@cells`); +0.07 (0.06) HP against the
  `@tsl1` cell twin, so `@lcb1` adds about nothing on cells, as before.

Both pass: `yardstick/one-turn-controls` moves to
`results/gauntlet/net1029-hpb0.01-tsl1-lcb1-starter-simboss.json`
(headline, 0.716 clears) and `results/gauntlet/net1029-hpb0.01-tsl1-lcb1.json`
(cells). A one-turn screen now plays `@hpb0.01@tsl1@lcb1` with
`--chooser <net>@hpb0.01@lcb1`, or reads with `--vary price` /
`--vary chooser`. `configs/product.json` `one_turn_control` still names the
old file; `scripts/product.py set --one-turn` changes it at the next
promotion (the navigator doesn't edit configs). The +0.036 clears is one
seed on one book: a lead for the one-turn ruler, not a product number.

**The product read (backlog 77).** The same two flags two turns deep
were not proposed on 2026-11-07 (*tsl1-two-turn*: an expected gain under
0.01 clears against a detectable 0.05). `decision/level-pass` removes
that reason: a misprice fix passes on a tie. Queued **0986**: the
product (`@hpe0.01 --two-turn --line-seed --step-line`) with `@tsl1@lcb1`,
trial fights `@hpe0.01@lcb1` (`--chooser`, keeping the turn-start leaf
out of the sim chooser as one turn deep), headline n 500, against
`yardstick/headline-control` with `--vary price --vary chooser`; 2
threads, about 7 thread-h; pinned 78f72320. It waits behind
`wide-recipe-confirm`'s seed-201 learn and reads by the lanes' shares
and ends before 14 Nov 08:00 (`decision/nov14`). Pass (level rule): the
product string gains `@tsl1@lcb1` and the chooser (`scripts/product.py
set` with `--headline` this file and `--one-turn` the combined file, a
decisions entry); the owner's 14 Nov player read can use it. Fail: the
product stays; `@lcb1` alone two turns deep is the next read.
Alternatives passed over: `@lcb1` alone first (the one-turn parts each
passed and add up; one read of both halves the CPU and a fail is split
after); move 0986 ahead of the seed-201 learn with `jobs.py first`
(either order ends tonight; the lane's chain is already waiting).
Reversible: fact pointers and one product string.

## wide-recipe-confirm: learn 0975 crashed on a stack overflow; 64 MB worker stacks, seeds re-queued (on the owner's behalf, 2026-11-13)

Learn 0975 (seed 101) died after 5 minutes of round-0 self-play (46,800
of 120,000 games) with exit 3221225725 (0xC00000FD, stack overflow), no
Python traceback. Seed 1's learn 0926 and 0935 ran the same recipe on
older pins; since then Havoc (PlayTop), the costs-0 marks, Discover and
40 card slots joined the Ironclad pool (deck_pool "all"), and
CombatState grew 860 -> 912 bytes (sparse-piles step a). The search's
`expand` -> `child` -> `expand` recursion goes one frame per action and
chance event of a line, and the node cap counts a node only after its
children return, so the first line of a long turn is bounded by nothing
but the fight; the worker threads (`std::thread::scope`) have Rust's
2 MB default stack. Taken as a deep, finite recursion, not a loop (the
turn loop in `run_opts` and PlayTop's queue are iterative).

Done: `scripts/learn.py`, `gauntlet.py` and `analysis/mutate_monsters.py`
set `RUST_MIN_STACK` to 64 MB (unless set) before `sts` loads; Rust's
spawned threads read it, and the reservation is virtual (committed only
as used). Seeds 101 and 201 and their eight reads are re-queued on that
commit; the old pending jobs (0976, 0979-0984) are left to cancel
themselves (`--if-passed 0975 --on-fail cancel`), since `jobs.py cancel`
was refused in this session. Alternatives: an explicit `stack_size` on
the engine's thread spawns (py/src/lib.rs, engine/src/runner.rs; a build and an `sts` swap); an
iterative `expand` (the real fix, a spec). If the re-run crashes again
at 64 MB the recursion is unbounded: then find the state (a loop of
0-cost plays the memo misses) before anything else. Reversible: drop
the three lines once the engine sets its own stack size.

Then (2026-11-13 12:45): learn 0987 (seed 101, the re-run) died out of
memory, not on the stack: numpy could not allocate 1.37 MiB at effects
epoch 2 (peak 4.95 GB, booked `mem_gb` 2.5). The machine's commit charge
    was nearly full, and seed 1's learn 0926
peaked at 6.8 GB, so the 2.5 booking let it start beside 0986. Seed 101
is re-queued as 0997-learn with `mem_gb` 5.0, after 0988 so the two
learns never overlap, and its reads as 0998-1001. Alternatives: cancel
0988 (running, same 2.5 booking) and re-book it too, which idles the
6 threads for its 13 minutes of progress and still waits on memory;
cut the learn's memory (code). If
0988 fails the same way, re-queue it as 0997 was.

Then (2026-11-13 13:50): learn 0988 (seed 201) failed the same way:
numpy could not allocate 7.22 MiB in `norm.tensors` at effects epoch 2
(peak 6.04 GB, booked 2.5); its four reads 0993-0996 cancelled
themselves. As planned, seed 201 is re-queued as 1002-learn (`mem_gb`
6.0, the observed peak; after 0997-learn so the learns never overlap)
with reads 1003-1006 (`--if-passed 1002-learn`), same pin 9fcf17ce.
 Alternative: book 7.0 (seed 1's 6.8 peak), which
    needs 8 GB free.

Then (2026-11-13 14:05): seed 101's re-run 0997 died out of memory too
(numpy could not allocate 1.35 MiB at effects epoch 2, peak 5.2 GB,
booked 5.0); reads 0998-1001 cancelled. Commit charge was again nearly full. The step rule said a third
death means cutting the learn's memory in code first; a retry is cheaper: learn reuses
its generated games (`learn.py` reuses datasets), so 0997 ran 23 minutes
of training only. Seed 101 is re-queued once more as 1008-learn
(`mem_gb` 6.0, after 1002-learn) with reads 1009-1012. The runner admits
a 6.0 booking only with 7 GB physically free, a better guard than 5.0.
If 1002 or 1008 dies the same way, stop retrying: cut the training
loop's memory (code) or wait for more free memory.
Alternatives: wait without queueing (idles the CPU, nothing else is
queued); cancel the main lane's 0986 gauntlet to free 2 GB (not this
lane's job).

## Product read 0986: `@tsl1@lcb1` two turns deep is level; the product gains both flags and the chooser (on the owner's behalf, 2026-11-13)

Job 0986 (backlog 77 `product-level-flags`; entry "Combined one-turn
control `@tsl1@lcb1` read; ...") read under `decision/level-pass`: the
product (10-29 net `@hpe0.01 --two-turn --line-seed --step-line`) with
`@tsl1@lcb1` in played fights and trial fights `@hpe0.01@lcb1`
(`--chooser`), headline setting, sequences 0-499, against
`yardstick/headline-control` with `--vary price --vary chooser`.

- **All 500:** paired end HP +0.08 (0.51), lower bound -0.93 against the
  -1 HP bar; clears 0.832 against 0.834 (-0.002, 0.012). The protocol
  fails at n 500 (no +1.5 HP gain), which a level change does by design.
- **Halves:** train +1.02 (0.60) HP, -0.004 clears; held out -0.86
  (0.81) HP, +0.000 clears. The held-out point estimate is inside 1.1 se.
- **Why the bound sits near the bar** (the pass is close, so it got a
  look): no fight type carries a loss. Paired HP lost per floor on the
  same encounter is within 0.25 HP everywhere (first elite -0.19 (0.18),
  second elite +0.16 (0.24), boss -0.24 (0.44); hallways within 0.08).
  Deaths: second elite 13 to 16, boss 62 to 59. 355 of 500 sequences
  keep the same picks; 589 picks differ, so the sd comes from diverging
  decks, not from a fight the flags play worse. The bound is the
  headline's usual noise (se about 0.5, `cause/headline-pairing-weak`).

Pass. The product becomes `<10-29 net>@hpe0.01@tsl1@lcb1 --two-turn
--line-seed --step-line --chooser <10-29 net>@hpe0.01@lcb1`
(`scripts/product.py set`); `configs/product.json` `headline_control` is
0986's file (0.832 clears) and `one_turn_control` the combined one-turn
file (`yardstick/one-turn-controls`). A two-turn headline read of a
player without these flags now adds `--vary price --vary chooser`.
What it moves: no clears or HP gain (as rated: a long shot for a gain);
the product's leaf now prices turn-start hooks and leftover block right,
which matters on content the curated headline doesn't hold (generated
powers with turn-start hooks; Act 1 relics that act at turn start). The
14 Nov bridge takes any player string (`docs/specs/real-game-bridge.md`,
decision 3), so it plays this one by default.

Alternatives passed over: keep the old product until a read shows a
gain (the owner's rule makes a misprice fix that reads level a pass);
split and read `@lcb1` alone (only on a fail); a confirm on sequences
500-999 (a level read has nothing to confirm, and nothing may be queued
past 14 Nov 08:00, `decision/nov14`). Reversible: `product.py set` back
to the `previous` entry and the old headline file, both kept.

## Parity source and arena after the install: the game's jar first, the real game is arena level 2 (on the owner's behalf, 2026-11-13)

`decision/parity-source` (owner, 2026-11-10) and `decision/goal2-arena`
both say "no install". The owner has since installed StS1 for the 14 Nov
live game: `desktop-1.0.jar` (game version 2022-12-18) is in the game's install folder, and `javap`
reads its classes. The owner's rule stands (the game's own code decides
content values and behaviour; sts_lightspeed and the wiki are leads
only); only where that code is read changes:
- **Parity:** the installed jar first (`javap -c -p`, cited by class and
  method), the decompiled GitHub copies when bytecode is hard to read,
  two sources compared where they could differ.
- **Arena:** level 2 is the real game through the bridge
  (`docs/specs/real-game-bridge.md`), run by the owner by hand; levels 0 and 1 stay the engine's rulers.

Alternatives passed over: leave both facts suspect until the owner
re-words them (they are wrong now and every reader would trip on them);
the jar only (decompiled copies are easier to read, and javap of the
same bytecode can't disagree with them on values). Reverse: re-set the
facts.

## Engine audit read against the lanes: blind-row-kinds starts from entries 9 and 14; 65 reports Dazed rows apart if entry 6 lands first (on the owner's behalf, 2026-11-13)

Navigator, woken by job 0986 (already read and acted on at 16:37, decisions
"Product read 0986"; that session ended before closing its wake). The owner's engine audit (`docs/research/engine-audit.md`,
read only) landed since the last run; two of its entries bear on open
lanes.

1. **blind-row-kinds starts from audit entries 9 and 14.** Entry 9 names
   nine effect atoms that write no net column (BlockAlly, ApplyPack, Heal,
   HealOf, GainMaxHp, DrawPicked, PlayTop, Discover, ObtainRandomPotions;
   Shield Gremlin's Protect is official Act 1 content among them) and why
   "no column" keeps winning (contract pins hash whole-layout bytes). The
   charter gains that starting list, and the per-named-column pins as an
   allowed first code step; its stop rule is unchanged (the test still
   confirms each element). Backlog 72 moves from even to likely.
   Alternatives: leave the charter as is (the lane worker would rediscover
   the list); widen the lane to all of entry 14's kinds (that is M-sized and
   carries the memory cost the opt-in decision was about; the charter's
   "without the official rows the opt-in kinds would add" already covers
   it). Reverse: drop the added line.
2. **65's step 0 reports the GE-*-Dazed rows apart if entry 6 lands
   before its relearn.** Entry 6: `Effect::scaled` leaves AddCard unscaled,
   so the wide pack's 2-stack Dazed copies add one Dazed. A fix between the
   seeds and step 0's relearn changes those rows' content as well as the
   encoding (GE-RoundEnd-Dazed is one of step 0's RoundEnd rows), so the
   five Dazed rows leave both of step 0's pools and are reported apart.
   Seeds 101 and 201 read on the current rules, as seed 1 did. Alternatives:
   hold entry 6's fix until 65 closes (blocks an owner-side fix for a lane's
   bookkeeping); ignore it (a confound on 5 of the grid's rows inside the
   step's 0.3 HP guard). Reverse: drop the clause.

Also this run: 14 suspect facts re-checked and confirmed, four re-set after
audit entry 1 (`how/player-strings-rules`, the shown-card-numbers
measurements); backlog 78 `final-run-inputs` added (a sequencing rule for
the owner's final training run, not a decision: the owner's plan sets the
run). No lane opened or closed; shares unchanged.

## Blood for Blood's cost per copy, replacing C5's one HP-loss counter (on the owner's behalf, 2026-11-14)

Run 16 (The Guardian) showed the C5 counter wrong: in the game each loss
drops only the copies in the hand, draw and discard piles
(`AbstractPlayer.updateCardsOnDamage`), so a copy in play when Sharp
Hide's thorns land keeps its cost. Each copy now carries its own combat
cost (a changed copy, docs/specs/sparse-piles.md); `times_lost_hp` stays
only for copies made in the fight (`makeCopy`). Alternative kept from C5:
one counter plus a per-copy "missed" mark (fewer card ids, but a second
cost mechanism beside the one every other combat cost uses). Reversible;
golden unchanged (official content has no such card).

## Rules version moves to cover the 14 Nov rule fixes (on the owner's behalf, 2026-11-14)

Why: the rules version is a hash of `engine/tests/data/golden.txt`, and
the rule fixes made since `e47bcfcdb6b2777a` left golden unchanged
(`cause/rules-changes-outside-golden`: Perfected Strike from limbo, the
Guardian's Mode Shift block at turn end, the turn-end order of Burn,
Combust, Regeneration, Metallicize, Plated Armor and Orichalcum, Feed's
max HP on a kill, Blood for Blood per copy, Rupture on the player's own
Burn, Artifact against Flex), and Duplication now ends at the round's
end. So data recorded under the same version would replay differently.
7947ae4d appends 5 cover games to golden, so the version moves
`e47bcfcdb6b2777a -> f59b662aa4500070`, with no `SAME_RULES` entry (the
rules did change). All existing golden and proving lines are
byte-identical.

Cost: nothing is recorded under `e47bcfcd`: every dataset and run is
older (`7042d1d6a6149ba0`, already refused on main), the solved DB keys on
rule files, and gauntlet results carry no version
(docs/research/golden-gap-impact-2026-11-14.md, kb
`measurement/golden-gap-impact`). Parked jobs 1016 and 1017 are re-pinned
to the landing commit.

What it covers: `cover_games_reach_their_mechanics` checks each game
reaches its rules: turn-end-hp (Burn, Regen and Combust order),
turn-end-block (Metallicize and Plated Armor against Burn),
rupture-duplication (Rupture from Burn, Tungsten Rod with Hemokinesis,
Duplication at the round's end), guardian (Mode Shift at turn end, Blood
for Blood per copy and in limbo, Orichalcum with Burn) and feed (Feed
kill, Perfected Strike with Havoc, Flex against Artifact). A rule fix
outside these games still leaves the version unchanged; the next one adds
a cover game at the end of `COVER` (engine/tests/golden.rs). Reverse:
revert 7947ae4d (the version returns to `e47bcfcd`).

## Ascension 20 becomes the default setting after the real-game day (owner, 2026-11-14)

The owner: "after this I plan to train on A20 as the default setting".

Why: at Ascension 0 the real game is too easy for the product's fighter.
Under run rules 1, 22 of 27 runs beat the Act 1 boss. At Ascension 20
the same player beats it about half the time (runs 28-56: Slime Boss 4
of 7, Hexaghost 3 of 8, The Guardian 4 of 6), and every Hexaghost loss
was a damage race lost to the turn-9 Inferno. The engine plays A20
faithfully: about 99.5% of predicted steps matched, and no miss came
from a monster's ascension rules (`docs/research/real-game-runs.md`;
`docs/specs/ascension.md`, built 725e8675). So A20 is where play still
has room to improve, and the net has never trained on A20 numbers.

What it changes, once research resumes:
- Training plays its games at A20 by default: self-play, labels and
  fine-tunes.
- New datasets record their level. A0 and A20 data are never pooled
  without saying so.
- Goal 2's ruler moves to A20 once the A20 controls exist. Every result
  already recorded stays valid at A0, and A0 stays available with
  `--ascension 0`.

Not ready yet (the order to do it in):
1. `scripts/learn.py`, `scripts/selfplay.py` and `scripts/finetune.py`
   have no ascension setting. They need a config key `ascension`, passed
   into every fight spec they make (the fight specs already take it).
2. `scripts/registry.py` records no level. It belongs in the dataset
   manifest and run.json, kept apart like the rules version.
3. The gauntlet's reward choosers project rests at 80 max HP (`MAX_HP`
   in `scripts/gauntlet.py`). At A20 it is 75 (left open in the
   ascension spec's Status).
4. A20 controls: the product and the one-turn controls on the headline
   setting with `--ascension 20` (backlog 80 (a)). After that, the
   yardstick facts get A20 versions.
5. Pack and generated monsters have no ascension rows, so at A20 they
   play their A0 numbers. That is a deliberate choice for goal 1 (custom
   content brings its own numbers), recorded here so it isn't mistaken
   for a gap.

Then the final training run (backlog 78) runs at A20, with backlog 81's
schedule inputs if their probe passes. Nothing ran today; research
resumes on the owner's word (`decision/nov14`). Reverse: the owner's
word. The A0 setting and all A0 results stay as they are.

## Rules version moves for Lagavulin's wake (on the owner's behalf, 2026-11-14)

Why: Lagavulin's wake now takes 8 Metallicize, as the game's
`Lagavulin.changeState("OPEN")` does (`ReducePowerAction(..., 8)`),
instead of clearing it; a negative Apply of an official non-negative
power acts as `ReducePowerAction`. It differs only when Lagavulin holds
more than 8 (the map's burning elite with the Metallicize buff, real-game
run 40), so golden's existing lines are byte-identical; e48f16f9 appends
the cover game `cover-lagavulin-burning` (Lagavulin, seed 1, buffed with
`EliteBuff::Metallicize`), and the version moves
`f59b662aa4500070 -> 696d607bbb413f47` with no `SAME_RULES` entry (the
rules did change). Approved by the manager session.

Cost: nothing is recorded under `f59b662a` or `696d607b` (datasets, runs
and the solved DB are older or keyed otherwise; gauntlet results carry no
version). Parked jobs 1016 and 1017 are re-pinned to e48f16f9, outputs
`-rf59b` -> `-r696d`. Alternative: a `SAME_RULES` entry mapping the new
version to the old, refused because a buffed Lagavulin plays differently.
Reverse: revert e48f16f9 (the version returns to `f59b662a`).

## Rules version moves for Pocketwatch's play count (on the owner's behalf, 2026-11-14)

Why: Pocketwatch's counter is now the game's play count: cards played
since the last post-draw reset, checked at `atTurnStartPostDraw` (draw 3
when the count is at most 3 and it isn't the first turn, then reset to
0), instead of a 0/1 flag set at turn end. The two agree on today's Act 1
content except for a card played between the turn end and the next
post-draw, and for a fight rebuilt from the game's view. Every power now
carries `can_go_negative`, the game's `AbstractPower.canGoNegative`
(Strength and Dexterity in the engine; Wraith Form is left out because
the engine stores its amount with the opposite sign), and a pack power
without it floors at 0 on a negative amount.

The floor changes no recorded or generated fight: a scan of all 3,222
JSON files under `content/`, `configs/`, `data/`, `runs/`, `results/`,
`engine/tests/` and `scripts/tests/` (40 of them pack-like) and of the
generators (`gen_content.py`, `gen_enemy_pack.py`,
`scripts/analysis/mutate_monsters.py`) found no negative Apply on a power
other than Strength or Dexterity except Lagavulin's official Metallicize
-8, which was already floored. The only such pack power is the test power
`fx_might` (`engine/tests/packs.rs`), now marked `can_go_negative`.

Golden's existing lines are byte-identical; e25453ec appends the cover
game `cover-pocketwatch:ironclad:jaw_worm:2` (starter plus Anger x2, Flex,
Double Tap and Havoc, relic Pocketwatch), and the version moves
`696d607bbb413f47 -> 32f1971b128452c4` (commits 57bcfade, e25453ec) with
no `SAME_RULES` entry (the rules did change). Approved by the manager
session.

Cost: nothing is recorded under `696d607b` (no file in `results/` or
`data/` names `r696d` or the version; gauntlet results carry no version).
Parked jobs 1016 and 1017 are re-pinned to e25453ec, outputs `-r696d` ->
`-r32f1`. Alternative: a `SAME_RULES` entry mapping the new version to
the old, refused because the rules changed. Reverse: revert e25453ec and
57bcfade (the version returns to `696d607b`).

## Draw knowledge item 4: picks past the node cap (2026-11-14)

Why: series-review finding D1 (`docs/specs/series-review-fixes/D-loader.md`).
A pick was exempt from the node cap on the claim that the transposition
cache bounds its subtree (~1,024 states at most, the entry under the
decision-points spec above). That holds only for DiscardFromHand: an
ordered pick (DiscardToTop, HandToTop) makes d!/(d-n)! states, so a pack
card picking 5 of 10 made 36,559 nodes at a 1,000-node cap.

What changed: search only, no rule change; golden and the rules version
are unchanged. Past the node cap a pick is still expanded (never a leaf)
but along its first option only, which equals the greedy agent's choice
at a pick. This supersedes the old "the subtree is bounded, ~1,024 at
most" line; the old entry stays as written. Below the cap nothing
changes, and the root's options are still all scored. A search that
meets a pick past the cap (pack picks, or proving cards such as
Headbutt, Survivor and Hologram) can choose differently than before.
Reverse: revert the commit.

## The final training round, with the best setting reached so far (owner, 2026-11-14)

The owner: "The normal workflow can continue now, but make sure that a
final training round is done with the best setting we managed to do for
now". So the roles resume, and the final training round of
`decision/nov14` gets queued with what is confirmed, not with what
research might add later.

The setting it uses:
- **Engine:** main after the Act 1 order already set for 15 Nov: F (Fire
  Breathing on Curse draws), V (monster-debuff skip, the 999 caps and
  Shield Gremlin's Protect, one rules-version move), C2 and C3 (no fixed
  cap on powers or piles). Training data then sits on one rules version
  with today's live fixes in.
- **Level:** Ascension 20 (`decision/a20-default`), once its readiness
  steps 1-3 land (an `ascension` key through learn, selfplay and
  finetune; the level in the registry; the choosers' 75 max HP).
- **Content:** everything in Act 1 that loads by then: all 75 Ironclad
  cards, the monsters, relics, potions, curses and the colorless cards
  landed.
- **Recipe:** the best from-scratch recipe on record when it is queued.
  That is the wide generated recipe if `lane/wide-recipe-confirm`'s
  seeds-go passes (seed 101's jobs 1008-1012 are unparked for it).
  Otherwise it is the 40k pack recipe behind packnet40k-s201: level with
  the product on Act 1 monsters (0.768 vs 0.756 clears, job 1014), ahead
  with Act 1 cards, and the real-game player of 14 Nov.
- **Inputs:** backlog 78's (a)-(e) items that have landed by the cutoff.
  Backlog 81's schedule columns go in only if their probe passes by
  then.
- **Prefer the kill (owner, the same evening):** the owner sees stalls as
  important, after the live runs' stall records (run 83's 84-turn
  gremlin standoff, run 56's Blue Slaver at 6 HP for turns 7-18, A0 run
  18's Acid Slime at 4 HP for about 23 turns). Backlog 82
  (leaf-beats-win) and 85 (stalls) get probed before the run is queued.
  Self-play plays through the same search, so a fix that passes its probe
  goes into the run's search and labels, not only into play.
- **Read:** against the A20 controls (backlog 80 (a)), recorded right
  after V, C2 and C3 land and before the run. It is judged on the
  headline setting at A20 with the protocol; a pass makes it the
  product's net.

Cutoff: queued by 2026-11-20 (78's date) with whatever has landed. "For
now" means nothing waits on research beyond that date. Not today:
research stays paused tonight.

Kept parked: 1016 and 1017 (draw-knowledge item 1's A0 re-records at
32f1971b). V moves the rules version tomorrow, so they would be stale.
The navigator re-pins them after V or retires them under the A20
default.

## One lane: the final round is the lane; machine-throughput and blind-row-kinds end, wide-recipe-confirm ends at seeds-go (on the owner's behalf, 2026-11-14)

Why: the owner's wake of 14 Nov 22:19 resumes the roles
from 15 Nov with one lane, and sets the order: the Act 1 session's F, V
(with C1 and Protect), C2, C3 (owner-run); A20 readiness steps 1-3
(lane work); backlog 80 (a)'s A20 controls; then the final round
(`decision/final-training-round`). One lane means one stream of lane
work: every lane session goes to that order until the round is queued.

What changes:
- `lane/final-round` opens (entry below) and carries the order: A20
  readiness, the recipe from seeds-go, the A20 controls, the run, its
  read. Share 40 now, 90 once wide-recipe-confirm closes.
- `lane/wide-recipe-confirm` stays open only to read seed 101 (jobs
  1008-1012, queued, CPU only) and closes at its seeds-go checkpoint
  with no wake and no new lane; its step 0 (RoundEnd rows) moves to
  final-round as optional input 3(a). Share 50 while its jobs run.
- `lane/machine-throughput` and `lane/blind-row-kinds` end today (their
  end dates move to 2026-11-14, so the lane worker closes them at its
  next session with no wake and no new lane). Neither had started: both
  waited on a spec. Shares 0. Reopen if: a second lane
  slot opens after the final round; machine-throughput's (a) would also
  return if learns become the queue's bottleneck (a final-round learn is
  about 2.2 h at 6 threads, three of them in this round).
- No exploration lane while the project runs one lane (the navigator's rule
  of one exploration lane gives way to the owner's one lane). Backlog 68
  and 73 lose their ready charters until a second slot opens, so a close
  can't open them.
- Parked jobs 1016 and 1017 (the A0 one-turn controls re-recorded under
  32f1971b) stay parked until V lands, as the owner's wake says. Then the
  navigator retires them: V moves the rules version again, the A20
  controls of final-round step 4 become goal 2's ruler
  (`decision/a20-default`), and no planned read compares against an A0
  headline control. Re-adding them is one `jobs.py add` with the same
  commands.

Alternatives passed over: (1) keep three lanes and run them one session
at a time: every lane session spent on throughput or row kinds delays
the A20 code, the one step the owner left to the lanes; (2) re-charter
wide-recipe-confirm into the final round: fewer closes, but its name and
goal-1 charter would hide the owner's milestone; (3) close
wide-recipe-confirm now and move its jobs: its seeds-go read is the
recipe input, and its own charter already says how to read it.
Reverse: re-set the lanes' end dates and shares.

## Lane final-round opened (on the owner's behalf, 2026-11-14)

The owner's final training round (`decision/final-training-round`) as
    its own lane. Charter: `docs/lanes/final-round.md`. Steps:
(1) A20 readiness (`ascension` through learn, selfplay and finetune; the
level in the registry and run.json, mixed levels refused; the choosers'
max HP from the run's level), now; (2) the recipe from
wide-recipe-confirm's seeds-go, else the 40k pack recipe (also on
2026-11-19 if seeds-go is still open); (3) optional inputs while waiting
for the owner's engine work: 78 (a) RoundEnd rows if the recipe is wide,
81's near-free probe; (4) the A20 controls (one-turn and product,
headline setting, 500 sequences) after F, V, C2, C3 land, or at
2026-11-20 12:00 with what has landed; (5) the round on that commit:
seed 201 as the pre-registered candidate, seeds 1 and 101 as replicates;
(6) the read: seed 201 one turn deep with the protocol against the A20
one-turn control, then in the product's flags against the A20 product
control, promotion on a protocol pass and a level-or-better product read.

Rating: **likely** that the round is queued by 2026-11-20 on A20 with
the controls recorded (each code step is small and named; against: F/V/C2/C3 are the owner's sessions, hence the 11-20
fallback). **Even** that seed 201 passes and is promoted: for, the net
trains on A20 numbers that no current net has seen, and bursts can't
teach plain numbers (`cause/bursts-no-boss-or-stat`), so only a
from-scratch net can learn them; the pack recipe was level with the
product on Act 1 monsters (job 1014, 0.768 vs 0.756 clears); against, no
from-scratch recipe has beaten the 10-29 net on the headline beyond noise
(`cause/gains-from-search`), and pairing between nets is weak
(`cause/headline-pairing-weak`, MDE 0.06-0.07 clears at 500).

CPU estimate: about 90 thread-h (A20 controls ~16; three 40k learns at
A20 ~48; seed 201's two reads ~16; the replicates' one-turn reads ~9).
Cap 135 cpu-h, end 2026-11-22, on-close wake always. Alternatives passed
over: one seed only (cheaper by ~25 thread-h, but a single seed is a
lead and the recipe's spread at A20 is unmeasured); picking the best of
three seeds for promotion (selection on the ruler; the candidate is
fixed before the reads instead).

## Reviews every 3 days from 2026-11-14 (on the owner's behalf, 2026-11-14)

The owner's operating section already sets the big-picture review to
every 3 days from 2026-11-14; no decision had re-set `owner/reviews`
from it. The next review is due 2026-11-15 (the last was 2026-11-12),
the navigator keeps it to the saved workflow, no extra rounds. Reverse: the owner's word.

## Rules version moves for Fire Breathing on a Curse draw (on the owner's behalf, 2026-11-14)

Why: the game's `FireBreathingPower.onCardDraw` fires on a Status or a
Curse draw (`EvolvePower` on Status only), and the engine counted Status
draws only. Live run 72 (A20, floor 7, burning Sentries) missed by it:
turn 3's draw took Ascender's Bane with Fire Breathing 10 held; the game
showed 38/24/39 HP and 0 block, the engine 44/30/45 and 4. Every A10+
deck holds Ascender's Bane, so under `no-deferring-generalization-gaps`
this is a bug now. A `CardDrawn` hook may now name `CardType Curse` (a
hook on both types is two hooks: Fire Breathing's row); a second counter
holds the Curse draws whose hooks haven't fired, fired after the draw's
Status ones (codec tag 19, only when nonzero). Known difference: the game
fires per card in draw order, the engine Status before Curse within one
draw; it matters only when Evolve's extra draw and a lethal Fire
Breathing hit share a batch (docs/specs/draw-triggers.md).

Golden's existing lines are byte-identical (golden.rs now also loads
act1-colorless.json, last, so earlier ids keep their places); 100444cc
appends the cover game `cover-fire-breathing-curse:ironclad:three_sentries:0`
(burning Sentries; Fire Breathing x2, Ascender's Bane, Clumsy, Dazed),
whose check fails without the Curse hook. The version moves
`32f1971b128452c4 -> d08bc2b781dd64da` with no `SAME_RULES` entry.
Approved by the manager session. Run 72's replay (decisions row 35,
seeds 0-2) on main's swapped sts gives the game's 38/24/39, block 0.

Cost: pack measurements where Fire Breathing meets a Curse shift, which
includes every A20 run. Parked jobs 1016 and 1017 stay pinned to
e25453ec (`-r32f1`) and are re-pinned once after Row V, which moves the
version again (manager's call). Alternative: a `SAME_RULES` entry,
refused because the rules changed. Reverse: revert 100444cc (the version
returns to `32f1971b`; main's sts must be swapped back with it, since
the old loader refuses a Curse draw hook).

## The stall probes become final-round's step 2 (on the owner's behalf, 2026-11-14)

Why: the owner's note of 14 Nov 23:51 (`decision/final-training-round`
rev 2, "Prefer the kill") puts backlog 82 (`leaf-beats-win`) and 85
(`stalls`) before the final round, and a fix that passes goes into the
run's search and labels. The final round is `lane/final-round`, so the probes join its charter
(`docs/lanes/final-round.md`) as step 2, after A20 readiness and before
the A20 controls; the later steps move down one number.

What the step does: (a) 82's cap on an unfinished leaf (no leaf outscores
an immediate win at its HP, with room for the healing its own lines can
add), probed by replaying the recorded decisions that passed a win; (b)
85's progress term at the leaf (or its history form: monsters back in a
state they held earlier in the fight, at lower player HP), probed by
replaying run 83's floor 5 and the stalls of run 56 and A0 run 18, plus a
check of how `learn.py` ends and labels a self-play game at the turn cap;
(c) the probes that pass go into one arm read one turn deep on the
headline at A0 under `decision/level-pass` (they fix a misprice), then
the product with the fix two turns deep; a pass sets the product's flags
(`scripts/product.py set`) before the A20 controls, so both controls and
the round's self-play carry the fix and the round's read varies only the
net. A fix not passed by 2026-11-20 12:00 stays out; the result is
recorded either way. About 10 thread-h, inside the lane's 135 cpu-h cap
(not changed).

Why after A20 readiness, not first: readiness gates the controls, the
run and the read; the probes gate only what goes into them, and their
replays need no CPU, so both fit before the owner's F, V, C2, C3 land.
Why level-pass and not the protocol's +1.5 HP: a leaf that outscores
every finish reachable from it is a misprice, the direction's "Level and
more general is a pass" case.

Alternatives passed over: probing on the bridge only (fight guard 2, a
turn limit handing the fight to a fallback): the owner wants the fix in
the run's search and labels, and a guard fixes play, not the games the
net learns from; reading each fix alone from the start: twice the CPU
for two changes to the same leaf price, so a combined arm goes first and
splits only if it reads below level; adding backlog 76 (`hpe-leaf-cap`,
the same function) to the step: not asked for, and it would confound the
probes' read; it stays on the probe sheet for the next slot.

## Rules version moves for Row V, the game's caps and Shield Gremlin's Protect (on the owner's behalf, 2026-11-15)

Why: three rule fixes land in one golden re-record, so the version moves
once (manager's plan, docs/research/build-plans-2026-11-14/README.md).

- Row V (live run 77): the game's `VulnerablePower` and `NoBlockPower`
  set `justApplied` only when `turnHasEnded && isSourceMonster`;
  `WeakPower` and `FrailPower` on `isSourceMonster` alone. The engine
  held every monster-sourced one back, so Spore Cloud from a Fungi Beast
  the player's card killed lasted a round too long. New power field
  `skips_first_round.from_monster_after_turn_end` (Vulnerable, NoBlock)
  and `CombatState::turn_has_ended` (from the monsters' turn start to the
  round's end).
- C1 (run 78's plan, docs/research/build-plans-2026-11-14/engine-caps.md):
  block stops at 999 for every creature, energy widens to i16 and stops
  at 999, and a power row's `cap` keeps its amount within -cap..cap
  (Strength, Dexterity, Shackled, Plated Armor 999; Poison 9999).
  Uncapped amounts and the per-turn counters saturate instead of
  wrapping.
- Shield Gremlin's Protect (run 83): `BlockAlly` lands when the move
  runs, before later monsters act (the monsters' turn pauses at
  `Stage::MonsterActing` on a pick among two or more candidates, which
  exclude monsters showing an Escape move); `Allies` reads whether
  another monster lived at the monster's last move; a lone Shield
  Gremlin opens with Protect.

Golden: 640 lines of golden.txt move, all Fungi encounters (two_fungi_beasts
285 Ironclad and 231 Silent, exordium_wildlife 62 and 62); golden_proving.txt
moves 273 Fungi lines. V alone gives the same lines; C1 and Protect move no
existing line; the 8 earlier cover games are byte-identical. Four cover games
are appended: cover-spore-cloud-held:silent:two_fungi_beasts:0,
cover-gremlin-protect:ironclad:pack:0, cover-gremlin-allies-at-move:ironclad:pack:0,
cover-lone-shield-gremlin:ironclad:pack:0. The version moves
`d08bc2b781dd64da -> 334dd4b4ef071632` with no `SAME_RULES` entry. Approved
by the manager session; landed in 378e2a40 (with 32c7fa17 V and 68d1bcc7
C1 rebased onto main), `jobs.py impact sts`: no unpinned job hit. Live replays on the new sts: run 77 floor 7 turn 3
Vulnerable 1, Strength 3, HP 56 and turn 4 Strength only (the game's); run
83 floor 5 turn 2's outcome protecting slot 2 gives the game's turn 3 (Mad
Gremlins 18/0 and 21/7).

Stale results (no comparison against them until they are re-recorded): the generated-enemy rows with Vulnerable on a trigger in the player's
turn now tick, GE-OppCard-Vulnerable and GE-AttackLoss-Vulnerable (24-mechanic
bench) and GE-OppAttack-Vulnerable and GE-Attacked-Vulnerable (wide bench);
36 files under results/mutate hold such rows (gen-*-all24, gen-*-boss24,
gen-wide-*, gen-enemies-b1, gen-b1-*, rw-*, fickle-enemy, pjb-*), and only
those rows change (elite and boss parents meet no Fungi Beast; no NoBlock
rows exist). The gauntlet's one-turn controls (yardstick/one-turn-controls)
shift through the Fungi hallway fights: parked jobs 1016 and 1017 are
re-pinned to 378e2a40 (outputs `-r334d`) and stay parked; the navigator
decides whether the A0 controls are re-recorded under the A20 default. gen_content.py's `Apply:Vulnerable` on a
monster-owned power splits the same way.

Cost: every ladder cache, self-play set and manifest keyed by the rules
version is from the old rules; nets trained on Fungi fights saw the old
timing (one turn of Vulnerable). Alternative: a `SAME_RULES` entry, refused
because the rules changed. Reverse: revert the landing commits (the version
returns to `d08bc2b7`; main's sts must be swapped back with them, since the
old loader refuses `from_monster_after_turn_end` and `cap`).

## Lane blind-row-kinds closed (2026-11-15)

Outcome: ended at its end date (2026-11-14, moved up when one lane took the final round) before it started: no spec, no test, no CPU. 0.0 cpu-h used of the
5 cpu-h cap. Opening entry's rating: even that it finds a blind element
beyond RoundEnd; about 3 thread-h. The charter's on-close (no wake, no new
lane) holds: the slot stays empty while one lane runs.

**Reopen if:** a second lane slot opens (after the final round). Backlog 72 keeps its text; its starting list is
`docs/research/engine-audit.md` entries 9 and 14 (the nine effect atoms that
write no column, Shield Gremlin's Protect among them). It also comes back
earlier if a goal-1 read shows a custom element the net can't see.

## Lane machine-throughput closed (2026-11-15)

Outcome: ended at its end date (2026-11-14, moved up when one lane took the final round) before it started: no spec, no code, no CPU. 0.0 cpu-h used of the
15 cpu-h cap. Opening entry's rating: likely to build parts (a)-(c) and
(e), even that (d) is adopted. The charter's on-close (no wake, no new lane)
holds: the slot stays empty while one lane runs.

**Reopen if:** a second lane slot opens (after the final round), or learns become the queue's bottleneck (a final-round learn is
about 2.2 h at 6 threads, three of them in this round): then (a) the sparse
feature cache comes back first. Backlog 66 keeps its text.

## Act 1 relics next after Row 1 (owner, 2026-11-15)

The owner set the act1 work's next scope and order, after Row 1
(805065dc): (1) Frozen Eye (build-plans row 6), then Runic Dome (row 7),
each landed on its own by `docs/research/build-plans-2026-11-14/frozen-eye-runic-dome.md`,
golden unmoved (a moved golden.txt stops the build and goes to the manager);
(2) the combat part of the 10 relics `docs/INDEX.md` lists as "writable,
out-of-combat part blocked" (Bottled Flame, Bottled Lightning, Bottled
Tornado, Busted Crown, Coffee Dripper, Cursed Key, Ectoplasm, Fusion Hammer,
Girya, Sozu) and the 2 "no effect" relics (Cultist Headpiece, Spirit Poop),
each checked against its game class, with `docs/research/act1-coverage.json`
saying what is loaded and what waits on the run layer; (3) a draft spec, not
built, for the run layer R2 covering the 45 out-of-combat relics (rests,
rewards, shops, max HP), left for the manager and owner to confirm since it
touches the gauntlet and headline reads. One landing per item or small group.
Rows 8-14 of the build-plans README come after.

## Stall probes, final-round step 2: the win cap goes to the adoption read, the progress term is dropped (on the owner's behalf, 2026-11-15)

Evidence: `docs/research/stall-probes.md`. The win cap (`@wc1`, an unfinished leaf scores at most a win at the HP it can still reach, less 0.001) turns the recorded stalls into kills inside the turn (run 56 floor 14: 9 of 10 cases, plain 1; run 52 floor 5: 3 of 4, plain 0) and stops no kill the plain search took. It goes to the adoption read: one turn deep at A0 on the headline setting against the one-turn control (`--vary price`, `decision/level-pass`); on a pass the product with it two turns deep against the headline control. Alternatives: skip the read and adopt on the probe (a gauntlet stall ends later as a win or a stall, so the headline effect is unknown: no); the cap without the 0.001 margin (ties fall to the lower option index: it took the win in fewer cases). The progress term for backlog 85 (a leaf with no monster HP lost or dead scores c lower) fails the probe's kill-fast rule: run 83 turn 40 still strikes the block at every c from 0.03 to 0.3 (12 damage into 11 block counts as progress), so backlog 85 needs the net input (backlog 81's); the term is not built. A self-play game at the turn cap is labelled a loss (`selfplay.hp_label`), nothing to fix.
