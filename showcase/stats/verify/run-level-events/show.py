import pickle, collections, sys
V = pickle.load(open('visits.pkl','rb'))
print('A0 non-neow', sum(v['asc']==0 and v['key'][1]!='Neow' for v in V), 'A20', sum(v['asc']==20 and v['key'][1]!='Neow' for v in V))
want = sys.argv[1:]
for v in V:
    if v['key'][1] not in want: continue
    f, l, a = v['first'], v['last'], v['after']
    d = lambda k: (a or l)[k] - f[k] if (a or l)[k] is not None and f[k] is not None else None
    rel = set((a or l)['relics']) - set(f['relics'])
    dk = collections.Counter((a or l)['deck']); dk.subtract(collections.Counter(f['deck']))
    print('run', v['run'], 'A%d r%d' % (v['asc'], v['rules']), 'fl', v['key'][0], v['key'][1], 'dHP', d('hp'), 'dMHP', d('mhp'), 'dGold', d('gold'), 'relics+', rel, 'deck', {k: n for k, n in dk.items() if n}, 'after', (a or {}).get('st'), (a or {}).get('mons'))
    for b, o in v['screens']: print('    ', [t for t, _ in o])
