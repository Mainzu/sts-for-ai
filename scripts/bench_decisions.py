"""Evaluation bench decision sets and their reference values.

- decisions.json: DECISIONS_PER_HALF decision states per tight-fight half,
  sampled from search + heuristic games (the calibration agent). Each is
  saved as its spec plus the action prefix that reaches it, so `replay`
  rebuilds the exact state. Only decisions with >= 2 distinct options.
- fixed_silent.json: FIXED_SILENT_PER_HALF Silent decision states per
  standard-set Silent half (silent_a, silent_b), sampled and stored the same
  way. With golden.py's states and decisions.json it is the fixed state set
  the rules-engine series checks net identity on (docs/decisions.md "Contract as built").
- reference.json: every option of every saved decision scored by a deeper,
  wider search than the agents' (REF, averaged over REF_SEEDS), with the
  contested flag (best - worst >= CONTESTED). Computed once; rerun only when
  the decisions or REF change, or with --rereference.

    python scripts/bench_decisions.py [--rereference] [--fixed-silent]
"""

import argparse
import hashlib
import json
import os
import time

import numpy as np

import bench_sets
import action_text
import sts
import stsnet

BENCH = bench_sets.BENCH
DECISIONS_PER_HALF = 1000
DECISION_SEED = 7_000_000
FIXED_SILENT_PER_HALF = 500
FIXED_SILENT_SEED = 7_100_000
# Reference search: two turns, sampling 8 outcomes at large random events,
# listing events up to 32 outcomes (agents: 1 turn, no sampling, 16). The
# node cap is the engine's default (50,000). Sibling options share sampled
# outcomes (common random numbers, 2026-10-30); SAMPLING names that, so a
# reference computed with the older per-option sampling reads as stale.
REF = {"limit": 32, "sample_k": 8, "turns": 2}
SAMPLING = "crn"
REF_SEEDS = (1, 2, 3)
MAX_NODES = 50_000
CONTESTED = 0.05


# Action text lives in action_text (one module for every record).
encode_action = action_text.encode_action
decode_action = action_text.decode_action


def sample_decisions(keep_states=False):
    """{half: [decision dict]} (and {half: [Combat]} with keep_states)."""
    tight = bench_sets.load_set("tight")
    decisions, states = {}, {}
    for h, (half, specs) in enumerate(tight.items()):
        by_hp = {}
        for i, s in enumerate(specs):
            by_hp.setdefault(s["hp"], []).append(i)
        games = {}
        for hp, idx in sorted(by_hp.items()):
            res = sts.run("search", [(specs[i]["encounter"], specs[i]["deck"], specs[i]["seed"]) for i in idx],
                          limit=bench_sets.LIMIT, hp=hp, record=True, **stsnet.job_threads({}))
            games.update(zip(idx, res))
        cands = [(i, k) for i in range(len(specs)) for k, c in enumerate(games[i]["states"])
                 if len(c.options(bench_sets.LIMIT)) >= 2]
        rng = np.random.default_rng(DECISION_SEED + h)
        pick = sorted(rng.choice(len(cands), size=min(DECISIONS_PER_HALF, len(cands)), replace=False))
        decisions[half], states[half] = [], []
        for j in pick:
            i, k = cands[j]
            s = specs[i]
            prefix = "|".join(encode_action(a) for a in games[i]["actions"][:k])
            decisions[half].append({"spec": i, "encounter": s["encounter"], "deck": s["deck"], "hp": s["hp"],
                                    "seed": s["seed"], "character": s["character"], "family": s["family"],
                                    "group": s["group"], "step": k, "actions": prefix})
            states[half].append(games[i]["states"][k])
    return (decisions, states) if keep_states else decisions


def sample_fixed_silent():
    """{half: [decision dict]}: FIXED_SILENT_PER_HALF decisions per standard
    Silent half from search + heuristic games at full HP."""
    std = bench_sets.load_set("standard")
    decisions = {}
    for h, half in enumerate(("silent_a", "silent_b")):
        specs = std[half]
        res = sts.run("search", [(s["encounter"], s["deck"], s["seed"]) for s in specs], limit=bench_sets.LIMIT,
                      record=True, character="silent", **stsnet.job_threads({}))
        cands = [(i, k) for i in range(len(specs)) for k, c in enumerate(res[i]["states"])
                 if len(c.options(bench_sets.LIMIT)) >= 2]
        rng = np.random.default_rng(FIXED_SILENT_SEED + h)
        pick = sorted(rng.choice(len(cands), size=min(FIXED_SILENT_PER_HALF, len(cands)), replace=False))
        decisions[half] = []
        for j in pick:
            i, k = cands[j]
            s = specs[i]
            prefix = "|".join(encode_action(a) for a in res[i]["actions"][:k])
            decisions[half].append({"spec": i, "encounter": s["encounter"], "deck": s["deck"], "hp": s["hp"],
                                    "seed": s["seed"], "character": s["character"], "group": s["group"],
                                    "step": k, "actions": prefix})
    return decisions


def write_fixed_silent(out=BENCH):
    head = {"version": bench_sets.VERSION, "set": "standard", "agent": "search", "evaluator": "heuristic",
            "limit": bench_sets.LIMIT, "per_half": FIXED_SILENT_PER_HALF, "seed": FIXED_SILENT_SEED}
    dump_rows(os.path.join(out, "fixed_silent.json"), head, sample_fixed_silent())


