import sys, os, json
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as R
runs = R.all_runs()
print("runs", len(runs))
# decisions split per folder
dec_runs = {}
for name in sorted(os.listdir(R.RECORDS)):
    folder = os.path.join(R.RECORDS, name)
    if not (os.path.isdir(folder) and name[:1].isdigit()): continue
    out, prev = [], None
    p = os.path.join(folder, "decisions.jsonl")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                d = json.loads(line)
                fl = d.get("floor")
                if prev is None or fl < prev: out.append([])
                prev = fl
                out[-1].append(d)
    dec_runs[name] = out
byfolder = {}
for i, r in enumerate(runs, 1):
    r["n"] = i
    byfolder.setdefault(r["folder"], []).append(r)
rows = []
for name, rs in byfolder.items():
    wf = [r for r in rs if r["fights"]]
    drs = dec_runs.get(name, [])
    if len(drs) != len(wf): print("MISMATCH count", name, len(drs), len(wf), [r["n"] for r in rs])
    for r, dr in zip(wf, drs):
        ffl = {f["floor"] for f in r["fights"]}
        dfl = {d["floor"] for d in dr if "options" in d and "card_reward" not in d}
        if not dfl <= ffl: print("floor mismatch run", r["n"], sorted(dfl - ffl))
        for f in r["fights"]:
            fd = [d for d in dr if d.get("floor") == f["floor"] and "card_reward" not in d and "two" in d]
            s = None; smax = None; t1 = None; mon = None
            if fd:
                d0 = fd[0]; t1 = d0.get("turn")
                s = d0["two"][d0["pick"]] if d0.get("two") else None
                smax = max(d0["two"]) if d0.get("two") else None
                mon = [(m["name"], m.get("hp")) for m in d0["view"]["monsters"]]
            rows.append(dict(n=r["n"], asc=R.asc(r), rules=r["run_rules"], guard=r["fight_guard"], floor=f["floor"],
                             group=f["group"], monsters=f["monsters"], won=f["won"], ho=f["handed_over"], hp=f["hp_start"],
                             s=s, smax=smax, t1=t1, mon=mon, ndec=len(fd)))
json.dump(rows, open(os.path.dirname(os.path.abspath(__file__)) + "/rows.json", "w"))
for a in (0, 20):
    L = [x for x in rows if x["asc"] == a and not x["won"] and x["ho"] is None and x["floor"] <= 17]
    Lall = [x for x in rows if x["asc"] == a and not x["won"]]
    print("asc", a, "losses played out", len(L), "all losses", len(Lall), "handed", sum(1 for x in Lall if x["ho"] is not None))
    for x in sorted(L, key=lambda x: -(x["s"] or -9)):
        print(x["n"], x["floor"], x["monsters"], x["hp"], x["s"], x["smax"], x["t1"], x["rules"], x["guard"], x["mon"])
lag = [x for x in rows if x["asc"] == 20 and "Lagavulin" in x["monsters"]]
print("Lag fights", len(lag))
for x in lag: print(x["n"], x["floor"], x["won"], x["ho"], x["s"], x["hp"])
