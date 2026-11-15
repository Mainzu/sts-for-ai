import sys, os, json, collections
ROOT="."
sys.path.insert(0, ROOT+"/scripts")
import real_game_report as R
REC=ROOT+"/results/real-game"
runs=[]; dec_by_run={}
kinds=collections.Counter()
for name in sorted(os.listdir(REC)):
    folder=os.path.join(REC,name)
    if not (os.path.isdir(folder) and name[:1].isdigit()): continue
    rs=R.runs_of(folder)
    withf=[r for r in rs if r["combat"]]
    groups=[]; prev=None
    with open(os.path.join(folder,"decisions.jsonl"),encoding="utf-8") as f:
        for x in f:
            if not x.strip(): continue
            d=json.loads(x)
            if prev is None or d["floor"]<prev: groups.append([])
            prev=d["floor"]; groups[-1].append(d)
    for r in rs: r["_dec"]=[]
    for i,g in enumerate(groups):
        if i<len(withf): withf[i]["_dec"]=g
        else: print("extra group",name,i,len(g))
    for r in rs:
        if r["fights"] or r["end"]:
            runs.append(r)
        elif r["_dec"]: print("dropped run with decisions",name,len(r["_dec"]))
print("runs",len(runs))
def pct(s,p):
    s=sorted(s); k=(len(s)-1)*p; lo=int(k); hi=min(lo+1,len(s)-1); return s[lo]+(s[hi]-s[lo])*(k-lo)
out={0:[],20:[]}
for i,r in enumerate(runs,1):
    a=R.asc(r)
    for d in r["_dec"]:
        if "card_reward" in d: kinds["reward"]+=1; continue
        if "options" not in d: kinds["other:"+",".join(sorted(d))[:80]]+=1; continue
        kinds["fight"]+=1
        out[a].append((d.get("seconds"),i,d["floor"],[m["name"] for m in d["view"]["monsters"]]))
print(kinds)
for a in (0,20):
    rn=sorted({x[1] for x in out[a]}); print("A",a,"runs",rn[0],rn[-1],len(rn))
    s=[x[0] for x in out[a] if x[0] is not None]; print("n",len(out[a]),"with sec",len(s))
    print("median %.3f p75 %.3f p90 %.3f p99 %.3f max %.3f"%(pct(s,.5),pct(s,.75),pct(s,.9),pct(s,.99),max(s)))
    print("frac<1s",sum(v<1 for v in s)/len(s),"total h",sum(s)/3600)
    ss=sorted(s,reverse=True); k=len(ss)//10; print("top10% share",sum(ss[:k])/sum(ss), sum(ss[:round(len(ss)*.1)])/sum(ss))
    m=max(out[a],key=lambda x:x[0] or 0); print("slowest",m)
