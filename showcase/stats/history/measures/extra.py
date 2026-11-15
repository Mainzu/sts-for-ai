import csv,json,os,re,collections,statistics as S
B='.'
xs=[];ys=[]
for r in csv.DictReader(open(B+'/runs/index.csv')):
    if r['bench_version']=='1' and r['date']>='2026-10-25':
        xs.append(float(r['tight_train_win']));ys.append(float(r['tight_held_out_win']))
print('n',len(xs),'r %.2f'%S.correlation(xs,ys),'sd held %.3f'%S.stdev(ys))
for f in ['net1029-hpb0.01.json','heuristic.json','net1029-hpb0.01-b500.json','heuristic-b500.json']:
    p=B+'/results/gauntlet/'+f
    if os.path.exists(p):
        d=json.load(open(p));s=d['sequences'];print(f,len(s),s[0]['i'],sum(all(x['won'] for x in q['floors']) and len(q['floors'])==11 for q in s)/len(s))
# seed spread block A, 3 seeds, P6
rows=json.load(open('gauntlet_rows.json'))
keys=collections.Counter(r[5] for r in rows); main=keys.most_common(1)[0][0]
g=collections.defaultdict(dict)
for t,b,f,n,c,k,pl in rows:
    if k!=main or n!=500 or 'b500' in f: continue
    if json.load(open(B+'/results/gauntlet/'+f))['sequences'][0]['i']!=0: continue
    m=re.search(r'-s(\d+)(?=[-.])',f)
    if not m: continue
    rec=re.sub(r'^\d{4}-\d\d-\d\d-','',f[:m.start()])+re.sub(r'-[0-9a-f]{7}(?=[-.])','',f[m.end():]).replace('.json','')
    g[rec].setdefault(m.group(1),(c,t))
allsp=[]
for rec,ss in sorted(g.items()):
    if len(ss)<2: continue
    cs=[v[0] for v in ss.values()]; sp=max(cs)-min(cs); allsp.append(sp)
    print('%.3f'%sp,rec,len(ss),{s:v[0] for s,v in ss.items()},min(v[1] for v in ss.values()))
print('median spread',S.median(allsp),len(allsp))
