"""Pull the chart data for the showcase site out of finished result files.

Reads only files under results/ (no engine, no search), writes showcase/data.js
(window.SHOWCASE = {...}). Every chart built from it shows one setting, read
from one set of files; the page's prose quotes its numbers by hand.

    python -I showcase/extract.py            # rewrite showcase/data.js
    python -I showcase/extract.py --check    # print the numbers the page quotes

Clean-up: data.js is the only file it writes; rerun to regenerate, or delete
it (the page then has no charts).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(ROOT, "results", "gauntlet")

HEUR = "heuristic-starter-simboss.json"                     # one turn, heuristic
NET1 = "net1029-hpb0.01-starter-simboss.json"               # one turn, 10-29 net
PROD = "net1029-hpe0.01-two-line-step-starter-simboss-a.json"   # product, 0-499
PROD_B = "net1029-hpe0.01-two-line-step-starter-simboss-500.json"  # product, 500-999
PROD_NEW = "net1029-hpe0.01-tsl1-lcb1-two-line-step-starter-simboss.json"  # product since 11-13, 0-499
REPLAY = os.path.join(ROOT, "results", "boss_replay",
    "net1029-hpe0.01-two-starter-simboss-2026-10-29-seed-check-r2-s1-1a789b2-hpb0.01-12a77a-55cb.json")
ELITESKIP = "net1029-hpb0.01-starter-simboss-eliteskip.json"
RESTSIM = "net1029-hpb0.01-starter-simboss-restsim-f64-m2.json"
BOSSES = ["slime_boss", "the_guardian", "hexaghost"]


def load(name):
    with open(os.path.join(G, name)) as f:
        return json.load(f)


def by_i(d):
    return {s["i"]: s for s in d["sequences"]}


def death(seq):
    """(floor index 1-11, encounter) of the lost fight, or None if cleared."""
    for k, fl in enumerate(seq["floors"]):
        if not fl["won"]:
            return k + 1, fl["encounter"]
    return None


def boss_floor(seq):
    fl = seq["floors"]
    return fl[10] if len(fl) == 11 else None


def summary(d):
    seqs = d["sequences"]
    n = len(seqs)
    deaths = [0] * 11
    hp_start = [[] for _ in range(11)]
    lost_by_floor = [[] for _ in range(11)]
    boss = {b: [0, 0] for b in BOSSES}   # arrivals, wins
    arrival_hp = []
    for s in seqs:
        dth = death(s)
        if dth:
            deaths[dth[0] - 1] += 1
        for k, fl in enumerate(s["floors"]):
            hp_start[k].append(fl["hp_start"])
            if fl["won"]:
                lost_by_floor[k].append(fl["hp_start"] - fl["hp_end"])
        bf = boss_floor(s)
        if bf:
            b = bf["encounter"]
            boss.setdefault(b, [0, 0])
            boss[b][0] += 1
            boss[b][1] += bf["won"]
            arrival_hp.append(bf["hp_start"])
    mean = lambda xs: round(sum(xs) / len(xs), 2) if xs else None
    return {
        "n": n,
        "clears": sum(s["cleared"] for s in seqs),
        "deaths_by_floor": deaths,
        "mean_hp_start": [mean(x) for x in hp_start],
        "mean_hp_lost_won": [mean(x) for x in lost_by_floor],
        "boss": boss,
        "boss_arrivals": len(arrival_hp),
        "mean_boss_arrival_hp": mean(arrival_hp),
    }


def boss_curve():
    with open(REPLAY) as f:
        d = json.load(f)
    hps = d["settings"]["hp"]
    out = {"settings": d["settings"], "decks": len(d["rows"]), "hp": hps, "curves": {}}
    pooled = {h: [0, 0] for h in hps}
    per = {}
    for r in d["rows"]:
        b = r["boss"]
        per.setdefault(b, {h: [0, 0] for h in hps})
        for h in hps:
            w = r["won"][str(h)]
            per[b][h][0] += sum(w)
            per[b][h][1] += len(w)
            pooled[h][0] += sum(w)
            pooled[h][1] += len(w)
    for b, m in per.items():
        out["curves"][b] = [round(m[h][0] / m[h][1], 3) for h in hps]
        out.setdefault("fights", {})[b] = m[hps[0]][1] // 4
    out["curves"]["pooled"] = [round(pooled[h][0] / pooled[h][1], 3) for h in hps]
    out["replayed_fights"] = sum(pooled[h][1] for h in hps)
    return out


def sequences():
    """Per sequence 0-499: who cleared (heuristic, one-turn net, product),
    the product's death floor, boss and boss-arrival HP, its picks, and
    whether the 11-13 product (@tsl1@lcb1) cleared."""
    h, n, p, q = by_i(load(HEUR)), by_i(load(NET1)), by_i(load(PROD)), by_i(load(PROD_NEW))
    rows = []
    for i in range(500):
        sp = p[i]
        dth = death(sp)
        bf = boss_floor(sp)
        picks = [fl.get("took") for fl in sp["floors"] if fl.get("took")]
        rows.append([
            i, int(h[i]["cleared"]), int(n[i]["cleared"]), int(sp["cleared"]),
            dth[0] if dth else 0, dth[1] if dth else "",
            bf["encounter"] if bf else "", bf["hp_start"] if bf else 0,
            "|".join(picks), int(q[i]["cleared"]),
        ])
    return rows


def paired_clears(a, b):
    da, db = by_i(load(a)), by_i(load(b))
    common = sorted(set(da) & set(db))
    return {"n": len(common),
            "a": sum(da[i]["cleared"] for i in common),
            "b": sum(db[i]["cleared"] for i in common),
            "a_end_hp": round(sum(end_hp(da[i]) for i in common) / len(common), 2),
            "b_end_hp": round(sum(end_hp(db[i]) for i in common) / len(common), 2)}


def end_hp(seq):
    return seq["floors"][-1]["hp_end"] if seq["cleared"] else 0


def real_game():
    """Each results/real-game/<stamp>/ folder: its fights (no states or
    decision dumps), its finished-run lines and its last status line."""
    base = os.path.join(ROOT, "results", "real-game")
    out = []
    if not os.path.isdir(base):
        return out
    keep = ("floor", "group", "monsters", "hp_start", "hp_end", "won", "handed_over",
            "left_out", "decisions", "predicted", "matched")
    # The bridge's own reader splits a folder into runs (a new run where the
    # floor drops back) and gives older rows their pre-heal hp_end from
    # states.jsonl; hp_after is the HP once Burning Blood has healed.
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from real_game_report import runs_of
    keep = keep + ("hp_after",)
    folders = []
    for stamp in sorted(os.listdir(base)):
        d = os.path.join(base, stamp)
        if not os.path.isdir(d) or not stamp[:1].isdigit():
            continue
        rows = lambda name: [json.loads(l) for l in open(os.path.join(d, name), encoding="utf-8")
                             if l.strip()] if os.path.exists(os.path.join(d, name)) else []
        groups = []
        for r in runs_of(d):
            if not r["fights"]:
                continue
            g = []
            for raw in r["fights"]:
                f = {k: raw.get(k) for k in keep}
                t = raw.get("think_s") or []
                f["think_max"] = round(max(t), 2) if t else None
                f["think_mean"] = round(sum(t) / len(t), 2) if t else None
                g.append(f)
            # the setting as the bridge reads it: ascension, run rules, fight guard
            setting = {"ascension": r.get("ascension") or 0, "rules": r.get("run_rules", 1), "guard": r.get("fight_guard", 0)}
            groups.append((r["seed"], g, setting))
        status = ""
        if os.path.exists(os.path.join(d, "status.txt")):
            status = open(os.path.join(d, "status.txt"), encoding="utf-8").read().strip()
        folders.append((stamp, groups, rows("runs.jsonl"), status))
    # A run's line in runs.jsonl (written when it ends) matches it by game seed.
    newest = max((s for s, g, _, _ in folders if g), default=None)
    for stamp, groups, lines, status in folders:
        by_seed = {}  # a seed can have more than one line; keep the one with the most fights
        for ln in lines:
            if len(ln.get("fights", [])) >= len(by_seed.get(ln.get("seed"), {}).get("fights", [])):
                by_seed[ln.get("seed")] = ln
        for k, (seed, g, setting) in enumerate(groups):
            line = by_seed.get(seed)
            live = line is None and stamp == newest and k == len(groups) - 1
            out.append({"key": "%s#%d" % (stamp, k + 1), "stamp": stamp, "fights": g, "setting": setting,
                        "run": {a: b for a, b in line.items() if a != "fights"} if line else None,
                        "live": live, "status": status if live else ""})
    return {"runs": out, "empty_folders": sum(1 for _, f, _, _ in folders if not f)}


def main():
    data = {
        "heuristic": summary(load(HEUR)),
        "net_one_turn": summary(load(NET1)),
        "product": summary(load(PROD)),
        "product_b": summary(load(PROD_B)),
        "boss_curve": boss_curve(),
        "sequences": sequences(),
        "elite_skip": paired_clears(ELITESKIP, NET1),
        "rest_sim": paired_clears(RESTSIM, NET1),
        "real_game": real_game(),
        "written": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    if "--check" in sys.argv:
        for k in ("heuristic", "net_one_turn", "product", "product_b"):
            s = data[k]
            print(k, "n", s["n"], "clears", s["clears"], round(s["clears"] / s["n"], 3),
                  "deaths", s["deaths_by_floor"], "boss", s["boss"],
                  "arrival hp", s["mean_boss_arrival_hp"])
            print("   hp lost per won fight by floor", s["mean_hp_lost_won"])
        bc = data["boss_curve"]
        print("boss curve", bc["decks"], "decks", bc["replayed_fights"], "fights", bc["fights"])
        for b, c in bc["curves"].items():
            print("  ", b, c)
        print("elite skip vs control", data["elite_skip"])
        print("rest sim vs control", data["rest_sim"])
        for r in data["real_game"]["runs"]:
            pred = sum(f["predicted"] or 0 for f in r["fights"])
            match = sum(f["matched"] or 0 for f in r["fights"])
            print("real game", r["key"], len(r["fights"]), "fights, floors",
                  [f["floor"] for f in r["fights"]], "matched", match, "of", pred,
                  "| live" if r["live"] else "", r["status"], r["run"] or "")
        rows = data["sequences"]
        allc = sum(1 for r in rows if r[1] and r[2] and r[3])
        alll = sum(1 for r in rows if not (r[1] or r[2] or r[3]))
        print("sequences cleared by all three", allc, "lost by all three", alll, "split", 500 - allc - alll)
        return
    out = os.path.join(ROOT, "showcase", "data.js")
    with open(out, "w", newline="\n") as f:
        f.write("// Written by showcase/extract.py from results/; rerun it, don't edit.\n")
        f.write("window.SHOWCASE = " + json.dumps(data, separators=(",", ":")) + ";\n")
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
