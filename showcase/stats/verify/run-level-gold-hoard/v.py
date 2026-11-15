import sys, os, json, statistics
R='.'
sys.path.insert(0,R+'/scripts')
import real_game_report as rg
runs=rg.all_runs()
print(len(runs))
# own stream per folder: per seed gold timeline, shop floors, gold drops inside shop
per={}
for name in sorted(os.listdir(rg.RECORDS)):
    f=os.path.join(rg.RECORDS,name)
    if not (os.path.isdir(f) and name[:1].isdigit()): continue
    with open(os.path.join(f,'states.jsonl'),encoding='utf-8') as fh:
        for l in fh:
            if not l.strip(): continue
            gs=json.loads(l)['msg'].get('game_state')
            if not gs or gs.get('seed') is None: continue
            s=per.setdefault(gs['seed'],{'shops':set(),'shopscreen':set(),'spent':0,'prev':None,'maxg':0,'roomtypes':set()})
            g=gs.get('gold'); fl=gs.get('floor')
            s['roomtypes'].add(gs.get('room_type'))
            if gs.get('room_type')=='ShopRoom': s['shops'].add(fl)
            if gs.get('screen_type')=='SHOP_SCREEN': s['shopscreen'].add(fl)
            if s['prev'] is not None and g is not None and g<s['prev'][0] and gs.get('room_type')=='ShopRoom':
                s['spent']+=s['prev'][0]-g
            if g is not None: s['prev']=(g,fl); s['last']=g; s['lastfloor']=fl
for i,r in enumerate(runs,1):
    s=per[r['seed']]
    r['n']=i; r['g']=s['last']; r['sh']=len(s['shops']); r['ss']=len(s['shopscreen']); r['sp']=s['spent']
    assert r['last'].get('gold')==s['last']
for a in (0,20):
    rs=[r for r in runs if rg.asc(r)==a]
    gs=[r['g'] for r in rs]
    print('asc',a,'n',len(rs),'runs',rs[0]['n'],rs[-1]['n'],'median',statistics.median(gs),'sum',sum(gs),
      'shops',sum(r['sh'] for r in rs),'shopscreens',sum(r['ss'] for r in rs),'runs w shop',sum(1 for r in rs if r['sh']),
      'spent in shop',sum(r['sp'] for r in rs))
    m=max(rs,key=lambda r:r['g']); print(' max',m['g'],'run',m['n'])
    b=[0]*5
    for g in gs: b[0 if g<150 else 1 if g<250 else 2 if g<350 else 3 if g<450 else 4]+=1
    print(' bins',b)
    print(' sorted', sorted((r['g'],r['n']) for r in rs)[-4:])
    print(' rules', sorted(set((r.get('run_rules'),r.get('fight_guard')) for r in rs)))
for r in runs:
    if r['n'] in (3,5,21): print(r['n'],r['g'],r['last'].get('floor'),r['sh'])
