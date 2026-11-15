"""Parity of the Rust flags (docs/specs/shown-card-numbers.md) with zs.py's
`shown` and zs_noex.py's `noex`: the batches `sts.Features(shown_numbers=,
exhaust_hidden=)` write equal the numpy transforms of the plain batch, and
the 10-29 net's `NetEvaluator` with the flags gives zs_noex.py's
correlations on pairs.jsonl (0.218 attack pairs with Strength or Weak,
shown; 0.203 all, hidden; 0.221 all, both) within 0.005.
Since the engine's `shown_damage` (engine audit entry 1) the Rust batches
round each hit, so the shown arms differ from zs.py's floor-the-total
numpy on multi-hit attacks under Weak: this script is the record of the
zs.py port, not a current check. The flags now come from the net's meta;
the arms set them there.
Run from the main checkout (its data): python <this file>; it imports the
scripts beside it. Exit 0 on PASS."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
import sts  # noqa: E402
import stsnet  # noqa: E402

PAIRS = "results/probes/pile-prices/pairs.jsonl"
NET = "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt"
model, norm, meta = stsnet.load(NET)
_cards = json.load(open("content/cards.json"))["cards"]
cards_type = {c["id"]: c["type"] for c in _cards}
plain = stsnet.features_for(meta)
kw = {k: meta.get(k) for k in stsnet.VOCAB_KEYS + stsnet.LAYOUT_KEYS}


def feats(**flags):
    return sts.Features(meta["card_repr"], lookahead=bool(meta.get("lookahead")), rates=bool(meta.get("rates")),
                        start_hp=bool(meta.get("start_hp")), **kw, **flags)


PI = {n: i for i, n in enumerate(plain.player_names)}
CI = {n: i for i, n in enumerate(plain.card_names)}
EXI = list(plain.piles).index("exhaust")


def shown(b):  # zs.py's, verbatim in effect
    cards = np.array(b["cards"], np.float32, copy=True); pl = np.asarray(b["player"]); s = np.asarray(b["card_state"])
    st, wk = pl[s, PI["power_Strength"]], pl[s, PI["power_Weak"]] > 0
    dx, fr = pl[s, PI["power_Dexterity"]], pl[s, PI["power_Frail"]] > 0
    for d, h in (("damage_single", "hits_single"), ("damage_all", "hits_all"), ("damage_random", "hits_random")):
        hit = cards[:, CI[h]]; on = hit > 0
        v = cards[:, CI[d]] + st * hit
        v = np.where(wk, np.floor(v * 0.75), v)
        cards[:, CI[d]] = np.where(on, np.maximum(v, 0), cards[:, CI[d]])
    blk = cards[:, CI["block"]]; on = blk > 0
    v = blk + dx; v = np.where(fr, np.floor(v * 0.75), v)
    cards[:, CI["block"]] = np.where(on, np.maximum(v, 0), blk)
    b = dict(b); b["cards"] = cards; return b


def noex(b):  # zs_noex.py's
    b = dict(b); c = np.array(b["card_count"], np.float32, copy=True); c[np.asarray(b["card_pile"]) == EXI] = 0
    b["card_count"] = c; return b


rows = [json.loads(line) for line in open(PAIRS)]
states, pairs = [], []
for r in rows:
    base = len(states)
    names = list(r["hex"])
    for n in names:
        states.append(sts.Combat.decode(bytes.fromhex(r["hex"][n]), 0))
    c0 = states[base]; pw = {p["name"]: int(p["amount"]) for p in c0.board()["player"]["powers"]}
    sw = pw.get("Strength", 0) != 0 or pw.get("Weak", 0) != 0
    o = r["scores"]["orig"]
    for j, n in enumerate(names[1:], 1):
        d = [b - a for a, b in zip(o, r["scores"][n])]
        pairs.append((base, base + j, float(np.mean(d)), sw and cards_type.get(n.rstrip("+")) == "Attack"))

arms = {"shown": dict(shown_numbers=True), "hidden": dict(exhaust_hidden=True),
        "both": dict(shown_numbers=True, exhaust_hidden=True)}
numpy_of = {"shown": shown, "hidden": noex, "both": lambda b: noex(shown(b))}
b0 = plain.encode(states)
ok = True
for name, fl in arms.items():
    want, got = numpy_of[name](b0), feats(**fl).encode(states)
    bad = [k for k in want if not np.array_equal(np.asarray(want[k]), np.asarray(got[k]))]
    print(f"batch {name:6s}: {'equal' if not bad else 'DIFFERS in ' + ', '.join(bad)}")
    ok &= not bad

td = np.array([p[2] for p in pairs]); att = np.array([p[3] for p in pairs])


def corr(y, m):
    d = np.array([y[q[1]] - y[q[0]] for q in pairs])
    return np.corrcoef(d[m], td[m])[0, 1]


allm = np.ones(len(td), bool)
targets = [("shown", att, 0.218, "attack pairs with Strength or Weak"), ("hidden", allm, 0.203, "all pairs"),
           ("both", allm, 0.221, "all pairs")]
today = np.asarray(stsnet.rust_evaluator(model, norm, meta).score(states), np.float64)
print(f"today: all {corr(today, allm):+.3f} (zs 0.178), attack Str/Weak {corr(today, att):+.3f} (zs 0.156)")
for name, m, want, label in targets:
    y = np.asarray(stsnet.rust_evaluator(model, norm, {**meta, **arms[name]}).score(states), np.float64)
    c = corr(y, m)
    good = abs(c - want) <= 0.005
    ok &= good
    print(f"{name:6s} {label:36s} corr {c:+.3f} (zs {want:.3f}) {'ok' if good else 'OFF'}")
print("PARITY", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
