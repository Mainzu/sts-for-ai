import subprocess,re,collections
R='.'
def g(*a): return subprocess.run(['git','-C',R]+list(a),capture_output=True,text=True,encoding='utf-8',errors='replace').stdout
C='39de9ebf'
files=g('ls-tree','-r','--name-only',C).split('\n')
tot=collections.Counter(); tests=0; nonblank=collections.Counter(); per={}
for f in files:
    ext=f.rsplit('.',1)[-1] if '.' in f else ''
    if ext not in('rs','py'):continue
    t=g('show',f'{C}:{f}'); n=len(t.splitlines()); tot[ext]+=n; per[f]=n
    nonblank[ext]+=sum(1 for l in t.splitlines() if l.strip())
    if ext=='rs': tests+=len(re.findall(r'#\[test\]',t))
print(tot,nonblank,tests)
for f,n in sorted(per.items()): print(n,f)
print(g('show','--stat','--format=%h %s','40b4f73b'))
# numstat sum
add=collections.Counter()
for l in g('log','--numstat','--format=','5003b824^..'+C if False else C).splitlines():
    p=l.split('\t')
    if len(p)==3 and p[0]!='-':
        e=p[2].rsplit('.',1)[-1]
        if e in('rs','py'): add[e]+=int(p[0])-int(p[1])
print('numstat',add)
