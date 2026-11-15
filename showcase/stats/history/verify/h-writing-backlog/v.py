import subprocess, re, collections, datetime
R='.'
tz=datetime.timezone(datetime.timedelta(hours=0))
def g(*a): return subprocess.run(['git','-C',R]+list(a),capture_output=True,text=True,encoding='utf-8',errors='replace').stdout
log=g('log','--reverse','--format=%H %at','--','docs/backlog.md').split()
PATS={'num':re.compile(r'^\d+\. \*\*([a-z0-9][a-z0-9-]*)\*\*'),
      'any':re.compile(r'^(?:-|\d+\.) \*\*([a-z0-9][a-z0-9-]*)\*\*')}
def cands(t,p):
    out=set(); on=False
    for l in t.splitlines():
        if l.startswith('## '): on = l.strip()=='## Candidates'; continue
        if on:
            m=p.match(l)
            if m: out.add(m.group(1))
    return out
texts=[]
for i in range(0,len(log),2):
    h,t=log[i],int(log[i+1]); d=datetime.datetime.fromtimestamp(t,tz).strftime('%m-%d')
    texts.append((d,g('show',f'{h}:docs/backlog.md')))
print('commits',len(texts))
for k,p in PATS.items():
    prev=set(); seen=set(); op=collections.Counter(); rm=collections.Counter(); end={}
    for d,t in texts:
        c=cands(t,p); op[d]+=len(c-prev); rm[d]+=len(prev-c); seen|=c; prev=c; end[d]=len(c)
    print('==',k,'distinct',len(seen),'opened',sum(op.values()),'removed',sum(rm.values()),'final',len(prev))
    for d in sorted(end): print(' ',d,'end',end[d],'op',op[d],'rm',rm[d])
