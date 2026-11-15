import json, collections, sys
d=json.load(open(sys.argv[1]))
ps=[(h,p) for h,L in d['halves'].items() for p in L]
ke=[]
for h,p in ps:
    ls=[o[2]['loss'] for o in p['options']]
    safe=[l for l in ls if l==0]
    if len(safe)==1 and all(l==1 for l in ls if l!=0) and len(ls)>=3: ke.append((h,p))
ke.sort(key=lambda x:-len(x[1]['options']))
for h,p in ke[:6]:
    print(h,'hor',p['horizon'],p['encounter'],'hp',p['hp'],'n',len(p['options']),p['seed'],p['step'])
    print('  win:',[o[0] for o in p['options'] if o[2]['loss']==0], ' others:',[o[0] for o in p['options'] if o[2]['loss']==1])
    print('  deck',p['deck'])
print('knife by n options', sorted(collections.Counter(len(p['options']) for h,p in ke).items()))
# biggest puzzle
for h,p in sorted(ps,key=lambda x:-len(x[1]['options']))[:2]:
    print('BIG',h,p['encounter'],p['hp'],p['horizon'],len(p['options']),sorted([(round(o[1],3),o[0]) for o in p['options']],reverse=True)[:5])
# certain loss puzzles: every option loses
allloss=[p for h,p in ps if all(o[2]['loss']==1 for o in p['options'])]
allwin=[p for h,p in ps if all(o[2]['loss']==0 for o in p['options'])]
print('all lose',len(allloss),'all win',len(allwin))
