import sys, os, json, collections
REPO = "."
sys.path.insert(0, REPO + "/scripts")
import real_game_report as R
REC = REPO + "/results/real-game"

def dec_runs(folder):
    out, cur, prev = [], None, None
    p = os.path.join(folder, "decisions.jsonl")
    if not os.path.exists(p): return out
    with open(p, encoding="utf-8") as f:
        for l in f:
            if not l.strip(): continue
            d = json.loads(l)
            if prev is None or d["floor"] < prev:
                cur = []; out.append(cur)
            prev = d["floor"]; cur.append(d)
    return out

import re
def isplay(x):
    return not (x == "End" or x == "Done" or x.lower().startswith(("potion", "choose:", "use", "discard")))
def name(a):
    c = re.sub(r"\{[^}]*\}", "", a.split("@")[0])
    return c[4:] if c.startswith("gen:") else c

kinds = collections.Counter()
res = {}  # asc -> stats
runno = 0
check = []
for nm in sorted(os.listdir(REC)):
    folder = os.path.join(REC, nm)
    if not (os.path.isdir(folder) and nm[:1].isdigit()): continue
    runs = [r for r in R.runs_of(folder) if r["fights"] or r["end"]]
    fr = [r for r in runs if r["fights"]]
    drs = dec_runs(folder)
    # map decision runs to runs with fights in order
    drs_f = [dr for dr in drs if any("view" in d for d in dr)]
    for r in runs:
        runno += 1
        r["no"] = runno
    if len(drs_f) != len(fr):
        print("MISMATCH", nm, len(drs_f), len(fr), [r["no"] for r in runs])
    for r, dr in zip(fr, drs_f):
        a = R.asc(r)
        S = res.setdefault(a, {"plays": collections.Counter(), "fights": set(), "turns": set(), "runs": set(), "decs": 0})
        S["runs"].add(r["no"])
        fd = [d for d in dr if "view" in d]
        # check fights count
        check.append((r["no"], a, len(r["fights"]), len({d["floor"] for d in fd})))
        for i, d in enumerate(fd):
            S["decs"] += 1
            S["fights"].add((r["no"], d["floor"])); S["turns"].add((r["no"], d["floor"], d["turn"]))
            line = d["line"]
            nxt = fd[i + 1] if i + 1 < len(fd) else None
            if nxt and nxt["floor"] == d["floor"] and nxt["turn"] == d["turn"]:
                k = nxt["view"]["cards_played_this_turn"] - d["view"]["cards_played_this_turn"]
                # take actions of line until k card plays counted
                take = []; n = 0
                for x in line:
                    if n >= k: break
                    take.append(x)
                    if isplay(x): n += 1
                line = take
            else:
                # up to first End
                if "End" in line: line = line[:line.index("End")]
            for x in line:
                kinds["card" if isplay(x) else re.split("[:@ ]",x)[0]] += 1
                if not isplay(x): continue
                S["plays"][name(x)] += 1
print("runs", runno)
for a, S in sorted(res.items()):
    t = sum(S["plays"].values())
    print("ASC", a, "runs", min(S["runs"]), max(S["runs"]), len(S["runs"]), "fights", len(S["fights"]), "turns", len(S["turns"]), "decs", S["decs"], "plays", t)
    for c, n in S["plays"].most_common(14):
        print("  %-15s %5d %.1f" % (c, n, 100 * n / t))
print(kinds.most_common(10))
bad = [c for c in check if c[2] != c[3]]
print("fight-count mismatches", bad[:20], len(bad))
