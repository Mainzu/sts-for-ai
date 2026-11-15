import os,json,glob
for p in sorted(glob.glob("results/real-game/*/decisions.jsonl")):
    for line in open(p,encoding="utf-8"):
        if "card_reward" not in line: continue
        d=json.loads(line)
        a=sorted(c.replace("gen:","").rstrip("+") for c in d["card_reward"]); b=sorted(o.replace("gen:","").rstrip("+") for o in d["options"] if o)
        if a!=b or any("Juggernaut" in c for c in d["card_reward"]):
            print(p.split("/")[-2][:15], d["floor"], d["card_reward"], d["options"], d["pick"], a==b)
