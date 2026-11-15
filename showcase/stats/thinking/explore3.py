import sys, statistics as S, collections
sys.path.insert(0, '.')
import load
from load import clean
D = [(n, s, d) for n, s, d in load.decisions() if 'turn' in d]
def base(m): return clean(m).split(' (')[0] if False else clean(m)
for A in (0, 20):
    sub = [d for n, s, d in D if s[0] == A]
    allm = S.mean(d['seconds'] for d in sub)
    print('==== A', A, len(sub), 'mean', round(allm, 2))
    for label, keyf in [('monster', lambda d: {clean(m['name']) for m in d['view']['monsters'] if m['hp'] > 0}),
                        ('hand', lambda d: {clean(k).rstrip('+') for k in d['view']['hand']}),
                        ('ppower', lambda d: set(d['view']['player']['powers'])),
                        ('mpower', lambda d: {p for m in d['view']['monsters'] if m['hp'] > 0 for p in m['powers']}),
                        ('relic', lambda d: {clean(r[0]) for r in d['view']['player']['relics']}),
                        ('potion', lambda d: {clean(p) for p in d['view']['player']['potions']}),
                        ('picked', lambda d: {clean(d['options'][d['pick']][0]).split('@')[0].rstrip('+')}),
                        ]:
        g = collections.defaultdict(list)
        for d in sub:
            for k in keyf(d): g[k].append(d)
        rows = []
        for k, ds in g.items():
            if len(ds) < 30 or len(ds) > len(sub) - 30: continue
            ids = {id(x) for x in ds}
            wo = [x['seconds'] for x in sub if id(x) not in ids]
            w = [x['seconds'] for x in ds]
            rows.append((S.mean(w) - S.mean(wo), k, len(ds), round(S.mean(w), 2), round(S.mean(wo), 2), round(S.median(w), 2), round(sum(x.get('cut', False) for x in ds) / len(ds), 3), len({(n) for n,s,dd in D if dd in ds}) if False else ''))
        rows.sort(reverse=True)
        print('--', label)
        for r in rows[:10]: print('  ', round(r[0], 2), r[1:])
        print('   ...lowest')
        for r in rows[-4:]: print('  ', round(r[0], 2), r[1:])
