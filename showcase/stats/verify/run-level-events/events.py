import pickle, collections, json
D = pickle.load(open('dump.pkl','rb')); RU = pickle.load(open('runs.pkl','rb'))
visits = []
for r in RU:
    rows = D.get(r['seed'], [])
    cur = None
    for x in rows:
        if x['st'] == 'EVENT' and x['ev']:
            key = (x['floor'], x['ev'])
            if cur is None or cur['key'] != key:
                cur = dict(run=r['n'], asc=r['asc'], rules=r['rules'], key=key, screens=[], first=x, after=None)
                visits.append(cur)
            if not cur['screens'] or cur['screens'][-1][1] != x['opts'] or cur['screens'][-1][0] != x['body']:
                cur['screens'].append((x['body'], x['opts']))
            cur['last'] = x
        if cur is not None and x['floor'] == cur['key'][0] and not x['combat']:
            cur['after'] = x
        if cur is not None and x['combat'] and x['floor'] == cur['key'][0]:
            cur.setdefault('fight', x['mons'])
pickle.dump(visits, open('visits.pkl','wb'))
c = collections.Counter((v['key'][1], v['asc']) for v in visits)
for k in sorted(c): print(k, c[k])
