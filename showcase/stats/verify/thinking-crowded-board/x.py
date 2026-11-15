import json,os,collections
R="results/real-game"
c=collections.Counter()
for name in sorted(os.listdir(R)):
    p=R+"/"+name+"/decisions.jsonl"
    if not os.path.exists(p): continue
    for ln in open(p,encoding="utf-8"):
        d=json.loads(ln)
        if "view" not in d or d["view"].get("ascension")!=20: continue
        al=[m["name"] for m in d["view"]["monsters"] if m["hp"]>0 and not m.get("escaped")]
        if len(al)>=4: c[(len(al),tuple(sorted(al)))]+=1
for k,v in c.most_common(): print(v,k)
