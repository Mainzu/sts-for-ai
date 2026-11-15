"""Generated enemies training pack (docs/specs/generated-pack.md): official
hallway and elite monsters carrying the generated enemies bench's 18
training-split mechanics as start powers, for a from-scratch learn.

    python scripts/gen_enemy_pack.py            # writes content/packs/gen-enemies-train.json
    python scripts/gen_enemy_pack.py --check    # exit 1 if the file differs
    python scripts/gen_enemy_pack.py --wide     # content/packs/gen-enemies-wide.json (docs/specs/wider-generators.md)
    python scripts/gen_enemy_pack.py --six      # content/packs/gen-enemies-six.json (docs/specs/mechanic-count-curve.md)

Powers are the bench's own (`mutate_monsters.gen_pack`); the held-out six
stay out. Each base monster (no native code, no split) gets one copy per
mechanic, its stacks drawn by a fixed hash from max(1, k // 2) .. 2k (k the
bench's stacks). Each official hallway or elite encounter holding a base
monster gets `GP <id>`: one `one_of` over the mechanics, every base monster
in its slots replaced by that mechanic's copy.
"""

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "analysis"))
import mutate_monsters as mm  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "content", "packs", "gen-enemies-train.json")
OUT_WIDE = os.path.join(ROOT, "content", "packs", "gen-enemies-wide.json")
OUT_SIX = os.path.join(ROOT, "content", "packs", "gen-enemies-six.json")
HELD_OUT = ("GE-AttackLoss-Damage", "GE-AttackLoss-Weak", "GE-OppCard-PlainDamage",
            "GE-OppCard-Damage", "GE-TurnEnd-Weak", "GE-TurnEnd-Frail")
TRAIN = [m for m in mm.GEN if m not in HELD_OUT]
# The wide pack: the old 18 and the wider grid's training split (mm.WIDE_SPLIT).
TRAIN_WIDE = TRAIN + mm.WIDE_SPLIT["train"]
# The six-mechanic pack (lane mechanic-count-curve): each held-out pair's
# trigger and effect, each trigger twice, every held-out effect at least once.
SIX = ("GE-AttackLoss-PlainDamage", "GE-AttackLoss-Frail", "GE-OppCard-Weak", "GE-OppCard-Frail",
       "GE-TurnEnd-Damage", "GE-TurnEnd-PlainDamage")
BASES = ("Cultist", "Jaw Worm", "Acid Slime (S)", "Acid Slime (M)", "Spike Slime (S)", "Spike Slime (M)",
         "Fungi Beast", "Looter", "Gremlin Nob", "Sentry")
GROUPS = ("hallway", "elite")


def stacks(base, mech):
    """The copy's stacks: the bench's k, varied per monster in max(1, k // 2) .. 2k."""
    k = mm.GEN_ALL[mech][0][2]
    lo, hi = max(1, k // 2), 2 * k
    h = int(hashlib.sha256(f"{base}|{mech}".encode()).hexdigest(), 16)
    return lo + h % (hi - lo + 1)


def _subst(slot, mech):
    """An encounter slot with every base monster replaced by its `mech` copy."""
    if isinstance(slot, str):
        return f"gen:{slot} {mech}" if slot in BASES else slot
    if "one_of" in slot:
        return {"one_of": [[_subst(s, mech) for s in opt] for opt in slot["one_of"]]}
    return {**slot, "from": [_subst(s, mech) for s in slot["from"]]}


def _has_base(slot):
    if isinstance(slot, str):
        return slot in BASES
    return any(_has_base(s) for opt in slot.get("one_of", [slot.get("from", [])]) for s in opt)


# The wide pack's carriers (the engine holds at most 236 pack monsters, so
# not every base gets every mechanic): every mechanic on both elites, and
# each on one single-base hallway encounter, dealt in turn in sha256 order of
# the name; the slime and mixed hallways stay official.
WIDE_HALLWAYS = ("cultist", "jaw_worm", "two_fungi_beasts", "looter")


def wide_carriers(train):
    """{encounter id: its mechanics} for the wide pack."""
    order = sorted(train, key=lambda m: hashlib.sha256(m.encode()).hexdigest())
    out = {"gremlin_nob": list(train), "three_sentries": list(train)}
    for e in WIDE_HALLWAYS:
        out[e] = [m for m in train if order.index(m) % len(WIDE_HALLWAYS) == WIDE_HALLWAYS.index(e)]
    return out


def _bases(slots):
    out = set()
    for s in slots:
        if isinstance(s, str):
            out |= {s} & set(BASES)
        else:
            for opt in s.get("one_of", [s.get("from", [])]):
                out |= _bases(opt)
    return out


def generate(train=TRAIN, carriers=None):
    """The pack as a dict, over the mechanics `train`; `carriers` ({encounter
    id: mechanics}, default every encounter holding a base: all of `train`)."""
    with open(os.path.join(ROOT, "content", "monsters.json"), encoding="utf-8") as f:
        official = {m["id"]: m for m in json.load(f)["monsters"]}
    with open(os.path.join(ROOT, "content", "encounters.json"), encoding="utf-8") as f:
        encounters = json.load(f)["encounters"]
    encounters = [e for e in encounters if e["group"] in GROUPS and any(_has_base(s) for s in e["monsters"])]
    if carriers is None:
        carriers = {e["id"]: list(train) for e in encounters}
    encounters = [e for e in encounters if e["id"] in carriers]
    powers = [p for p in json.loads(mm.gen_pack())["powers"] if p["id"] in train]
    need = {(b, m) for e in encounters for b in _bases(e["monsters"]) for m in carriers[e["id"]]}
    monsters = []
    for base in BASES:
        m = official[base]
        assert "code" not in m and "split" not in m, base
        for mech in train:
            if (base, mech) in need:
                monsters.append({**m, "id": f"{base} {mech}",
                                 "start_powers": m["start_powers"] + [{"power": mech, "amount": stacks(base, mech)}]})
    encs = [{"id": f"GP {e['id']}", "group": e["group"],
             "monsters": [{"one_of": [[_subst(s, mech) for s in e["monsters"]] for mech in carriers[e["id"]]]}]}
            for e in encounters]
    return {"version": 1, "powers": powers, "monsters": monsters, "encounters": encs}


def text(pack):
    """The file text: one entry per line, as the Act 1 packs."""
    parts = []
    for key in ("powers", "monsters", "encounters"):
        rows = ",\n".join(json.dumps(x, sort_keys=True) for x in pack[key])
        parts.append(f'"{key}": [\n{rows}\n]')
    return '{"version": 1,\n' + ",\n".join(parts) + "}\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed file differs")
    ap.add_argument("--wide", action="store_true", help="the wide pack (old 18 + the wider grid's training split)")
    ap.add_argument("--six", action="store_true", help="the six-mechanic pack (lane mechanic-count-curve)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    a.out = a.out or (OUT_WIDE if a.wide else OUT_SIX if a.six else OUT)
    if a.wide:
        t = text(generate(TRAIN_WIDE, wide_carriers(TRAIN_WIDE)))
    else:
        t = text(generate(list(SIX)) if a.six else generate())
    if a.check:
        with open(a.out, encoding="utf-8") as f:
            sys.exit(0 if f.read() == t else 1)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(t)
    print(f"{a.out}: {t.count(chr(10))} lines")


if __name__ == "__main__":
    main()
