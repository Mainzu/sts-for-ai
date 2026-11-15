import json,collections
G=json.load(open('gathered.json'));first={}
for r in G['runs']:
    for d in r['datasets'] or []:
        first[d]=min(first.get(d,'9'),r['md'])
P=[('10-23','10-24'),('10-25','10-28'),('10-29','10-31'),('11-01','11-02'),('11-03','11-05'),('11-06','11-09'),('11-10','11-12'),('11-13','11-14')]
per=lambda md:next(i+1 for i,(a,b) in enumerate(P) if a<=md<=b)
mis=0;g=collections.Counter();n=collections.Counter();byday=collections.Counter();parent=collections.Counter()
for d in G['ds']:
    md=first.get(d['id'],d['md'])
    if d['id'] in first and first[d['id']]<d['md']: mis+=1
    g[per(md)]+=d['n_games'];n[per(md)]+=1;byday[md]+=d['n_games']
    parent['net' if d['parent'] else 'heuristic or no parent']+=d['n_games']
print('mtime later than first use:',mis)
print('games by period',sorted(g.items()),sum(g.values()));print('datasets',sorted(n.items()),sum(n.values()))
print(sorted(byday.items()));print(parent)
