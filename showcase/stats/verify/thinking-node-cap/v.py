import sys, os, json, collections
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as R
REC = ROOT + "/results/real-game"
allr = R.all_runs(REC)
num = {(r["folder"], r["seed"]): i + 1 for i, r in enumerate(allr)}
D = []  # (runnum, asc, rules, decision)
unmatched = 0
for name in sorted(os.listdir(REC)):
    folder = os.path.join(REC, name)
    if not (os.path.isdir(folder) and name[:1].isdigit()): continue
    runs = [r for r in R.runs_of(folder) if r["combat"]]
    k, prev = -1, None
    p = os.path.join(folder, "decisions.jsonl")
    if not os.path.exists(p): continue
    with open(p, encoding="utf-8") as f:
        for l in f:
            if not l.strip(): continue
            d = json.loads(l)
            if prev is None or d["floor"] < prev: k += 1
            prev = d["floor"]
            if "view" not in d: continue
            if k >= len(runs): unmatched += 1; continue
            r = runs[k]
            n = num.get((r["folder"], r["seed"]))
            D.append((n, R.asc(r), r["run_rules"], d))
print("runs", len(allr), "unmatched", unmatched, "nonum", sum(1 for x in D if x[0] is None))
def bare(s): return s.replace("gen:", "").split("{")[0]
def rate(rows, label):
    c = sum(1 for x in rows if x[3]["cut"]); n = len(rows)
    rs = len({x[0] for x in rows})
    sec = sum(x[3]["seconds"] for x in rows) / n if n else 0
    print(f"{label:30s} {c:4d}/{n:5d} = {100*c/n if n else 0:5.1f}%  runs {rs}  mean {sec:.1f}s")
for a in (0, 20):
    S = [x for x in D if x[1] == a]
    print("== asc", a, "runs", min(x[0] for x in S), max(x[0] for x in S))
    rate(S, "all")
    pw = lambda nm: [x for x in S if nm in x[3]["view"]["player"]["powers"]]
    for nm in ("Evolve", "Juggernaut", "Frail", "Dexterity"): rate(pw(nm), nm)
    mv = lambda x: x[3]["options"][x[3]["pick"]][0]
    rate([x for x in S if mv(x).startswith("Potion")], "potion move")
    rate([x for x in S if mv(x) == "Strike" or mv(x).startswith("Strike@")], "Strike exact")
    rate([x for x in S if bare(mv(x).split("@")[0]).rstrip("+") == "Strike"], "Strike any")
    hand = lambda nm: [x for x in S if any(bare(c).rstrip("+") == nm for c in x[3]["view"]["hand"])]
    rate(hand("Battle Trance"), "Battle Trance in hand")
    rate(hand("Burn"), "Burn in hand")
    rate([x for x in S if any(bare(m["name"]) == "Spike Slime (L)" and m["hp"] > 0 and not m.get("escaped") for m in x[3]["view"]["monsters"])], "SSL alive")
    rate([x for x in S if any(bare(m["name"]) == "Spike Slime (L)" for m in x[3]["view"]["monsters"])], "SSL present")
    # rules split
    for rr in sorted({x[2] for x in S}): rate([x for x in S if x[2] == rr], f"rules {rr}")
    # evolve/jugg per run
    for nm in ("Evolve", "Juggernaut"):
        c = collections.Counter(); t = collections.Counter()
        for x in pw(nm): t[x[0]] += 1; c[x[0]] += x[3]["cut"]
        print(nm, {k: f"{c[k]}/{t[k]}" for k in t})
