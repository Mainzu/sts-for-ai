import subprocess, re, datetime, collections
R='.'
out=subprocess.run(['git','-C',R,'blame','--line-porcelain','HEAD','--','docs/decisions.md'],capture_output=True,text=True,encoding='utf-8').stdout
ents=[];t=None;c=None;tz=None
for ln in out.split('\n'):
    if ln.startswith('author-time '): t=int(ln.split()[1])
    elif ln.startswith('committer-time '): c=int(ln.split()[1])
    elif ln.startswith('\t'):
        s=ln[1:]
        if s.startswith('## '): ents.append((t,c,s))
P=[('10-23','10-24'),('10-25','10-28'),('10-29','10-31'),('11-01','11-02'),('11-03','11-05'),('11-06','11-09'),('11-10','11-12'),('11-13','11-14')]
def per(d):
    for i,(a,b) in enumerate(P):
        if a<=d<=b: return i+1
tz=datetime.timezone(datetime.timedelta(hours=0))
grid=collections.Counter();days=collections.Counter();pt=collections.Counter();diff=0
for t,c,s in ents:
    d=datetime.datetime.fromtimestamp(t,tz).strftime('%m-%d'); dc=datetime.datetime.fromtimestamp(c,tz).strftime('%m-%d')
    if per(d)!=per(dc): diff+=1
    p=per(d); low=s.lower()
    if "on the owner's behalf" in low or 'on the owner’s behalf' in low: w='roles'
    elif 'owner away' in low: w='away'
    elif re.search(r'\(owner',low): w='owner'
    elif re.match(r'## lane .* (opened|closed)',low): w='lane'
    elif d<'10-29': w='owner'
    else: w='untagged'
    grid[(w,p)]+=1;days[d]+=1;pt[p]+=1
print(len(ents),'author/committer period differ',diff)
for w in ['owner','away','roles','lane','untagged']:
    print(w,[grid[(w,p)] for p in range(1,9)],sum(grid[(w,p)] for p in range(1,9)))
print(dict(pt)); print(days.most_common(3))
for t,c,s in ents:
    d=datetime.datetime.fromtimestamp(t,tz).strftime('%m-%d %H:%M')
    low=s.lower()
    if '11-03'>d>='10-29' and 'behalf' not in low and 'owner away' not in low and not re.match(r'## lane',low): print(d,s)
