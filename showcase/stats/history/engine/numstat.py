import subprocess, collections, json, sys, os
R='.'
P={1:('10-23','10-24'),2:('10-25','10-28'),3:('10-29','10-31'),4:('11-01','11-02'),5:('11-03','11-05'),6:('11-06','11-09'),7:('11-10','11-12'),8:('11-13','11-14')}
def per(d):
    for k,(a,b) in P.items():
        if a<=d<=b: return k
out=subprocess.run(['git','-C',R,'log','--reverse','--no-renames','--numstat','--format=@@%H|%ad|%s','--date=format:%m-%d %H:%M'],capture_output=True,text=True,encoding='utf-8',errors='replace').stdout
cum=collections.Counter(); daily={}; edits=collections.Counter(); commits=[]; cur=None
golden=[]
for line in out.splitlines():
    if line.startswith('@@'):
        h,d,s=line[2:].split('|',2); cur={'h':h[:8],'d':d,'s':s,'add':0,'del':0,'files':0,'rs':0,'py':0}; commits.append(cur); continue
    if not line.strip() or cur is None: continue
    a,b,f=line.split('\t',2)
    if a=='-': continue
    a,b=int(a),int(b); ext=os.path.splitext(f)[1]
    cur['files']+=1
    if ext in ('.rs','.py'):
        k='rs' if ext=='.rs' else 'py'
        if True:
            cum[k]+=a-b; cur[k]+=a+b
    cur['add']+=a; cur['del']+=b
    edits[f]+=1
    if f=='engine/tests/data/golden.txt': golden.append((cur['d'],cur['h'],a,b,cur['s']))
    daily[cur['d'][:5]]=dict(cum)
json.dump({'daily':daily,'edits':edits.most_common(40),'golden':golden,'commits':commits},open('numstat.json','w'),indent=0)
print('days',daily)
for f,n in edits.most_common(25): print(n,f)
print('golden commits',len(golden))
pc=collections.Counter(per(g[0][:5]) for g in golden); print(sorted(pc.items()))
for g in golden: print(g)
big=sorted(commits,key=lambda c:-(c['rs']+c['py']))[:8]
for c in big: print(c)
bigall=sorted(commits,key=lambda c:-(c['add']+c['del']))[:5]
for c in bigall: print(c)
print(collections.Counter(per(c['d'][:5]) for c in commits))
