import sys, os, json, statistics as st
sys.path.insert(0, "scripts")
import real_game_report as R
REC = "results/real-game"
runs = R.all_runs(REC)
print("runs", len(runs))
num = {(r["folder"], r["seed"]): (i+1, r) for i, r in enumerate(runs)}
camps = {}  # (folder,seed,floor) -> dict
for name in sorted(os.listdir(REC)):
    p = os.path.join(REC, name, "states.jsonl")
    if not os.path.isfile(p): continue
    pend = {}
    with open(p, encoding="utf-8") as f:
        for line in f:
            if '"REST"' not in line and not pend: continue
            gs = json.loads(line)["msg"].get("game_state")
            if not gs: continue
            key = (name, gs.get("seed"), gs.get("floor"))
            up = sum(c.get("upgrades",0) for c in gs.get("deck",[]))
            if gs.get("screen_type") == "REST" and not gs["screen_state"].get("has_rested"):
                if key not in camps:
                    camps[key] = dict(hp=gs["current_hp"], mx=gs["max_hp"], up=up, choice=None, opts=gs["screen_state"]["rest_options"])
                pend[key] = camps[key]
            elif key in pend and pend[key]["choice"] is None and (gs.get("screen_type") != "REST" or gs["screen_state"].get("has_rested")):
                c = pend.pop(key)
                if gs["current_hp"] > c["hp"]: c["choice"] = "rest"
                elif up > c["up"]: c["choice"] = "smith"
                else: c["choice"] = "other:%s/%s" % (gs.get("screen_type"), gs["current_hp"])
groups = {}
for (fo, seed, fl), c in camps.items():
    if (fo, seed) not in num: print("unmatched", fo, seed, fl); continue
    n, r = num[(fo, seed)]
    a, rr = r.get("ascension"), r["run_rules"]
    g = "A0 r1" if a == 0 else ("A20 r1" if rr == 1 else ("A20 r2-4" if rr in (2,3,4) else "A20 r%d" % rr))
    groups.setdefault(g, []).append((n, fl, c))
for g in sorted(groups):
    L = groups[g]
    ns = sorted({x[0] for x in L})
    ch = [c["choice"] for _,_,c in L]
    sm = [c["hp"]/c["mx"] for _,_,c in L if c["choice"]=="smith"]
    rs = [c["hp"]/c["mx"] for _,_,c in L if c["choice"]=="rest"]
    print(g, "runs", ns[0], "-", ns[-1], "n", len(L), {k: ch.count(k) for k in set(ch)},
          "smith%% %.0f" % (100*len(sm)/len(L)), "medHP smith %.0f rest %.0f" % (100*st.median(sm) if sm else -1, 100*st.median(rs) if rs else -1))
    # rule check
    bad = [(n, fl, round(c["hp"]/c["mx"],2), c["choice"]) for n, fl, c in L if c["choice"] in ("rest","smith") and ((c["hp"]/c["mx"] < (0.75 if fl==15 else 0.6)) != (c["choice"]=="rest"))]
    print("  rule mismatches", bad)
    print("  others", [(n, fl, c["choice"], c["opts"]) for n, fl, c in L if c["choice"] not in ("rest","smith")])
print("----")
for g in sorted(groups):
    L = [(n, fl, c, "smith" if c["choice"].startswith("other:GRID") else c["choice"]) for n, fl, c in groups[g]]
    sm = [c["hp"]/c["mx"] for _,_,c,k in L if k=="smith"]; rs = [c["hp"]/c["mx"] for _,_,c,k in L if k=="rest"]
    print(g, len(L), "smith", len(sm), "%.1f%%" % (100*len(sm)/len(L)), "med smith %.0f rest %.0f" % (100*st.median(sm), 100*st.median(rs)), "runs", len({x[0] for x in L}))
    bad = [(n, fl, round(c["hp"]/c["mx"],2), k) for n, fl, c, k in L if (c["hp"]/c["mx"] < (0.75 if fl==15 else 0.6)) != (k=="rest")]
    print("  rule mismatches", bad)
