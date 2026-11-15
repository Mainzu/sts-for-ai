import json,collections,statistics as st
G=json.load(open('gathered.json'));R=[r for r in G['runs'] if r['model']]
def kind(r):
    if r['games'] is not None or r['parent']: return 'fine-tune (burst)'
    if r['n_train'] is not None: return 'from scratch, rounds'
    return 'other'
k=collections.defaultdict(collections.Counter); nt=collections.defaultdict(list); ep=collections.defaultdict(list); gm=collections.defaultdict(list)
for r in R:
    k[r['period']][kind(r)]+=1
    if r['n_train']: nt[r['period']].append(r['n_train'])
    if r['games']: gm[r['period']].append(r['games'])
    ep[r['period']].append(r['epochs'])
for p in range(1,9):
    print(p,dict(k[p]),'n_train',sorted(collections.Counter(nt[p]).items()),'games',sorted(collections.Counter(gm[p]).items())[:8],'epochs med',st.median(ep[p]) if ep[p] else None)
others=[r['run'] for r in R if kind(r)=='other'];print(len(others),others[:5])
cut='2026-10-29T22:32'
print('nets after product',sum(1 for r in R if r['created'][:16]>cut))
print('lr runs',[(r['run'],r['lr']) for r in G['runs'] if r['lr']])
