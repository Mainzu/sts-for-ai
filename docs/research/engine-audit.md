# Engine audit: patches over old constraints (2026-11-13)

The question: card ids and piles turned out to be a patch over an early
constraint (count-per-id byte arrays, then 4 variants and 40 pack-card
slots to work around them). Where else does the engine have patches like
that, what does each one cost today, and which are worth fixing first?

Scope: `engine/src`, `py/src`, and the Python scripts that mirror them
(`scripts/`, `solvedb/`). This was read only: nothing was built, run or
measured. Every "blocks" claim comes from the code, the docs, kb facts or
git history, and each one is cited.

Method: ten readers each covered one area (state.rs in two halves,
registry.rs in two halves, content modules, monsters and runner, search
and solver, the binding, the encoder, the Python mirrors). A second
skeptical reader then checked every finding: it opened the line, checked
the cited commits with `git show`, and looked for content that actually
hits the problem. It corrected 60-odd findings and refuted 8. A last
critic searched the whole tree for kinds nobody had reported and added 5.
I merged the 95 surviving findings into the 46 entries below and
spot-checked the top ones against the code.

**Covered elsewhere.** `docs/specs/sparse-piles.md` (being written) covers
card ids as a byte (`CardId(u8)`, `NUM_CARD_IDS <= 256`), piles as
count-per-id lists (`Pile`, `PILE_CAP`, `PILE_SLOTS`, `PILE_SLOTS_32`),
per-copy `VARIANTS` and variant ids, and `CARD_SLOTS` with the
`LOW_SLOTS` id mapping. They are not analysed here. The section
"Consequences of the card ids" lists what they cause downstream, so the
spec can check that it reaches all of them.

## How entries are scored

- **Blocks (1-5).** 5 means real Act 1-3 content is kept out, or play is
  wrong now. 3 means a measured cost today (a rules deviation in loaded
  content, wrong net inputs on a bench in use, research scope cut), or a
  near-term silent bug. 1 means upkeep only, or a latent problem nothing
  reaches.
- **Cost (1-5).** 1 is an hour to a day in one session (S). 3 is a spec of
  a few steps (M). 5 is a multi-spec change that moves the codec, nets or
  golden files (L).
- **Rank** is blocks divided by cost. Ties go to the higher blocks score,
  then to what is wrong today over what is latent. The scores are rough,
  so read neighbouring ranks as one band.

## Top five

1. **Encoder value flags aren't in the net's meta** (`py/src/lib.rs:1203`).
   Backlog 75(d) trains the next net with `@sn1`/`@xh1`. Nothing records
   those flags in the saved net, the self-play and `features_for` paths
   never set them, and `@sn1`'s arithmetic is wrong for multi-hit attacks
   under Weak. Fix: S, before that training.
2. **Known top drops a 9th shuffled card** (`engine/src/state.rs:591`).
   The draw odds are wrong, and official cards reach it (Headbutt plus
   Wild Strikes: Bash first at 0.2 where the game gives 0.1). Fix: S, and
   it is already specified as B-5.
3. **Python mirrors engine bytes and constants by hand**
   (`scripts/selfplay.py:44`, `scripts/analysis/mutate_monsters.py:241`).
   `WIN_HEAL[character]` ignores Black Blood and Meat on the Bone, which
   are both loaded. The codec byte walkers break silently on the next
   `Monster` field. Fix: S.
4. **Power rules held in code by name** (`engine/src/state.rs:3315`). This
   causes a real Act 1 deviation. In the game, Artifact blocks Flex's
   LoseStrength, so the Strength stays. In this engine LoseStrength is
   `debuff: false`, so Artifact ignores it and the Strength goes at turn
   end. The `debuff` field in `powers.json` is never read. Fix: S.
5. **Monster damage hand-computed twice** (`engine/src/agent.rs:101`,
   `engine/src/heuristic.rs:150`). The copies skip generic statics, so on
   the goal-1 bench mods `dmg0.8` and `weakhit1-dmg0.8` the `rate_damage`
   input nets read, and the heuristic's damage rate, are 25% too high.
   Fix: S.

The entries that block the most, whatever they cost:

