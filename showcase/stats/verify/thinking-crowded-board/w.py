import json,os,collections
R="results/real-game"
c=collections.Counter(); keys=collections.Counter(); odd=[]
for name in sorted(os.listdir(R)):
    p=R+"/"+name+"/decisions.jsonl"
    if not os.path.exists(p): continue
    for ln in open(p,encoding="utf-8"):
        d=json.loads(ln)
        if "view" not in d: continue
        c[d["view"].get("ascension")]+=1
        for m in d["view"]["monsters"]:
            keys.update(m.keys())
            if m.get("hp",0)>0 and any(m.get(k) for k in ("is_gone","gone","half_dead","escaped")): odd.append((name,m["name"],{k:m.get(k) for k in m if k in("is_gone","gone","half_dead","escaped")}))
print(c); print(keys); print(len(odd), odd[:5])
