import json,collections
R='results/gauntlet/'
seqs=[]
for f in ['net1029-hpe0.01-two-line-step-starter-simboss-a.json','net1029-hpe0.01-two-line-step-starter-simboss-500.json']:
    s=json.load(open(R+f))['sequences']; print(f,len(s),min(x['i'] for x in s),max(x['i'] for x in s),collections.Counter(x['half'] for x in s)); seqs+=s
print('n',len(seqs),'uniq i',len({x['i'] for x in seqs}),'clear',sum(x['cleared'] for x in seqs))
nm=lambda c:c[4:] if c and c.startswith('gen:') else c
off=collections.defaultdict(lambda:[0,0,0,0]) # took n, took clr, pass n, pass clr
for x in seqs:
    o=set();t=set()
    for fl in x['floors']:
        for c in fl.get('offer') or []: o.add(nm(c))
        if fl.get('took'): t.add(nm(fl['took']))
    for c in o:
        r=off[c]; k=0 if c in t else 2; r[k]+=1; r[k+1]+=int(x['cleared'])
for c,r in sorted(off.items(),key=lambda kv:-(kv[1][1]/max(kv[1][0],1)-kv[1][3]/max(kv[1][2],1))):
    if r[0]>=40 and r[2]>=40: print(f'{c:20s} took {r[1]}/{r[0]} {100*r[1]/r[0]:.1f}  pass {r[3]}/{r[2]} {100*r[3]/r[2]:.1f}  diff {100*(r[1]/r[0]-r[3]/r[2]):.1f}')
    else: print('  small',c,r)