- No action queue (#29).
- No encoding for pack content (#12).
- Random-target chance events (#13).
- `extra_rows` (#14).

Together these keep out Juggernaut, Dead Branch, Mummified Hand, Warped
Tongs, Toolbox, Magnetism and Mayhem, exact labels for every pack fight,
and every default net's view of relics, potions and rules.

## Five root causes

Most entries come from five causes. Fixing a cause retires several
entries at once.

1. **Content numbered by process-local order.** Card ids, the
   `Power::Gen0..Gen23` slots, `MonsterKind` bytes and the registry
   tables are all numbered by load order. As a result the codec can't
   write pack content (#12), the solver gets no labels for pack fights,
   pack powers can't be named in conditions (#43), the wide pack was cut
   from 580 copies to 174 (#24), and AddCard can only name official
   cards. Relics and potions already follow the rule kb
   `decision/registry-first` sets ("strings name content"), and nothing
   else does.
2. **Only a card in play can pause.** A pick or a random hit needs a
   stage, and only cards, potions and Gambling Chip's relic pick have
   one. So hooks refuse pausing effects (an allow-list), the monster turn
   is one synchronous loop, and each deferred mechanic got its own side
   counter (#29, #13, #30). This is the biggest content blocker.
3. **"Keep old bytes identical."** The habit is sensible, but it has
   frozen several things: `Encounter::ALL` at 15 (#7), the contract pins
   that push specs toward "no column" (#9), Debug text kept as a
   compatibility surface (#39), the codec append-only at v1 (#36), legacy
   net columns (#37), content-file v1 readers (#40), replay-by-seed
   records that rule fixes must not disturb (#44), and versions that hash
   source text (#26). Each one is cheap alone, but together they mean
   every rules fix needs a re-baseline, and the re-baseline never comes.
4. **Readers that re-derive rules.** The agents, heuristic, encoder and
   leaves each keep their own approximation of what the engine does:
   damage (#5), shown numbers (#1), hook rates and the next draw (#17),
   the turn-reset stages (#25), and the score in about eight places
   (#30). Each new rule (DamageDown, relic hooks, the turn-start move)
   lands in the engine and is missed in one or more copies.
5. **Silent no-ops at a cap.** Several places do nothing, or the wrong
   thing, instead of failing: known-top floaters (#2), the variant table,
   `TOP_QUEUE_CAP` (#15), `Effect::scaled`'s wildcard (#6), effect atoms
   that write no column (#9), and i16 wrapping in release (#10). Making
   each one loud is usually an hour's work and should come first.

## Ranked list

| # | Entry | Where | B | C | Size |
|---|-------|-------|---|---|------|
| 1 | Encoder value flags not in net meta; shown-numbers arithmetic | py/src/lib.rs:1203 | 4 | 2 | S |
| 2 | Known top silently drops floaters past 8 | engine/src/state.rs:591 | 2 | 1 | S |
| 3 | Python mirrors engine bytes and constants | scripts/selfplay.py:44 | 2 | 1 | S |
| 4 | Power rules held in code by name, plus gating lists | engine/src/state.rs:3315 | 3 | 2 | S |
| 5 | Monster attack damage hand-computed twice | engine/src/agent.rs:101 | 3 | 2 | S |
| 6 | `Effect::scaled` wildcard leaves effects unscaled | engine/src/effects.rs:282 | 3 | 2 | S |
| 7 | `Encounter::ALL` frozen at 15 (bosses in `ADDED`) | engine/src/monsters.rs:598 | 3 | 2 | S-M |
| 8 | Search settings ride in the net's `Prices` | py/src/lib.rs:1097 | 3 | 2 | S-M |
| 9 | Effect atoms with no net column; pins by position | py/src/features.rs:1077 | 3 | 2 | S-M |
| 10 | i16 game numbers wrap in release; unchecked casts | engine/src/powers.rs:250 | 3 | 2 | S |
| 11 | `POWER_CAP` 12 asserts (panics) in release | engine/src/powers.rs:182 | 3 | 2 | S |
| 12 | Codec numbers content by process order: no encoding for pack fights | engine/src/codec.rs:146 | 4 | 3 | M (+S guard) |
| 13 | Random-target chance event carries only an amount | engine/src/chance.rs:218 | 4 | 3 | M |
| 14 | Seven row kinds behind one `extra_rows` switch | py/src/features.rs:108 | 4 | 3 | M |
| 15 | `TOP_QUEUE_CAP` 6: PlayTop silently stops | engine/src/state.rs:1605 | 1 | 1 | S |
| 16 | Code-backed monsters by `MonsterKind` | engine/src/state.rs:3221 | 3 | 3 | M |
| 17 | Card rules as one field per mechanic | engine/src/registry.rs:1810 | 3 | 3 | M |
| 18 | `MonsterKind` is a byte: 236 pack monsters a process | engine/src/registry.rs:586 | 3 | 3 | M |
| 19 | Leaf switches; a hand copy of the turn-reset stages | engine/src/search.rs:289 | 3 | 3 | M |
| 20 | Versions by hashing source and golden text | solvedb/src/fingerprint.rs:18 | 3 | 3 | M |
| 21 | Product two-turn player lives in an analysis script | scripts/analysis/depth_paired.py:67 | 3 | 3 | M |
| 22 | Boss status: a global mask plus a side flag | engine/src/monsters.rs:443 | 2 | 2 | S |
| 23 | Readers that see power hooks only | engine/src/agent.rs:350 | 2 | 2 | S |
| 24 | Fight setup and the play loop copied in the binding | py/src/lib.rs:2149 | 2 | 2 | S-M |
| 25 | One `condition_param` and hand-offset row writers | py/src/features.rs:1193 | 2 | 2 | S-M |
| 26 | Gauntlet rest-site upgrade shim | scripts/gauntlet.py:602 | 1 | 1 | S |
| 27 | render.rs pending text written twice | py/src/render.rs:126 | 1 | 1 | S |
| 28 | CardDrawn fires with a fake Dazed, Status only | engine/src/state.rs:1175 | 1 | 2 | S |
| 29 | No action queue: hooks can't pause; side counters | engine/src/registry.rs:2172 | 4 | 5 | L |
| 30 | Outcome score defined in about eight places | engine/src/solve.rs:310 | 2 | 3 | M |
| 31 | Relic side tables; eight helper powers | engine/src/relics.rs:61 | 2 | 3 | M |
| 32 | Every effect in about eight hand-kept matches | engine/src/upgrade.rs:224 | 2 | 3 | M |
| 33 | One-card mechanics as CardDef side fields | engine/src/cards.rs:216 | 2 | 3 | M |
| 34 | Character as a closed enum | engine/src/character.rs:77 | 2 | 3 | M |
| 35 | `MAX_MONSTERS` slots reserved, never freed | engine/src/state.rs:22 | 2 | 3 | M |
| 36 | Codec append-only at version 1 | engine/src/codec.rs:177 | 2 | 3 | M |
| 37 | Legacy columns in the full layout | py/src/features.rs:453 | 2 | 3 | M |
| 38 | Explorer re-implements content, RNG and run order | scripts/explore.py:1811 | 2 | 3 | M |
| 39 | Debug text as a compatibility surface | engine/src/state.rs:752 | 1 | 2 | S-M |
| 40 | Content-file v1 readers woven into the parsers | engine/src/registry.rs:2274 | 1 | 2 | S |
| 41 | gen_content's hand pair lists have drifted | scripts/gen_content.py:72 | 1 | 2 | S |
| 42 | Seven stacked constructors | engine/src/state.rs:912 | 1 | 2 | S |
| 43 | Two tiers of content: official enums plus Gen slots | engine/src/powers.rs:82 | 2 | 5 | L |
| 44 | Records replay from seed, so rule fixes are declined | engine/src/monsters.rs:126 | 3 | 5 | L |
| 45 | Rust forward pass duplicates stsnet | py/src/net.rs:218 | 1 | 3 | S-M |
| 46 | Unchecked `as` casts in the pack parser | engine/src/registry.rs:1944 | 1 | 1 | S |

(#46 belongs with #10. It is listed apart because it is a separate,
mechanical fix.)

## Entries

### 1. Encoder value flags aren't in the net's meta; shown numbers use their own arithmetic

- **What.** `shown_numbers` and `exhaust_hidden` are encoder flags
  bolted on with `.with_*` (`py/src/lib.rs:900-923`). `PyNet::new` reads
  them from its config (`lib.rs:1203`), and `stsnet.rust_evaluator` takes
  them as player-setting kwargs (`scripts/stsnet.py:852`). But
  `stsnet.features_for` (`stsnet.py:1057`), used by finetune, curve,
  gauntlet and convert_net, never passes them, and selfplay's training
  encoder (`selfplay.py:74`) has no such flag. Unlike lookahead, rates
  and start_hp, these two change values without adding any column name,
  so nothing in a saved net records them. Separately, `@sn1`'s arithmetic
  (`py/src/features.rs:716`) is ported from a probe script and floors the
  total, not each hit. Twin Strike 5x2 under Weak shows 7 where the game
  deals 6, Pummel 2x4 shows 6 where it deals 4, and statics other than
  Strength, Dexterity, Weak and Frail are ignored. `next_draw_size`
  reads power hooks only, so a draw relic misplaces the known-top split.
- **Works around.** Each column group was added as "off writes today's
  layout bit for bit" (c2795ea6, a7dac15c, 76e75e4e, 662b6c66). The two
  value flags came later as zero-shot player settings (2ad0e585).
- **Blocks.** Backlog 75(d) (68750d9a) trains the next net with
  `@sn1`/`@xh1` on. As things stand, its training batches and its play
  batches agree only if every player string repeats the flags and someone
  first adds them to the self-play and `features_for` paths. A mismatch
  would be silent. The arithmetic would then become the trained input.
- **Clean model.** The flags become net meta keys. `features_for`,
  `rust_evaluator` and self-play read them from the meta, and a setting
  that disagrees with the meta is refused. Shown numbers come from an
  engine helper (`CombatState::shown_damage(card)`, per hit, on the real
  `attack_shape` and statics path), and the parity script checks against
  the engine. Later, optionally: the saved layout is the only switch for
  what is written, and the prefix sniffing (`features.rs:509-521`, 556)
  goes.
- **Cost.** S for the meta keys and the refusal (three Python call sites).
  S for the helper (the `@sn1` reads would be redone). M for the
  layout-is-the-switch redesign, which is optional.

### 2. Known top silently drops floaters past 8

- **What.** `Top` holds `known: [u8; 16]` and `floaters: [(u8, u8); 8]`
  (`engine/src/state.rs:519-536`). `add_floater` returns without doing
  anything once 8 are held (591-598), and each copy takes its own entry.
  An untracked card is then treated as certainly below every known card.
- **Works around.** A fixed-size `Copy` state. docs/decisions.md:1989
  called the caps "unreachable with in-scope content" (c8516bb4).
- **Blocks.** A rules deviation that official content reaches. B3 in
  `docs/specs/series-review-fixes/B-chance.md:166` reproduces it: Headbutt
  puts Bash on top, then 9 Wild Strikes shuffle in 9 Wounds, and the
  engine gives Bash first at 0.2 where the game gives 0.1. Search and the
  solver use these odds. In real play this setup is rare, but a pack
  AddCard-to-draw with n >= 9 reaches it in one play. B3 sits in the Part
  3 backlog, unscheduled.
- **Clean model.** Counted floaters, one entry per distinct (card, above)
  with a copy count, as B-5 specifies. If the table of distinct pairs
  overflows, that is an error, not a forget.
- **Cost.** S. B-5 is fully specified (about 70 lines plus a codec
  varint), and existing encodings and golden files don't change.

### 3. Python mirrors engine bytes and constants by hand

- **What.** Each of these is a hand copy of something the engine owns:
  - `selfplay.WIN_HEAL = {"ironclad": 6, "silent": 0}`
    (`scripts/selfplay.py:44`, used at 299 and 492) is a per-character
    constant for what is now a per-fight value (`CombatState.win_heal`,
    65550e28).
  - `mutate_monsters.py:241` and `bias_audit.py:94` walk codec bytes by
    hand to patch monster HP and powers (5b78f06c, 303e65f1). They are
    load-bearing: `finetune.py:142` uses them for mutated starts, and so
    does random_world.py.
  - `stsnet.NUM_SLOTS = 5` (`stsnet.py:53`) copies `MAX_MONSTERS`.
  - The play turn limit of 100 (`runner.rs:22`) is mirrored in Python,
    and a stalled loss reports the HP it has left, against the doc.
- **Blocks.** Black Blood (`win_heal` 6, `content/packs/act1-relics.json:52`)
  and Meat on the Bone (a `CombatWon` Heal 12, line 58) are loaded. The
  moment a self-play config holds relics, the HP-lost labels are wrong,
  with no error. A `Monster` field added without a codec version bump
  (#16's phase field, for one) makes the walkers patch the wrong bytes,
  and their round-trip assert passes on any well-formed splice.
- **Clean model.** Labels read the state's `win_heal` (an accessor, or the
  batch column the encoder already writes). Add
  `Combat.with_monster_hp(slot, hp, max_hp)` beside `with_monster_power`
  (f0b20018) and delete both walkers. Export `MAX_MONSTERS` and
  `PLAY_TURN_LIMIT`, plus a `stalled` flag in the result.
- **Cost.** S: one PyO3 method, an accessor, three exports, and about 120
  lines of Python deleted. Labels stay identical on current data.

### 4. Power rules held in code by name, beside their data rows

- **What.** Several power rules match on names in code:
  - `apply_power` marks `just_applied` only for `is_duration_debuff()`
    from a monster (Vulnerable, Weak, Frail, `powers.rs:162`) or for
    `Power::Ritual` (`engine/src/state.rs:3315`).
  - Poison's LoseHp gets `HpLossFrom::Any` by name (2321).
  - SplitHits halves hits by name (3350).
  - Official debuff status is code (`powers.rs:167`), and `powers.json`'s
    own `debuff` field is only checked to equal it
    (`registry.rs:2618`), never read.
  - Hand-kept lists gate the hook scans (`ATTACKED_POWERS`, the RoundEnd
    gate, the static fast path, `state.rs:2866`, f3a11c06, fee56fef).
    Any binding or held relic turns the gates off.
  - Rule fields (forbids, sets_cost, exhausts_played) and CardDrawn are
    read for pack powers only (`state.rs:1183`). On an official power
    they would be silently dropped.
- **Works around.** These rules were written before powers became data
  rows (b4f9b968, 18b3fba5) and stayed in code to keep golden output
  identical.
- **Blocks.** A real Act 1 deviation. In the game, `LoseStrengthPower` is
  a debuff, so Artifact blocks it when Flex applies it and the Strength
  is kept. Here the official LoseStrength is `debuff: false`
  (`content/powers.json:13`), so Artifact lets it through and the
  Strength is lost at turn end. Artifact reaches the
  player through the pack's Ancient Potion (`act1-potions.json:22`) and
  Clockwork Souvenir (`act1-relics.json:33`). docs/extending.md:525
  records this as a known limit, kept because "fixing it changes existing
  content". The first pack duration debuff, Ritual-like power or
  poison-like power would hit the other name rules. Pack fights pay the
  full hook scan, a cost that has not been measured on its own.
- **Clean model.** Official powers read their `debuff` field. Add data
  fields `skips_first_round { from_monster, on_monster }`, an
  `hp_loss_source` on LoseHp rows, and an attack-shape static for Split
  Hits. Compute the per-trigger masks at bind time from the rows, which
  replaces the lists. Fixing LoseStrength then becomes a one-word data
  change with a deliberate golden re-record.
- **The other side: temporary Strength down (owner's note, 2026-11-13).**
  The game handles the two directions differently. For temporary
  Strength up (Flex), it applies Strength +n, a buff, and then
  LoseStrength n, a debuff that Artifact can block. For temporary
  Strength down (Piercing Wail, Dark Shackles), it applies Strength -n,
  a debuff. Only if that wasn't blocked does it apply the restoring
  GainStrength (Shackled), which the game also types as a debuff,
  although it is really a buff. This engine already treats negative
  Strength as a debuff (`powers.rs:167`, as the game does). It has no
  GainStrength power, and no card that uses one is loaded, so nothing
  is wrong yet. Adding one needs either "apply only if the previous
  effect landed", which the effect language can't say today, or a
  single "temporary Strength change" effect that carries this rule.
  The game patches its fake debuff in one more place, by name: Sadistic
  Nature skips Shackled when it counts debuffs
  (`powers/SadisticPower.java:37` in aeubanks/sts,
  `!power.ID.equals("Shackled")`), so Piercing Wail triggers it once per
  enemy. A signed turn-end power that counts as a buff when it raises
  Strength gives the same result with no exception, so no switch for a
  deliberate deviation is needed.
- **Cost.** S for the fields with golden identical. The LoseStrength fix
  is a deliberate rules change on top. The bind-time masks are S-M with a
  series_speed read.
- **Status.** The fields are built (`registry::PowerRules`, the hook's
  `hp_loss_source`; docs/extending.md "Power fields"), golden identical:
  official powers read `debuff`, `debuff_if_negative`,
  `skips_first_round`, `attack_shape` and the card rules from their rows,
  and the `CardDrawn` gate scans official powers with such a hook.
  `LoseStrength` is `debuff: true`, so Artifact blocks Flex's loss as in
  the game (golden unchanged: no golden game holds Artifact). Left:
  the bind-time masks, and `Power::is_duration_debuff`, which the
  counterfactual reader (`cf.rs`) still uses.

### 5. Monster attack damage hand-computed in two more copies

- **What.** `agent::move_damage` (`engine/src/agent.rs:101`) and
  `heuristic::move_damage` (`engine/src/heuristic.rs:150`) compute a
  move's damage as base + Strength, then Weak, by hand. They skip the
  engine's generic static path.
- **Blocks.** 71332048 added DamageDown (a generic DamageDealt x4/5) and
  SplitHits together. It put `attack_shape` into all four walks but left
  the hand formula without DamageDown. So on the goal-1 bench mods
  `dmg0.8` and `weakhit1-dmg0.8` (`scripts/analysis/mutate_monsters.py:64,81`),
  the lookahead `rate_damage` input that nets read, and the heuristic's
  future damage rate (`heuristic.rs:224`), overstate damage by 25%. The
  "now" term is right. Any pack static that changes attack damage does
  the same. Official monsters hold no generic static, so official play is
  unaffected.
- **Clean model.** One engine helper,
  `CombatState::move_attacks(slot, mv) -> (per_hit, hits)`, on
  `attack_shape` and `attack_damage` (with a flag to leave out the
  defender's Vulnerable). `intent_damage`, both `move_damage`s and
  `board`'s hit count all call it.
- **Cost.** S: one helper and four call sites. It is bit-identical on
  official content, because `attack_damage`'s fast path equals the hand
  formula. Only the dmg0.8 mutate rows re-pin, checked with series_check.
- **Fixed** (2026-11-13). `CombatState::move_attacks(slot, mv, vulnerable)`
  gives one (damage per hit, hits) per attack effect; `intent_damage`,
  both `move_damage`s and `board`'s hit count read it. Test:
  `monster_mods.rs` `damage_down_reaches_move_damage`. Golden unchanged;
  series_check skipped (no time, manager's call), so the moved mutate
  outputs aren't listed.

### 6. `Effect::scaled` leaves most effects unscaled by stacks

- **What.** `Effect::scaled` ends in `e => e` (`engine/src/effects.rs:282`),
  so AddCard, ApplyPack, RandomDamage, RandomApply, ScaledDamage, Pick,
  PlayTop and ExhaustRandom come back unchanged when a power with
  several stacks fires. The hook docs (`hooks.rs:1-3`, 269) and the
  generator (`mutate_monsters.py:197`, "stacks scale every amount") both
  assume every effect scales. `potions::scaled_effect`
  (`potions.rs:201`) is a second hand list for potion potency.
- **Works around.** It was written for the few hook effects of 086bd849
  (2026-10-24), and arms were added one at a time after that.
- **Blocks.** One wrong result in content in use now:
  `content/packs/gen-enemies-wide.json` (lane wide-recipe-confirm) gives
  11 monster copies 2 stacks of a GE-*-Dazed atom (AddCard Dazed 1). At 2
  stacks the engine still adds one Dazed, so `gen_enemy_pack.py`'s stack
  variation does nothing for those copies (4ec79767). No official content
  is affected.
- **Clean model.** One exhaustive `scaled` with no wildcard, every
  variant either scaled or explicitly unscaled (ReplayCard, RemoveSelf,
  ReduceSelf). `scaled_effect` becomes that function plus a
  potency-only flag. Multiply in i16 and clamp, rather than casting down.
- **Cost.** S. It changes play for those 11 copies and moves the rules
  fingerprint, so wide-pack reads stay pinned or get re-measured.

### 7. `Encounter::ALL` frozen at 15; the two Act 1 bosses sit in `ADDED`

- **What.** `Encounter::ADDED = [Hexaghost, TheGuardian]`
  (`engine/src/monsters.rs:598`) sits beside `ALL` (577, 15 entries), "so
  spec generators by group, encounter_names(), golden games and every
  bench set keep their 15 encounters" (833f6939, 8ec38ffd). Several
  readers see `ALL` only: `runner::group_specs_as` (`runner.rs:89`, which
  `make_specs` uses), `sts.encounter_names()` (`py/src/lib.rs:2380`), and
  through it `replay.py --encounter` and
  `selfplay.with_pack_encounters`. The last one would treat a pack
  encounter with id `hexaghost` as an addition, not a replacement. The
  determinism, golden, fuzz, codec and solve tests never run these two
  bosses.
- **Blocks.** Default self-play never meets 2 of Act 1's 3 bosses. kb
  `cause/boss-deaths` puts Hexaghost (70) and the Guardian (57) at most of
  the headline's boss deaths, against 13 for Slime Boss. The verifier's
  correction: training on them was tried on purpose (lane
  unseen-boss-burst failed, and they are now held out as "unseen
  bosses"), so this freeze is not the only reason. Still, every new
  official encounter (Act 2) gets the same two-list treatment, and
  scripts hand-name the bosses (`bench_sets.py:95`, `gauntlet.py:40`).
- **Clean model.** Recorded artefacts name their roster: `group_specs`
  takes an encounter list, and the bench, golden and test generators pass
  a frozen "act1-15" list, so their bytes stay the same. `ALL` becomes
  every official encounter, and whether training sees the bosses becomes
  a config choice.
- **Cost.** S-M. No codec or net change. It needs a decision on keeping
  the bosses unseen in training reads.

### 8. Search settings ride inside the net evaluator's `Prices`

- **What.** Six leaf and search switches (`@tsl1`, `@lcb1`, `@tb1`, `@dl`,
  `@pl`, tie_break) live in the binding's `NetEvaluator` "Prices"
  (`py/src/lib.rs:1097`). The leaf prices wrapper (`add_prices`, 1141) is
  binding-only too.
- **Blocks.** The heuristic baseline can't take `@tsl1`/`@lcb1`/`@tb1`.
  Backlog 75 (68750d9a) wants them as default player settings, while
  goal 1's novelty cost is net minus heuristic on the same starts (kb
  `measurement/genpack-reach@bosses`). So the two players would search
  under different leaf rules. `run(luck=)` refuses any net whose Prices
  differ from the default (`lib.rs:2132`), even tie_break. Each new flag
  costs about 45-50 lines across lib.rs, bench.py and stsnet.py (3872195e,
  c297a943, 17ca5006, 1e568630). 1d9c3cca (max-HP scaling) had to edit
  search.rs and lib.rs together and left the binding test unscaled.
- **Clean model.** Search options live only in `SearchConfig`, and one
  `search=` dict goes to `sts.search`/`run`/`play_on`. `Priced<E>` is an
  engine adapter that wraps any evaluator. `bench.player_settings` splits
  a player string into net settings and search settings, so
  `heuristic@tsl1` works. Later, optionally: the player string is parsed
  in Rust with versioned defaults.
- **Cost.** S-M, about a day. Ladder keys stay the same strings.

### 9. Effect atoms that write no net column, and pins that make columns expensive

- **What.** `Encoder::effects` writes nothing for BlockAlly, ApplyPack,
  Heal, HealOf, GainMaxHp, DrawPicked, PlayTop, Discover or
  ObtainRandomPotions (`py/src/features.rs:1077-1081`, "no column, the
  layout stays"). The arms are explicit, so the compiler does make each
  author decide. The reason "no column" keeps winning is the pins:
  `scripts/tests/contract_pins.py:41` hashes whole-layout batch bytes and
  keeps three positional pre-contract tiny nets. Every additive column
  is therefore a re-pin: `pins.json` has 26 commits (23c0da1a, 851790af,
  461e1efc, 94f807c6, 6b619461, 11d99c51). act1-singles.md:277 gives
  "so the contract tiny nets keep loading" as the reason to add no
  column.
- **Blocks.** Act 1 content reads as incomplete:
  - Shield Gremlin's Protect intent reads as empty.
  - The Regen potion's power reads as one that only shrinks.
  - Infernal Blade, Havoc, Distilled Chaos and Entropic Brew read as cards
    or potions with no effect.
  - Healing relics and potions read as zero, though those rows are opt-in
    anyway (#14).

  A net can't learn the value of an in-fight heal or ally block. The
  size of this cost has not been measured.
- **Clean model.** Pins compare per named column, the way
  `card_vectors.txt` already lists non-zero columns, so a new column
  that is zero on the pinned states changes no pin. The three tiny nets
  are converted once. Then each atom gets a column, or an explicit
  test-checked exemption (WinHeal and the counters are already covered
  elsewhere). Old nets gather by name and never read the new columns.
- **Cost.** S-M: the pin rewrite first, then about six scalars.

### 10. Game numbers are i16 and u8, and release builds wrap silently

- **What.** HP, block, power amounts and `Amount` values are i16, and
  several counters are u8. The release profile sets no `overflow-checks`
  (none in `Cargo.toml`), so `+=` wraps in release and panics in debug.
  Examples: `Powers::add` (`engine/src/powers.rs:250`), `gain_block`
  (`state.rs:3292`), the Strength addition in `attack_damage` (2873), and
  `cards_played_this_turn` (1314). `Amount::at` casts an i32 product
  `as i16` (`effects.rs:62`), which truncates in both builds. The pack
  parser narrows JSON integers with unchecked `as` casts
  (`registry.rs:1944`, #46), so `Draw 256` would load as `Draw(0)`.
  Patches stand around this: no-death HP is floored at `i16::MIN / 2`
  (`state.rs:2030`), the solver refuses states near the wrap
  (`solve.rs:265-281`), and Searing Blow's max level stops at 252.
- **Blocks.** One real bug already: d5dcc55d found no-death HP below
  -16384 overflowing `2 * hp`, which in release gave a wrong bloodied
  check. Only a debug test run found it. The pack's Limit Break doubles
  Strength without bound, and past 32767 it wraps to negative with no
  error. The game uses 32-bit ints.
- **Clean model.** Saturating arithmetic at the few mutation points, plus
  either `overflow-checks = true` in release or a scheduled debug test
  run. Use checked conversions (`T::try_from`) in the parser, as
  `upgrade.rs` already does. Widening to i32 is the alternative: the
  codec already writes varints, so the bytes stay the same.
- **Cost.** S for saturating ops, parser checks and a debug run. M to
  widen, with a clone-speed read.

### 11. `POWER_CAP` 12 is a release assert sized before relics existed

- **What.** `Powers` holds at most 12 entries per creature, and
  `Powers::add` asserts it in release too (`engine/src/powers.rs:257`).
  The number came from the 2026-11-06 census (`docs/specs/sparse-state.md:24`:
  at most 6 on the player, 4 on a monster) over the starter deck and 5
  decks (7d271bcd). `bind_relics` checks only the powers a relic starts
  with (c43ef5ed), not the ones gained later.
- **Blocks.** No recorded hit. But relics (d189cb0d), the 8 Ironclad pack
  powers, potion powers and 8 relic helper powers (#31) all arrived
  after the census. A relic-heavy power deck can now hold Strength,
  Dexterity, Weak, Vulnerable, Frail, LoseStrength, Combust plus
  CombustDamage, Metallicize, Rupture, Demon Form, Vigor, Plated Armor,
  Buffer and helpers such as TheBoot or Torii. In a full-content run that
  panics a job instead of playing on. The game has no cap.
- **Clean model.** Re-census on all-content decks with relics and size
  the cap from that, with a series_speed check. Or use a per-binding
  bound, since the binding knows which powers can appear. Folding the
  helper powers back into relics (#31) also lowers the count.
- **Cost.** S to re-census and raise the cap. M for a per-binding
  capacity.

### 12. The codec numbers content by process order, so pack fights have no encoding

- **What.** `encode()` asserts `!has_generated()` (`engine/src/codec.rs:146`,
  `state.rs:1021`): no binding, no pack monster, no open Discover offer,
  no pending RandomPotion. Cards and monsters are code-order bytes, and
  powers are a mask over the official ones. Relics and potions are
  already written by name (sections 7 and 8), and variants by value in a
  trailer (06fc5c01).
- **Works around.** Codec v1 (349f67e1) was built on official code order.
  Registry-lite (c98fe6b2) then bound pack content into process-local
  slots that have no stable identity.
- **Blocks.** Real today. Act 1 content is mostly packs: 36 Ironclad
  cards and 8 powers, 7 monsters, 31 potions, 56 relics. Effects:
  - Pack fights get no exact labels. learn.py:807 refuses the solve step,
    and learn.py:472 skips states without codec bytes (bd04797a).
  - solvedb and position stores can't hold pack states.
  - The explorer names such states by their replay line.
  - A latent crash: a root state can be encodable (official deck, a pack
    potion held by name, such as Attack Potion or Entropic Brew) while its
    potion-use child is not. `Solver::open` encodes every child
    (`solve.rs:363`), and `representable()` (`solve.rs:275`) doesn't
    check `has_generated`, so engine solve, `puzzles.py:124` or
    `explore.py:765` would panic there instead of returning Unsolvable.
    This was read from the code, not run.
- **Clean model.** Write every content kind by stable identity, as relics
  and potions are: a tagged trailer section holding the pack name and
  hash plus the entry names. Decoding resolves them against the loaded
  packs. Official-only states write no section, so golden bytes stay the
  same. Once encodable, the pack hashes go into the solved-DB
  fingerprint (the stage docs/decisions.md:4130 foresees). This gets much
  smaller after sparse piles and global power ids (#43).
- **Cost.** S, now, for the `representable()` guard (an hour). M for the
  trailer section and a rebind on decode, with solvedb keys gaining the
  pack hash. L if every content kind moves to names in the main body.

### 13. Random-target chance events carry only an amount

- **What.** `ChanceEvent::RandomTarget { amount }` (`engine/src/chance.rs:20`)
  doesn't say what the hit does or who deals it. `random_hit` (218-229)
  re-reads the effect from the card or potion in play, and falls back to
  "an attack from the player". To keep that sound, `runs_outside_a_card`
  (`registry.rs:2172`, 662b6c66) makes hooks and turn-end effects refuse
  RandomDamage, RandomApply, ExhaustRandom, PlayTop, Discover,
  ObtainRandomPotions and Pick.
- **Works around.** The event was built for Sword Boomerang. The potion
  stage was added as a second case (46f5477b) instead of moving "what"
  into the event.
- **Blocks.** Juggernaut, an official Ironclad card that is still blocked
  (`docs/research/act1-inventory.md:121`). It also needs a "gains block"
  trigger, and its damage isn't an attack, so the fallback would be
  wrong for it anyway. Pack relics or powers with a random target are
  kept out, as are random effects in monster moves.
- **Clean model.** `RandomTarget { src, kind: Attack | Plain | Apply(power), amount }`,
  written in the codec only when it isn't the card default, so old bytes
  stay. Hooks then pause and resume mid-hook, which is #29's queue in
  small.
- **Cost.** M, together with a BlockGained trigger for Juggernaut.
  Official games are unchanged.

### 14. Seven row kinds share one opt-in switch

- **What.** By default only triggered, threshold and held rows are
  written (`BASE_KINDS = 3`, `py/src/features.rs:108`). Static,
  countdown, replacement, pattern, rule, relic and potion rows are written
  only with `extra_rows` on, or when a layout names them. RoundEnd hooks
  exist only as the opt-in countdown kind (1216, 155).
- **Works around.** Memory. Written by default, the kinds took rows per
  state from 12.0 to 21.1 and row data to 2.5x (docs/decisions.md:2323,
  662b6c66). Most of that growth was official modifiers writing rows that
  repeat their `power_*` columns.
- **Blocks.** Measured: kb `cause/roundend-blind`. A pack power whose
  only hook is RoundEnd gives no input row, so training on nine RoundEnd
  mechanics taught nothing. By default no net sees a relic (23 Act 1
  pack relics), a potion, Entangled's or Corruption's rule, or a
  monster's next-move pattern. Each of rule, relic and potion was added
  to the opt-in block (d43a6396, 8699ac55, 862d4c42). This is already
  tracked as lane blind-row-kinds and candidate 71 (7e526a0d).
- **Clean model.** Decide per element, not with one memory switch: a row
  that repeats a dimension the entity already has is skipped, and
  everything else is written by default. Saved nets still drop kinds
  they don't read, through `keep_kind`.
- **Cost.** M: new default kinds, a "dimension already present" test,
  re-pins, and series_check with the product net bit-identical.

### 15. `TOP_QUEUE_CAP` 6: PlayTop silently stops

`state.rs:1605` and `registry.rs:2020` (f2f4213c). A full `top_queue`
silently stops taking cards. The load-time `n <= 6` check ignores Sacred
Bark's potency, and the potency's `as u8` cast wraps. Nothing official
reaches it (Distilled Chaos 3 with Bark, Havoc 1). A pack potion with
PlayTop n >= 4 under Bark plays fewer cards. Fix (S): check the scaled n
at fight build where potions and relics meet, use a checked cast, and
make overflow an error.

### 16. Code-backed monsters matched by `MonsterKind`

`state.rs:3221` (`lost_hp`, `after_move`, `rolled_damage`; 40b4f73b,
833f6939, 8ec38ffd). Lagavulin's wake, Hexaghost's Divider and Inferno,
and the Guardian's Mode Shift (whose threshold rides in `rolled_damage`)
are code, with no `phase` field, and Hexaghost keeps a second move-id
cycle. These monsters work in official fights, but they can't become
pack content (docs/decisions.md:6614), and generated enemies can't use
mode shifts or wake-on-damage. kb `cause/bursts-buy-mechanics` names
the boss move schedule as an input the net lacks. Each Act 2-3 boss of
this shape (Champ, Bronze Automaton, Awakened One, Time Eater) adds
another arm. The two 4-move walks in `agent.rs:127` (rate_terms and
lookahead) each copy the same kind checks. Clean model: a `phase: u8`
on `Monster` with `PhaseIs` pattern conditions, monster hooks on
`OwnerLostHp` with a counter, and a `SetMove` effect. Cost M (L with
phase-aware net features). Golden games stay identical by construction.

### 17. Card rules are one optional field per mechanic

`registry.rs:1810` (296d753a, 2860918a). The fields are `forbids`,
`sets_cost`, `exhausts_played` and `cost_less_per_hp_loss`, each
holding one card type. Velvet Choker is listed as blocked for exactly
this reason (`docs/research/act1-relics-potions.md:291`: "forbids takes
a card type, not a count"). Normality, and Blue Candle and Medical Kit
(which make curses or statuses playable), have the same shape. Each new
rule adds a field, an accessor, a check site, a key, a net row and
wording. Clean model: a list of `CardRule { filter, when: Condition,
action: Forbid | SetCost | AddCost | ExhaustOnPlay | AllowPlay }` that
powers, relics and cards can all carry, read by the existing rule rows.
Cost M, with rule-row re-pins.

### 18. `MonsterKind` is a byte: 236 pack monsters a process

`registry.rs:586` (2733882a). Generated enemies are whole monster copies,
each taking a kind. This has already shaped research: the wide pack
wanted 58 mechanics x 10 bases (580 copies) and was cut to 174
(docs/decisions.md:12821, 4ec79767), and the three generated packs plus
act1-monsters can't load in one process. Clean model: an encounter slot
(or a light pack entry) is a base kind plus extra start powers and an
optional HP, so a mechanic attaches to an official monster without a new
kind. Cost M. It changes pack hashes, which matters to pinned jobs.

### 19. Leaf switches pile up, and one keeps a hand copy of the turn-reset stages

`search.rs:289` (17ca5006, de8d5a6f, 1e568630). `leaf_clear_block`
copies the engine's turn-reset stage list, and that copy caused a real
bug: when the turn reset moved, `@lcb1` zeroed the new turn's pre-draw
block (de888ed0). The fix extended the list. Backlog 75 lists `@tsl1`,
`@lcb1` and `@tb1` as more correct and still off by default.
`cause/unseen-cards-half-edge` shows the default leaf hiding Demon Form's
first tick (-7.54 HP a copy until `@tsl1`). The allow-lists in the leaf's
hook passes (`state.rs:2197`) are the same kind. Clean model: one engine
method that "advances through every step that needs no chance, up to the
next chance event or decision", and search picks the leaf with one enum.
The stage list goes away. This pairs with #8. Cost M.

### 20. Versions made by hashing source and golden text

`solvedb/src/fingerprint.rs:18` and `scripts/registry.py:140`. The
solved-DB version hashes the text of 17 rule files, so any refactor or
new card retires the whole cache. docs/decisions.md:605 records 2.43M
rows left behind after one merge, with a CPU-hours refill. Code even
gets placed to dodge it: 06c8f3d3 put an accessor in `threshold.rs`
"outside the rules fingerprint". The rules version is a hash of
golden.txt, patched by `SAME_RULES` (80d6c86c), and new golden games go
into other files to keep the hash (e267baaa). A rule change that only
touches relics, potions or packs leaves the version alone, so datasets
holding such content are not refused. Clean model: an explicit
`RULES_VERSION`, bumped whenever play changes, with golden games and a
sample of solved values checking it. Per-content fingerprints come once
#12 lands. Cost M. Machine time is this project's bottleneck, so the
recurring refills are the main price.

### 21. The product two-turn player lives in an analysis script

`scripts/analysis/depth_paired.py:67` (57656171, e05ed583). The product
player (two-turn search, one-turn fallback, line seed, stepped line)
calls `sts.search` twice per decision, with its own seed rule and its
own play loop, one Python process per thread.
`ladder.play_two_turn`, `gauntlet.py:709`, two_turn_games, learn,
explore and mutate_monsters all import it. Each worker loads the net
itself (about 1.4-1.6 GB a thread, kb `how/two-turn-search`), and every
decision pays a full one-turn search even when it isn't needed. Clean
model: a fallback two-turn agent in `agent.rs`/`runner.rs`, played by the
same threaded runner. Check it against the recorded two-turn games. Cost
M. It buys memory and CPU, which are the bottleneck.

### 22. Boss status: a global mask plus a side flag

`monsters.rs:443` and `state.rs:738` (cfe99eab, be76e88e). The fight's
kind is worked out from a process-wide bitset of boss kinds, filled as
encounters load, plus a `boss_fight` bool that is set only when a held
potion needs it. Meanwhile the constructor drops the `EncounterGroup` it
was given (`state.rs:919`). This is latent, but Act 2-3 content would hit
it: Awakened One's boss encounter includes Cultists, so once it loads,
Cultist counts as a boss in every fight of the process and Smoke Bomb
stops working in a Cultist hallway. Clean model: store `group` in the
state, and the codec writes it only when it isn't Hallway. Cost S. Old
encoded Slime Boss states need a decode fallback.

### 23. Readers that see power hooks only

`agent.rs:350` (`hook_rates`), `heuristic.rs:131` (`deck_output`), and
`features.rs` `next_draw_size`. `hook_rates` reads power hooks only,
into 11 fixed fields shaped after named official powers, with no energy
field. The heuristic's per-turn block, draw and Strength growth
therefore ignore every relic. 9f2a7ed0 fixed the same gap in the
turn-start leaf and `can_heal`, but not here. `deck_output` scores
unclassified effects as 0, while its module doc says new content needs
no changes. Clean model: one "hook holders in firing order" iterator
(relics, then powers) that every reader uses, plus exhaustive effect
matches. Cost S. Heuristic numbers change only in fights with relics or
energy hooks.

### 24. Fight setup and the play loop copied in the binding

`py/src/lib.rs:2149`, `state.rs:912` and `lib.rs:2006`. Setup is built
three times (`Combat::new`, `versus`, `run`), and keyed specs miss
`character` and `max_hp`. Seven constructors are stacked, each adding
one argument. The thread-pool play loop is copied twice, and forced
openings exist only in the binding (dd5a9436, d7209377). Clean model: a
`GameSpec::new(...) -> Result` that binds once and a `start(&mut Rng)`
used by `runner::play`, with `Forced` as an agent adapter. Cost S-M. It
mostly pays off when the next fight option arrives.

### 25. One `condition_param`, and row writers with hand-computed offsets

`py/src/features.rs:1193`. Five row writers are copied by hand. One
`condition_param` column holds five meanings, so the loader refuses a
hook with two numbered conditions (`registry.rs:1755`): a net-layout
limit has become a content rule. No Act 1 content hits it. Clean model:
one `RowWriter` and a value column per numeric condition. Cost S
(bit-identical refactor), or M with the column split.

### 26. Gauntlet rest-site upgrade shim

`scripts/gauntlet.py:602` (68dbf088). An official card counts as
upgradable only if `X+` is in `sts.deck_card_names()`, "as before
upgrades as data". In the game any upgradable card can be upgraded at a
rest site. Today only check9 and proving decks are affected, but a
Silent gauntlet would get no upgrades. Fix (S): `sts.upgrade_name(c) is
not None`, with a run setting if old files must replay the old rule.

### 27. render.rs writes the pending-event text twice

`py/src/render.rs:126`. `render` and `board` each format pending events.
f2f4213c, 0a0c6414 and bc628442 each had to edit both. `board`'s
"upgraded" is read from the card name. S, under an hour.

### 28. CardDrawn fires with a fake Dazed, for Status cards only

`state.rs:1175` and `registry.rs:2122` (a843c019). `unfired_draws`
counts Status draws only, and the hook fires with a hard-coded Dazed.
The loader refuses any other card condition loudly, so nothing goes wrong
silently. This waits on curses for Fire Breathing's "or Curse" half, and
for Act 2-3 "when drawn" statuses. S-M, best done with sparse piles
(the real card) or with #29's queue.

### 29. No action queue: hooks can't pause, and each deferred mechanic got a side counter

- **What.** Only a card in play, a potion in use, or Gambling Chip's
  relic pick can pause for a pick or a chance event. Hooks refuse pausing
  effects through an allow-list (`registry.rs:2172`), and a second relic
  pick is silently skipped. The monster turn is one synchronous loop
  outside the stage machine (`state.rs:2101`). Each ordering a spec
  needed became a field on `CombatState`, with its own drain point,
  codec section and Debug branch: `deferred_block` (Curl Up, 40b4f73b),
  `card_hp_losses` (Rupture, 7061603d), `unfired_exhausts` and
  `owed_draw` (5488c736), `unfired_draws` (a843c019), and `top_queue`
  (f2f4213c), all at `state.rs:684-722`. The effect-stepping loop exists
  in three stage arms plus `run_relic_hooks` (`state.rs:1588`, 1673,
  1747, 2337), and the hook interpreter in five copies (2280). One pending
  chance slot, which only `run()` checks, has already needed a patch for
  Gremlin Horn (`request_draw` merges draws, 00b20ea9).
- **Blocks.** Content listed as blocked by this:
  - Dead Branch, Mummified Hand, Warped Tongs and Toolbox
    (`docs/research/act1-relics-potions.md:268, 242, 354, 319`).
  - Magnetism and Mayhem (`discovery.md:221`).
  - Juggernaut, together with #13.

  Generated packs reach series-review B1 (lost or overwritten draws,
  turn-end draws landing in the next hand). d5dcc55d documents a
  monster-turn draw-timing gap with Runic Cube. The Thorns
  intent-overwrite note (docs/decisions.md:1910) says only proving content
  can cause it, but it is stale: pack Bronze Scales and Liquid Bronze now
  bring Thorns into real Act 1 fights. Each new deferred mechanic costs
  another field, codec tag, reset and drain.
- **Clean model.** A small bounded, canonical queue in the state:
  `Block`, `FireHooks{trigger, count}`, `Draw{n}`, `PlayQueued`,
  `Resolve{source, effects, cursor}` and `ChanceEvent`. Mechanics push to
  the back (`addToBot`) or the front (`addToTop`), and `run()` pops one at
  a time, pausing at a chance event or a pick. The monster turn becomes a
  stage stepped by `run()`. One cursor with a per-source policy (scale,
  raw or modified block, whether pile placement follows) replaces the
  copied loops. The six fields become one codec section.
- **Cost.** L, a multi-spec change: the codec, golden trajectories,
  turn-start pins and the solver all see it. Official play should stay
  the same, and golden can check that. It is best done with #36 (a real
  codec version) and after sparse piles.

### 30. The outcome score is defined in about eight places

`solve.rs:310`, `lib.rs:1141`, `heuristic.rs` and stsnet. "2 - HP lost
/ 100" is hand-copied in `score`, the bound and the heuristic. Search
scores through `ScoreRule` plus the end-HP price, while the exact solver
is hard-wired to `CombatState::score`. Nets trained with `hp_weight`
predict on another scale than search's finished-combat score, a known,
unmeasured confound. 6115ceff and 1d9c3cca each edited several copies by
hand. Clean model: one `OutcomeRule` in the engine with
`terminal(state)` and `leaf(state, value)`, exported to Python for
labels. The solver carries its objective. Cost M.

### 31. Relic properties in side tables; eight helper powers came back

`relics.rs:61` and `state.rs:939` (a3c238d1, 807602bc, bc628442).
Relics are interned names with a separate process-global `OnceLock`
table per property (hooks, potion potency, potion slots). A second spec
for one name panics in the constructor. Relics can't hold statics or
replacements, so eight helper pack powers (TheBoot, Torii, TungstenRod,
...) carry them. That undoes relic-entity's own aim of not sharing the
power cap and not showing the net a relic as a power. The helper powers
were an owner decision (fight-vocabulary.md:170). Clean model: one
interned `RelicDef`, and the static and replacement passes treat relics
as owners. Cost M. It also relieves #11.

### 32. Every effect is listed in about eight hand-kept matches

`upgrade.rs:224` and `registry.rs`: parse, write, number,
`number_fields`, `element_names`, the run-outside check, and more.
upgrade.rs alone was touched by six effect-adding commits in three days.
`features.rs:284`'s TRIGGERS and `condition_names()` are hand lists
beside the engine enums, and a missing entry falls silently into
`trigger_unknown`. Clean model: one declarative table per effect, built
with a `macro_rules!` macro, that generates all of those. Cost M. The
round-trip tests check it is exact.

### 33. One-card mechanics as `CardDef` side fields and state counters

`cards.rs:216`: `cost_less_per_hp_loss`, `turn_end`, `exhausted`, the
closed `Tag` enum (363eff5f, 5488c736, 9dd603f8). No Ironclad card is
kept out, but the next character multiplies the pattern:
second-character-census.md plans another per-copy `discarded` list and
a discards-this-turn counter. Clean model: cost as an `Amount` over
counted quantities, and card-owned reactions as rows keyed by trigger.
Cost M.

### 34. Character is a closed enum

`character.rs:77`. A third or generated character needs edits in several
arms. Ring of the Snake is code (and its draw is copied in features). The
Silent's default deck keeps a historical deviation. This is already
backlog 41. Cost M.

### 35. `MAX_MONSTERS` slots are reserved up front and never freed

`state.rs:22` (b4f9b968). All of Act 1 fits. But split children reserve
slots up front and dead monsters never free theirs, so a Spawn atom
(Reptomancer, Gremlin Leader, Bronze Automaton, Collector) can't be
written. Clean model: dead or escaped slots are reused, so the cap means
"alive at once". Cost M.

### 36. The codec stays append-only at version 1

`codec.rs:177` (2ec1ab49, 06fc5c01, 3b203f7f). Every change becomes an
extra tag, flag bit or optional section, with canonical checks per field.
Nothing is kept out today, but sparse piles and #12 both need a real
format change. Clean model: a frozen `decode_v1` plus v2, or a one-time
migration of datasets and the DB. Cost M, best done in the same change
as sparse piles.

### 37. Legacy columns stay in the full layout for old nets

`features.rs:453` (343186a5, 2ec1ab49). Clash's `only_attacks_in_hand`
and five pre-expression ScaledDamage scalars are always written, and a
Rust list and a Python list of them are kept in step by hand
(finetune.py). Clean model: a derived-column table that is computed only
when a layout names the column. Cost M.

### 38. The explorer re-implements content, RNG and run order

`scripts/explore.py:1811`, 2825 and 2419. It re-parses raw content JSON
and has broken three times on format changes (ce984fe7, 7d7d48a9,
958b7d1e). It re-implements xoshiro256** and splitmix64, the agent-seed
salt and the play loop. The gauntlet run order is coded in five places.
These are viewer-only, and most fail loudly. Clean model: an `sts`
export of resolved content and a recording option on `play_on`. Cost M.

### 39. Debug text as a compatibility surface

`state.rs:752` and `powers.rs:207`. Hand-written Debug impls for
`CombatState`, `Powers`, `Amount` and `Pile` imitate old layouts,
because `turn_start_pins` and golden hash or print Debug text.
`win_heal` is already missing from it. Clean model: pins hash codec
bytes or a purpose-built named dump, and Debug goes back to derived.
Cost S-M, with one re-record.

### 40. Content-file version 1 readers woven into the parsers

`registry.rs:1770` and 2274 (0abcd447, 343186a5, c8fcf0a2). Clean
model: `migrate(json, version)` before parsing, so the parser knows only
the current format. S, best done alongside a pack regeneration, since it
changes pack hashes.

### 41. gen_content's hand pair lists have drifted

`scripts/gen_content.py:72` (a4ed5384). The "seen" official (trigger,
effect) pairs are a hand list, and since the post-draw trigger split
(0abcd447, 957153a4) the unseen-mechanic split is slightly mislabelled.
Fix (S): `sts.official_hook_pairs()` and a test.

### 42. Seven stacked constructors

Merged into #24.

### 43. Two tiers of content: official enums plus Gen slots

`powers.rs:82`, `registry.rs:33`, `registry.rs:2055` and 2602, and
`monsters.rs:18`.
- `Power::ALL`, `CardKind::ALL`, `MonsterKind` and `Encounter` are Rust
  enums order-locked to the content files.
- Pack powers have no identity of their own: they get 24 per-fight slots
  (`Gen0..Gen23`), already raised once from 8 (656d8e9c, 17ed7f2d).
- A pack power is referenced through a `GEN[0]` placeholder plus a side
  vector of names.

So a new game power becomes a pack power, because adding it to the enum
moves codec masks, golden and a net column (docs/decisions.md:9446).
Pack powers can't be named by TargetHas, Applying or ApplyOf. Each
content source added another `bind_*` path, and deck-order slot
assignment drove the slot-set growth that broke learn 0746 (e353b47a).
Clean model: one power table with process-stable u16 ids, official
first, so official codec masks stay the same. Official content becomes
the first pack loaded. Cost L. This is the power-side twin of sparse
piles, and the two should share a key scheme.

### 44. Records replay from seed and actions, so rule fixes get declined

`monsters.rs:126`. Datasets, bench and puzzle files and golden games
store the setup plus actions, and replay through the live engine. So
every rule must "make today's random calls in today's order" (1cc15915,
docs/extending.md:219). Known deviations stay for this reason
(LoseStrength, e4e2d84c). Monster patterns can't read phases, so those
monsters become code (#16). `Encounter::ALL` stays frozen (#7). Each fix
is put off to one later re-baseline that hasn't happened. Clean model:
records carry the rules version they were made under, plus their chance
outcomes or a re-label step. A rules fix bumps the version (#20) instead
of being declined. Cost L.

### 45. The Rust forward pass duplicates stsnet

`py/src/net.rs:218`. This is a deliberate port for speed, kept in step by
`test_rust_net`. The constraint (no torch in Rust) still holds, so it is
not a patch. A small hardening, S: Rust refuses state-dict keys it
doesn't know, and `ALIVE` comes from one place.

### 46. Unchecked `as` casts in the pack parser

See #10.

## Consequences of the card ids (for the sparse-piles spec)

Readers met these while auditing. Each is downstream of count-per-id
piles or byte card ids, so the spec can check it reaches all of them:

- **The variant table fails silently.** `VARIANT_DEFS` is process-global,
  capped at 4096 and keyed by a def address (`registry.rs:117`, 157). When
  it is full, or an upgrade fails to apply, `variant_index` returns
  `None`, and the callers treat that as "nothing happens": Rampage
  doesn't grow (`state.rs:2583`) and Armaments doesn't upgrade
  (`state.rs:2622`). The same holds when the 4 per-fight variants are
  used up. Whatever replaces it should fail loudly. If sparse piles is
  far off, making these two `None`s errors is an hour's work now.
- **AddCard can only name an official card** (`registry.rs:1996`,
  1710). Pack cards, monsters, relics and potions can't create pack
  cards (no custom statuses or curses), and docs/decisions.md:11658 notes
  a test case that can't exist for this reason. Effects should name
  cards by the same content key piles use.
- **FreeMarks** (`state.rs:435`, 3b203f7f) keeps cost-0-this-turn as a
  list beside the hand. It becomes a pile-entry parameter.
- **CardDrawn's fake Dazed** (#28) can fire with the real card.
- **Card sets** hold official ids only and pair upgrades by appending
  `+` (`card_sets.rs:46`). They become pools resolved by name.
- **The encoder re-encodes pack cards** for every pile entry of every
  state (`features.rs:1853`, 7689d550), which costs unmeasured speed. A
  cache keyed by the card's content key fixes it.
- **The solver's guard on u8 counts** (`solve.rs:265`, `PILE_COPIES` 60).
- **The codec** writes piles as (byte, count) pairs, and variants in
  trailer section 2. With #12 and #36, this is the moment to version the
  format.
- **The ids-mode vocabularies** (`known_cards`, `selfplay.KNOWN_CARDS`,
  `card_index: [usize; NUM_CARDS]`) are keyed by card id.

## Refuted

The checkers dropped these as trivial, deliberate, or not a patch:

- A hook's second condition as a side field (deliberate, loud at load).
- Pack parsing through thread-locals (hygiene only).
- `POTION_CAP` with a silent min (game content can't exceed 3 + 2).
- Afterstate option grouping written three times (identity lives in one
  place).
- cf.rs as a closed probe still compiled (a parked probe with a reopen
  condition).
- Power names as Debug text (they equal the content ids).
- Ids mode's `relic_unknown` (a documented baseline limit).
- The value net defined twice (a deliberate port, see #45).

## Caveats

- Nothing was run. The crash path in #12 and the Thorns reach in #29 are
  read from the code, not reproduced.
- "Blocks" scores lean on docs and kb facts. Where a fact was stale, the
  checkers said so (decisions.md:1989 on the known top, decisions.md:1910
  on Thorns), and each mismatch is pointed out in its entry.
- Costs are guesses at the scale of this project's specs (S = one
  session, M = a few steps, L = several specs).
