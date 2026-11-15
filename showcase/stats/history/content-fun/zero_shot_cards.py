# Act 1 cards the net never trained on (results/pack_cards/act1/table.json, jobs 0428-0431, 2026-11-07)
import json
R=''
d=json.load(open(R+'results/pack_cards/act1/table.json'))
rows=sorted(d['rows'].items(), key=lambda kv: kv[1]['tsl1_won']['all']['d'])
for k,v in rows:
    w=v['tsl1_won']['all']; h=v['tsl1_hp_end']['all']
    print(f"{k:16s} lead {w['d']:+.3f} ({w['se']:.3f}) hp {h['d']:+.2f} ({h['se']:.2f}) cells {w['cells']} heurplays {v['heur_play_rate']:.2f} pred {v['prediction']} costs {v.get('costs_tsl1')}")
print(len(rows), d['net'], d['seeds'])
