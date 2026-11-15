import subprocess, collections, datetime as dt
out = subprocess.run(['git','-C','.','log','main','--name-only','--format=@@%H %at %ct %P'],capture_output=True,text=True,encoding='utf-8').stdout
P=[('10-23','10-24'),('10-25','10-28'),('10-29','10-31'),('11-01','11-02'),('11-03','11-05'),('11-06','11-09'),('11-10','11-12'),('11-13','11-14')]
def per(ts):
    d=(dt.datetime.utcfromtimestamp(int(ts))+dt.timedelta(hours=0)).strftime('%m-%d')
    for i,(a,b) in enumerate(P):
        if a<=d<=b: return i
    return None
cnt=collections.defaultdict(lambda:[0]*8); cntc=collections.defaultdict(lambda:[0]*8)
ncom=0; cur=None; files=set(); bad=0; pc=[0]*8
def flush():
    global bad
    if cur is None: return
    pa,pc_=per(cur[1]),per(cur[2])
    if pa is None: bad+=1; return
    pc[pa]+=1
    for f in files:
        if f.endswith(('.rs','.py')):
            cnt[f][pa]+=1
            if pc_ is not None: cntc[f][pc_]+=1
for line in out.splitlines():
    if line.startswith('@@'):
        flush(); cur=line[2:].split(); files=set(); ncom+=1
    elif line.strip(): files.add(line.strip())
flush()
print(ncom,bad,pc)
for f,v in sorted(cnt.items(),key=lambda x:-sum(x[1]))[:14]: print(f,sum(v),v, 'commitdate',cntc[f])
