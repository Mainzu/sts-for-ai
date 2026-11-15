import sys, statistics as S, collections
sys.path.insert(0, '.')
import load
from load import clean
D = [(n, s, d) for n, s, d in load.decisions() if 'turn' in d]
def show(n, s, d):
    v = d['view']; p = v['player']
    print(f"run {n} A{s[0]} floor {d['floor']} turn {d['turn']} {d['seconds']}s cut={d.get('cut')} opts={len(d['options'])} hp={p['hp']} en={p['energy']}")
    print('  hand', {clean(k): c for k, c in v['hand'].items()}, 'played', v.get('cards_played_this_turn'))
    print('  powers', p['powers'], 'relics', p['relics'], 'potions', p['potions'])
    print('  monsters', [(m['name'], m['hp'], m['powers']) for m in v['monsters'] if m['hp'] > 0])
    print('  line', d['line'])
for A in (0, 20):
    top = sorted([x for x in D if x[1][0] == A], key=lambda x: -x[2]['seconds'])[:6]
    for x in top: show(*x)
