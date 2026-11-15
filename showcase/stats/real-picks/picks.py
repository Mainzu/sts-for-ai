"""Real-game card-reward picks, split by ascension. Read-only."""
import sys, os, json
from collections import Counter, defaultdict
R = "."
sys.path.insert(0, R + "/scripts")
import real_game_report as g

def nm(x): return None if x is None else x.replace("gen:", "")

runs = g.all_runs()  # sorted per folder; number globally by t0
runs.sort(key=lambda r: r["t0"])
for i, r in enumerate(runs, 1): r["n"] = i; r["rewards"] = []
byfolder = defaultdict(list)
for r in runs: byfolder[r["folder"]].append(r)
for f, rs in byfolder.items():
    rs.sort(key=lambda r: r["t0"])
    k = -1; prev = None
    for line in open(os.path.join(g.RECORDS, f, "decisions.jsonl"), encoding="utf-8"):
        d = json.loads(line)
        if prev is None or d["floor"] < prev: k += 1
        prev = d["floor"]
        if "card_reward" in d: rs[k]["rewards"].append(d)

# rarity / type from decks seen in final states
rar, typ = {}, {}
for r in runs:
    for c in r["last"].get("deck", []):
        rar[c["name"].rstrip("+")] = c["rarity"]; typ[c["name"].rstrip("+")] = c["type"]
# also rarity from card reward screens across states (stream)
for f in byfolder:
    with open(os.path.join(g.RECORDS, f, "states.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            if '"CARD_REWARD"' not in line: continue
            gs = json.loads(line)["msg"].get("game_state", {})
            for c in gs.get("screen_state", {}).get("cards", []):
                rar[c["name"].rstrip("+")] = c["rarity"]; typ[c["name"].rstrip("+")] = c["type"]

out = {}
for A in (0, 20):
    rs = [r for r in runs if (r.get("ascension") or 0) == A]
    offered, taken, score_adv = Counter(), Counter(), defaultdict(list)
    nrew = nskip = 0; rar_off, rar_take = Counter(), Counter()
    skipmargin = []
    for r in rs:
        for d in r["rewards"]:
            nrew += 1
            pick = nm(d["pick"]); opts = [nm(o) for o in d["options"]]; sc = d["scores"]
            skip_score = sc[opts.index(None)] if None in opts else None
            if pick is None: nskip += 1
            for o, s in zip(opts, sc):
                if o is None: continue
                base = o.rstrip("+")
                offered[base] += 1; rar_off[rar.get(base, "?")] += 1
                if skip_score is not None: score_adv[base].append(s - skip_score)
            if pick is not None:
                taken[pick.rstrip("+")] += 1; rar_take[rar.get(pick.rstrip("+"), "?")] += 1
    print("=== A%d: runs %d, rewards %d, skipped %d (%.0f%%)" % (A, len(rs), nrew, nskip, 100*nskip/max(nrew,1)))
    print("runs", rs[0]["n"], "-", rs[-1]["n"], "settings", Counter(g.setting_tag(r) for r in rs))
    print("-- pick rate, offered>=4")
    rows = sorted(((taken[c]/offered[c], offered[c], taken[c], c) for c in offered if offered[c] >= 4), reverse=True)
    for x in rows: print("  %-20s %d/%d  %.0f%%  %s  meanadv %+.3f" % (x[3], x[2], x[1], 100*x[0], rar.get(x[3]), sum(score_adv[x[3]])/len(score_adv[x[3]])))
    print("-- rarity offered/taken", dict(rar_off), dict(rar_take))
    for k in rar_off: print("  %s %d/%d %.0f%%" % (k, rar_take[k], rar_off[k], 100*rar_take[k]/rar_off[k]))
    print("-- offered<4 but taken", [(c, taken[c], offered[c]) for c in offered if offered[c] < 4 and taken[c]])
    # final decks
    decksize = []; addcnt = Counter(); nr = 0
    for r in rs:
        deck = r["last"].get("deck", [])
        if not deck: continue
        nr += 1; decksize.append(len(deck))
        for c in deck:
            if c["rarity"] not in ("BASIC",): addcnt[c["name"].rstrip("+")] += 0
        names = Counter(c["name"].rstrip("+") for c in deck)
        for c, k in names.items(): addcnt[c] += 1  # runs containing
    print("-- final decks: runs %d, mean size %.1f, min %d max %d" % (nr, sum(decksize)/nr, min(decksize), max(decksize)))
    print("  runs whose final deck holds card:", addcnt.most_common(25))
    upg = [sum(c.get("upgrades",0)>0 for c in r["last"].get("deck",[])) for r in rs if r["last"].get("deck")]
    print("  upgraded cards per final deck mean %.1f" % (sum(upg)/len(upg)))
    fl = [r["last"].get("floor") for r in rs]
    # deck size vs floor reached
    print("  final floors", Counter(fl).most_common())
    # skip rate by floor band / act
    band = defaultdict(lambda: [0,0])
    for r in rs:
        for d in r["rewards"]:
            b = "1-6" if d["floor"]<=6 else "7-12" if d["floor"]<=12 else "13-17" if d["floor"]<=17 else "18+"
            band[b][0]+=1; band[b][1]+= d["pick"] is None
    print("-- skip by floor band", {k:(v[1],v[0]) for k,v in sorted(band.items())})
    # per setting skip rate
    st = defaultdict(lambda:[0,0])
    for r in rs:
        for d in r["rewards"]:
            st[g.setting_tag(r)][0]+=1; st[g.setting_tag(r)][1]+= d["pick"] is None
    print("-- skip by setting", dict(st))
    # think time
    secs=[d.get("seconds",0) for r in rs for d in r["rewards"]]
    print("-- reward seconds mean %.2f max %.2f" % (sum(secs)/len(secs), max(secs)))
