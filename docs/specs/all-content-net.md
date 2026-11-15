# All-content net (lane all-content-net, step 1 and 2)

Status: closed (2026-11-08, built; lane closed at its CPU cap, seeds 1 and 101 read: decisions "Lane all-content-net closed (2026-11-08)").

**Outcome:** `learn.py` can train the data40k recipe with the Guardian and
Hexaghost in its boss group and the held-out cards in its decks, and seed 1
of it is queued with its boss replay beside its seed twin's.

**Goal and how we'll know (goal 2).** 127 of the product's 193 deaths over
1,000 headline sequences fall at the Guardian and Hexaghost, two bosses no
net trained on from scratch; the product's decks also hold the held-out
cards the training pool lacks. The owner's training rule gives CPU to new
content. If training on them from scratch lifts boss wins one turn deep by
0.03 or more against the data40k seed twin (boss replay, 474 headline boss
fights, se about 0.004-0.010), the lane goes on to seeds 2-3 and the
one-turn headline; under 0.03 at both bosses on seed 1 it fails (charter).

Non-goals: no change to the official groups or encounter lists in the
engine (lane act1-content's E1 owns encounters); no new features; no
goal-1 hold-out use of this net.

## Behaviour

- Config key `bosses: [<encounter names>]`: after `selfplay.make_specs`,
  the boss group's specs take their encounters from the list in turn;
  decks, seeds and HP stay. An unknown name raises. It enters the dataset
  config (`gen["bosses"]`), so no older dataset is reused for it. It
  applies to train and validation sets and to every round.
- Config key `deck_pool: "all"` (varied setups only): extra cards come from
  the whole Ironclad pool (`sts.deck_card_names()` plus
  `sts.held_out_card_names()`, checks 6 and 9 held-out cards included),
  uniform, count as `VARIED["extra_cards"]`. Enters the dataset config as
  `gen["deck_pool"] = "all"`; train and validation alike. With
  `train_pool` it raises (two pools).
- Without either key, every dataset config and spec is unchanged.
- `configs/allcontent40k-s1.json`: `data40k-s1.json` plus
  `bosses: ["slime_boss", "hexaghost", "the_guardian"]`, `deck_pool:
  "all"`, name `allcontent40k-s1`; today's inputs (mode `effects`, the
  current feature width: 56 effect columns and 20 triggers against the
  twin's 28 and 8).

**Fits with:** existing configs (dataset configs unchanged: the
`test_setups` tests pin them); `two_turn_games.specs_for` keeps its own
encounter swap; `registry.selfplay` already plays added encounters (boss
bursts did).

**When in doubt:** prefer the recipe as data40k ran it over tuning.

**Scope:** `scripts/learn.py` (dataset), `scripts/selfplay.py` (a deck
function and a boss swap), `scripts/tests/test_setups.py`, `configs/`, this
spec. Off limits: engine, `py/`, feature code.

## Decisions (on the owner's behalf)

- Validation follows the training distribution (both keys), so the
  epoch the trainer keeps is chosen on the content it is for; the
  alternative (validation on the old pool, as `train_pool` does) would pick
  epochs for content the net is not for.
- Uniform full pool rather than "at least 2 held-out" decks
  (`varied_held_out_deck`): the headline's decks are reward picks, not
  held-out-heavy.
- The twin is the existing `runs/2026-10-31-data40k-s1-r1-72d8ced` (the
  charter's); it differs in inputs as well as content, so a gain is "this
  recipe today against data40k", not content alone. A today's-inputs twin
  costs another 7 thread-hours and is the navigator's call after a go.

## Verification

- `test_bosses_swap_boss_group_encounters`: 3 per group, bosses list of 3:
  boss specs' encounters are the list in turn, other fields equal to the
  unswapped specs; hallway and elite unchanged; an unknown name raises.
- `test_full_pool_deck_draws_held_out_cards`: 300 decks: extra cards
  include a check-6 and a check-9 held-out card, 13-25 cards.
- `test_all_content_keys_enter_dataset_config`: with both keys, train and
  val configs carry them; without, the config equals today's.
- End to end: `learn.dataset` on a tiny all-content config plays boss
  games at all three bosses (registry games' encounters).

## Build steps

1. Code and tests above; `test_setups.py` passes. In-session.
2. Config; queue (long run, ~90-120 min at 6 threads) `learn.py --config
   configs/allcontent40k-s1.json`, then its boss replay and the twin's
   (5 min each, `--after`); record the learn job's peak memory.
