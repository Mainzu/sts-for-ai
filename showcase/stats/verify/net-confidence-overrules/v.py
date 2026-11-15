import os, json, sys, collections, statistics
R="results/real-game"
def lab(o):
    a=o[0] if o else "?"
    a=a.split("@")[0]
    return a[4:] if a.startswith("gen:") else a
S={}
for name in sorted(os.listdir(R)):
    p=os.path.join(R,name,"decisions.jsonl")
    if not (name[:1].isdigit() and os.path.exists(p)): continue
    with open(p,encoding="utf-8") as f:
        for ln in f:
            if not ln.strip(): continue
            d=json.loads(ln)
            if "view" not in d: continue
            a=d["view"].get("ascension")
            s=S.setdefault(a,collections.Counter()); sw=S.setdefault((a,"sw"),collections.Counter()); costs=S.setdefault((a,"c"),[])
            s["fight"]+=1
            if d.get("cut"): s["cut"]+=1; continue
            if len(d["options"])<2: s["single"]+=1; continue
            s["n"]+=1
            one=d["one"]; pk=d["pick"]
            m=max(one); i=one.index(m)
            ties=[j for j,v in enumerate(one) if v==m]
            if pk!=i: s["idx_diff"]+=1
            if lab(d["options"][pk])!=lab(d["options"][i]):
                s["lab_diff"]+=1
                sw[lab(d["options"][i])+" -> "+lab(d["options"][pk])]+=1
                costs.append(m-one[pk])
                if pk in ties: s["lab_diff_but_tied"]+=1
                if not any(lab(d["options"][j])==lab(d["options"][pk]) for j in ties):
                    s["real"]+=1
                    S.setdefault((a,"swr"),collections.Counter())[lab(d["options"][i])+" -> "+lab(d["options"][pk])]+=1
            if d["options"][pk]!=d["options"][i]: s["full_diff"]+=1
for k in S:
    if not isinstance(k,tuple):
        print(k,dict(S[k]))
        print(" top", S[(k,"sw")].most_common(10))
        c=S[(k,"c")]
        if c: print(" median cost",statistics.median(c)," >5:",sum(x>5 for x in c), "max",max(c))
        if (k,"swr") in S: print(" real top",S[(k,"swr")].most_common(10))
