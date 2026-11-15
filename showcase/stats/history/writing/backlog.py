import subprocess,re,datetime,collections
R='.'
P=[(1,'10-23','10-24'),(2,'10-25','10-28'),(3,'10-29','10-31'),(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
def per(d):
    for p,a,b in P:
        if a<=d<=b: return p
tz=datetime.timezone(datetime.timedelta(hours=0))
log=subprocess.run(['git','-C',R,'log','--reverse','--format=%H %at','--','docs/backlog.md'],capture_output=True,text=True).stdout.split('\n')
first={};last={};prev=set();opened=collections.Counter();gone=collections.Counter();size=[]
pat=re.compile(r'^(\d+)\. \*\*([a-z0-9-]+)\*\*',re.M)
for l in log:
    if not l: continue
    h,t=l.split(); d=datetime.datetime.fromtimestamp(int(t),tz).strftime('%m-%d')
    txt=subprocess.run(['git','-C',R,'show',h+':docs/backlog.md'],capture_output=True,text=True,encoding='utf-8',errors='replace').stdout
    cand=txt.split('## Candidates')[1].split('## Parked')[0] if '## Candidates' in txt else txt
    cur={m.group(2) for m in pat.finditer(cand)}
    for n in cur-prev: opened[d]+=1; first.setdefault(n,d)
    for n in prev-cur: gone[d]+=1
    prev=cur; size.append((d,len(cur)))
days=sorted(set(opened)|set(gone))
end={}
for d,s in size: end[d]=s
for d in days: print(d,'opened',opened[d],'gone',gone[d],'end size',end.get(d))
print('distinct names',len(first),'at end',len(prev))
