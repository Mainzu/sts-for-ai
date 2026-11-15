import subprocess,datetime,collections
R='.'
P=[(1,'10-23','10-24'),(2,'10-25','10-28'),(3,'10-29','10-31'),(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
def per(d):
    for p,a,b in P:
        if a<=d<=b: return p
tz=datetime.timezone(datetime.timedelta(hours=0))
pr=subprocess.Popen(['git','-C',R,'log','-p','--no-merges','--no-renames','--format=@@C %at','--','*.md'],stdout=subprocess.PIPE,text=True,encoding='utf-8',errors='replace')
add=collections.Counter();rem=collections.Counter();day=collections.Counter()
p=None;f=None
def cat(f):
    if f.startswith('docs/decisions'): return 'decisions'
    if f.startswith('docs/research'): return 'research notes'
    if f.startswith('docs/specs'): return 'specs'
    if f.startswith('docs/backlog'): return 'backlog'
    if f.startswith('docs/claims'): return 'kb facts'
    if f.startswith('docs/'): return 'other docs'
    return 'outside docs'
for l in pr.stdout:
    if l.startswith('@@C '):
        d=datetime.datetime.fromtimestamp(int(l[4:]),tz).strftime('%m-%d'); p=per(d)
    elif l.startswith('+++ '):
        f=l[6:].strip() if l.startswith('+++ b/') else None
    elif l.startswith('+') and f and p:
        n=len(l[1:].split()); add[(p,cat(f))]+=n; day[d]+=n
    elif l.startswith('-') and not l.startswith('---') and f and p:
        rem[p]+=len(l[1:].split())
cats=sorted({k[1] for k in add})
for c in cats: print(c,[add[(q,c)] for q in range(1,9)])
print('total added',[sum(add[(q,c)] for c in cats) for q in range(1,9)], sum(add.values()))
print('removed',[rem[q] for q in range(1,9)])
print(sorted(day.items()))
