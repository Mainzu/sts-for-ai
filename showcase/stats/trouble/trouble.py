import sys, os, json, collections, statistics
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as R

runs = R.all_runs()
print("runs", len(runs))
# attach decisions per run: per folder, split by floor drop, map to runs-with-fights in that folder
byfolder = collections.defaultdict(list)
for i, r in enumerate(runs):
    r["num"] = i + 1
    byfolder[r["folder"]].append(r)
for folder, rs in byfolder.items():
    wf = [r for r in rs if r["fights"]]
    k, prev = -1, None
    path = os.path.join(R.RECORDS, folder, "decisions.jsonl")
    if not os.path.exists(path): continue
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            d = json.loads(line)
            if prev is None or d["floor"] < prev: k += 1
            prev = d["floor"]
            if k < len(wf) and "view" in d:
                wf[k].setdefault("dec", collections.defaultdict(list))[d["floor"]].append(d)

def asc(r): return "A20" if r.get("ascension") == 20 else "A0"
NAMES = {"JawWorm":"Jaw Worm","FuzzyLouseNormal":"Red Louse","FuzzyLouseDefensive":"Green Louse","SlaverBlue":"Blue Slaver","SlaverRed":"Red Slaver",
 "GremlinNob":"Gremlin Nob","TheGuardian":"The Guardian","Hexaghost":"Hexaghost","SlimeBoss":"Slime Boss","Sentry":"Sentry","Lagavulin":"Lagavulin",
 "Cultist":"Cultist","FungiBeast":"Fungi Beast","Looter":"Looter","AcidSlime_L":"Acid Slime (L)","AcidSlime_M":"Acid Slime (M)","AcidSlime_S":"Acid Slime (S)",
 "SpikeSlime_L":"Spike Slime (L)","SpikeSlime_M":"Spike Slime (M)","SpikeSlime_S":"Spike Slime (S)","GremlinFat":"Fat Gremlin","GremlinThief":"Sneaky Gremlin",
 "GremlinTsundere":"Shield Gremlin","GremlinWarrior":"Mad Gremlin","GremlinWizard":"Gremlin Wizard"}
def enc(f):
    ms = f["monsters"]
    if all(m.startswith("Gremlin") and m!="GremlinNob" for m in ms) and len(ms)>=3: return "Gremlin Gang"
    if all("Louse" in m for m in ms) and len(ms)>=2: return "%d lice" % len(ms)
    if all("Slime" in m for m in ms) and len(ms)>=3: return "Lots of slimes"
    if all(m=="Sentry" for m in ms): return "3 Sentries"
    c = collections.Counter(NAMES.get(m,m) for m in ms)
    return " + ".join((("%d %ss"%(n,k)) if n>1 else k) for k,n in sorted(c.items()))

fights = []
for r in runs:
    for f in r["fights"]:
        dl = r.get("dec", {}).get(f["floor"], [])
        mp, pp, slimed = set(), collections.Counter(), 0
        for d in dl:
            v = d["view"]
            for m in v["monsters"]:
                for p, a in (m.get("powers") or {}).items(): mp.add(p)
            for p in (v["player"].get("powers") or {}): pp[p] += 1
            s = sum(z.get("Slimed",0) for z in (v["hand"], v["draw"], v["discard"]))
            slimed = max(slimed, s)
        fights.append(dict(run=r["num"], a=asc(r), rules=r["run_rules"], floor=f["floor"], group=f["group"], enc=enc(f),
            lost=f["hp_start"]-f["hp_end"], won=f["won"], ho=f.get("handed_over"), mp=mp, pp=pp, slimed=slimed, ndec=len(dl), mons=f["monsters"]))
print("fights", len(fights), collections.Counter(x["a"] for x in fights), "with decisions", sum(1 for x in fights if x["ndec"]))
allmp = collections.Counter(p for x in fights for p in x["mp"]); print(allmp)
allpp = collections.Counter(p for x in fights for p in x["pp"]); print(allpp)

for A in ("A0","A20"):
    F = [x for x in fights if x["a"]==A]
    print("\n=====", A, "fights", len(F), "runs", len({x['run'] for x in F}))
    g = collections.defaultdict(list)
    for x in F: g[(x["group"], x["enc"])].append(x)
    rows = sorted(g.items(), key=lambda kv: -statistics.mean(y["lost"] for y in kv[1]))
    for (grp,e), xs in rows:
        print("%-8s %-40s n=%3d mean %5.1f median %4.1f max %3d lost %d" % (grp, e, len(xs), statistics.mean(y["lost"] for y in xs),
              statistics.median(y["lost"] for y in xs), max(y["lost"] for y in xs), sum(not y["won"] for y in xs)))
    print("-- deaths/losses:")
    for x in F:
        if not x["won"]: print("  run", x["run"], "rules", x["rules"], "floor", x["floor"], x["enc"], "lost", x["lost"], "ho", x["ho"])
    print("-- total HP lost by group:", {k: sum(x["lost"] for x in F if x["group"]==k) for k in ("hallway","elite","boss")})
    # biggest single fights
    for x in sorted(F, key=lambda x: -x["lost"])[:8]: print("  big", x["run"], x["floor"], x["enc"], x["lost"])
    # monster powers: hallway+elite+boss, fights w/ power
    Fd = [x for x in F if x["ndec"]]
    base = statistics.mean(x["lost"] for x in Fd)
    print("-- monster powers (fights with decisions %d, mean lost %.1f)" % (len(Fd), base))
    for p, n in collections.Counter(p for x in Fd for p in x["mp"]).most_common():
        xs = [x for x in Fd if p in x["mp"]]
        encs = collections.Counter(x["enc"] for x in xs).most_common(3)
        print("  %-22s n=%3d mean lost %5.1f  %s" % (p, n, statistics.mean(x["lost"] for x in xs), encs))
    print("-- player powers/debuffs")
    for p, n in collections.Counter(p for x in Fd for p in x["pp"]).most_common():
        xs = [x for x in Fd if p in x["pp"]]
        turns = sum(x["pp"][p] for x in xs)
        print("  %-22s fights=%3d decisions=%4d mean lost %5.1f" % (p, n, turns, statistics.mean(x["lost"] for x in xs)))
    xs = [x for x in Fd if x["slimed"]]
    if xs: print("  Slimed fights", len(xs), "mean lost %.1f max slimed %d" % (statistics.mean(x["lost"] for x in xs), max(x["slimed"] for x in xs)))
    tot = sum(x["ndec"] for x in Fd)
    print("  total decisions", tot)
