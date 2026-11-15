import os, json, collections
REC = "results/real-game"
c = collections.Counter(); ex = []
for name in sorted(os.listdir(REC)):
    p = os.path.join(REC, name, "decisions.jsonl")
    if not os.path.isfile(p): continue
    for line in open(p, encoding="utf-8"):
        d = json.loads(line)
        if "card_reward" not in d: continue
        o = [x.replace("gen:", "").rstrip("+") for x in d["options"] if x]
        if sorted(o) != sorted(d["card_reward"]):
            c[len(d["card_reward"]) - len(o)] += 1
            if len(ex) < 6: ex.append((name, d["floor"], d["card_reward"], d["options"], d["pick"]))
print(c); [print(e) for e in ex]
