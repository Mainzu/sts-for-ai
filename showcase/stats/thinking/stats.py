"""Thinking-time statistics for the showcase. python -I stats.py"""
import sys, statistics as S, collections
sys.path.insert(0, '.')
import load
from load import clean
D = [(n, s, d) for n, s, d in load.decisions() if 'turn' in d]
A20 = [(n, d) for n, s, d in D if s[0] == 20]
A0 = [(n, d) for n, s, d in D if s[0] == 0]
r2 = lambda x: round(x, 2)

print('## 1 distribution')
for name, sub in (('A0', A0), ('A20', A20)):
    xs = sorted(d['seconds'] for n, d in sub)
    N = len(xs)
    print(name, 'n', N, 'runs', len({n for n, d in sub}), 'median', S.median(xs), 'mean', r2(S.mean(xs)),
          'p90', xs[int(.9 * N)], 'p99', xs[int(.99 * N)], 'max', xs[-1],
          'under1s', r2(sum(x < 1 for x in xs) / N), 'slowest10%share', r2(sum(xs[-N // 10:]) / sum(xs)),
          'total_h', r2(sum(xs) / 3600), 'cut', sum(d.get('cut', False) for n, d in sub), r2(sum(d.get('cut', False) for n, d in sub) / N))

def groups(sub, keyf, minn=30, minruns=4):
    g = collections.defaultdict(list)
    for n, d in sub:
        for k in keyf(d): g[k].append((n, d))
    out = []
    for k, ds in g.items():
        runs = len({n for n, d in ds})
        if len(ds) < minn or runs < minruns: continue
        w = [d['seconds'] for n, d in ds]
        out.append(dict(k=k, n=len(ds), runs=runs, mean=r2(S.mean(w)), median=r2(S.median(w)),
                        over5=r2(sum(x > 5 for x in w) / len(w)), cut=r2(sum(d.get('cut', False) for n, d in ds) / len(ds))))
    return sorted(out, key=lambda r: -r['mean'])

def pr(rows, top=12, bottom=4):
    for r in rows[:top]: print('  ', r)
    if len(rows) > top:
        print('   ...')
        for r in rows[-bottom:]: print('  ', r)

alive = lambda d: [m for m in d['view']['monsters'] if m['hp'] > 0 and not m.get('escaped')]
print('## 2 hand cards, A20'); pr(groups(A20, lambda d: {clean(k).rstrip('+') for k in d['view']['hand']}))
print('## 2b hand cards, A0'); pr(groups(A0, lambda d: {clean(k).rstrip('+') for k in d['view']['hand']}), 6, 3)
print('## 3 monsters, A20'); pr(groups(A20, lambda d: {clean(m['name']) for m in alive(d)}), 8, 5)
print('## 3b monsters alive count, A20'); pr(groups(A20, lambda d: {len(alive(d))}, 1, 1))
print('## 4 player powers, A20 (cut)'); pr(groups(A20, lambda d: set(d['view']['player']['powers'])), 6, 4)
print('## 5 action taken, A20'); pr(groups(A20, lambda d: {clean(d['options'][d['pick']][0]).split('@')[0].split(':')[0].rstrip('+')}), 8, 3)
print('## 6 relics, A20'); pr(groups(A20, lambda d: {clean(r[0]) for r in d['view']['player']['relics']}), 8, 4)
print('## 6b relics, A0'); pr(groups(A0, lambda d: {clean(r[0]) for r in d['view']['player']['relics']}), 6, 3)

print('## 7 worst A20 decisions')
for n, d in sorted(A20, key=lambda x: -x[1]['seconds'])[:6]:
    v = d['view']
    print(n, d['floor'], d['turn'], d['seconds'], d.get('cut'), {clean(k): c for k, c in v['hand'].items()},
          [(clean(m['name']), m['hp']) for m in alive(d)], v['player']['powers'], [clean(r[0]) for r in v['player']['relics']], d['line'])
print('## 7b worst A0 decisions')
for n, d in sorted(A0, key=lambda x: -x[1]['seconds'])[:3]:
    v = d['view']
    print(n, d['floor'], d['turn'], d['seconds'], d.get('cut'), {clean(k): c for k, c in v['hand'].items()},
          [(clean(m['name']), m['hp']) for m in alive(d)], d['line'])
# Which fights ate the most total thinking time (A20)
print('## 8 fight totals A20 (by run, floor)')
tot = collections.Counter(); mons = {}
for n, d in A20:
    tot[(n, d['floor'])] += d['seconds']; mons.setdefault((n, d['floor']), set()).update(clean(m['name']) for m in d['view']['monsters'])
for k, t in tot.most_common(6): print(k, r2(t), mons[k])
ft = sorted(tot.values()); print('fights', len(ft), 'median fight total', r2(S.median(ft)))
