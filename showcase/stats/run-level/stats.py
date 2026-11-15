"""Run-level fun stats from runs.json (made by extract.py) plus fights from
real_game_report.all_runs(). Prints each stat's rows."""
import json, os, sys, collections as C, statistics as S
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as R
HERE = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(os.path.join(HERE, "runs.json")))
F = {i + 1: r["fights"] for i, r in enumerate(R.all_runs())}
def tag(m): return "A%d r%d%s" % (m["asc"], m["rules"], " g1" if m["guard"] else "")
A0 = [m for m in M if m["asc"] == 0]; A20 = [m for m in M if m["asc"] == 20]
BOSS = {"Hexaghost", "TheGuardian", "SlimeBoss"}; ELITE = {"Lagavulin", "GremlinNob", "Sentry"}

print("## 1 endings by setting")
groups = [("A0 r1", lambda m: m["asc"] == 0), ("A20 r1", lambda m: tag(m) == "A20 r1"), ("A20 r2", lambda m: tag(m) == "A20 r2"),
          ("A20 r3-4", lambda m: tag(m) in ("A20 r3", "A20 r4")), ("A20 r5 (+g1)", lambda m: m["asc"] == 20 and m["rules"] == 5)]
for name, f in groups:
    g = [m for m in M if f(m)]
    beat = sum(m["boss_beaten"] for m in g)
    at_boss = sum(m["end"] == "died" and m["floor"] == 16 for m in g)
    early = sum(m["end"] == "died" and m["floor"] < 16 for m in g)
    act2 = sum(m["end"] == "died" and m["floor"] > 17 for m in g)
    print(name, "runs", len(g), "boss beaten", beat, "died at Act1 boss", at_boss, "died before boss", early,
          "died in Act 2", act2, "left", sum(m["end"] == "left" for m in g), "runs", [m["n"] for m in g][0], [m["n"] for m in g][-1])

print("## 2 gold never spent")
for name, g in (("A0", A0), ("A20", A20)):
    gold = [m["gold"] for m in g]
    print(name, "n", len(g), "median end gold", S.median(gold), "max", max(gold), "run", max(g, key=lambda m: m["gold"])["n"],
          "total", sum(gold), "shops walked past", sum(len(m.get("shops", [])) for m in g), "runs with a shop", sum(bool(m.get("shops")) for m in g))
    for lo, hi in ((0, 150), (150, 250), (250, 350), (350, 450), (450, 700)):
        print("   gold %d-%d: %d" % (lo, hi - 1, sum(lo <= x < hi for x in gold)))

print("## 3 where gold went: events")
import re
for name, g in (("A0", A0), ("A20", A20)):
    sp = C.Counter()
    for m in g:
        for e in m.get("events", []):
            for s in e["steps"]:
                t = s["chosen"] or ""
                if "Lose ALL" in t: sp[e["name"]] += s["gold"]
                else:
                    mm = re.search(r"(\d+) Gold", t)
                    if mm and ("Lose" in t or "Gold:" in t or "Buy" in t): sp[e["name"]] += int(mm.group(1))
    print(name, dict(sp), "total", sum(sp.values()), "gold carried at end", sum(m["gold"] for m in g))

print("## 4 potions at death")
for name, g in (("A20 deaths", [m for m in A20 if m["end"] == "died"]), ("A0 deaths in Act 1 (engine)", [m for m in A0 if m["end"] == "died" and m["floor"] <= 17]),
                ("A0 deaths in Act 2 (fallback rule)", [m for m in A0 if m["end"] == "died" and m["floor"] > 17]),
                ("A20 stopped after boss", [m for m in A20 if m["end"] == "stopped"])):
    print(name, "n", len(g), "with >=1 potion unused", sum(bool(m["potions_end"]) for m in g), "potions", sum(len(m["potions_end"]) for m in g))
