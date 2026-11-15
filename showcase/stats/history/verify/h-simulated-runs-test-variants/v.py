import json,os,datetime,glob
G='results/gauntlet/'
for f in sorted(glob.glob(G+'net1029-hpb0.01*.json')):
    d=json.load(open(f))
    s=d.get('settings',{});q=d.get('sequences',[])
    n=len(q)
    cl=sum(1 for x in q if x['floors'] and len(x['floors'])==len(s.get('shape',[])) and all(fl['won'] for fl in x['floors']))
    idx=[x['i'] for x in q]
    mt=datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%m-%d %H:%M')
    rest={k:v for k,v in s.items() if k not in('shape',)}
    print(os.path.basename(f),mt,n,cl,round(cl/n,3) if n else None,min(idx) if idx else '',max(idx) if idx else '',len(s.get('shape',[])),rest)
