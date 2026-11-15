import sys, os, json, collections
R='.'
sys.path.insert(0, R+'/scripts'); os.chdir(R)
import real_game_report as g
runs=g.all_runs(); num={id(r):i+1 for i,r in enumerate(runs)}
byfolder=collections.defaultdict(list)
for r in runs: byfolder[r['folder']].append(r)
def nm(d,a):
    a=a.split('@')[0]
    if a.startswith('Potion:'):
        p=d['view']['player']['potions'][int(a[7:])]; a='potion '+p
    return a.replace('gen:','')
cutc=collections.Counter(); C=collections.defaultdict(lambda:[0,0,0]); T=collections.defaultdict(lambda:[0,0])
for folder, rs in byfolder.items():
    wf=[r for r in rs if r['combat']]; k=-1; prev=None
    for l in open(os.path.join(g.RECORDS, folder, 'decisions.jsonl'), encoding='utf-8'):
        if not l.strip(): continue
        d=json.loads(l)
        if prev is None or d['floor']<prev: k+=1
        prev=d['floor']
        if 'turn' not in d: continue
        r=wf[k]; a=g.asc(r)
        cutc[(a,bool(d.get('cut')),d.get('two') is None)]+=1
        if d.get('cut') or d.get('two') is None: continue
        ops=[o[0] for o in d['options']]
        if 'End' not in ops: continue
        e=ops.index('End'); best={}
        for i,o in enumerate(ops):
            if i==e: continue
            c=nm(d,o)
            if c not in best or d['two'][i]>d['two'][best[c]]: best[c]=i
        for c,i in best.items():
            g1=d['one'][i]-d['one'][e]; g2=d['two'][i]-d['two'][e]
            x=C[(a,c)]; x[0]+=g2>g1; x[1]+=1; x[2]+=g2==g1
            # mean shift
print(cutc)
for key in [(0,'Demon Form'),(0,'Evolve'),(0,'Inflame'),(20,'Inflame'),(20,'Shockwave'),(20,'Bash'),(20,'Carnage'),(20,'Evolve'),(20,'Armaments+'),(20,'potion Weak Potion'),(0,'Slimed'),(0,'Blood for Blood'),(20,'Demon Form'),(20,'Metallicize'),(0,'potion Weak Potion')]:
    print(key, C.get(key))
print([(k,v) for k,v in C.items() if k[1] in ("Strike","Defend","Bash","Bash+")])
print('A20 lowest', sorted([(round(v[0]/v[1]*100,1),k,v) for k,v in C.items() if v[1]>=20 and k[0]==20])[:6])
print('A0 lowest', sorted([(round(v[0]/v[1]*100,1),k,v) for k,v in C.items() if v[1]>=20 and k[0]==0])[:6])
print('A20 top', sorted([(round(v[0]/v[1]*100,1),k,v) for k,v in C.items() if v[1]>=20 and k[0]==20])[-6:])
