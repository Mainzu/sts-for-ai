import json,glob,collections,subprocess,sys
R='.'
fs=[json.load(open(f,encoding='utf-8')) for f in glob.glob(R+'/docs/claims/**/*.json',recursive=True)]
chk=subprocess.run([sys.executable,'-I',__import__('os').path.expanduser('~/.claude/skills/kb/kb.py'),'check'],cwd=R,capture_output=True,text=True,encoding='utf-8').stdout
sus={l.split(' [')[0] for l in chk.splitlines() if '[suspect]' in l}
print('suspect lines',len(sus), collections.Counter(l.split('[')[1].split(']')[0] for l in chk.splitlines() if '[' in l))
A=collections.defaultdict(collections.Counter)
for f in fs:
    a=f['key'].split('/')[0]; A[a][f['status']]+=1
    if f['key'] in sus: A[a]['suspect']+=1
    if f['rev']>1: A[a]['revised']+=1
    A[a]['revs']+=f['rev']
    if f['flags']: A[a]['flagged']+=1
for a,c in sorted(A.items(),key=lambda x:-sum(x[1][k] for k in ('active','retired'))): print(a,dict(c))
print(collections.Counter(f['status'] for f in fs))
for f in sorted(fs,key=lambda f:-f['rev'])[:6]: print(f['rev'],f['key'],f['value'][:120])
print(json.dumps(fs[0]['history'][:1])[:300] if fs[0]['history'] else '')
h=[x for f in fs for x in f['history']]; print(h[0].keys() if h else None)
