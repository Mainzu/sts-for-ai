import json, collections, sys
d=json.load(open(sys.argv[1]))
ps=[(h,p) for h,L in d['halves'].items() for p in L]
print(len(ps))
c=collections.Counter()
for h,p in ps:
    c[('hor',min(p['horizon'],3))]+=1; c[('fam',p['family'])]+=1; c[('grp',p['group'])]+=1; c[('enc',p['encounter'])]+=1
    c[('nopt',len(p['options']))]+=1
for k in sorted(c): print(k,c[k])
# knife edge
ke=[]
for h,p in ps:
    ls=[o[2]['loss'] for o in p['options']]
    safe=[l for l in ls if l==0]
    if len(safe)==1 and all(l==1 for l in ls if l!=0) and len(ls)>=3: ke.append((h,p))
print('knife',len(ke), collections.Counter(min(p['horizon'],3) for h,p in ke))
deep=sorted(ps,key=lambda x:-x[1]['horizon'])[:5]
for h,p in deep: print(h,p['horizon'],p['encounter'],p['hp'],p['gap'],len(p['options']),[ (o[0],round(o[1],3),o[2]['loss']) for o in p['options']], p['deck'])
