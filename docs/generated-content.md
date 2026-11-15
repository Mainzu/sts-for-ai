# Generated content

The project can make up new powers, cards and monsters from the same
building blocks as the real ones, and save them as a content pack. Packs
also carry real content, such as the real Act 1 cards. Generated packs
test whether the AI plays well on content it has never seen.

## Generated content

```bash
.venv/Scripts/python scripts/gen_content.py --seed 1 --powers 200 --out data/content/gen-s1.json
```

Writes a content pack (`docs/specs/registry-lite.md`) of generated powers,
each with one power card (`gen:<card id>` in a deck; load the pack with
`sts.load_content`). A power is 1-2 hooks of existing triggers, conditions
and effects plus one of four lifetimes (permanent, this turn, used up,
wearing down); its card costs 1-3 and grants 1-3 stacks. Each power is
`train` or `test` by its (trigger, effect kind) pairs: official training
pairs are train, about a quarter of the rest are test (turn start ->
+Strength, Demon Form's pairing, always is), and a test power shares no
pair with any train power. Budget: the heuristic's value from playing the
card, per energy, lies in the official power cards' range (0.092 Demon
Form to 0.253 Combust); powers the heuristic can't price (about 3 in 4)
get cost 1-2 and are marked unpriced. Same seed, same bytes. Tests:
`scripts/tests/test_gen_content.py` (~10 s).

A pack can hold more than the generator writes (`docs/decisions.md`
"Content packs carry every atom"): any card type (`Attack`, `Skill`,
`Power`, `Status`) with every flag (`exhaust`, `ethereal`, `retain`,
`x_cost`, `innate`, `unplayable`), a play condition (`playable_if`,
Clash's `{"HandAll": "Attack"}`; a version-1 file says
`only_attacks_in_hand`), `tags`, conditional `rows` and `turn_end` effects, and powers with `hooks`,
`statics` and `replacements`, using every effect, trigger and condition the
engine has. `sts_engine::registry::card_json` / `power_json` write any
official card or power as a pack entry; `engine/tests/packs.rs` loads every
one back unchanged.

A pack can also hold `monsters` (`docs/decisions.md` "Runtime registry
stage 3 spec"): HP
range, moves (any effect that runs outside a card, plus `Split` and
`Escape`), pattern rows that pick moves by index, start block, official
start powers and a split into official or earlier-loaded monsters.
`sts.Combat.versus(deck, ["gen:<id>", "Jaw Worm"], seed)` fights them; a
state holding one has no codec bytes. `registry::monster_json` writes an
official monster as a pack entry; the 13 without code-only behaviour (all
but the lice, Lagavulin, Hexaghost and The Guardian) load back unchanged
and play the same games (`engine/tests/monster_packs.rs`).

Official content is data too (`docs/specs/official-content-files.md`):
`content/cards.json` (64 card kinds in `CardId` order, one entry each with
its upgrade as data, or an `X` / `X+` pair for an upgrade that changes how
the card works; 128 card ids), `content/powers.json`
(30 powers in `Power::ALL` order) and `content/monsters.json` (kinds 1-18)
are in the pack format, compiled into the engine and parsed by the pack
parser on first use; there are no Rust tables behind them. Adding or
changing official content is a file edit, then `cargo run -p sts-engine
--example export_content` to rewrite the files in canonical form (a test
fails on a non-canonical file). Card names carry their level: `Bash` and
`Bash+` are a card's two ids, `gen:Searing Blow+3` a level-3 copy
(`docs/specs/card-upgrades.md`; `sts.upgrade_name`, `sts.base_name`).
Official-only fields: a card's `class`;
a monster's `code` (`louse`, `lagavulin`, `hexaghost`, `guardian`), which
attaches its code-driven behaviour; packs using them are refused (and the
retired pool flags `held_out` and `proving`, which the official loader
ignores in an older file). The files count as rules: editing them changes
the solved DB's fingerprint.

Card sets (the lists we choose for training and testing; a *pool* is a
list the game itself draws from, `docs/extending.md` "Pool or set") are
named in `configs/card-sets.json`
(`docs/specs/card-sets.md`), not card fields: each set is a list of base
card names (a name brings its `+` card), used in card order. `ironclad`
is `deck_cards()` / `sts.deck_card_names()`, `silent` is
`class_cards(Silent)` / `sts.class_card_names("silent")`, `check9` is
`held_out_cards()` / `sts.held_out_card_names()`, and `proving` holds the
rules-engine proving cards; `sts.card_set(name)` and
`sts.card_set_names()` read any set. Editing a set changes training
sets only: it is not in the solved DB's fingerprint or the golden games.

Training with it (`learn.py` config keys): `content`, a pack's path or
`{"seed": S, "powers": N}` (generated at run start), and `content_share`,
the share of training decks (varied setups, rounds 0 and later) that get 1-2
of the pack's *train* power cards (`content_split: "test"` gives them the
test cards instead: the oracle arm); validation decks stay official. Without
them (or at share 0) datasets are unchanged byte for byte. A content
dataset's config and manifest carry the pack's `content_hash`, each round's
run folder holds the pack (`content.json`) and its round.json the hash, and
replaying the dataset refuses (`registry.ContentError`) until that pack is
loaded (`selfplay.load_content`). States with generated cards have no codec
bytes, so they take no exact labels, and the solve step refuses such a
config unless `solve_games` and `solve_games0` are 0 (the lean recipe's).
Tests: `scripts/tests/test_content_selfplay.py` (~20 s).

Mutated monsters, stage A (spec folded into the results doc "Mutated monsters,
stage A" sections and decisions of that name):
`scripts/analysis/mutate_monsters.py play --starts 200 --seeds 8 --players
heuristic,one[,two] --out results/mutate/<name>.json` replays the gauntlet's
elite and boss fights from their first decision with the enemies mutated by
a patch of the start state (HP x0.8 / x1.25, Strength, Metallicize, Ritual,
SharpHide; the owner's boon + bane pairs; one stack), common seeds per
start, played by the heuristic, the product net one turn deep and (a
subset) two turns deep; `read` gives per modifier the difficulty change,
the one-turn net's drop beyond it (novelty cost) and whether depth repairs
it. `--mods a,b` plays a subset of the modifiers (new files, or more
modifiers into an existing one).
