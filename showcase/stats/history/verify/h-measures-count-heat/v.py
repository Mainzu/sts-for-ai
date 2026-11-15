import csv,json,os,datetime,collections
R=''
P=[('10-23','10-24'),('10-25','10-28'),('10-29','10-31'),('11-01','11-02'),('11-03','11-05'),('11-06','11-09'),('11-10','11-12'),('11-13','11-14')]
def per(md):
    for i,(a,b) in enumerate(P):
        if a<=md<=b: return i
    return None
tz=datetime.timezone(datetime.timedelta(hours=0))
c=collections.defaultdict(lambda:[0]*8); miss=collections.Counter()
for r in csv.DictReader(open(R+'runs/index.csv')):
    p=per(r['date'][5:]); 
    if p is None: miss['run']+=1
    else: c['runs'][p]+=1
# run dirs with run.json mtime
dirs=[d for d in os.listdir(R+'runs') if os.path.isdir(R+'runs/'+d)]
dd=[0]*8
for d in dirs:
    p=per(d[5:10]); 
    if p is not None: dd[p]+=1
print('rundirs by name',len(dirs),dd)
for l in open(R+'results/ladder/log.jsonl'):
    j=json.loads(l); p=per(j['when'][5:10]); c['ladder'][p]+=1
top=collections.Counter(); rec=collections.Counter()
for k in sorted(os.listdir(R+'results')):
    d=R+'results/'+k
    if not os.path.isdir(d) or k=='real-game': continue
    for f in os.listdir(d):
        fp=d+'/'+f
        if f.endswith('.json') and os.path.isfile(fp):
            t=datetime.datetime.fromtimestamp(os.path.getmtime(fp),tz).strftime('%m-%d')
            p=per(t)
            if p is None: miss[k]+=1
            else: c[k][p]+=1
    for root,ds,fs in os.walk(d):
        rec[k]+=sum(f.endswith('.json') for f in fs)
for k,v in c.items(): print(k,v,sum(v))
print('miss',miss); print('recursive json',rec)
