import os, json, collections
REC = "results/real-game"
cnt = collections.Counter(); first = collections.Counter()
for name in sorted(os.listdir(REC)):
    p = os.path.join(REC, name, "states.jsonl")
    if not os.path.isfile(p): continue
    before = {}; seen=set(); firstdone=set()
    with open(p, encoding="utf-8") as f:
        for line in f:
            if '"REST"' not in line: continue
            gs = json.loads(line)["msg"]["game_state"]; k=(gs["seed"], gs["floor"])
            d = {c["uuid"]: (c["name"], c.get("upgrades",0)) for c in gs["deck"]}
            if not gs["screen_state"]["has_rested"]: before.setdefault(k, d)
            elif k in before and k not in seen:
                seen.add(k)
                for u,(nm,up) in d.items():
                    if u in before[k] and up > before[k][u][1]:
                        cnt[nm]+=1
                        if gs["seed"] not in firstdone: first[nm]+=1; firstdone.add(gs["seed"])
print(sum(cnt.values()), cnt.most_common(8)); print("first", first.most_common(5))
