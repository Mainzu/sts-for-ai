import subprocess, re, collections
R='.'
def g(*a): return subprocess.run(['git','-C',R]+list(a),capture_output=True,text=True,encoding='utf-8',errors='replace').stdout
last={}
for l in g('log','--reverse','--format=%H|%ad','--date=format:%m-%d').split():
    h,d=l.split('|'); last[d]=h
def cnt(h,pat,paths):
    out=g('grep','-c','-E',pat,h,'--',*paths)
    return sum(int(x.rsplit(':',1)[1]) for x in out.splitlines() if x)
for d,h in last.items():
    rs=cnt(h,r'#\[test\]','*.rs')
    py=cnt(h,r'^\s*def test_','*.py')
    files=len(g('ls-tree','-r','--name-only',h).splitlines())
    rsf=[f for f in g('ls-tree','-r','--name-only',h).splitlines() if f.endswith('.rs')]
    print(d,h[:8],'rust_tests',rs,'py_tests',py,'files',files,'rs_files',len(rsf),'test_rs',sum(f.startswith('engine/tests/') for f in rsf))
