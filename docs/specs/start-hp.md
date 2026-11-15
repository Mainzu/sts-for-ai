# Start-HP column: let the net see HP already lost

Status: closed (2026-11-01, read: decisions "Start-HP column passes but the bonus stays"; start_hp encoder option stays, off in the product).

## Why (goal 2, and how we'll know)

The champion loses 8.2 HP per fight at run-like HP, the heuristic 5.6, at
the same win rate; 70% of the gap is hallways, where the net takes more
damage per turn (tempo probe, results doc "Run-HP at two turns,
HP-weighted champion, and where the HP goes"). A run is decided by HP
carried between fights, so this gap matters more for goal 2 than any
tight-fight win rate.

Why it happens: the label scores a win 2 - w x (start HP - end HP) / 100,
but the encoder has no start-HP column, and training fights start at a
random 10-100% of max HP (`selfplay.VARIED`). Seeing only current HP, the
net can't tell HP lost from HP it never had: in a safe state, higher
current HP mostly means "started higher", so the regression gives HP
almost no price. Measured (`scripts/analysis/hp_price_probe.py`, run-HP
fights, the net's value with only current HP lowered): in hallways the
champion's value falls ~0.0013 per HP, against its labels' ~0.02 (w 2).
Search then trades HP for damage at a fifteenth of the HP's real price.

The first plan, an `unblocked_incoming` column, can't help one-turn
search: its leaves are states after End turn, where the monsters have
already hit and the HP column shows the loss. What the net can't do is
price that loss.

How we'll know: run-HP (`ladder.py runhp`) of nets with the column
against the same recipe without it, paired by fight; the probe shows
whether the HP price moved toward the label's.

## Outcome and non-goals

Outcome: an encoder option `start_hp` adding one player column, the
combat's start HP; off by default, every existing batch, pin and net
unchanged; a config key to train with it; four test arms.

Non-goals: changing labels, the score, search, the heuristic, or the
start-HP draw of training games; making it the default (that waits for the
arms); a product champion with it (a burst of the champion with a widened
input is the follow-up if the arms pass).

## Behaviour

- `Encoder::with_start_hp(on)`; when on, the player path ends with
  `start_hp` (after the rate block when rates are on). Value: the state's
  `start_hp` as f32.
- `sts.Features(..., start_hp=False)`, getter `start_hp`; `NetEvaluator`
  config key `start_hp`; both turn it on when the layout's player columns
  name `start_hp` (a net trained with it).
- Feature mode suffix `+start` after `+lookahead` and `+rates`
  (`selfplay.START`, `split_mode` returns four fields); `learn.feature_mode`
  adds it for config key `"start_hp": true`; net meta `start_hp: true`;
  `stsnet.features_for` / `rust_evaluator` pass it.
- Datasets don't depend on it (games and labels unchanged); feature
  caches are keyed by the mode, so a new layout tag.

## Fits with

- Every existing net and batch: off by default; pinned by
  `test_start_hp.py::test_off_unchanged` (full-layout names and the pinned
  batches) and the existing `test_rates.py`, `test_contract.py`.
- Contract nets' layouts: a net with `start_hp` in its columns loads with
  the option on (`test_roundtrip`, torch and Rust bit-identical).
- `split_mode` callers (`learn.fit`, `selfplay.features`, `finetune.py` if
  it splits): all updated to four fields; `test_rates.py`'s split_mode
  test updated to the new tuple.

## When in doubt

Prefer copying the `rates` option's plumbing over a new mechanism.

## Scope

May change: `py/src/features.rs`, `py/src/lib.rs` (option plumbing only),
`scripts/selfplay.py`, `scripts/learn.py`, `scripts/stsnet.py`, any
`split_mode` caller, new `scripts/tests/test_start_hp.py`, the split_mode
lines of `test_rates.py`, new `configs/lean-start*.json`, README, this
spec, results doc, decisions. Off limits: engine rules (`engine/src`),
the codec, labels, search, existing configs and nets.

## Decisions taken

- A flag, not a new full-layout column: every saved net lists its
  columns, but a net whose layout differs from the full one takes the
  gather pass (~2x encoder time), so a full-layout column would slow the
  champion and every old net.
- Raw `start_hp`, not `hp_lost_so_far`: the net's first layer is linear,
  so start - current is one weight pair, and the raw value stays true
  if the label's reference point changes later.

## Verification

`scripts/tests/test_start_hp.py`:
1. `test_off_unchanged`: `Features(mode)` names and pinned batches as today.
2. `test_names_and_value`: on, player names = off + [`start_hp`]; a combat
   built at hp 50 reads 50, and still 50 after it takes damage (current hp
   lower).
3. `test_with_rates`: both on, `start_hp` last, rate columns unchanged.
4. `test_roundtrip`: tiny net with `start_hp` saves the column; reloads
   with the option on from columns alone; torch and Rust scores equal.
5. `test_config_key`: `feature_mode` and `split_mode` for the four
   suffix combinations; the lean-start configs equal their twins plus the key.

End to end: learn smoke (200 games, rounds 0-1, `start_hp` on) saves the
column; the probe on the arms' r2 nets.

## The experiment

- Arms (2 seeds each, own round 0 on the shared round-0 games, as
  lean-hpw2 did): `lean-start-hpw2-s1/s101` = `lean-hpw2-s*` + `start_hp`;
  `lean-start-s1/s101` = `lean-thr-s*` + `start_hp` (w 1: is the HP weight
  still needed once HP is priced?).
- Controls: `lean-hpw2-s*` r2 and `lean-thr-s*` r2, whose run-HP reads
  exist (same fights, block 6000 on).
- Read: `ladder.py runhp <r2 model.pt> --pairs 2000` per arm net; saved HP
  = control's HP lost - arm's, per fight, mean over fights, then seeds;
  hallways separately; deaths; tight2 held-out from round.json; the probe
  per net.
- Rule (pre-registered): an arm **passes** when it saves >= 1.0 HP per
  fight on the mean of 2 seeds, each seed > 0, deaths at most 20 more per
  2000 than its control, tight2 held-out lead no more than 0.02 below its
  control's. Pass: burst the champion with the column (widened input) and
  run the promotion tests (ladder + run-HP). Both arms < 0.5 HP: the
  column isn't the lever; record that the net's flat HP price is not what
  costs HP. Between: one more seed of the better arm.
- Noise: run-HP se ~0.35 HP per run, seed sd ~0.5 HP: 2 seeds detect ~1.5
  HP at the usual power; 1.0 is a third of the 2.6 gap. The probe effect
  (price x15 too low) suggests a large effect if the mechanism holds.

## Don't guard

`start_hp` above max HP (can't happen in our setups); generated content
(the column is content-free).

## Build steps

1. Rust option (features.rs, lib.rs), Python plumbing, tests 1-5; rebuild
   `sts`; fast suites pass.
2. Configs, learn smoke.
3. **Long run:** 4 learn jobs (~40-60 min each), then 4 run-HP reads and
   probes. Read per the rule.