def load_fixed_silent(bench=BENCH):
    with open(os.path.join(bench, "fixed_silent.json"), encoding="utf-8") as f:
        return json.load(f)["halves"]


def replay(d):
    """The Combat at a saved decision."""
    c = action_text.combat_of(d)
    for a in d["actions"].split("|") if d["actions"] else []:
        c.step(decode_action(a))
    return c


def dump_rows(path, head, halves):
    """Header fields, then one row per line; byte-identical per input."""
    parts = [json.dumps(head, sort_keys=True)[1:-1]]
    hs = []
    for half, rows in halves.items():
        body = ",\n".join("  " + json.dumps(r, sort_keys=True) for r in rows)
        hs.append(f" {json.dumps(half)}: [\n{body}\n ]")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("{" + parts[0] + ', "halves": {\n' + ",\n".join(hs) + "\n}}\n")


def write_decisions(out=BENCH):
    os.makedirs(out, exist_ok=True)
    head = {"version": bench_sets.VERSION, "set": "tight", "agent": "search", "evaluator": "heuristic",
            "limit": bench_sets.LIMIT, "per_half": DECISIONS_PER_HALF, "seed": DECISION_SEED}
    dump_rows(os.path.join(out, "decisions.json"), head, sample_decisions())


def load_decisions(bench=BENCH):
    with open(os.path.join(bench, "decisions.json"), encoding="utf-8") as f:
        return json.load(f)["halves"]


def options_of(c):
    """Each distinct option's actions (encoded), in `options()` order."""
    return [[encode_action(a) for a in o[0]] for o in c.options(REF["limit"])]


def reference_search(c):
    """(values per option averaged over REF_SEEDS, max nodes)."""
    total, nodes = None, 0
    for seed in REF_SEEDS:
        r = sts.search(c, "heuristic", seed=seed, **REF)
        v = np.array([val for _, val in r["options"]], dtype=np.float64)
        total = v if total is None else total + v
        nodes = max(nodes, r["nodes"])
    return [round(float(x), 6) for x in total / len(REF_SEEDS)], nodes


def reference_values(c):
    return reference_search(c)[0]


def reference_pick(c):
    """The reference's own choice: the first action of its best option."""
    values = reference_values(c)
    return c.options(REF["limit"])[int(np.argmax(values))][0][0]


def regret(row, action):
    """Reference value of the best option minus that of the option `action`
    leads to."""
    a = encode_action(action)
    i = next(i for i, acts in enumerate(row["options"]) if a in acts)
    return round(max(row["values"]) - row["values"][i], 6)


def decisions_hash(bench=BENCH):
    with open(os.path.join(bench, "decisions.json"), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def reference_head(bench=BENCH):
    return {"version": bench_sets.VERSION, "settings": REF, "seeds": list(REF_SEEDS), "max_nodes": MAX_NODES,
            "sampling": SAMPLING, "contested": CONTESTED, "decisions_sha256": decisions_hash(bench)}


def compute_reference(bench=BENCH):
    halves = {}
    for half, ds in load_decisions(bench).items():
        rows = []
        for i, d in enumerate(ds):
            c = replay(d)
            values, nodes = reference_search(c)
            rows.append({"index": i, "options": options_of(c), "values": values, "nodes": nodes,
                         "capped": nodes >= MAX_NODES, "contested": max(values) - min(values) >= CONTESTED})
        halves[half] = rows
    dump_rows(os.path.join(bench, "reference.json"), reference_head(bench), halves)


def load_reference(bench=BENCH):
    """The cached reference; raises if it is missing or stale."""
    path = os.path.join(bench, "reference.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing: run scripts/bench_decisions.py")
    with open(path, encoding="utf-8") as f:
        ref = json.load(f)
    head = reference_head(bench)
    if any(ref.get(k) != v for k, v in head.items()):
        raise ValueError(f"{path} is stale (decisions or settings changed): run scripts/bench_decisions.py")
    return ref


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rereference", action="store_true", help="recompute reference.json even if current")
    ap.add_argument("--fixed-silent", action="store_true", help="write fixed_silent.json only")
    args = ap.parse_args()
    t = time.time()
    if args.fixed_silent:
        write_fixed_silent()
        print("fixed_silent: " + ", ".join(f"{h} {len(d)}" for h, d in load_fixed_silent().items())
              + f" ({time.time() - t:.0f}s)")
        return
    write_decisions()
    print(f"decisions: " + ", ".join(f"{h} {len(d)}" for h, d in load_decisions().items()) + f" ({time.time() - t:.0f}s)")
    try:
        if args.rereference:
            raise ValueError
        load_reference()
        print("reference: current")
    except (FileNotFoundError, ValueError):
        t = time.time()
        compute_reference()
        print(f"reference: computed in {time.time() - t:.0f}s")
    for half, rows in load_reference()["halves"].items():
        print(f"{half}: {len(rows)} decisions, {sum(r['contested'] for r in rows)} contested, "
              f"{sum(r['capped'] for r in rows)} hit the node cap")


if __name__ == "__main__":
    main()
