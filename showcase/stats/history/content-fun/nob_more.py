import json, sys
R=''
sys.path[:0]=[R+'scripts/analysis', R+'scripts', R]
import mutate_monsters as mm
for f in ['gen-enemies-b1.json','gen-b1-sharp399-s1.json','gen-b1-sharp399-s2.json','gen-b1-gacalw-g99-s1.json','gen-b1-gacalw-g99-s2.json']:
    d=json.load(open(R+'results/mutate/'+f, encoding='utf-8'))
    rows,mods=d['rows'],d['settings']['mods']
    s=d['settings']; 
    nob=[r for r in rows if r['encounter']=='gremlin_nob']
    tt=mm.gen_table(nob,mods,'one'); v=tt['mechanics'].get('GE-AttackLoss-Damage')
    if v is None: print(f,'no row'); continue
    print(f,'seeds',s.get('seeds'),'net',s.get('net'),'n',tt['n'],'heur',round(v['heur_win'],3),'net',round(v['net_win'],3),'cost',[round(x,2) for x in v['cost']], 'heurlost',round(v['heur_lost'],2),'netlost',round(v['net_lost'],2))
