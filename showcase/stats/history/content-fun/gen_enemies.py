# Generated-enemy reads: cost by trigger (job 0470) and the Nob that hits back (0469/0473/0474).
import json, sys, collections
R=''
sys.path[:0]=[R+'scripts/analysis', R+'scripts', R]
import mutate_monsters as mm
def load(f):
    d=json.load(open(R+'results/mutate/'+f, encoding='utf-8')); return d['rows'], d['settings']['mods']
rows,mods=load('gen-enemies-b1.json')
t=mm.gen_table(rows,mods,'one')
collapse={'GE-OppCard-Weak','GE-OppCard-Vulnerable','GE-AttackLoss-Vulnerable'}
by=collections.defaultdict(list)
for m,v in t['mechanics'].items():
    print(f"{m:28s} heur {v['heur_win']:.3f} net {v['net_win']:.3f} cost {v['cost'][0]:+.2f} ({v['cost'][1]:.2f})")
    if m in collapse: continue
    by[m.split('-')[1]].append(v['cost'][0])
print('starts',t['n'])
for k,v in by.items(): print('TRIGGER',k,len(v),round(sum(v)/len(v),2))
# Nob that hits back
for f in ['gen-enemies-b1.json','gen-b1-sharp399-s1.json','gen-b1-sharp399-s2.json']:
    rows,mods=load(f)
    nob=[r for r in rows if r['encounter']=='gremlin_nob']
    # first 4 seeds only for the zero-shot file, to pair with the bursts
    seeds=sorted({r.get('seed') for r in nob}) if 'seed' in nob[0] else None
    tt=mm.gen_table(nob,mods,'one')
    v=tt['mechanics'].get('GE-AttackLoss-Damage')
    print(f, 'n',tt['n'],'seeds',None if seeds is None else len(seeds),'heur',round(v['heur_win'],3),'net',round(v['net_win'],3),'cost',[round(x,2) for x in v['cost']])
