import subprocess, datetime as dt
R='.'
def g(*a,inp=None): return subprocess.run(['git','-C',R,*a],capture_output=True,input=inp).stdout
log=g('log','--first-parent','main','--format=%H %ct').decode().split('\n')
cs=[(l.split()[0],int(l.split()[1])) for l in log if l.strip()]
tz=dt.timezone(dt.timedelta(hours=0))
print('commits',len(g('rev-list','main').split()))
for d in range(23):
    day=dt.date(2026,10,23)+dt.timedelta(days=d)
    end=dt.datetime(day.year,day.month,day.day,tzinfo=tz)+dt.timedelta(days=1)
    c=[h for h,t in cs if t<end.timestamp()]
    if not c: print(day,'none'); continue
    h=c[0]
    tree=g('ls-tree','-r',h).decode('utf-8','replace').split('\n')
    tot={'rs':0,'py':0}; blobs=[]
    for l in tree:
        if not l: continue
        meta,p=l.split('\t',1)
        ext=p.rsplit('.',1)[-1]
        if ext in tot and meta.split()[1]=='blob': blobs.append((ext,meta.split()[2]))
    out=g('cat-file','--batch',inp=''.join(b+'\n' for _,b in blobs).encode())
    i=0
    for ext,b in blobs:
        nl=out.index(b'\n',i); size=int(out[i:nl].split()[2]); data=out[nl+1:nl+1+size]; i=nl+1+size+1
        tot[ext]+=data.count(b'\n')+(1 if data and not data.endswith(b'\n') else 0)
    print(day.strftime('%m-%d'),tot['rs'],tot['py'],h[:8])
