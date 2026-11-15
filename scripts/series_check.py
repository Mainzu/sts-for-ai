"""Rules-engine series checks 4 and 5 (docs/specs/rules-engine-upgrade.md,
"Per-spec checklist"): the heuristic, contract nets and feature batches on
the fixed state set, compared between two builds of `sts`.

    # old module (the shared venv), then this checkout's (target/pyroot):
    python scripts/series_check.py dump old.npz [--cards "Body Slam,Heavy Blade"] [net.pt ...]
    PYTHONPATH=target/pyroot python scripts/series_check.py dump new.npz [--cards ...] [net.pt ...]
    python scripts/series_check.py compare old.npz new.npz

`dump` writes, over `contract_pins.fixed_states()` (plus, with `--cards`,
greedy-played states of starter decks holding those cards, so content a
spec re-expresses is covered): the heuristic estimate
per state; the default effects and ids batches (every array, with each
path's column names); and per net its torch and Rust outputs. `compare`
needs the heuristic and every net's outputs bit-identical, and every column
present in the old batch equal in the new one by name (new columns are
allowed; batches hold only the pre-series row kinds `BASE_KINDS`, so rows of
newer kinds are left out; rows, cards and their indices must line up).
"""

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tests"))

BASE_KINDS = ["triggered", "threshold", "held"]
PATHS = {"player": "player_names", "monsters": "monster_names", "cards": "card_names", "rows": "row_names"}


ENCOUNTERS = ["jaw_worm", "cultist", "two_louse", "gremlin_nob", "lagavulin", "three_sentries", "slime_boss"]


def card_states(cards):
    """Greedy-play states, Ironclad starter + 3 copies of each card (base and
    upgraded) per encounter, 20 states each, Strength or block mixed in by
    seed so amounts that read them vary."""
    import sts
    out = []
    starter = ["Strike"] * 5 + ["Defend"] * 4 + ["Bash"]
    for name in cards:
        for up in ("", "+"):
            for i, enc in enumerate(ENCOUNTERS):
                c = sts.Combat(starter + [name + up] * 3 + ["Inflame", "Shrug It Off"], enc, seed=100 + i)
                n0 = len(out)
                while not c.is_over() and len(out) < n0 + 20:
                    out.append(c.clone())
                    c.step(sts.greedy_action(c))
    return out


def dump(out, nets, cards=()):
    import sts
    import torch
    import contract_pins
    import stsnet
    torch.set_num_threads(4)
    states = contract_pins.fixed_states() + card_states(cards)
    d, names = {}, {}
    for mode in ("effects", "ids"):
        # Only the row kinds from before the series: rows of newer kinds are
        # new content; old rows must still line up exactly.
        f = sts.Features(mode, row_kinds=BASE_KINDS)
        b = f.encode(states, heuristic=True)
        for k, v in b.items():
            d[f"{mode}/{k}"] = np.asarray(v)
        names[mode] = {p: list(getattr(f, m)) for p, m in PATHS.items()}
    for i, p in enumerate(nets):
        model, norm, meta = stsnet.load(p)
        b = stsnet.features_for(meta).encode(states, heuristic=True)
        with torch.no_grad():
            d[f"net{i}/torch"] = stsnet.score_of(model, norm.tensors(b)).numpy().astype(np.float32)
        d[f"net{i}/rust"] = np.asarray(stsnet.rust_evaluator(model, norm, meta).score(states), np.float32)
    d["meta"] = np.frombuffer(json.dumps({"names": names, "nets": nets, "n": len(states),
                                          "module": sts.__file__}).encode(), np.uint8)
    np.savez_compressed(out, **d)
    print(f"{out}: {len(states)} states, {len(nets)} nets, module {sts.__file__}")


def _meta(z):
    return json.loads(bytes(z["meta"]).decode())


def compare(a_path, b_path):
    a, b = np.load(a_path), np.load(b_path)
    ma, mb = _meta(a), _meta(b)
    bad = []
    if ma["n"] != mb["n"]:
        bad.append(f"state count {ma['n']} vs {mb['n']}")
    for mode in ("effects", "ids"):
        h = f"{mode}/heuristic"
        if not np.array_equal(a[h], b[h]):
            bad.append(f"{h}: {int((a[h] != b[h]).sum())} states differ")
        for path, key in (("player", "player"), ("monsters", "monsters"), ("cards", "cards"), ("rows", "rows")):
            na, nb = ma["names"][mode][path], mb["names"][mode][path]
            missing = [n for n in na if n not in nb]
            if missing:
                bad.append(f"{mode}/{path}: columns gone {missing[:5]}")
                continue
            xa, xb = a[f"{mode}/{key}"], b[f"{mode}/{key}"]
            if xa.shape[:-1] != xb.shape[:-1]:
                bad.append(f"{mode}/{path}: shape {xa.shape} vs {xb.shape}")
                continue
            idx = [nb.index(n) for n in na]
            diff = [n for j, n in enumerate(na) if not np.array_equal(xa[..., j], xb[..., idx[j]])]
            if diff:
                bad.append(f"{mode}/{path}: {len(diff)} old columns differ, e.g. {diff[:6]}")
        for k in [k for k in a.files if k.startswith(mode + "/")]:
            base = k.split("/", 1)[1]
            if base in ("player", "monsters", "cards", "rows", "heuristic"):
                continue
            if k not in b.files:
                bad.append(f"{k}: missing")
            elif not np.array_equal(a[k], b[k]):
                bad.append(f"{k}: differs")
    for i, p in enumerate(ma["nets"]):
        for fw in ("torch", "rust"):
            k = f"net{i}/{fw}"
            if k not in b.files or not np.array_equal(a[k], b[k]):
                n = "missing" if k not in b.files else f"{int((a[k] != b[k]).sum())} states differ"
                bad.append(f"{p} {fw}: {n}")
    for line in bad:
        print("FAIL", line)
    print(f"{'FAIL' if bad else 'PASS'}: {ma['n']} states, heuristic, {len(ma['nets'])} nets, old columns "
          f"({ma['module']} vs {mb['module']})")
    return 1 if bad else 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "dump" and len(sys.argv) >= 3:
        rest = sys.argv[3:]
        cards = []
        if rest[:1] == ["--cards"]:
            cards, rest = [c for c in rest[1].split(",") if c], rest[2:]
        dump(sys.argv[2], rest, cards)
    elif cmd == "compare" and len(sys.argv) == 4:
        sys.exit(compare(sys.argv[2], sys.argv[3]))
    else:
        print(__doc__)
        sys.exit(2)
