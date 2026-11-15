"""Share of a burst dataset's training states where the player holds a power.

States are sampled exactly as finetune.encoded samples them (same rng seed,
chunks and selfplay.sample_states), so the count is of the rows the burst
trained on (the replay pool's rows are not counted). Decks are split by
whether they hold the card; per group (elite, boss) and both.

    python scripts/analysis/power_exposure.py --power DemonForm --card "Demon Form" \
        --ds aa2d9e40ac32:1600 --ds 48a0cf093824:400 [--out file.json]
"""
import argparse, collections, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
import finetune, registry, selfplay

GROUPS = {0: "hallway", 1: "elite", 2: "boss"}


def count(ds, k, power, card):
    m = registry.load_manifest(ds)
    c = m["config"]  # a learn dataset (from scratch) keeps its sampler seed as sample_seed
    rng = np.random.default_rng(c["seed"] + finetune.SAMPLE_OFFSET if "seed" in c else c.get("sample_seed", 0))
    it = finetune.first_per_group(ds, k)
    st = collections.Counter()
    while True:
        chunk = [g for _, g in zip(range(registry.CHUNK), it)]
        if not chunk:
            break
        reps = [registry.replay(g) for g in chunk]
        states, _, _ = selfplay.sample_states(reps, [g["group"] for g in chunk], rng)
        ids = {id(s): gi for gi, r in enumerate(reps) for s in r["states"]}
        gi = None
        for s in states:
            gi = ids.get(id(s), gi)  # a paused afterstate follows its own game's state
            g = chunk[gi]
            key = ("card" if any(c.rstrip("+") == card for c in g["deck"]) else "other", GROUPS[g["group"]])
            st[key + ("n",)] += 1
            st[key + ("held",)] += any(p["name"] == power for p in s.board()["player"]["powers"])
        for g in chunk:
            if any(c.rstrip("+") == card for c in g["deck"]):
                key = ("card", GROUPS[g["group"]])
                st[key + ("games",)] += 1
                st[key + ("played",)] += any(a.split("@")[0].rstrip("+") == card for a in g["actions"])
    res = {}
    for strat in ("card", "other"):
        for grp in ("hallway", "elite", "boss", "all"):
            gs = ("hallway", "elite", "boss") if grp == "all" else (grp,)
            row = {f: sum(st[(strat, x, f)] for x in gs) for f in ("n", "held", "games", "played")}
            row["share"] = round(row["held"] / row["n"], 3) if row["n"] else None
            if strat == "card":
                row["played_share"] = round(row["played"] / row["games"], 3) if row["games"] else None
            else:
                del row["games"], row["played"]
            res[f"{strat}-{grp}"] = row
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--power", required=True)
    ap.add_argument("--card", required=True)
    ap.add_argument("--ds", action="append", required=True, help="dataset id:games per group")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    out = {}
    for spec in a.ds:
        ds, k = spec.split(":")
        out[ds] = count(ds, int(k), a.power, a.card)
        print(ds, json.dumps(out[ds]), flush=True)
    if a.out:
        with open(a.out, "w") as f:
            json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
