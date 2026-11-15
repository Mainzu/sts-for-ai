import json
from collections import Counter
D = r'results/real-game/20261114-205554/decisions.jsonl'
runi = 0; prev = 0; rows = []
for l in open(D):
    d = json.loads(l)
    if d['floor'] < prev: runi += 1
    prev = d['floor']
    if runi == 1 and d['floor'] == 5 and 'options' in d and 'view' in d: rows.append(d)
print(Counter(x['turn'] for x in rows).most_common(5))
for x in rows:
    if x['turn'] in (1,2,3,4,40,82,83,84):
        v=x['view']; p=v['player']
        print(x['turn'], 'e',p['energy'],'hp',p['hp'],'hand',v['hand'],'opts',x['options'],'pick',x['pick'],'line',x.get('line'),'cut',x.get('cut'), [(m['name'],m['hp'],m['block'],m.get('moves')) for m in v['monsters']])
