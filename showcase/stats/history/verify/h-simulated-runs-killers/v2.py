import json,os,glob,hashlib,datetime,collections as C
R='results/gauntlet'
P=[(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
def per(d):
    for p,a,b in P:
        if a<=d<=b: return p
seen={};fights=C.Counter();loss=C.Counter();ends=C.Counter();lost=0;runs=0;pe=C.Counter();dups=[]
for f in sorted(glob.glob(R+'/*.json'),key=os.path.getmtime):
    d=json.load(open(f));h=hashlib.md5(json.dumps(d['sequences'],sort_keys=True).encode()).hexdigest()
    if h in seen: dups.append((os.path.basename(f),seen[h]));continue
    seen[h]=os.path.basename(f)
    p=per(datetime.datetime.fromtimestamp(os.path.getmtime(f),datetime.timezone(datetime.timedelta(hours=0))).strftime('%m-%d'))
    for q in d['sequences']:
        runs+=1;lost+= not q['cleared']
        for fl in q['floors']:
            e=fl['encounter'];fights[(p,e)]+=1
            if not fl['won']: loss[(p,e)]+=1;ends[e]+=1;pe[(p,e)]+=1
for a,b in dups: print('DUP',a,'==',b)
print('runs',runs,'lost',lost)
for e,c in ends.most_common(4):print(e,c,round(100*c/lost,1))
print('top3',round(100*sum(c for _,c in ends.most_common(3))/lost,1))
tot=C.Counter()
for (p,e),n in fights.items(): tot[p]+=n
print(dict(tot))
for e in ['hexaghost','the_guardian','slime_boss','lagavulin','three_sentries','gremlin_nob']:
    print(e,[round(100*loss[(p,e)]/fights[(p,e)],1) for p in range(4,9)],sum(fights[(p,e)] for p in range(4,9)),'ends/period',[pe[(p,e)] for p in range(4,9)])
