"""Fight records from the real-game bridge's records. Read-only.
python -I records.py  -> prints tables and writes records.json beside it."""
import json, os, sys
ROOT = "."
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from real_game_report import runs_of
BASE = os.path.join(ROOT, "results", "real-game")
OUT = os.path.dirname(os.path.abspath(__file__))

runs = []  # numbered like showcase/extract.py: runs with fights, in folder order
for stamp in sorted(os.listdir(BASE)):
    d = os.path.join(BASE, stamp)
    if not os.path.isdir(d) or not stamp[:1].isdigit():
        continue
    rs = [r for r in runs_of(d) if r["fights"]]
    if not rs:
        continue
    # per seed, per floor: turn -> [first hp, last hp], monsters per turn, relics
    per = {}
    with open(os.path.join(d, "states.jsonl"), encoding="utf-8") as f:
        for line in f:
            if '"combat_state"' not in line:
                continue
            gs = json.loads(line)["msg"].get("game_state") or {}
            cs = gs.get("combat_state")
            if not cs:
                continue
            fl = per.setdefault(gs["seed"], {}).setdefault(gs["floor"], {})
            t = cs.get("turn")
            hp = cs["player"]["current_hp"]
            e = fl.setdefault(t, {"first": hp, "last": hp, "mon": None, "relics": None})
            e["last"] = hp
            e["mon"] = [(m.get("name"), m.get("current_hp"), m.get("intent"), m.get("move_adjusted_damage"), m.get("move_hits"))
                        for m in cs.get("monsters", []) if not m.get("is_gone") and m.get("current_hp", 0) > 0]
            e["relics"] = [x["name"] for x in gs.get("relics", [])]
    for r in rs:
        r["turns"] = per.get(r["seed"], {})
        r["stamp"] = stamp
        runs.append(r)

print("runs", len(runs))
rows = []
for i, r in enumerate(runs, 1):
    asc = r.get("ascension") or 0
    for f in r["fights"]:
        tt = r["turns"].get(f["floor"], {})
        turns = max((t for t in tt if t is not None), default=None)
        hits = []
        ks = sorted(t for t in tt if t is not None)
        for a, b in zip(ks, ks[1:]):
            if b == a + 1:
                hits.append((tt[a]["last"] - tt[b]["first"], a, [m[0] for m in tt[a]["mon"] or []],
                             [(m[0], m[3], m[4]) for m in tt[a]["mon"] or []]))
        rows.append(dict(run=i, stamp=r["stamp"], asc=asc, rules=r.get("run_rules"), guard=r.get("fight_guard"),
                         floor=f["floor"], group=f["group"], monsters=f["monsters"], hp_start=f["hp_start"],
                         hp_end=f["hp_end"], hp_after=f.get("hp_after"), won=f["won"], handed=f.get("handed_over"),
                         turns=turns, max_hp=r["hp"].get(f["floor"], (None, None))[1],
                         relics=(tt[ks[-1]]["relics"] if ks else None),
                         hits=sorted(hits, reverse=True)[:2]))
json.dump(rows, open(os.path.join(OUT, "records.json"), "w"), indent=0)
print("fights", len(rows), "A0", sum(r["asc"] == 0 for r in rows), "A20", sum(r["asc"] == 20 for r in rows))
print("run settings", [(r["run"], r["asc"]) for r in rows if r["run"] in (27, 28)][:1], [(r["run"], r["asc"]) for r in rows if r["run"] == 28][:1])
