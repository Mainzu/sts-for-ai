import json,collections
T=json.load(open('trainjobs.json'))
P=[('10-23','10-24'),('10-25','10-28'),('10-29','10-31'),('11-01','11-02'),('11-03','11-05'),('11-06','11-09'),('11-10','11-12'),('11-13','11-14')]
per=lambda md:next(i+1 for i,(a,b) in enumerate(P) if a<=md<=b)
th=collections.defaultdict(collections.Counter);n=collections.Counter();st=collections.Counter()
for t in T:
    p=per(t['started'][5:10]); s=[x for x in ('learn.py','finetune.py','family.py','two_turn_round.py') if x in t['cmd']][0]
    th[p][s]+=t['h']*(t['threads'] or 1); n[p]+=1; st[t['status']]+=1
for p in sorted(th): print(p,n[p],{k:round(v,1) for k,v in th[p].items()},round(sum(th[p].values()),1))
print(st, min(t['started'] for t in T))
fail=sum(t['h']*(t['threads'] or 1) for t in T if t['status']!='ok');print('non-ok thread-h',round(fail,1))
