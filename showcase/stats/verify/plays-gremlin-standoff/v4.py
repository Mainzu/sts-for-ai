import json
from collections import Counter
S = r'results/real-game/20261114-205554/states.jsonl'
SEED = -5085640134281314222
snaps = []
for l in open(S):
    d = json.loads(l); g = d['msg'].get('game_state')
    if not g or g.get('seed') != SEED or g.get('floor') != 5: continue
    c = g.get('combat_state')
    if not c: continue
    mons = [(m['name'], m['current_hp'], m['block'], m.get('is_gone')) for m in c['monsters']]
    hand = Counter(x['name'] for x in c['hand'])
    snaps.append((c['turn'], c['player']['energy'], c['player']['current_hp'], hand, mons))
print('snaps', len(snaps), 'turns', min(s[0] for s in snaps), max(s[0] for s in snaps))
plays = Counter(); sgturns=set()
for a, b in zip(snaps, snaps[1:]):
    if a[0] != b[0]: continue
    for card in ('Strike','Bash'):
        if b[3][card] < a[3][card] and b[1] < a[1]:
            drop = [i for i,(x,y) in enumerate(zip(a[4],b[4])) if (y[1]+y[2]) < (x[1]+x[2])]
            sg = a[4][1]
            tgt = drop[0] if drop else None
            key = (card, a[4][tgt][0] if tgt is not None else '?', ('blk' if tgt is not None and a[4][tgt][2]>0 else 'noblk'))
            if sg[1]==4: plays[key]+=1; sgturns.add(a[0])
            else: plays[('notSG4',)+key]+=1
for k,v in plays.most_common(): print(k,v)
print('turns with SG on 4 & plays', len(sgturns), min(sgturns), max(sgturns))
for s in snaps:
    if s[0] in (40,): print(s)
blk=Counter(s[4][2][2] for s in snaps if s[4][1][1]==4); print('mad#2 block during SG4', blk)
print('SG block', Counter(s[4][1][2] for s in snaps if s[4][1][1]==4))
