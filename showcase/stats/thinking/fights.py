"""Total thinking time per fight, by encounter (A20 pooled). python -I fights.py"""
import sys, statistics as S, collections
sys.path.insert(0, 'scripts')
import real_game_report as R
rs = R.all_runs()
g = collections.defaultdict(list)
for i, r in enumerate(rs):
    if R.asc(r) != 20: continue
    for f in r['fights']:
        key = '+'.join(sorted(set(m.replace('gen:', '') for m in f['monsters'])))
        g[(f['group'], key)].append((sum(f.get('think_s') or []), f['decisions'], i + 1, f['floor'], f['won']))
rows = []
for k, v in g.items():
    if len(v) < 3: continue
    rows.append((round(S.median(x[0] for x in v), 1), k, len(v), round(max(x[0] for x in v), 1), round(S.median(x[1] for x in v))))
for r in sorted(rows, reverse=True): print(r)
print([x for x in g[('hallway','JawWorm+SpikeSlime_M')]] if ('hallway','JawWorm+SpikeSlime_M') in g else '')
for k, v in g.items():
    for x in v:
        if x[2] == 49 and x[3] == 10: print(k, x)
