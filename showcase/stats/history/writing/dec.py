import subprocess,re,collections,datetime,json,sys
R='.'
P=[(1,'10-23','10-24'),(2,'10-25','10-28'),(3,'10-29','10-31'),(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
def per(d):
    for p,a,b in P:
        if a<=d<=b: return p
out=subprocess.run(['git','-C',R,'blame','--line-porcelain','HEAD','--','docs/decisions.md'],capture_output=True,text=True,encoding='utf-8').stdout
lines=[];cur={}
for l in out.split('\n'):
    if l.startswith('author-time '): cur['t']=int(l.split()[1])
    elif l.startswith('author-tz '): cur['tz']=l.split()[1]
    elif l.startswith('\t'): lines.append((cur.get('t'),l[1:]))
tz=datetime.timezone(datetime.timedelta(hours=0))
secs=[]
for t,l in lines:
    if l.startswith('## '):
        secs.append({'h':l[3:],'d':datetime.datetime.fromtimestamp(t,tz).strftime('%m-%d %H:%M'),'w':0,'n':0})
    elif secs:
        secs[-1]['w']+=len(l.split())
def who(h):
    h=h.lower()
    if "owner's behalf" in h: return 'on the owner\'s behalf'
    if 'owner away' in h: return 'owner away (Claude)'
    if re.search(r'\(owner( present)?[,)]',h) or 'owner present' in h or "(owner's" in h: return 'owner'
    return 'unmarked'
c=collections.Counter();w=collections.Counter();ws=collections.defaultdict(int)
for s in secs:
    s['p']=per(s['d'][:5]); s['who']=who(s['h'])
    c[(s['p'],s['who'])]+=1; ws[s['p']]+=s['w']
print(len(secs))
for p in range(1,9):
    print(p,{k[1]:v for k,v in c.items() if k[0]==p}, 'words',ws[p], 'n',sum(v for k,v in c.items() if k[0]==p))
print(collections.Counter(s['who'] for s in secs))
for s in sorted(secs,key=lambda s:-s['w'])[:8]: print(s['w'],s['d'],s['h'][:150])
# per day
dd=collections.Counter(s['d'][:5] for s in secs); print(sorted(dd.items()))
json.dump(secs,open('secs.json','w'),indent=0)
