import sys, json
sys.path.insert(0, r'scripts')
import real_game_report as r
runs = r.all_runs()
for i, x in enumerate(runs, 1):
    f = x.get('folder') if isinstance(x, dict) else None
    if i in (82,83,84): print(i, {k:(v if not isinstance(v,(list,dict)) else type(v).__name__) for k,v in (x.items() if isinstance(x,dict) else [])})
print(len(runs))
D = r'results/real-game/20261114-205554/decisions.jsonl'
runi = 0; prev = 0; rows = []
for l in open(D):
    d = json.loads(l)
    if d['floor'] < prev: runi += 1
    prev = d['floor']
    if runi == 1 and d['floor'] == 5 and 'options' in d and 'view' in d: rows.append(d)
print('decisions', len(rows), 'secs', round(sum(x.get('seconds',0) for x in rows),2), 'turns', max(x['turn'] for x in rows))
hp = {}
for x in rows: hp.setdefault(x['turn'], x['view']['player']['hp'])
print({t: hp[t] for t in sorted(hp) if t in (1,4,5,10,15,30,45,60,75,82,83,84)})
from collections import Counter
c = Counter(); start=None
for x in rows:
    mons = x['view']['monsters']
    act = x['options'][x['pick']]
    act = act if isinstance(act,str) else str(act)
    ts = [m for m in mons if m['name'].startswith('Shield') or 'Tsundere' in m['name']]
    alive = [ (m['name'],m['hp'],m['block']) for m in mons if m['hp']>0]
    if x['turn'] in (3,4,5,40,84) : print(x['turn'], alive, act)
    tsa = [m for m in ts if m['hp']>0]
    if tsa and tsa[0]['hp']==4:
        if start is None: start = x['turn']
        if '@' in act:
            card, t = act.split('@'); t=int(t); m = mons[t]
            c[(card, m['name'], 'blk' if m['block']>0 else 'noblk')] += 1
        else: c[(act,)] += 1
print('start', start); [print(k,v) for k,v in c.most_common()]
