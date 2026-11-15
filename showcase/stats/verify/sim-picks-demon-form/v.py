import json, collections
G="results/gauntlet/"
F={"heur":"heuristic-starter-simboss.json","net":"net1029-hpe0.01-two-line-step-starter-simboss-a.json"}
st={}
for k,f in F.items():
    s=json.load(open(G+f))["sequences"]
    assert len({x["i"] for x in s})==len(s)==500
    off=collections.Counter(); took=collections.Counter(); nrew=0; dup=0
    runs_df={}
    for x in s:
        df_off=df_took=False
        for fl in x["floors"]:
            if "offer" not in fl: continue
            nrew+=1
            o=[c.replace("gen:","") for c in fl["offer"]]
            if len(set(o))<len(o): dup+=1
            for c in set(o): off[c]+=1
            t=fl.get("took")
            if t: t=t.replace("gen:",""); took[t]+=1
            if "Demon Form" in o: df_off=True
            if t=="Demon Form": df_took=True
        runs_df[x["i"]]=(df_off,df_took,x["cleared"])
    st[k]=(off,took,nrew,runs_df)
    print(k,"rewards",nrew,"dup-offers",dup,"clears",sum(x["cleared"] for x in s))
ho,ht,_,hr=st["heur"]; no,nt,_,nr=st["net"]
rows=[]
for c in sorted(set(ho)|set(no)):
    if ho[c]>=30 and no[c]>=30:
        a=100*ht[c]/ho[c]; b=100*nt[c]/no[c]; rows.append((b-a,c,ht[c],ho[c],a,nt[c],no[c],b))
rows.sort()
for r in rows: print("%+6.1f %-20s heur %d/%d %.1f  net %d/%d %.1f"%r)
print("cards",len(rows),"within10",sum(abs(r[0])<=10 for r in rows))
for nm,rr in (("heur",hr),("net",nr)):
    took=[v for v in rr.values() if v[1]]; offnot=[v for v in rr.values() if v[0] and not v[1]]
    print(nm,"took DF runs",len(took),"cleared",sum(v[2] for v in took),"| offered never took",len(offnot),"cleared",sum(v[2] for v in offnot))
