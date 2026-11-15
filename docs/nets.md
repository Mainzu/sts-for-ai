# Value nets and the generalisation tests

A value net is a small neural network that looks at a combat position and
estimates how well the fight will go. The search uses it to score the
positions it reaches, in place of the hand-written formula.

This page covers training a net, loading it for search, and its optional
inputs. It also covers three tests of whether a net generalises: to cards
it never saw in training (check 6), to the Silent after training on the
Ironclad (check 8), and to five cards held out of training, among them
Demon Form (check 9). The check numbers are the project's own names for
these tests.

## Value nets and the generalisation test (check 6)

```bash
.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/python scripts/tests/test_net.py
.venv/Scripts/python scripts/generalise.py
```

`generalise.py` plays self-play data into `data/`, trains both nets into
`models/value_effects.pt` and `models/value_ids.pt` (both cached; `--retrain`
ignores saved models), then prints the MSE and win-rate tables. Load a net
for search:

```python
import sys; sys.path.insert(0, "scripts")
import stsnet, sts
model, norm, meta = stsnet.load("models/value_effects.pt")
sts.search_action(c, stsnet.rust_evaluator(model, norm, meta))   # scored in Rust
sts.search_action(c, stsnet.Evaluator(model, norm), features=stsnet.features_for(meta))  # PyTorch
```

`stsnet.rust_evaluator` gives an `sts.NetEvaluator`: the same net's forward
pass in Rust (`py/src/net.rs`), run inside every search thread without
Python's lock. The bench, self-play rounds, `generalise.py` and
`transfer.py` search with it; `stsnet.Evaluator` (PyTorch) stays for static
values over encoded batches (the bench's prediction metric) and for custom
callables, which `sts.run` still accepts (they run on `stsnet.NET_THREADS`
threads).

Search can also score leaves with the mean of several nets: give
`bench.load_evaluator` (and so `--evaluator` in `bench.py`, `ladder.py` and
`depth_paired.py`) paths joined by `+`, as in `a.pt+b.pt+c.pt`
(decisions "Ensemble evaluator: no change at two turns").

Nets are saved under the contract (`docs/specs/rules-engine-upgrade.md`,
spec 1): `stsnet.save` writes `schema` 1, the column names per input path,
the row kinds and the pile names, and loading has the encoder write each
batch in the net's own column order, so a net keeps loading bit-identical
after columns are reordered, appended or removed. A newer schema is refused.
A net saved before the contract (no `schema`) loads through the converted
file beside it, `<name>.contract.pt`, and is refused when that file is
missing.

Row kinds (`sts.ROW_KINDS`): `triggered` (card effects, hook powers and
the hooks a card or intent grants), `threshold` (a monster's "once it has
lost N more HP" switch, condition `HpLostReaches` with N in
`condition_param`: The Guardian's Mode Shift and the large slimes' split,
from the read-only `engine/src/threshold.rs`) and `held` (a card's effects
while held at turn end: Burn, scalar `damage_plain_self`). A net drops the
kinds and columns it wasn't saved with, so nets saved before a kind existed
encode bit-identically (`test_old_layout_unchanged`). Feature caches are
keyed by the full layout (`registry.layout_tag`), so a feature change
rebuilds them.

Monster lookahead (`docs/specs/monster-lookahead.md`, off by default):
`sts.Features(..., lookahead=True)` adds to each monster, after its
`intent_*` block, `intent_pending` (its shown intent is still to roll),
`look_rate_damage` / `look_rate_hits` (per round over its next 4 moves) and
`next1_*` / `next2_*` (the expected effects of its next two moves), from
its AI rolled forward over its move history (`agent::lookahead`). A config
turns it on with `"lookahead": true` (feature mode `effects+lookahead`); a
saved net whose monster columns name these columns gets them on when it
loads. Encoding with it on costs about 3x the encoder's time.

Power rates (`docs/specs/rate-features.md`, off by default):
`sts.Features(..., rates=True)` adds to the player and each monster the
heuristic's per-turn sums of its hook powers (`agent::hook_rates`) as
`rate_<field>` (block, strength, self_loss, damage_all, draw, ...), and
`rate_strength_x_turns` / `rate_block_x_turns` (times the heuristic's
rounds-left estimate); the player also gets `turns_left_est`, and each card
(effects mode) `grant_rate_<field>` for the powers it applies to its user.
Generated powers get rates through their binding. A config turns it on with
`"rates": true` (feature mode `effects+rates`, after `+lookahead` when both
are on); a saved net whose player columns name them gets them on when it
loads. Encoding with it on costs about 7x the encoder's time (the
rounds-left estimate runs the heuristic).

Start HP (`docs/specs/start-hp.md`, off by default):
`sts.Features(..., start_hp=True)` ends the player path with `start_hp`,
the HP the combat started at (the score counts HP lost from it). A config
turns it on with `"start_hp": true` (feature mode `...+start`, the last
suffix); a saved net whose player columns name it gets it on when it loads.

Convert old nets with:

```bash
.venv/Scripts/python scripts/convert_net.py models/*.pt runs/*/model.pt
```

It writes `<name>.contract.pt` beside each net (never over the original or
an existing converted file), only after the converted net's outputs on the
fixed state set equal the original's bit for bit in both passes. It refuses
anything but the `rows` layout, nets whose input widths don't match their
vocabularies, and heuristic-correction and quantile-HP nets (`stsnet`
refuses those anyway); it exits 1 when it refused any.

Speed, Python vs Rust on the same specs:

```bash
.venv/Scripts/python scripts/inference_speed.py --hp-net <run>/model.pt
```

## Silent transfer test (check 8)

```bash
.venv/Scripts/python scripts/transfer.py
```

Uses the two nets from `generalise.py` unchanged (trained on Ironclad only)
on Silent games: tier A decks (cards built from primitives Ironclad uses,
gated) and tier B (Poison, reported). Labelled Silent data is cached in
`data/silent_*`.

## Granting a held-out power (check 9)

```bash
.venv/Scripts/python scripts/granting.py
```

Uses the two nets from `generalise.py` (trained without Metallicize, Demon
Form, Rage, Go for the Eyes and FTL) and a reference effects net trained the
same way with those cards in the pool (`models/value_reference.pt`, cached;
`--retrain` rebuilds it). At every decision where a held-out card is
playable, each net's search scores the options; the gate compares each net's
gain from playing the card with the reference net's (result in
`docs/decisions.md`).
