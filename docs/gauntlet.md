# The Act 1 gauntlet

The gauntlet is the project's own Act 1 test: a seeded chain of 11 fights
with HP carried from fight to fight, where one loss ends the run. Every
player plays the same chains, so two players can be compared chain by
chain. The headline numbers in the README and the showcase come from it.

## Act-1 gauntlet

Goal 2's headline number (`docs/specs/gauntlet.md`): seeded chains of 11
fights (3 easy hallways, 2 hard, an elite, 2 hard, an elite, 1 hard, a boss)
with one tight2 deck per sequence and HP carried over from 80: the engine
adds Burning Blood's 6 on a win, a rest before the boss heals 24, a loss
ends the sequence. Sequence i alternates train / held-out decks, and every
agent plays the same sequences, so two result files pair by sequence. `play`
writes `results/gauntlet/<tag>.json` (a rerun adds only missing sequences);
`read` prints each agent's clear rate, the paired difference, HP at the
boss and deaths by floor and encounter, by half too:

```
.venv/Scripts/python scripts/gauntlet.py play runs/<net>/model.pt@hpb0.01 --sequences 200 --threads 6 [--two-turn]
.venv/Scripts/python scripts/gauntlet.py read results/gauntlet/<a>.json results/gauntlet/<b>.json
```

