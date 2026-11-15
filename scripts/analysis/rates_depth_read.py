# Pair lean-rates vs lean-thr r2 nets (s101/s201/s301) on tight_bosses depth runs
# (job 0057a8z4) by (cell, seed); prints rates - thr won at one and two turns.
# Usage: python scripts/analysis/rates_depth_read.py held_out|train
import json,math,collections,glob,sys
half=sys.argv[1]
def se(v):
  n=len(v);m=sum(v)/n;return m,math.sqrt(sum((t-m)**2 for t in v)/(n-1)/n)
tot=collections.defaultdict(list)
for s in ['s101','s201','s301']:
  r=glob.glob(f'results/depth/bosses-{half}-2026-10-31-lean-rates-{s}-r2-*.json')
  t=glob.glob(f'results/depth/bosses-{half}-2026-10-31-lean-thr-{s}-r2-*.json')
  if not r or not t: print(s,'missing');continue
  R={(f['cell'],f['seed']):f for f in json.load(open(r[0]))['fights']}
  T={(f['cell'],f['seed']):f for f in json.load(open(t[0]))['fights']}
  keys=sorted(set(R)&set(T))
  per=collections.defaultdict(lambda: collections.defaultdict(list))
  for k in keys:
    a,b=R[k],T[k]
    for arm in ['one','two']:
      d=int(a[arm]['won'])-int(b[arm]['won'])
      per[a['encounter']][arm].append(d); per['all'][arm].append(d)
      tot[(a['encounter'],arm)].append(d); tot[('all',arm)].append(d)
  print(s,len(keys),{e:{arm:round(sum(v)/len(v),3) for arm,v in d.items()} for e,d in per.items()})
print('pooled 3 seeds (rates - thr, won):')
for (e,arm),v in sorted(tot.items()):
  m,s_=se(v);print(f'  {e:14s} {arm} {m:+.3f} se {s_:.3f} n {len(v)}')
