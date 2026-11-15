import pickle
recs=pickle.load(open('recs.pkl','rb'))
for pl in ['runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt@hpb0.01','heuristic']:
  print('==',pl)
  for r in sorted(recs,key=lambda r:r['when']):
    s=r['settings']
    if s['player']!=pl or s['two_turn']: continue
    q=[x for x in r['seqs'] if x[0]<500]
    if len(q)<500: continue
    print(r['when'],r['src'],r['file'][:70],sorted(k for k in s if k not in('player','shape','rest','seed','two_turn')),round(sum(x[1] for x in q)/500,3))
