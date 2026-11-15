"""Lane shown-card-numbers step 2 read: arm files against a control on the
one-turn cell gauntlet, paired by sequence, at fixed n, split by stratum:
decks holding a Strength source or a multi-hit attack (STRATUM) and the
rest. Prints per arm and stratum the paired end HP (gauntlet_protocol.end_hp)
and clears with se, the protocol's verdict on all pairs in index order
(--d1 1.5) and on the stratum alone, and the charter's go rule: the
stratum's end HP gain > 2 se with no stratum losing more than 1.5 HP at
2 se (mean + 2 se < -1.5).

    python scripts/analysis/shown_strata.py <control.json> <arm.json> [<arm.json> ...]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import numpy as np  # noqa: E402
import gauntlet  # noqa: E402
import gauntlet_protocol as gp  # noqa: E402

STRATUM = {"Inflame", "Spot Weakness", "Flex", "Limit Break", "Rupture", "Heavy Blade", "Twin Strike",
           "Sword Boomerang", "Pummel"}


def mean_se(x):
    x = np.asarray(x, float)
    return float(x.mean()), float(x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else 0.0


def read(control, arm):
    c = {r["i"]: r for r in json.load(open(control))["sequences"]}
    a = {r["i"]: r for r in json.load(open(arm))["sequences"]}
    keys = sorted(k for k in set(a) & set(c) if a[k]["cell"] == c[k]["cell"])
    decks = {s["i"]: s["deck"] for s in gauntlet.sequences(max(keys) + 1)}
    held = {k: bool(STRATUM & {n.rstrip("+") for n in decks[k]}) for k in keys}
    out = {}
    for name, ks in (("all", keys), ("stratum", [k for k in keys if held[k]]), ("rest", [k for k in keys if not held[k]])):
        dh = [gp.end_hp(a[k]) - gp.end_hp(c[k]) for k in ks]
        dc = [float(a[k]["cleared"]) - float(c[k]["cleared"]) for k in ks]
        verdict = gp.sprt(dh, dc, 1.5, 50) if len(ks) >= 50 else ("open", len(ks))
        out[name] = {"n": len(ks), "hp": mean_se(dh), "clears": mean_se(dc), "protocol": verdict,
                     "clear_arm": float(np.mean([a[k]["cleared"] for k in ks]))}
    s, r = out["stratum"]["hp"], out["rest"]["hp"]
    out["go"] = s[0] > 2 * s[1] and all(m + 2 * se >= -1.5 for m, se in (s, r))
    return out


def main(argv):
    control, arms = argv[0], argv[1:]
    for arm in arms:
        o = read(control, arm)
        print(f"\n{arm} against {control}")
        for k in ("all", "stratum", "rest"):
            v = o[k]
            print(f"  {k:8s} n {v['n']:4d}  end HP {v['hp'][0]:+6.2f} ({v['hp'][1]:.2f})  clears {v['clears'][0]:+.3f} "
                  f"({v['clears'][1]:.3f}), arm {v['clear_arm']:.3f}  protocol {v['protocol']}")
        print(f"  go rule (stratum > 2 se, no stratum below -1.5 HP at 2 se): {'GO' if o['go'] else 'no'}")


if __name__ == "__main__":
    main(sys.argv[1:])
