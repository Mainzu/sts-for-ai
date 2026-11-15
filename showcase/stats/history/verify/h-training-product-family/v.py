import json,os,glob,collections
R=''
P='2026-10-29-seed-check-r2-s1-1a789b2'
pc=json.load(open(R+'runs/'+P+'/run.json'))['created']
runs={}
for d in sorted(os.listdir(R+'runs')):
    p=R+'runs/'+d
    if not os.path.isdir(p): continue
    rj=p+'/run.json'
    if not os.path.exists(rj): continue
    r=json.load(open(rj)); r['has_model']=os.path.exists(p+'/model.pt')
    rd=p+'/round.json'
    r['round']=json.load(open(rd)) if os.path.exists(rd) else None
    r['cfgtxt']=open(p+'/config.json').read() if os.path.exists(p+'/config.json') else ''
    runs[d]=r
print('runs with run.json',len(runs),'with model',sum(r['has_model'] for r in runs.values()))
later=[d for d,r in runs.items() if r['created']>pc and r['has_model']]
same=[d for d,r in runs.items() if r['created']==pc]
print('created after product, with model:',len(later), 'created >= :', sum(1 for r in runs.values() if r['created']>=pc and r['has_model']))
print('last created', max(r['created'] for r in runs.values()))
print('s1-r10', runs.get('2026-10-28-score+branch-s1-r10-3c58554',{}).get('created'))
# dataset parent_model
dsparent={}
for m in glob.glob(R+'datasets/*/manifest.json'):
    j=json.load(open(m)); dsparent[os.path.basename(os.path.dirname(m))]=j.get('parent_model')
# descendants: parent_run chain, or any dataset whose parent_model descends, or config mentions P
desc=set([P]);changed=True
while changed:
    changed=False
    for d,r in runs.items():
        if d in desc: continue
        pr=(r['round'] or {}).get('parent_run')
        hit= pr in desc or any(dsparent.get(x) in desc for x in r.get('datasets',[])) or P in r['cfgtxt']
        if hit: desc.add(d);changed=True
print('descendants',len(desc)-1)
print('mention P in config', sum(P in r['cfgtxt'] for r in runs.values()))
byday=collections.Counter(runs[d]['created'][:10] for d in desc if d!=P); print(sorted(byday.items()))
print('---full-text pass')
def txt(d):
    s=''
    for f in ('config.json','round.json','run.json'):
        p=R+'runs/'+d+'/'+f
        if os.path.exists(p): s+=open(p).read()
    return s
T={d:txt(d) for d in runs}
dsman={os.path.basename(os.path.dirname(m)):open(m).read() for m in glob.glob(R+'datasets/*/manifest.json')}
desc=set([P]);changed=True
while changed:
    changed=False
    descds={k for k,v in dsman.items() if any(x in v for x in desc)}
    for d in runs:
        if d in desc: continue
        if any(x in T[d] for x in desc) or any(k in T[d] for k in descds):
            desc.add(d);changed=True
print('transitive descendants',len(desc)-1)
direct=[d for d in runs if d!=P and (P in T[d] or any(k in T[d] for k in {k for k,v in dsman.items() if P in v}))]
print('direct',len(direct))
print(collections.Counter(runs[d]['created'][:10] for d in direct))
print('later-with-model that are direct', sum(1 for d in direct if d in later))
