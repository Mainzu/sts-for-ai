"""Pins for the contract with the net (docs/decisions.md "Contract as built", step 1): the
fixed state set, today's feature batches on it and today's outputs of tiny
pre-contract (`format: "rows"`) nets, so later steps can check that nothing
they don't mean to change has changed.

The fixed set: py/tests/golden.py's states, data/bench/decisions.json (2,000
Ironclad tight-fight decisions) and data/bench/fixed_silent.json (1,000
Silent decisions). Batches are pinned as sha256 of their bytes (the full
arrays would be tens of MB); outputs as float32 arrays.

`python scripts/tests/contract_pins.py` rewrites the pins; only do that on
purpose, since test_contract.py checks new builds against them."""

import hashlib
import json
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "py", "tests"))
import sts  # noqa: E402
import bench_decisions  # noqa: E402
import golden  # noqa: E402
import stsnet  # noqa: E402

DATA = os.path.join(HERE, "data", "contract")
PINS = os.path.join(DATA, "pins.json")
# The full layout as it was before threshold and held rows (2026-10-30), as
# a net saved then carries it, with that layout's batch hashes: written once
# by `write_old_layout`, never re-pinned (threshold-and-held-rows spec).
OLD_LAYOUT = os.path.join(DATA, "old_layout.json")
OUTPUTS = os.path.join(DATA, "outputs.npz")
# Tiny pre-contract nets, saved the old way: (file, card repr, HP-histogram head).
NETS = (("tiny_effects.pt", "effects", False), ("tiny_ids.pt", "ids", False), ("tiny_effects_hp.pt", "effects", True))
MODES = ("effects", "ids")

_states = None


def fixed_states():
    """The fixed state set, in a fixed order: golden, Ironclad, Silent."""
    global _states
    if _states is None:
        out = golden.states()
        for rows in (bench_decisions.load_decisions(), bench_decisions.load_fixed_silent()):
            for half in rows.values():
                out += [bench_decisions.replay(d) for d in half]
        _states = out
    return _states


def batch_hashes(b):
    return {k: {"dtype": str(v.dtype), "shape": list(v.shape), "sha256": hashlib.sha256(v.tobytes()).hexdigest()}
            for k, v in sorted(b.items())}


def net_path(name):
    return os.path.join(DATA, name)


def make_nets():
    """Writes the tiny nets: fixed init, normaliser fitted on the fixed set."""
    states = fixed_states()
    for name, mode, hp in NETS:
        torch.manual_seed(0)
        feats = sts.Features(mode)
        b = feats.encode(states)
        ds = stsnet.Dataset.from_batches([b], np.zeros(len(states), np.float32))
        model = stsnet.ValueNet(feats.dims, width=8, row_width=4, hp_loss=hp)  # `hidden` isn't saved: default
        save_pre_contract(net_path(name), model, stsnet.Normalizer.fit(ds), {"card_repr": mode, "format": "rows"})


def save_pre_contract(path, model, norm, meta):
    """Saves a net the way `stsnet.save` did before the contract: no
    schema, no layout, no bin_rep."""
    hp = getattr(model, "hp_loss", False)
    torch.save({"state": model.state_dict(), "dims": model.dims, "width": model.width,
                "row_width": model.row_width, "hp_loss": hp, **({"hp_head": "histogram"} if hp else {}),
                "norm": norm.state_dict(), "meta": meta}, path)


def outputs():
    """{"<net>/torch", "<net>/rust": scores [N] on the fixed set} for each tiny net."""
    states = fixed_states()
    out = {}
    for name, _, _ in NETS:
        model, norm, meta = stsnet.load_pre_contract(net_path(name))
        b = stsnet.features_for(meta).encode(states, heuristic=True)
        with torch.no_grad():
            out[f"{name}/torch"] = stsnet.score_of(model, norm.tensors(b)).numpy().astype(np.float32)
        out[f"{name}/rust"] = np.asarray(stsnet.rust_evaluator(model, norm, meta).score(states), np.float32)
    return out


def batches():
    states = fixed_states()
    return {mode: batch_hashes(sts.Features(mode).encode(states)) for mode in MODES}


def old_layout_features(mode, layout):
    """Features writing `layout` (columns, row_kinds, piles), full vocabularies."""
    return sts.Features(mode, columns=layout["columns"], row_kinds=layout["row_kinds"], piles=layout["piles"])


def write_old_layout():
    """Pins today's full layout per mode and its batches on the fixed set."""
    states = fixed_states()
    out = {}
    for mode in MODES:
        f = sts.Features(mode)
        layout = {"columns": {"player": f.player_names, "monsters": f.monster_names, "cards": f.card_names,
                              "rows": f.row_names}, "row_kinds": f.row_kinds, "piles": f.piles}
        out[mode] = {"layout": layout, "batches": batch_hashes(old_layout_features(mode, layout).encode(states))}
    with open(OLD_LAYOUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")


def load_pins():
    with open(PINS, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    os.makedirs(DATA, exist_ok=True)
    make_nets()
    with open(PINS, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"states": len(fixed_states()), "batches": batches()}, f, indent=1, sort_keys=True)
        f.write("\n")
    np.savez_compressed(OUTPUTS, **outputs())
    print(PINS, OUTPUTS, len(fixed_states()), "states")
