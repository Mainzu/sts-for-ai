import sys, collections
sys.path.insert(0, "scripts")
import real_game_report as R
runs = R.all_runs()
print("runs", len(runs))
rows=[]
for i, r in enumerate(runs, 1):
    deck = [c["id"].replace("_R","") for c in r["last"].get("deck", [])]
    boss = [f for f in r["fights"] if f.get("group") == "boss"]
    rows.append(dict(n=i, asc=R.asc(r), rules=r["run_rules"], guard=r["fight_guard"], floor=r["last"].get("floor"),
        deck=deck, boss=boss, won=any(f["won"] for f in boss), end=R.ending(r, i==len(runs)), bossname=r.get("act1_boss")))
a20=[x for x in rows if x["asc"]==20]
print("A20", len(a20), a20[0]["n"], a20[-1]["n"])
sizes=[len(x["deck"]) for x in a20]
print("deck sizes mean %.2f min %d max %d" % (sum(sizes)/len(sizes), min(sizes), max(sizes)))
print("bane all", all("AscendersBane" in x["deck"] or "Ascender's Bane" in x["deck"] for x in a20), collections.Counter(c for x in a20 for c in x["deck"] if "ane" in c))
for x in a20:
    if x["floor"]>=16 and not x["boss"] or len(x["boss"])>1: print("odd", x["n"], x["floor"], len(x["boss"]), x["end"])
reach=[x for x in a20 if x["boss"]]
reach16=[x for x in a20 if x["floor"]>=16]
print("reach(boss fight)", len(reach), "won", sum(x["won"] for x in reach), "reach16", len(reach16), sum(x["won"] for x in reach16))
def tab(S):
    cards=collections.Counter(c for x in S for c in set(x["deck"]))
    out=[]
    for c,k in cards.items():
        w=[x for x in S if c in x["deck"]]; wo=[x for x in S if c not in x["deck"]]
        out.append((c,len(w),sum(x["won"] for x in w),len(wo),sum(x["won"] for x in wo)))
    for o in sorted(out,key=lambda o:-o[1]):
        if o[1]>=5: print("%-20s %d/%d  without %d/%d  %.0f%%" % (o[0],o[2],o[1],o[4],o[3],100*o[2]/o[1]))
tab(reach16)
print(collections.Counter(x["bossname"] for x in reach16))
print(collections.Counter((x["rules"],x["guard"]) for x in reach16))
