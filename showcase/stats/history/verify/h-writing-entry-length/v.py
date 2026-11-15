import subprocess,datetime,statistics as st,re
R='.'
out=subprocess.run(['git','-C',R,'blame','--line-porcelain','HEAD','--','docs/decisions.md'],capture_output=True,text=True,encoding='utf-8').stdout
lines=[];at=ct=None
for l in out.split('\n'):
    if l.startswith('author-time '): at=int(l.split()[1])
    elif l.startswith('committer-time '): ct=int(l.split()[1])
    elif l.startswith('\t'): lines.append((l[1:],at,ct))
tz=datetime.timezone(datetime.timedelta(hours=0))
P=[('10-23','10-24'),('10-25','10-28'),('10-29','10-31'),('11-01','11-02'),('11-03','11-05'),('11-06','11-09'),('11-10','11-12'),('11-13','11-14')]
def per(d):
    for i,(a,b) in enumerate(P):
        if a<=d<=b: return i+1
ents=[];cur=None
for t,a,c in lines:
    if t.startswith('## '):
        cur=[t[3:],a,c,0];ents.append(cur)
    elif cur: cur[3]+=len(t.split())
import sys
mode=sys.argv[1] if len(sys.argv)>1 else 'a'
by={}
for e in ents:
    ts=e[1] if mode=='a' else e[2]
    d=datetime.datetime.fromtimestamp(ts,tz).strftime('%m-%d')
    by.setdefault(per(d),[]).append((e[3],e[0],d))
print(len(ents),sum(e[3] for e in ents))
for p in sorted(by):
    w=[x[0] for x in by[p]]
    m=max(by[p])
    print(p,len(w),st.median(w),m)
