import os,json,csv,datetime as dt,collections,statistics as S
B='.'
P=[('10-23','10-24'),('10-25','10-28'),('10-29','10-31'),('11-01','11-02'),('11-03','11-05'),('11-06','11-09'),('11-10','11-12'),('11-13','11-14')]
def per(d):
    for i,(a,b) in enumerate(P):
        if a<=d[:5]<=b: return i
    return None
grid=collections.OrderedDict()
def add(kind,d):
    p=per(d); 
    if p is None: return
    grid.setdefault(kind,[0]*8)[p]+=1
for r in csv.DictReader(open(B+'/runs/index.csv')): add('training runs',r['date'][5:10])
for l in open(B+'/results/ladder/log.jsonl'): add('ladder tests',json.loads(l)['when'][5:10])
for k in ['gauntlet','mutate','boss_replay','depth','probes','families','real-game','exact-puzzles','adapt','packs','gen_powers','depth_probe']:
    for f in os.listdir(B+'/results/'+k):
        if f.endswith('.json'):
            add(k,dt.datetime.fromtimestamp(os.stat(B+'/results/'+k+'/'+f).st_mtime).strftime('%m-%d'))
for k,v in grid.items(): print('%-14s'%k,v,sum(v))
print('total',[sum(v[i] for v in grid.values()) for i in range(8)])
json.dump(grid,open('heat.json','w'))
