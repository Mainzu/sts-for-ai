# Daily fights (gauntlet floors + ladder pair fights), encounters seen / deadliest per period.
import pickle,collections,json,glob
ROOT='.'
recs=pickle.load(open('recs.pkl','rb'))
day=collections.Counter(); runs_day=collections.Counter(); lad=collections.Counter()
seen=collections.defaultdict(collections.Counter); died=collections.defaultdict(collections.Counter)
for r in recs:
    d=r['when'][:5]
    runs_day[d]+=len(r['seqs'])
    for i,c,fl in r['seqs']:
        day[d]+=len(fl)
        for e,a,b,w in fl:
            seen[r['period']][e]+=1
            if not w: died[r['period']][e]+=1
for l in open(ROOT+'/results/ladder/log.jsonl'):
    x=json.loads(l); lad[x['when'][5:10]]+=2*x['pairs']
for f in glob.glob(ROOT+'/results/ladder/runhp/*.json'):
    x=json.load(open(f)); lad[x['when'][5:10]]+=2*x['pairs']
print('ladder by day',sorted(lad.items()))
print('gauntlet fights by day',sorted(day.items()))
print('runs by day',sorted(runs_day.items()))
print('total gauntlet runs',sum(runs_day.values()),'fights',sum(day.values()),'ladder fights',sum(lad.values()))
tot=collections.Counter(); totd=collections.Counter()
for p in seen: tot.update(seen[p]); totd.update(died[p])
print('distinct encounters',len(tot))
print('most seen', tot.most_common(8))
print('deaths', totd.most_common(12), sum(totd.values()))
for e,n in totd.most_common(12): print(e, n, tot[e], round(n/tot[e],3), [ (p, seen[p][e], died[p][e]) for p in sorted(seen)])
for p in sorted(seen): print(p, len(seen[p]), seen[p].most_common(3), sum(died[p].values()))
