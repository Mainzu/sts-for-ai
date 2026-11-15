import json, subprocess, collections
R='.'
P={1:('10-23','10-24'),2:('10-25','10-28'),3:('10-29','10-31'),4:('11-01','11-02'),5:('11-03','11-05'),6:('11-06','11-09'),7:('11-10','11-12'),8:('11-13','11-14')}
def per(d):
    for k,(a,b) in P.items():
        if a<=d<=b: return k
out=subprocess.run(['git','-C',R,'log','--no-renames','--name-only','--format=@@%ad','--date=format:%m-%d'],capture_output=True,text=True,encoding='utf-8',errors='replace').stdout
grid=collections.defaultdict(collections.Counter); tot=collections.Counter(); d=None
for l in out.splitlines():
    if l.startswith('@@'): d=l[2:]; continue
    if l.endswith(('.rs','.py')): grid[l][per(d)]+=1; tot[l]+=1
top=[f for f,_ in tot.most_common(10)]
for f in top: print(f, tot[f], [grid[f][p] for p in range(1,9)])
# first evening
log=subprocess.run(['git','-C',R,'log','--reverse','--format=%h %ad %s','--date=format:%m-%d %H:%M'],capture_output=True,text=True,encoding='utf-8').stdout.splitlines()
for l in log:
    if l.split()[1]=='10-23': print(l[:150])
