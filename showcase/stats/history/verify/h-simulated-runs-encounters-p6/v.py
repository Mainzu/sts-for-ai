import json,os,glob,datetime,collections,hashlib
R=''
end={}
for f in glob.glob(R+'jobs/done/*.json'):
    try: j=json.load(open(f))
    except: continue
    cmd=j.get('cmd') or []
    for i,a in enumerate(cmd):
        if isinstance(a,str) and 'results/gauntlet/' in a.replace(chr(92),'/'):
            p=os.path.basename(a.replace(chr(92),'/'))
            if j.get('ended') and j.get('status')!='failed': end[p]=j['ended']
tz=datetime.timezone(datetime.timedelta(hours=0))
P6=(datetime.date(2026,11,6),datetime.date(2026,11,9))
files=[];src=collections.Counter();mism=0
for f in sorted(glob.glob(R+'results/gauntlet/*.json')):
    b=os.path.basename(f)
    mt=datetime.datetime.fromtimestamp(os.path.getmtime(f),tz).date()
    if b in end:
        d=datetime.datetime.fromisoformat(end[b]).date(); src['job']+=1
        if d!=mt: mism+=1
    else: d=mt; src['mtime']+=1
    if P6[0]<=d<=P6[1]: files.append(f)
print('src',src,'job/mtime date mismatches',mism)
enc=collections.defaultdict(lambda:[0,0]); runs=0; fights=0
hashes=collections.Counter(); seqhash=collections.Counter()
players=collections.Counter()
for f in files:
    raw=open(f,'rb').read(); hashes[hashlib.md5(raw).hexdigest()]+=1
    d=json.loads(raw)
    players[(d['settings'].get('player','?').split('@')[0][-40:])]+=1
    seqhash[hashlib.md5(json.dumps(d['sequences'][:5]).encode()).hexdigest()+str(d['settings'])]+=1
    for s in d['sequences']:
        runs+=1
        for fl in s['floors']:
            e=enc[fl['encounter']]; e[0]+=1; e[1]+= (not fl['won']); fights+=1
print(len(files),'files',runs,'runs',fights,'fights',len(enc),'enc')
print('dup files',sum(v-1 for v in hashes.values()),'dup settings+seq',sum(v-1 for v in seqhash.values()))
for k,(n,l) in sorted(enc.items(),key=lambda x:-x[1][0]): print(f'{k:30}{n:8}{l:6}{100*l/n:7.2f}')
top=sorted(enc.items(),key=lambda x:-x[1][0])[:4]; print('top4 losses',sum(v[1] for k,v in top),sum(v[0] for k,v in top))
import pickle
recs=pickle.load(open('scratch/hist/simulated-runs/recs.pkl','rb'))
m6={r['file']:r['when'] for r in recs if r['period']==6}
mine={os.path.basename(f) for f in files}
allw={r['file']:(r['when'],r['src']) for r in recs}
for b in sorted(mine-set(m6)): print('only mine',b,allw[b],end.get(b))
for b in sorted(set(m6)-mine): print('only miner',b,m6[b],end.get(b))
byh=collections.defaultdict(list)
for f in glob.glob(R+'results/gauntlet/*.json'): byh[hashlib.md5(open(f,'rb').read()).hexdigest()].append(os.path.basename(f))
for h,v in byh.items():
    if len(v)>1: print('DUP',[(x,allw[x][0]) for x in v])
