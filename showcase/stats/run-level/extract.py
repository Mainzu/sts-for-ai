"""Run-level facts per real-game run: states.jsonl streamed, the i-th state
paired with the i-th 'send:' line of log.txt (the command answering it).
Writes runs.json next to this script. Read-only on the repo."""
import json, os, re, sys
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as R

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs.json")
runs = R.all_runs()
meta = {r["seed"]: dict(n=i + 1, asc=R.asc(r), rules=r["run_rules"], guard=r["fight_guard"],
                        end=("won" if r["end"] and r["end"].get("victory") else "died" if r["end"] is not None
                             else "stopped" if R.stopped(r) else "left"),
                        floor=r["last"].get("floor"), act=r["last"].get("act"), folder=r["folder"],
                        boss_beaten=any(f["group"] == "boss" and f["won"] and f["floor"] <= 17 for f in r["fights"]),
                        act1_boss=r.get("act1_boss"))
        for i, r in enumerate(runs)}
print("runs", len(runs))
bad = tot = 0
for folder in sorted({m["folder"] for m in meta.values()}):
    d = os.path.join(R.RECORDS, folder)
    sends = []
    for line in open(os.path.join(d, "log.txt"), encoding="utf-8"):
        m = re.match(r"\d\d:\d\d:\d\d send: (.*)", line.strip())
        if m:
            sends.append(m.group(1))
    # Pair states with sends; where a command can't answer its state, the
    # offset that makes the next 8 pairs valid is taken (one folder drifts).
    avail = [json.loads(l)["msg"].get("available_commands") for l in open(os.path.join(d, "states.jsonl"), encoding="utf-8")]
    def ok(i, off):
        j = i + off
        return j < 0 or j >= len(sends) or not avail[i] or sends[j].split()[0] in avail[i]
    off = 0
    with open(os.path.join(d, "states.jsonl"), encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not ok(i, off):
                for o in sorted(range(-6, 7), key=abs):
                    if all(ok(x, o) for x in range(i, min(i + 8, len(avail)))):
                        off = o; break
            row = json.loads(line)
            msg = row["msg"]
            gs = msg.get("game_state")
            cmd = sends[i + off] if 0 <= i + off < len(sends) else None
            if cmd and msg.get("available_commands"):
                tot += 1
                if cmd.split()[0] not in msg["available_commands"]:
                    bad += 1
            if not gs or gs.get("seed") not in meta:
                continue
            m = meta[gs["seed"]]
            st, ss = gs.get("screen_type"), gs.get("screen_state") or {}
            m["gold"] = gs.get("gold"); m["max_gold"] = max(m.get("max_gold", 0), gs.get("gold") or 0)
            m["relics"] = [x["name"] for x in gs.get("relics", [])]
            m["potions_end"] = [p["name"] for p in gs.get("potions", []) if p["id"] != "Potion Slot"]
            m["hp_end"] = (gs.get("current_hp"), gs.get("max_hp"))
            m["deck"] = [c["name"] + "+" * 0 for c in gs.get("deck", [])]
            m["upgraded"] = sum(1 for c in gs.get("deck", []) if c.get("upgrades"))
            m.setdefault("screens", {}).setdefault(st, 0)
            m["screens"][st] += 1
            parts = (cmd or "").split()
            k = int(parts[1]) if len(parts) > 1 and parts[0] == "choose" and parts[1].isdigit() else None
            if st == "SHOP_ROOM":
                m.setdefault("shops", set()).add(gs.get("floor"))
            if st == "EVENT":
                opts = {o.get("choice_index"): o for o in ss.get("options", [])}
                name = ss.get("event_name")
                ev = m.setdefault("events", [])
                if not ev or ev[-1]["floor"] != gs.get("floor") or ev[-1]["name"] != name:
                    ev.append(dict(floor=gs.get("floor"), name=name, steps=[]))
                if k is not None and k in opts:
                    ev[-1]["steps"].append(dict(chosen=opts[k].get("text"), offered=[o.get("text") for o in ss.get("options", [])],
                                                hp=gs.get("current_hp"), gold=gs.get("gold")))
            if st == "REST" and not ss.get("has_rested") and k is not None:
                ro = ss.get("rest_options", [])
                if k < len(ro):
                    m.setdefault("rests", []).append(dict(floor=gs["floor"], pick=ro[k], hp=gs["current_hp"], mx=gs["max_hp"]))
            if st == "BOSS_REWARD" and k is not None:
                rel = ss.get("relics", [])
                if k < len(rel):
                    m.setdefault("boss_relic", []).append(dict(pick=rel[k]["name"], offered=[x["name"] for x in rel], floor=gs["floor"]))
            if st == "COMBAT_REWARD" and k is not None:
                rw = ss.get("rewards", [])
                if k < len(rw):
                    t = rw[k].get("reward_type")
                    if t == "POTION":
                        m.setdefault("potions_got", []).append(rw[k].get("potion", {}).get("name"))
                    if t == "RELIC":
                        m.setdefault("relics_got", []).append(dict(name=rw[k].get("relic", {}).get("name"), floor=gs["floor"]))
                    if t in ("GOLD", "STOLEN_GOLD"):
                        m["gold_taken"] = m.get("gold_taken", 0) + rw[k].get("gold", 0)
                # potions left on the floor
                if cmd == "proceed":
                    m["potions_left"] = m.get("potions_left", 0) + sum(1 for r in rw if r.get("reward_type") == "POTION")
            if parts[:2] == ["potion", "use"] and len(parts) > 2:
                pots = gs.get("potions", [])
                j = int(parts[2])
                if j < len(pots):
                    m.setdefault("potions_used", []).append(dict(name=pots[j]["name"], floor=gs["floor"],
                                                              combat="combat_state" in gs,
                                                              monsters=[x["id"] for x in gs.get("combat_state", {}).get("monsters", [])]))
print("commands checked", tot, "not in available_commands", bad)
for m in meta.values():
    if "shops" in m:
        m["shops"] = sorted(m["shops"])
json.dump(list(meta.values()), open(OUT, "w"), indent=1)
print("wrote", OUT)
