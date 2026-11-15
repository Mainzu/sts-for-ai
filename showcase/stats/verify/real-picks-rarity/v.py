import sys, os, json, collections
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as R
REC = ROOT + "/results/real-game"
runs = R.all_runs(REC)
print("runs", len(runs))
num = {(r["folder"], r["seed"]): i + 1 for i, r in enumerate(runs)}
rar = {}
def walk(o):
    if isinstance(o, dict):
        if "rarity" in o and "name" in o and "uuid" in o:
            rar.setdefault(o["name"], set()).add(o["rarity"]); rar.setdefault(o.get("id"), set()).add(o["rarity"])
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
# per folder: decisions groups; per run (seed) count of CARD_REWARD screens
tally = collections.defaultdict(lambda: [0, 0])
rewards = collections.Counter(); offers = collections.Counter(); skips = collections.Counter()
floor0 = collections.Counter()
unknown = collections.Counter()
mism = []
for name in sorted(os.listdir(REC)):
    folder = os.path.join(REC, name)
    if not (os.path.isdir(folder) and name[:1].isdigit()): continue
    with open(os.path.join(folder, "states.jsonl"), encoding="utf-8") as f:
        for line in f:
            if '"rarity"' in line: walk(json.loads(line))
    fr = [r for r in R.runs_of(folder)]
    groups, prev = [], None
    for d in R.lines(os.path.join(folder, "decisions.jsonl")):
        if prev is None or d["floor"] < prev: groups.append([])
        prev = d["floor"]; groups[-1].append(d)
    kept = [r for r in fr if (folder and (r["fights"] or r["end"]))]
    # match groups to runs with decisions: runs that had combat
    wf = [r for r in fr if r["combat"]]
    if len(groups) != len(wf): mism.append((name, len(groups), len(wf), len(kept)))
    for g, r in zip(groups, wf):
        k = (r["folder"], r["seed"])
        if k not in num: continue
        n = num[k]; a = R.asc(r)
        for d in g:
            if "card_reward" not in d: continue
            rewards[a] += 1
            if d["pick"] is None: skips[a] += 1
            pk = d["pick"].replace("gen:", "").rstrip("+") if d["pick"] else None
            if d["floor"] == 0: floor0[a] += 1
            for c in d["card_reward"]:
                rs = rar.get(c) or rar.get(c.rstrip("+"))
                if not rs: unknown[c] += 1; continue
                rr = sorted(rs)[0] if len(rs) == 1 else "/".join(sorted(rs))
                key = (a, rr, d["floor"] == 0)
                tally[key][1] += 1; offers[a] += 1
                if pk == c: tally[key][0] += 1
print("mismatch", mism)
print("rewards", rewards, "skips", skips, "offers", offers, "floor0", floor0, "unknown", unknown)
for a in (0, 20):
    agg = collections.defaultdict(lambda: [0, 0])
    for (aa, rr, f0), v in sorted(tally.items()):
        if aa != a: continue
        print(a, rr, "floor0" if f0 else "", v, round(100 * v[0] / v[1], 1))
        agg[rr][0] += v[0]; agg[rr][1] += v[1]
    print("all", {k: (v, round(100 * v[0] / v[1], 1)) for k, v in agg.items()})
    print("asc", a, "runs", sum(1 for r in runs if R.asc(r) == a))
bad = collections.Counter(); offered_rare = collections.Counter()
for name in sorted(os.listdir(REC)):
    folder = os.path.join(REC, name)
    if not os.path.isdir(folder) or not name[:1].isdigit(): continue
    for d in R.lines(os.path.join(folder, "decisions.jsonl")):
        if "card_reward" in d:
            pk = d["pick"].replace("gen:", "").rstrip("+") if d["pick"] else None
            if pk and pk not in d["card_reward"]: bad[(pk, tuple(d["card_reward"]))] += 1
            for c in d["card_reward"]:
                if "RARE" in rar[c]: offered_rare[c] += 1
print("pick not in offer", bad)
print("rares", offered_rare)
# pickable options only (engine-modelled), with and without floor 0 (Neow colorless)
for excl0 in (False, True):
    t = collections.defaultdict(lambda: [0, 0]); nrw = collections.Counter(); unm = collections.Counter()
    for name in sorted(os.listdir(REC)):
        folder = os.path.join(REC, name)
        if not (os.path.isdir(folder) and name[:1].isdigit()): continue
        fr = R.runs_of(folder); wf = [r for r in fr if r["combat"]]
        groups, prev = [], None
        for d in R.lines(os.path.join(folder, "decisions.jsonl")):
            if prev is None or d["floor"] < prev: groups.append([])
            prev = d["floor"]; groups[-1].append(d)
        for g, r in zip(groups, wf):
            if (r["folder"], r["seed"]) not in num: continue
            a = R.asc(r)
            for d in g:
                if "card_reward" not in d or (excl0 and d["floor"] == 0): continue
                nrw[a] += 1
                pk = d["pick"].replace("gen:", "").rstrip("+") if d["pick"] else None
                opts = [o.replace("gen:", "").rstrip("+") for o in d["options"] if o]
                for c in d["card_reward"]:
                    if c not in opts: unm[(a, sorted(rar[c])[0])] += 1
                for c in opts:
                    k = (a, sorted(rar[c])[0]); t[k][1] += 1; t[k][0] += (pk == c)
    print("excl floor0" if excl0 else "all floors", dict(nrw), {k: (v, round(100*v[0]/v[1], 1)) for k, v in sorted(t.items())}, "unmodelled", dict(unm))
