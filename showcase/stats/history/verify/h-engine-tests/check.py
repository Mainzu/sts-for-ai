import subprocess, re, collections
R='.'
def g(*a): return subprocess.run(['git','-C',R,*a],capture_output=True,text=True,encoding='utf-8',errors='replace').stdout
last={}
for line in g('log','--first-parent','main','--format=%H %cI').splitlines():
    h,d=line.split(); day=d[5:10]
    if day not in last: last[day]=h  # newest first
for day in sorted(last):
    h=last[day]
    rs=g('grep','-c',r'#\[test\]',h,'--','*.rs')
    py=g('grep','-cE',r'^\s*(async\s+)?def test_',h,'--','*.py')
    pyall=g('grep','-c',r'def test_',h,'--','*.py')
    s=lambda t: sum(int(l.rsplit(':',1)[1]) for l in t.splitlines() if l)
    # rust: exclude commented
    rsx=g('grep','-cE',r'^\s*#\[test\]',h,'--','*.rs')
    dirs=collections.Counter(l.split(':')[1].split('/')[0] for l in rs.splitlines() if l)
    pd=collections.Counter(l.split(':')[1].split('/')[0] for l in pyall.splitlines() if l)
    print(day,h[:8],'rs',s(rs),s(rsx),'py',s(py),s(pyall),dict(dirs),dict(pd))