pu = [p for m in A20 for p in m.get("potions_used", [])]
kind = C.Counter("boss" if set(p["monsters"]) & BOSS else "elite" if set(p["monsters"]) & ELITE else "hallway" for p in pu)
print("A20 potions drunk", len(pu), kind)
nf = C.Counter(f["group"] for m in A20 for f in F[m["n"]])
print("A20 fights by group", nf)
print("A20 most drunk", C.Counter(p["name"] for p in pu).most_common(10))

print("## 5 rest vs smith")
for name, f in (("A0 r1", lambda m: m["asc"] == 0), ("A20 r1", lambda m: tag(m) == "A20 r1"), ("A20 r2-4", lambda m: m["asc"] == 20 and 2 <= m["rules"] <= 4),
                ("A20 r5", lambda m: m["asc"] == 20 and m["rules"] == 5)):
    rs = [r for m in M if f(m) for r in m.get("rests", [])]
    sm = [r for r in rs if r["pick"] == "smith"]; re_ = [r for r in rs if r["pick"] == "rest"]
    print(name, "campfires", len(rs), "smith", len(sm), "rest", len(re_), "median HP%% at rest %.0f" % (100 * S.median(r["hp"] / r["mx"] for r in re_)) if re_ else "",
          "median HP%% at smith %.0f" % (100 * S.median(r["hp"] / r["mx"] for r in sm)) if sm else "", C.Counter(r["pick"] for r in rs))

print("## 6 events")
for name, g in (("A0", A0), ("A20", A20)):
    ch = C.Counter()
    for m in g:
        for e in m.get("events", []):
            if e["name"] != "Neow" and e["steps"]:
                ch[(e["name"], e["steps"][0]["chosen"])] += 1
    print(name, "events met", sum(1 for m in g for e in m.get("events", []) if e["name"] != "Neow"), ch.most_common(14))
    for m in g:
        for e in m.get("events", []):
            if e["name"] == "Mushrooms":
                ff = [f for f in F[m["n"]] if f["floor"] == e["floor"]]
                print("   mushrooms run", m["n"], tag(m), "floor", e["floor"], [(f["monsters"], f["hp_start"], f["hp_end"], f["won"]) for f in ff])
            if e["name"] == "Golden Idol":
                print("   idol run", m["n"], tag(m), e["steps"][0]["chosen"])
            if e["name"] == "World of Goop":
                print("   goop run", m["n"], tag(m), e["steps"][0]["chosen"], "offered", e["steps"][0]["offered"])

print("## 7 Neow and boss relics")
for name, g in (("A0", A0), ("A20", A20)):
    neow = C.Counter()
    for m in g:
        for e in m.get("events", []):
            if e["name"] == "Neow":
                real = [s for s in e["steps"] if s["chosen"] not in ("[Talk]", "[Leave]")]
                if real: neow[real[0]["chosen"]] += 1
    print(name, "Neow", neow.most_common(), sum(neow.values()))
    br = [b for m in g for b in m.get("boss_relic", [])]
    print(name, "boss relic picks", len(br), C.Counter(b["pick"] for b in br).most_common(),
          "Runic Dome offered", sum("Runic Dome" in b["offered"] for b in br), "taken", sum(b["pick"] == "Runic Dome" for b in br))
    print(name, "relics from rewards", C.Counter(r["name"] for m in g for r in m.get("relics_got", [])).most_common(8),
          "median relics at end", S.median(len(m["relics"]) for m in g), "max", max(len(m["relics"]) for m in g))

print("## 8 Neow: Max HP offered vs taken")
for name, g in (("A0", A0), ("A20", A20)):
    off = took = 0
    for m in g:
        for e in m.get("events", []):
            if e["name"] == "Neow":
                real = [s for s in e["steps"] if s["chosen"] not in ("[Talk]", "[Leave]")]
                if real:
                    o = any("Max HP" in (t or "") and "Lose" not in (t or "") for t in real[0]["offered"])
                    off += o; took += o and "Max HP" in real[0]["chosen"]
    print(name, "Max HP offered", off, "taken", took)
print("## 9 potions per fight by group, A20 (all rule versions pooled)")
for k in ("hallway", "elite", "boss"):
    print(k, kind[k], nf[k], round(kind[k] / nf[k], 2))
