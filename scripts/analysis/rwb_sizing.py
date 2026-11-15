"""random-world-bench step 1 (no CPU): sizes the world bench from
results/mutate/gen-enemies-b1.json (docs/research/random-world-bench.md,
"Step 1"). Run from the main checkout:
    .venv/Scripts/python.exe .claude/worktrees/lane-random-world-bench/scripts/analysis/rwb_sizing.py
"""
import json, numpy as np
d=json.load(open('results/mutate/gen-enemies-b1.json'))
rows=[r for r in d['rows'] if r['group']=='elite']
mods=[m for m in d['settings']['mods'] if m.startswith('GE-')]
COLL={'GE-OppCard-Weak','GE-OppCard-Vulnerable','GE-AttackLoss-Vulnerable'}
# D[m] : array starts x 16 of novelty d per seed
def L(r,a): return np.array([r['hp']-h for w,h in a],float)
D={}
for m in mods:
  D[m]=np.array([(L(r,r['mods'][m]['one'])-L(r,r['parent']['one']))-(L(r,r['mods'][m]['heuristic'])-L(r,r['parent']['heuristic'])) for r in rows])
rng=np.random.default_rng(1)
for name,pool in (('all24',mods),('excl3',[m for m in mods if m not in COLL])):
  c=np.array([D[m].mean() for m in pool])
  # noise of a world estimate: 50 starts x 4 seeds (first 4)
  noise=[]
  for m in pool:
    est=[D[m][rng.choice(len(rows),50,replace=False)][:,:4].mean() for _ in range(400)]
    noise.append(np.std(est))
  noise=np.array(noise)
  print(name,'n',len(pool),'c1 mean %.2f sd_between %.2f  median noise(50x4) %.2f max %.2f'%(c.mean(),c.std(ddof=1),np.median(noise),noise.max()))
  sb=c.std(ddof=1); sn=np.sqrt((noise**2).mean()); c1=c.mean()
  for k in (1,2,4,8):
    for N in (20,30,40):
      # paired: interaction noise (world + k singles on the same 50x4) ~ sqrt(1+k)*sn, conservatively
      sint=np.sqrt(1+k)*sn
      # go statistic g = cost - 1.5 S; var = sint^2 + 0.25 k sb^2
      se_g=np.sqrt(sint**2+0.25*k*sb**2)/np.sqrt(N)
      # unpaired version (charter literal): cost(k) vs 1.5 k mean cost(1) from N k=1 worlds
      se_u=np.sqrt((k*sb**2+k*sn**2)/N + (1.5*k)**2*(sb**2+sn**2)/N)
      add=-0.5*k*c1
      print('  k%d N%d  additive E[g]=%.2f  se_paired %.2f (|E|/se %.1f)  se_unpaired %.2f (%.1f)'%(k,N,add,se_g,abs(add)/se_g,se_u,abs(add)/se_u))

# --- saturation: summed single raw costs against start HP ---
hp=np.array([r['hp'] for r in rows],float)
par=np.array([L(r,r['parent']['one']).mean() for r in rows])
raw={m:np.array([L(r,r['mods'][m]['one']).mean() for r in rows])-par for m in pool}
wins={m:np.mean([np.mean([w for w,h in r['mods'][m]['one']]) for r in rows]) for m in pool}
print('parent loss mean %.1f, hp mean %.1f, parent net win %.3f'%(par.mean(),hp.mean(),np.mean([np.mean([w for w,h in r['parent']['one']]) for r in rows])))
print('single net win rates min %.3f median %.3f'%(min(wins.values()),np.median(list(wins.values()))))
rng=np.random.default_rng(2)
for k in (2,4,8):
  fr=[]
  for _ in range(2000):
    items=rng.choice(pool,k,replace=False)
    pred=par+sum(raw[m] for m in items)
    fr.append(np.mean(pred>hp))
  print('k%d: share of starts where parent loss + summed single raw costs exceeds start HP: mean %.2f, worlds over 0.3: %.2f'%(k,np.mean(fr),np.mean(np.array(fr)>0.3)))
