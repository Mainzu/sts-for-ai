import json
d=json.load(open('results/pack_cards/act1/table.json'))
print({k:v for k,v in d.items() if k!='rows'})
rows=d['rows'];print(len(rows))
for n,r in sorted(rows.items(),key=lambda x:x[1]['tsl1_won']['all']['d']):
    p=r['plain_won']['all'];t=r['tsl1_won']['all']
    print(f"{n:16s} plain {p['d']:+.3f}({p['se']:.3f}) tsl1 {t['d']:+.3f}({t['se']:.3f}) hpT {r['tsl1_hp_end']['all']['d']:+.2f} hpP {r['plain_hp_end']['all']['d']:+.2f} play {r['heur_play_rate']:.2f} cells {t['cells']} {r.get('costs_tsl1')} {r.get('costs_plain')} | {r['prediction']}")
