import json,os,re,collections
ROOT=''
T=json.load(open('trainjobs.json'));G=json.load(open('gathered.json'))
cmds=[]
for f in os.listdir(ROOT+'jobs/done'):
    j=json.load(open(ROOT+'jobs/done/'+f)); c=j['cmd']; cmds.append((j['id'],' '.join(c) if isinstance(c,list) else c))
# all text under docs + results file names
txt=[]
for base in ('docs','configs'):
    for dp,_,fs in os.walk(ROOT+base):
        for f in fs:
            if f.endswith(('.md','.json')):
                try: txt.append(open(os.path.join(dp,f),encoding='utf-8',errors='ignore').read())
                except: pass
alltxt='\n'.join(txt)
names=collections.defaultdict(float); jobsof=collections.defaultdict(list)
for t in T:
    m=re.search(r'--config configs/([^ ]+)\.json',t['cmd'])
    if m and 'learn.py' in t['cmd']:
        names[m.group(1)]+=t['h']*(t['threads'] or 1); jobsof[m.group(1)].append((t['id'],round(t['h'],2),t['status']))
rows=[]
for n,th in names.items():
    runs=[r['run'] for r in G['runs'] if r['name']==n and r['model']]
    uses=sum(1 for jid,c in cmds for r in runs if r in c and 'learn.py' not in c)
    docs=sum(alltxt.count(r) for r in runs)
    rows.append((th,n,len(runs),uses,docs,jobsof[n]))
rows.sort(reverse=True)
for r in rows[:25]: print(round(r[0],1),r[1:])
