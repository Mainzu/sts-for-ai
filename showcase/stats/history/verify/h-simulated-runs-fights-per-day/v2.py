import json,glob,os,collections,datetime,hashlib
R=''
tz=datetime.timezone(datetime.timedelta(hours=0))
ids=[json.loads(l)['id'] for l in open(R+'results/ladder/runhp/log.jsonl')]
fs=sorted(os.path.basename(f)[:-5] for f in glob.glob(R+'results/ladder/runhp/*.json'))
print(len(ids),len(set(ids)),set(ids)^set(fs))
for l in open(R+'results/ladder/runhp/log.jsonl'):
    d=json.loads(l)
    if d['id'] not in fs: print(d)
for f in glob.glob(R+'results/ladder/runhp/*.partial.jsonl'): print(f, sum(1 for _ in open(f)))
dig=collections.defaultdict(list);d7=collections.Counter()
for f in sorted(glob.glob(R+'results/gauntlet/*.json')):
    d=json.load(open(f));s=d['sequences'];n=sum(len(q['floors']) for q in s)
    dig[hashlib.md5(json.dumps(s,sort_keys=True).encode()).hexdigest()].append((os.path.basename(f),n))
    md=datetime.datetime.fromtimestamp(os.path.getmtime(f),tz).strftime('%m-%d %H')
    if md.startswith('11-07'): d7[(md, len(s))]+=1
for k,v in dig.items():
    if len(v)>1: print(v)
print(sorted(d7.items()))
