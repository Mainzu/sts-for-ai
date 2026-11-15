import subprocess, collections, datetime, sys
R='.'
P=[('10-23','10-24'),('10-25','10-28'),('10-29','10-31'),('11-01','11-02'),('11-03','11-05'),('11-06','11-09'),('11-10','11-12'),('11-13','11-14')]
def per(d):
    for i,(a,b) in enumerate(P):
        if a<=d<=b: return i
    return None
def cat(f):
    if not f.startswith('docs/'): return 'outside'
    if f.startswith('docs/research/'): return 'research'
    if f.startswith('docs/specs/'): return 'specs'
    if f=='docs/decisions.md': return 'decisions'
    if f=='docs/backlog.md': return 'backlog'
    return 'other'
p=subprocess.Popen(['git','-C',R,'log','-p','--no-merges','--no-renames','--format=@@C %H %ad','--date=format-local:%m-%d','--','*.md'],stdout=subprocess.PIPE)
W=collections.defaultdict(float); D=collections.defaultdict(float); newf=collections.defaultdict(set); unk=0
day=None;f=None;tot=0;outside=0;dele=0;days=collections.Counter()
for raw in p.stdout:
    l=raw.decode('utf-8','replace').rstrip('\n')
    if l.startswith('@@C '):
        day=l.split()[2]; continue
    if l.startswith('diff --git'): f=None; isnew=False; continue
    if l.startswith('new file mode'): isnew=True; continue
    if l.startswith('+++ '):
        f=l[6:] if l.startswith('+++ b/') else None
        if f and isnew and f.startswith('docs/research/'): newf[per(day)].add(f)
        continue
    if l.startswith('--- '): continue
    if f is None: continue
    if l.startswith('+'):
        n=len(l[1:].split()); c=cat(f); i=per(day)
        if i is None: unk+=n; continue
        W[(c,i)]+=n
        if c=='outside': outside+=n
        else: tot+=n; days[day]+=n
    elif l.startswith('-') and f.startswith('docs/'): dele+=len(l[1:].split())
print('docs',tot,'outside',outside,'deleted docs',dele,'unk',unk)
for c in ['research','specs','decisions','backlog','other','outside']:
    print(c,[round(W[(c,i)]/1000,1) for i in range(8)])
print('newresearch',[len(newf[i]) for i in range(8)])
print(sorted(days.items()))
