import sys, os, json
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as R
REC = ROOT + "/results/real-game"
fights_all = []  # (runno, asc, rules, fight, score)
runno = 0
issues = []
for name in sorted(os.listdir(REC)):
    folder = os.path.join(REC, name)
    if not (os.path.isdir(folder) and name[:1].isdigit()): continue
    runs = [r for r in R.runs_of(folder) if r["fights"] or r["end"]]
    # decisions split by floor drop
    druns, prev = [], None
    p = os.path.join(folder, "decisions.jsonl")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                d = json.loads(line)
                if prev is None or d["floor"] < prev: druns.append({})
                prev = d["floor"]
                if "options" in d and "card_reward" not in d and d.get("turn") == 1:
                    druns[-1].setdefault(d["floor"], d)  # first turn-1 decision per floor
    wf = [r for r in runs if r["fights"]]
    if len(wf) != len(druns): issues.append((name, len(wf), len(druns)))
    for r in runs:
        runno += 1
        r["n"] = runno
    for i, r in enumerate(wf):
        dm = druns[i] if i < len(druns) else {}
        for fi in r["fights"]:
            d = dm.get(fi["floor"])
            sc = (d["two"][d["pick"]] if d.get("two") else ("ONE", d["one"][d["pick"]] if d.get("one") else None)) if d else None
            if isinstance(sc, tuple): issues.append(("notwo", name, fi["floor"], sc[1])); sc = sc[1]
            fights_all.append((r["n"], r.get("ascension"), r["run_rules"], fi, sc, bool(d and d.get("two"))))
print("runs", runno, "issues", issues)
def bucket(s, edges):
    for lo, hi in edges:
        if lo <= s < hi: return (lo, hi)
for asc, edges in ((20, [(-9,1.0),(1.0,1.5),(1.5,1.7),(1.7,1.8),(1.8,1.9),(1.9,9)]), (0, [(-9,1.5),(1.5,1.8),(1.8,9)])):
    fs = [x for x in fights_all if x[1] == asc]
    ho = [x for x in fs if x[3].get("handed_over")]
    pl = [x for x in fs if not x[3].get("handed_over")]
    nos = [x for x in pl if x[4] is None]
    pl2 = [x for x in pl if x[4] is not None]
    print("A%d runs %s-%s fights %d handed %d played %d noscore %d lost %d" % (asc, min(x[0] for x in fs), max(x[0] for x in fs), len(fs), len(ho), len(pl), len(nos), sum(not x[3]["won"] for x in pl)))
    for e in edges:
        b = [x for x in pl2 if bucket(x[4], [e])]
        print(" ", e, sum(x[3]["won"] for x in b), "of", len(b))
    hi = [x for x in pl2 if x[4] >= 1.8]
    print("  >=1.8:", sum(x[3]["won"] for x in hi), "of", len(hi), "lost:", [(x[0], x[3]["floor"], x[3]["monsters"], round(x[4],3)) for x in hi if not x[3]["won"]])
    w = [x for x in pl2 if x[3]["won"]]
    exp = sum((2 - x[4]) * 100 for x in w) / len(w)
    act = sum(x[3]["hp_start"] - x[3]["hp_end"] for x in w) / len(w)
    act2 = sum(x[3]["hp_start"] - x[3]["hp_after"] for x in w) / len(w)
    print("  won n=%d expected loss %.2f actual %.2f (after heals %.2f)" % (len(w), exp, act, act2))
    exps = sum(min(200,(2 - x[4]) * 100) for x in w if x[4] > 1.0) / len([x for x in w if x[4] > 1.0])
    print("  won score>1 exp %.2f" % exps)
print("---- two-only subset")
for asc, edges in ((20, [(-9,1.0),(1.0,1.5),(1.5,1.7),(1.7,1.8),(1.8,1.9),(1.9,9)]), (0, [(-9,1.5),(1.5,1.8),(1.8,9)])):
    pass
for asc, edges in ((20, [(-9,1.0),(1.0,1.5),(1.5,1.7),(1.7,1.8),(1.8,1.9),(1.9,9)]), (0, [(-9,1.5),(1.5,1.8),(1.8,9)])):
    fs = [x for x in fights_all if x[1] == asc]
    print("A%d handed floors" % asc, sorted((x[3]["floor"], x[0]) for x in fs if x[3].get("handed_over")))
    pl2 = [x for x in fs if not x[3].get("handed_over") and x[5]]
    print(" two-only n", len(pl2), "lost", sum(not x[3]["won"] for x in pl2))
    for e in edges:
        b = [x for x in pl2 if bucket(x[4], [e])]
        print(" ", e, sum(x[3]["won"] for x in b), "of", len(b))
    w = [x for x in pl2 if x[3]["won"]]
    print("  won n=%d exp %.2f act %.2f after %.2f" % (len(w), sum((2-x[4])*100 for x in w)/len(w), sum(x[3]["hp_start"]-x[3]["hp_end"] for x in w)/len(w), sum(x[3]["hp_start"]-x[3]["hp_after"] for x in w)/len(w)))
    nt = [x for x in fs if not x[3].get("handed_over") and not x[5]]
    print("  no-two fights: n", len(nt), "lost", sum(not x[3]["won"] for x in nt), "groups", {g: sum(x[3]["group"]==g for x in nt) for g in ("hallway","elite","boss")})
    print("  floors>17 played", sum(x[3]["floor"]>17 for x in fs if not x[3].get("handed_over")))
print("----- score>=2.0 check")
for asc in (20, 0):
    pl = [x for x in fights_all if x[1]==asc and not x[3].get("handed_over")]
    print(asc, "score>=2.0:", sum(x[4]>=2.0 for x in pl), "won", sum(x[4]>=2.0 and x[3]["won"] for x in pl))
    w = [x for x in pl if x[3]["won"] and x[4] < 2.0]
    print("  won <2.0 n=%d exp %.2f act %.2f after %.2f" % (len(w), sum((2-x[4])*100 for x in w)/len(w), sum(x[3]["hp_start"]-x[3]["hp_end"] for x in w)/len(w), sum(x[3]["hp_start"]-x[3]["hp_after"] for x in w)/len(w)))
    print("  >17:", [(x[0], x[3]["floor"], x[3]["monsters"]) for x in pl if x[3]["floor"]>16])
print("----- final (act 1 floors<=16, floored after-heal loss)")
for asc, edges in ((20, [(-9,1.0),(1.0,1.5),(1.5,1.7),(1.7,1.8),(1.8,1.9),(1.9,9)]), (0, [(-9,1.5),(1.5,1.8),(1.8,9)])):
    pl = [x for x in fights_all if x[1]==asc and not x[3].get("handed_over") and x[3]["floor"] <= 16]
    print(asc, "n", len(pl), "lost", sum(not x[3]["won"] for x in pl), "one-turn fallback", sum(not x[5] for x in pl))
    for e in edges:
        b = [x for x in pl if bucket(x[4], [e])]
        print(" ", e, sum(x[3]["won"] for x in b), "of", len(b), "%.1f" % (100*sum(x[3]["won"] for x in b)/len(b)))
    hi=[x for x in pl if x[4]>=1.8]; print("  >=1.8", sum(x[3]["won"] for x in hi), len(hi))
    w = [x for x in pl if x[3]["won"]]
    print("  wins n=%d exp %.2f act floored-after %.2f in-fight %.2f" % (len(w), sum((2-x[4])*100 for x in w)/len(w), sum(max(0,x[3]["hp_start"]-x[3]["hp_after"]) for x in w)/len(w), sum(x[3]["hp_start"]-x[3]["hp_end"] for x in w)/len(w)))
