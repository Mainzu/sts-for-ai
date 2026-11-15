import json,glob,os,subprocess
from datetime import datetime
R='.'
th=0;starts=[]
for f in sorted(glob.glob(R+'/jobs/done/*.json')):
    j=json.load(open(f))
    c=' '.join(j.get('cmd',[]))
    if 'learn.py' in c and 'lean-distil' in c:
        s=datetime.fromisoformat(j['started']);e=datetime.fromisoformat(j['ended'])
        h=(e-s).total_seconds()/3600;th+=h*j['threads'];starts.append(s)
        print(j['id'],j['status'],round(h,2),j['threads'])
print('thread-hours',round(th,1))
t=subprocess.run(['git','-C',R,'log','--format=%aI','-S','Distillation closed','--','docs/decisions.md'],capture_output=True,text=True).stdout.split()[-1]
print('closed',t,'hours from first start',round((datetime.fromisoformat(t)-min(starts)).total_seconds()/3600,1))
for l in open(R+'/results/ladder/log.jsonl'):
    d=json.loads(l)
    if 'distil' in d['candidate']: print(d['id'],d['candidate'].split('/')[1],d['verdict'],round(d['lead'],3))
