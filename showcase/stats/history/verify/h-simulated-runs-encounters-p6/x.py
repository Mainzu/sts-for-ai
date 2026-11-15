import pickle,collections
recs=pickle.load(open('scratch/hist/simulated-runs/recs.pkl','rb'))
n=collections.Counter(); first={}
for r in recs:
    for i,c,fl in r['seqs']:
        for e,a,b,w in fl:
            n[e]+=1; first[e]=min(first.get(e,99),r['period'])
print(n.most_common(6)); print({e:p for e,p in first.items() if e.startswith('gen')})
# pack files in P6: compare same-file hallway loss rates
pk=collections.Counter(); pl=collections.Counter(); pos=collections.Counter()
for r in recs:
    if r['period']!=6: continue
    if not any(e.startswith('gen') for i,c,fl in r['seqs'] for e,*_ in fl): continue
    pk['files']+=1
    for i,c,fl in r['seqs']:
        for k,(e,a,b,w) in enumerate(fl):
            pk[e]+=1; pl[e]+=(not w)
            if e.startswith('gen'): pos[k]+=1
print(pk['files'], pos)
for e,c in pk.most_common(): 
    if e!='files': print(f'{e:26}{c:6}{pl[e]:5}{100*pl[e]/c:6.2f}')
