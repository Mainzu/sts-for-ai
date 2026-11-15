import sys, os, json, collections, statistics
R='.'
sys.path.insert(0, R+'/scripts')
import real_game_report as rg
REC=R+'/results/real-game'
runs=rg.all_runs()
print('runs',len(runs))
# index runs by folder in order of all_runs, with global number
byfolder=collections.defaultdict(list)
for i,r in enumerate(runs,1):
    r['n']=i; byfolder[r['folder']].append(r)
recs=[]  # (runno, asc, fight, powers:dict power->set monsters)
mismatch=0
for folder, rs in byfolder.items():
    fr=[r for r in rs if r['fights']]
    # split decisions by floor drop
    groups=[]; prev=None
    with open(os.path.join(REC,folder,'decisions.jsonl'),encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            d=json.loads(line)
            fl=d['floor']
            if prev is None or fl<prev: groups.append([])
            prev=fl
            if 'view' in d: groups[-1].append(d)
    if len(groups)!=len(fr): mismatch+=1; print('MISMATCH',folder,len(groups),len(fr),[r['n'] for r in rs])
    for r,g in zip(fr,groups):
        pw=collections.defaultdict(lambda: collections.defaultdict(set))
        asc_view=set()
        for d in g:
            asc_view.add(d['view'].get('ascension'))
            for m in d['view']['monsters']:
                ps=m.get('powers') or {}
                names = ps.keys() if isinstance(ps,dict) else [p if isinstance(p,str) else (p.get('id') or p.get('name')) for p in ps]
                for p in names: pw[d['floor']][p].add(m['name'])
        for ft in r['fights']:
            if ft['floor'] not in pw and not any(d['floor']==ft['floor'] for d in g): continue
            recs.append((r['n'], rg.asc(r), ft, pw.get(ft['floor'],{}), asc_view))
print('mismatch folders',mismatch)
for A in (0,20):
    sub=[x for x in recs if x[1]==A]
    print('ASC',A,'fights with decisions',len(sub),'runs',sorted(set(x[0] for x in sub))[:3],'..',max(x[0] for x in sub))
    loss=lambda ft: ft['hp_start']-ft['hp_end']
    lossA=lambda ft: ft['hp_start']-(ft['hp_after'] if ft.get('hp_after') is not None else ft['hp_end'])
    print(' all mean loss %.2f (after-heal %.2f)'%(statistics.mean(loss(x[2]) for x in sub), statistics.mean(lossA(x[2]) for x in sub)))
    agg=collections.defaultdict(list); owners=collections.defaultdict(collections.Counter)
    for x in sub:
        for p,ms in x[3].items():
            agg[p].append(x[2]); 
            for m in ms: owners[p][m]+=1
    for p,l in sorted(agg.items(), key=lambda kv:-statistics.mean(loss(f) for f in kv[1])):
        print('  %-22s n=%3d mean %.2f  after %.2f  won %d/%d  %s'%(p,len(l),statistics.mean(loss(f) for f in l),statistics.mean(lossA(f) for f in l),sum(f['won'] for f in l),len(l),dict(owners[p].most_common(4))))
