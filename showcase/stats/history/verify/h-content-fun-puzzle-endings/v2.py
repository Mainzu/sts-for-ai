import json,sys,collections
d=json.load(open(sys.argv[1]))
P=[p for h in ('train','held_out') for p in d['halves'][h]]
E=1e-9
c=collections.Counter();K=[]
for p in P:
    L=[o[2]['loss'] for o in p['options']]
    one=[l>1-E for l in L]; zero=[l<E for l in L]
    if all(one): c['lost']+=1
    elif all(zero): c['won']+=1
    elif len(L)>=3 and sum(zero)==1 and all(a or b for a,b in zip(one,zero)): c['knife']+=1;K.append(p)
    else: c['other']+=1
print(c, sum(c.values()))
print('knife by n',sorted(collections.Counter(len(p['options']) for p in K).items()))
print('lost by horizon',collections.Counter(p['horizon'] for p in P if all(o[2]['loss']>1-E for o in p['options'])))
