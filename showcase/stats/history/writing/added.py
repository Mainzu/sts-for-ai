import collections,json,glob
P=[(1,'10-23','10-24'),(2,'10-25','10-28'),(3,'10-29','10-31'),(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
def per(d):
    for p,a,b in P:
        if a<=d<=b: return p
c=collections.Counter();d=None;ex=collections.defaultdict(list)
for l in open('added.txt'):
    l=l.strip()
    if l.startswith('@'): d=l[1:]
    elif l.endswith('.md'):
        k='research' if 'research' in l else 'specs'; c[(per(d),k)]+=1; ex[(per(d),k)].append(l.split('/')[-1])
for k in ('research','specs'): print(k,[c[(p,k)] for p in range(1,9)])
for p in range(1,9): print(p,ex[(p,'research')][:12])
fs=[json.load(open(f,encoding='utf-8')) for f in glob.glob('docs/claims/**/*.json',recursive=True)]
kc=collections.Counter()
for f in fs:
    ats=[f['at']]+[h['at'] for h in f['history']]
    a=min(x[:19] for x in ats); kc[per(a[5:10])]+=1
print('kb created',[kc[p] for p in range(1,9)])
