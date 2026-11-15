# Four generated mechanics on one elite at once: net cost beyond the heuristic, start-HP cap (genpack-reach 0842-0843).
import json, sys, os, numpy as np
R=''
os.chdir(R); sys.path.insert(0, R+'scripts/analysis')
import random_world as rw
for f in ['rw-nodeath.json','rw-nd-pns1-k4.json','rw-nd-gp1-k4.json']:
    d=rw.load('results/mutate/'+f)
    H0=np.array(d['start_hp'],float)[:,None]
    cells=d['cells']; par=next(c for c in cells if c['kind']=='parent')
    L=lambda c,p: np.minimum(H0-np.array([[h for _,h in r] for r in c['res'][p]],float),H0)
    pn,ph=L(par,'one'),L(par,'heuristic')
    C=[((L(c,'one')-pn)-(L(c,'heuristic')-ph)).mean() for c in cells if c['kind']=='world' and c['pool']=='main' and c['k']==4]
    C=np.array(C)
    dn=[(np.array([[h for _,h in r] for r in c['res']['one']])<=0).mean() for c in cells if c['kind']=='world' and c['pool']=='main' and c['k']==4]
    print(f, d.get('settings',{}).get('net') if isinstance(d.get('settings'),dict) else '', 'worlds',len(C),'starts',H0.shape, 'res shape', np.array(par['res']['one'],dtype=object).shape, 'cost %+.2f (%.2f)'%(C.mean(),C.std(ddof=1)/np.sqrt(len(C))))
