import json, collections
R=''
b=json.load(open(R+'data/bench/gen_powers.json'))
r=json.load(open(R+'results/gen_powers/first-check.json'))
F=b['fights']; H=r['won']['heuristic']; N=r['won']['champion']
assert len(F)==len(H)==len(N)
agg=collections.defaultdict(lambda:[0,0,0,0,0,0])
for f,h,n in zip(F,H,N):
    a=agg[f['gen_card']]
    if f['set']=='original': a[0]+=1;a[1]+=h;a[2]+=n
    else: a[3]+=1;a[4]+=h;a[5]+=n
print('cards',len(agg))
rows=[]
for k,a in agg.items():
    if a[3]>=8: rows.append((a[4]/a[3]-a[1]/a[0], a[5]/a[3]-a[2]/a[0], a[3], k))
rows.sort()
for x in rows[:6]+rows[-4:]: print(x)
pack=json.load(open(R+'data/bench/gen_powers_pack.json'))
print(pack.keys())
cards={c['id']:c for c in pack.get('cards',[])}
pw={p['id']:p for p in pack.get('powers',[])}
for x in rows[:3]+rows[-2:]:
    c=cards.get(x[3]); print(json.dumps(c)[:700])
    for e in json.dumps(c).split('"power": "')[1:]:
        pid=e.split('"')[0]
        if pid in pw: print('   POWER',json.dumps(pw[pid])[:700])
print(collections.Counter(a[3] for a in agg.values()))
