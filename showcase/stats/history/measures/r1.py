import csv,json,os,collections
B='runs'
P=[('10-23','10-24'),('10-25','10-28'),('10-29','10-31'),('11-01','11-02'),('11-03','11-05'),('11-06','11-09'),('11-10','11-12'),('11-13','11-14')]
def per(d):
    for i,(a,b) in enumerate(P):
        if a<=d<=b: return i+1
rows=list(csv.DictReader(open(B+'/index.csv')))
by=collections.defaultdict(list)
for r in rows: by[per(r['date'][5:10])].append(r)
for p in sorted(by,key=lambda x:(x is None,x)):
    rs=by[p]
    bv=collections.Counter(r['bench_version'] for r in rs)
    print('P',p,len(rs),'bench',dict(bv),'feat',dict(collections.Counter(r['feature_format'] for r in rs)))
    for v in bv:
        w=[(float(r['tight_held_out_win']),r['run']) for r in rs if r['bench_version']==v and r['tight_held_out_win']]
        rg=[(float(r['tight_held_out_regret']),r['run']) for r in rs if r['bench_version']==v and r['tight_held_out_regret']]
        if w: print('   v',v,'best win',max(w),'n',len(w), 'best regret',min(rg) if rg else None)
# rules versions
rv={}
for d in sorted(os.listdir(B)):
    f=os.path.join(B,d,'run.json')
    if os.path.exists(f):
        try: j=json.load(open(f))
        except: continue
        c=j.get('created','')[:16]; v=j.get('rules_version')
        if v and c: rv.setdefault(v,[]).append(c)
for v,cs in sorted(rv.items(),key=lambda x:min(x[1])): print(v,min(cs),max(cs),len(cs))
