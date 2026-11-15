import sys, os, json, collections
R='.'
sys.path.insert(0, R+'/scripts'); os.chdir(R)
import real_game_report as g
runs=g.all_runs()
print('runs', len(runs))
num={id(r):i+1 for i,r in enumerate(runs)}
byfolder=collections.defaultdict(list)
for r in runs: byfolder[r['folder']].append(r)
def nm(a):
    a=a.split('@')[0]
    return a[4:] if a.startswith('gen:') else a
# variants: A best-per-card decision-level; B per option
cnt={v:collections.defaultdict(lambda:[0,0]) for v in 'AB'}
nd=collections.Counter(); ndrun=collections.Counter(); kinds=collections.Counter()
for folder, rs in byfolder.items():
    wf=[r for r in rs if r['combat']]
    k=-1; prev=None
    with open(os.path.join(g.RECORDS, folder, 'decisions.jsonl'), encoding='utf-8') as f:
        for l in f:
            if not l.strip(): continue
            d=json.loads(l)
            if prev is None or d['floor']<prev: k+=1
            prev=d['floor']
            if 'two' not in d: continue
            if k>=len(wf): kinds['unmapped']+=1; continue
            r=wf[k]; n=num[id(r)]
            if d.get('cut'): continue
            ops=[o[0] if len(o)==1 else '|'.join(o) for o in d['options']]
            if 'End' not in ops: continue
            a=g.asc(r); e=ops.index('End')
            nd[a]+=1; ndrun[n]+=1
            best={}
            for i,o in enumerate(ops):
                if o=='End': continue
                c=nm(o); g1=d['one'][i]-d['one'][e]; g2=d['two'][i]-d['two'][e]
                x=cnt['B'][(a,c)]; x[0]+=g2>g1; x[1]+=1
                b=best.setdefault(c,[-9,-9]); b[0]=max(b[0],g1); b[1]=max(b[1],g2)
            for c,(g1,g2) in best.items():
                x=cnt['A'][(a,c)]; x[0]+=g2>g1; x[1]+=1
print('decisions by asc', dict(nd), kinds)
print('runs asc', collections.Counter(g.asc(r) for r in runs), 'first20', [num[id(r)] for r in runs if g.asc(r)==20][:1])
for v in 'AB':
    print('==',v)
    for (a,c),(p,t) in sorted(cnt[v].items(), key=lambda kv:(kv[0][0],-kv[1][0]/kv[1][1])):
        if t>=20: print(a, c, p, t, round(100*p/t,1))
