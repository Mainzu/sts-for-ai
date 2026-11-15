import json,sys,collections
d=json.load(open(sys.argv[1]))
P=[p for h in ('train','held_out') for p in d['halves'][h]]
print(len(P), collections.Counter(p['horizon'] for p in P))
print(len(set((p['seed'],p['step'],p['spec']) for p in P)))
c=collections.Counter();knife=[];same=0
for p in P:
    L=[o[2]['loss'] for o in p['options']]
    if all(l==1.0 for l in L): c['lost']+=1
    elif all(l==0.0 for l in L):
        c['won']+=1
    elif len(L)>=3 and sum(l<1.0 for l in L)==1: c['knife']+=1; knife.append(p)
    else: c['other']+=1
print(c)
wonall=[p for p in P if all(o[2]['loss']==0 for o in p['options'])]
print('won all, values differ:',sum(len(set(round(o[1],6) for o in p['options']))>1 for p in wonall))
k=max(knife,key=lambda p:len(p['options']))
print(len(k['options']),k['encounter'],k['hp'],[ (o[0],o[2]['loss']) for o in k['options']])
for p in P:
    names={}
    for o in p['options']:
        a=o[0][0].split('@')
        names.setdefault(a[0],[]).append((o[0],o[2]['loss']))
    if 'Thunderclap' in names and 'Thunderclap+' in names:
        t=min(x[1] for x in names['Thunderclap']);u=min(x[1] for x in names['Thunderclap+'])
        if t<1 and u==1: print('TC',p['encounter'],p['seed'],names['Thunderclap'],names['Thunderclap+'])
print(collections.Counter(p['encounter'] for p in knife).most_common(5))
rest=[p for p in P if not all(o[2]['loss']==1 for o in p['options']) and not all(o[2]['loss']==0 for o in p['options'])]
rest=[p for p in rest if not (len(p['options'])>=3 and sum(o[2]['loss']==0 for o in p['options'])==1 and all(o[2]['loss'] in (0,1) for o in p['options']))]
print('rest',len(rest),'flat loss',sum(len(set(o[2]['loss'] for o in p['options']))==1 for p in rest),'one-opt',sum(len(p['options'])==1 for p in rest))
print('2opt knife-like',sum(len(p['options'])<3 for p in rest))
fl=[p for p in rest if len(set(o[2]['loss'] for o in p['options']))==1]
print('flat loss, flat value',sum(len(set(round(o[1],6) for o in p['options']))==1 for p in fl), [o[2]['loss'] for o in fl[0]['options']][:3])
