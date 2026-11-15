"""Converts pre-contract nets to contract nets (docs/decisions.md "Contract as built").

A pre-contract net (no `schema`) is read as saved, its meta's vocabularies
give today's encoder, its input widths must match that encoder's, and it is
saved again by `stsnet.save` with `schema`, `columns` (today's names, so ids
columns are `id_<name>`), `row_kinds` and `piles`. Weights and normaliser are
copied unchanged. The new file goes beside the original as
`<name>.contract.pt`, never over it or over an existing converted file, and
only after its outputs on the fixed state set equal the original's bit for
bit, torch against torch and Rust against Rust.

Known pre-contract layouts: one, `format: "rows"`. Anything else, and nets
`stsnet` already refuses (correction heads, quantile HP nets), is refused.

    python scripts/convert_net.py models/*.pt runs/*/model.pt
"""

import glob
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(__file__))
import stsnet  # noqa: E402


class Refused(Exception):
    """A net the converter won't convert, with the reason."""


def _outputs(model, norm, meta, states):
    b = stsnet.features_for(meta).encode(states, heuristic=True)
    with torch.no_grad():
        t = stsnet.score_of(model, norm.tensors(b)).numpy().astype(np.float32)
    r = np.asarray(stsnet.rust_evaluator(model, norm, meta).score(states), np.float32)
    return t, r


def convert(path, states):
    """Converts the net at `path`, checked on `states`; returns the new
    file's path. Raises Refused (nothing written) when it can't."""
    conv = stsnet.contract_path(path)
    if os.path.exists(conv):
        raise Refused(f"{conv} exists")
    d = torch.load(path, weights_only=False)
    if "schema" in d:
        raise Refused(f"already a contract net (schema {d['schema']})")
    fmt = d.get("meta", {}).get("format")
    if fmt != "rows":
        raise Refused(f"unknown pre-contract format {fmt!r} (only 'rows')")
    try:
        model, norm, meta = stsnet.load_pre_contract(path)
    except ValueError as e:  # correction heads, quantile HP nets
        raise Refused(str(e)) from None
    tmp = conv + ".tmp"
    try:
        try:
            stsnet.save(tmp, model, norm, meta)
        except ValueError as e:  # widths don't match the meta's encoder
            raise Refused(str(e)) from None
        before = _outputs(model, norm, meta, states)
        after = _outputs(*stsnet.load(tmp), states)
        for side, x, y in zip(("torch", "Rust"), before, after):
            if x.tobytes() != y.tobytes():
                raise Refused(f"{side} outputs differ after conversion on {int((x != y).sum())} states")
        os.replace(tmp, conv)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return conv


def main(patterns):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tests"))
    import contract_pins
    torch.set_num_threads(4)
    states = contract_pins.fixed_states()
    paths = sorted({p for pat in patterns for p in (glob.glob(pat) or [pat])
                    if not p.endswith(".contract.pt")})
    done, already, refused = [], [], []
    for p in paths:
        if os.path.exists(stsnet.contract_path(p)):
            already.append(p)
            continue
        try:
            convert(p, states)
            done.append(p)
            print("converted", p, flush=True)
        except Refused as e:
            refused.append((p, str(e)))
            print("refused  ", p, "-", e, flush=True)
    print(f"{len(done)} converted, {len(already)} already converted, {len(refused)} refused "
          f"({len(states)} fixed states, torch and Rust bit-identical)")
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
