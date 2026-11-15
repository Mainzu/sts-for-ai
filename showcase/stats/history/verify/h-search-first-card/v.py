import json,sys,collections
R=sys.argv[1]+'/results/depth/'
p=json.load(open(R+'line-probe.json'))
rows=p['rows']; print(len(rows), rows[0].keys())
g=collections.defaultdict(list)
for r in rows: g[r['idx']].append(r)
tot=sum(r['nodes'] for r in rows)
turns=set((r['fight'],r['turn']) for r in rows); print('turns',len(turns),'fights',len(set(r['fight'] for r in rows)))
for k in sorted(g): L=g[k]; print(k,len(L),sum(r['nodes'] for r in L)/len(L),sum(r['ms'] for r in L)/len(L),sum(r['nodes'] for r in L)/tot)
print(collections.Counter(r.get('encounter') for r in rows))
c=json.load(open(R+'line-step-compare.json'))
s1=st=0;n=same=0;srch=0
for f in c['fights']:
  a=f['stage1'];b=f['step']
  s1+=sum(x['nodes'] for x in a); st+=sum(x['nodes'] for x in b)
  for x,y in zip(a,b):
    n+=1; same+= x['action']==y['action']
  print(len(a),len(b),f['spec']['encounter'],f['spec'].get('family'),f['spec'].get('group'),end='; ')
print();print(s1,st,st/s1,n,same)
