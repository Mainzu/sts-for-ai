import sys, collections, statistics
sys.argv = ["x"]
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    exec(open("trouble.py").read().split("for A in (")[0])
# status cards: patch by re-reading decisions per fight
for r in runs:
    for f in r["fights"]:
        pass
def status_counts(r, floor):
    c = collections.Counter()
    for d in r.get("dec", {}).get(floor, []):
        v = d["view"]
        for s in ("Slimed","Burn","Dazed","Wound","Burn+"):
            n = sum(z.get(s,0) for z in (v["hand"], v["draw"], v["discard"]))
            c[s] = max(c[s], n)
    return c
idx = {(r["num"], f["floor"]): status_counts(r, f["floor"]) for r in runs for f in r["fights"]}
for x in fights: x["st"] = idx[(x["run"], x["floor"])]
print("max floor A20", max(x["floor"] for x in fights if x["a"]=="A20"))
for A in ("A0","A20"):
    F = [x for x in fights if x["a"]==A and x["floor"]<=16 and x["ndec"]]
    print("\n==", A, "Act1 fights w/ decisions", len(F), "runs", len({x['run'] for x in F}), "mean lost %.1f" % statistics.mean(x["lost"] for x in F))
    # bosses
    for b in ("Hexaghost","The Guardian","Slime Boss"):
        xs = [x for x in fights if x["a"]==A and x["enc"]==b]
        print("  boss", b, "n", len(xs), "won", sum(x["won"] for x in xs), "mean lost %.1f" % statistics.mean(x["lost"] for x in xs) if xs else "")
    for p in ("Weak","Frail","Vulnerable","Entangled"):
        xs = [x for x in F if p in x["pp"]]; ys = [x for x in F if p not in x["pp"]]
        print("  %-10s fights %3d with %.1f without %.1f decisions %d  src %s" % (p, len(xs), statistics.mean(x["lost"] for x in xs), statistics.mean(x["lost"] for x in ys), sum(x["pp"][p] for x in xs), collections.Counter(x["enc"] for x in xs).most_common(4)))
    for s in ("Slimed","Burn","Dazed","Wound"):
        xs = [x for x in F if x["st"][s]]; ys = [x for x in F if not x["st"][s]]
        if xs: print("  %-10s fights %3d with %.1f without %.1f max %d src %s" % (s, len(xs), statistics.mean(x["lost"] for x in xs), statistics.mean(x["lost"] for x in ys), max(x["st"][s] for x in xs), collections.Counter(x["enc"] for x in xs).most_common(3)))
    hx = [x for x in F if x["enc"]=="Hexaghost"]
    if hx: print("  Hexaghost burns per fight", [x["st"]["Burn"]+x["st"]["Burn+"] for x in hx])
    for p in ("SharpHide","Artifact","Metallicize","Enrage","Angry","Strength","CurlUp","SporeCloud","Ritual"):
        xs = [x for x in F if p in x["mp"]]
        if xs: print("  mp %-12s n %3d mean %.1f won %d" % (p, len(xs), statistics.mean(x["lost"] for x in xs), sum(x["won"] for x in xs)))
    # A20 death encounters
    d = collections.Counter(x["enc"] for x in fights if x["a"]==A and not x["won"] and not x["ho"])
    reach = collections.Counter(x["enc"] for x in fights if x["a"]==A)
    print("  deaths", sum(d.values()), [(k, v, reach[k]) for k, v in d.most_common()])
    print("  runs", len({x["run"] for x in fights if x["a"]==A}))
