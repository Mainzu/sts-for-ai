import subprocess
R='.'
def g(*a): return subprocess.run(['git','-C',R,*a],capture_output=True,text=True,encoding='utf-8',errors='replace').stdout
last={}
for l in reversed(g('reflog','show','main','--date=iso','--format=%H %gd').splitlines()):
    h,rest=l.split(' ',1); day=rest.split('{')[1][5:10]; last[day]=h
mlast={}
for l in g('log','--reverse','--format=%H|%ad','--date=format:%m-%d').split():
    h,d=l.split('|'); mlast[d]=h
def s(t): return sum(int(x.rsplit(':',1)[1]) for x in t.splitlines() if x)
for d in sorted(last):
    h=last[d]; m=mlast.get(d)
    f=lambda h:(s(g('grep','-c',r'#\[test\]',h,'--','*.rs')), s(g('grep','-cE',r'^\s*def test_',h,'--','*.py')))
    print(d,h[:8],f(h),'miner-commit',m[:8],f(m) if m!=h else 'same')