A net player spec takes search-time settings after `.pt`, each at most
once: `@hpb<c>` (HP bonus), `@hpe<c>` (end-HP bonus, also on finished
combats; c prices one HP at 80 max HP and the same share of the HP bar at
any other, `c x 80 / max HP` per HP; not with `@hpb`; decisions "End-HP
bonus built and read", "End-HP bonus scales with max HP"), `@esp<k>`
(enemy-Strength price, `docs/specs/enemy-strength-price.md`), `@shl<k>`
(enemy Strength priced by the hits it will still land,
`docs/specs/strength-hits-price.md`), `@sc<c>` (a
survive net's c), `@tb1` (exact value ties go to the sooner win, then lower
enemy HP; values unchanged, `docs/specs/finish-faster-tiebreak.md`),
`@sn1` (card damage and block encoded as the game shows them: + Strength x
hits, x0.75 under Weak; + Dexterity, x0.75 under Frail) and `@xh1` (the
exhaust pile's counts encoded as 0; both `docs/specs/shown-card-numbers.md`),
e.g. `model.pt@hpb0.01@esp0.04`.

Leaf settings: `@dl<k>` scores end-of-turn leaves after k sampled draws;
`@tsl1` after the player's turn-start hooks that need no chance; `@lcb1`
with the player's block at 0; `@pl<k>` applies once-a-turn Strength and
Dexterity hooks k more times there, player and monsters
(`docs/specs/projected-leaf.md`); `@pd1` (only with `@pl<k>`) also
monsters' once-a-turn Weak, Frail and Vulnerable on the player
(`docs/specs/recurring-debuff-leaf.md`). Read `@sn1`/`@xh1` against a
plain control with `--vary price`.

`--two-turn --one-turn-floors 3` plays floors 1-3 one turn deep;
`--two-turn --line-seed` gives every two-turn search of a combat turn the
same sample seed, so later decisions follow the first tree's line (the
committed-line player: level or better than plain two-turn, +0.60 HP,
+0.024 clears on cells 0-249; decisions "Line seed passes";
`scripts/analysis/line_probe.py` records how a turn's two-turn cost splits
by decision index: ~60% sits in the first tree,
`results/depth/line-probe.json`); `--line-seed --step-line` plays each
uncut tree's principal line (`sts.search(...)["line"]`: the best child at
every decision up to End turn or the first chance node) instead of
searching every decision: the same decisions exactly (20 of 20 probe
fights, 526 of 526 decisions) at 0.70 of the search cost (decisions
"Line-step probe"; `line_probe.py --compare` measures agreement and the
cost ratio against the stage-1 player, `results/depth/line-step-compare.json`).
A control played without a flag needs `--vary line_seed` / `--vary
step_line` under `--against`. Card
rewards (decisions "Card rewards are a goal-2 lever"): `--rewards random|sim` offers 3
cards (seeded, from the half's pool, no upgrades) after each won fight
before the boss; `random` takes one at random, `sim` takes the option (or
skip) that scores best over 8 one-turn fights against the next floor's
pool, with common seeds. `--start starter` starts from the starter deck
instead of the cell's deck. The defaults (`skip`, `cell`) give today's
files; rows record `offer` and `took` when rewards are on. `--sim-boss`
(decisions "Sim-boss passes: new headline setting") adds 8 fights against the boss pool at the
post-rest HP to each option's sim score. `--chooser <player>`
(decisions "Crossed chooser arms read: the chooser is the larger
one-turn lever") scores the sim chooser's option fights
with another player (e.g. the heuristic) while `<player>` fights the
floors; the file records `chooser`. `--rewards vrun --fit <gauntlet
file> [--fit-first 250 --fit-n 250]` (decisions "Run-value chooser: fails,
use (b) closes for card picks")
scores each option by the run value instead of `1 + 0.01 x end HP`: the
next-floor sims' end HP priced as P(reach the boss at that HP, from the
fit file's sequences) x P(win the sequence's own boss | HP, deck) (the
boss's causal curve from `scripts/run_value_unit.py`'s `BOSS_CURVE`,
shifted to the deck's level from 8 fights against that boss); rows record
`took_sim`, the old score's pick on the same fights
(`run_value_unit.py pickrate <file>`). `--remove strike|sim`
(`docs/specs/card-removal.md`) removes one card after the first elite's
reward (a shop proxy): `strike` the first Strike, `sim` the option (or
keep) that scores best the same way; the floor-6 row records `removed`.
`--elites skip|hp [--elite-hp 40]` (decisions "Elite-skip read") fights a
hard hallway instead of an elite, always or when the HP entering the
floor is under `--elite-hp`; elite-floor rows record `path`. With no
relics an elite has no payoff here, so `skip` is the ceiling of a path
choice on this gauntlet, not a product rule.

Early stop (`docs/specs/gauntlet-early-stop.md`): `play` runs in blocks of
`--block` sequences (default 50) and rewrites the file after each.
`--against results/gauntlet/<control>.json` runs the gauntlet protocol
(decisions "Gauntlet protocol") after each block on the sequences both
files hold, and stops on pass, fail or fail-guard; the file's `protocol`
key holds the verdict and n. Report a promotion's effect at fixed n (the
confirmation book, sequences 500-999), not at the stopping point. A
control must cover the candidate's sequences, or the verdict stays open.
`--against` refuses a control played with other settings (depth,
`--one-turn-floors`, the price after the player's `@`, `--start`,
`--rewards`, `--sim-boss`, the chooser, rest, removal or elite options),
naming each difference, unless the read declares the ones it tests with
`--vary <field>` (repeatable; e.g. `--vary remove` for a removal read
against the plain headline file); the file's `protocol` key records them.

Pack cards in the offers (`docs/specs/gauntlet-pack-offers.md`): `--pack
<file>` loads a content pack (in the two-turn workers too) and adds its
base cards, as `gen:<id>`, to both halves' reward pools; offers stay
uniform. Its `hallway` encounters join the hard floors
(docs/research/act1-inventory.md "Block G2"): one named like an official
hard encounter replaces it, the others are added, all equally likely, on a
second stream so every other floor matches the pack-less sequences. A pack
without hallway encounters needs `--rewards` other than `skip`. It is recorded as
`"pack": "<file>@<content hash>"`, and a read against a pack-less control
declares `--vary pack`; `--match` refuses a file of another pack setting.

Deck-matched reads (`docs/specs/deck-matched-reads.md`): `--match <file>`
replays that file's recorded card picks (extra elite picks too), rest
choice and removal wherever it has one, so a fighter read `--against` the
same file varies only the fighter; where the file has no record (its
sequence died earlier) the run's own chooser decides. The file must share
the choice settings (rewards, chooser, rest, removal, elite options,
start); fighter settings may differ. Matched floors are marked
`"matched": true`; `match` is recorded in settings but never compared by
`--against`. A matched read can't see a chooser change.

Which read answers which question: the sim chooser picks cards by
playing fights with the fighting player, so nearly any change to the
player also changes its picks. A whole-player question (is this net, or
this setting, better?) plays each arm with its own picks, unmatched. A
fighting-only question (does it fight better on the same decks?) is a
matched read on the control's picks: the cheapest read (no chooser
fights, 2.4-4.2x lower variance one turn deep), leaning slightly toward
the control, whose decks were picked for its own play. Each arm on both
sets of picks (crossed arms, `--match` plus `--chooser`) only when a
decision needs fighting and picking split apart.

Boss replays (decisions "Boss replays: the boss curve is causal; the run
value is per boss"): `scripts/analysis/boss_replay.py
play --file <headline file>` rebuilds every boss-reaching sequence's boss
fight (its deck at the boss, boss and seed) and plays it one turn deep at
entry HP 30, 40, ..., 80 on common seeds (`--seeds 4`), so only HP varies;
`read` prints the causal P(win | HP) per boss beside the observational
curve, the per-deck step and the confound (results/boss_replay/).
`--hp arrival --seeds 8` instead replays each boss at the sequence's own
arrival HP (`docs/specs/boss-replay-score.md`), recording win and end HP
per seed; `pair <a> <b>` (two such files) prints the paired sd of clears
and end HP beside that of the mean replay score (0 for a sequence that
died before the boss).

Other `gauntlet.py play` options: `--pack-picks originals` (with --pack
and offers: pack cards are offered, the chooser takes only original cards
or skips; recorded as pack_picks); `--rewards value [--value-hands K]`
(picks by the net's static values of fight-start states, no trial fights;
train-card sequences only, decision/value-chooser-use); `--elite-offers N
--mid-rest K` (the mini-run); `--elites skip|hp --elite-hp H`; `--rest sim
--rest-fights F --rest-margin M`.
