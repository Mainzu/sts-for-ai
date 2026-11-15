import json,glob,os,collections,datetime,hashlib
R=''
tz=datetime.timezone(datetime.timedelta(hours=0))
g=collections.Counter();runs=0;fights=0;files=0;namedate=collections.Counter();mt=collections.Counter()
dig=collections.Counter();keys=collections.Counter();nonmatch=0
for f in sorted(glob.glob(R+'results/gauntlet/*.json')):
    d=json.load(open(f));files+=1
    s=d.get('sequences',[])
    n=sum(len(q['floors']) for q in s);runs+=len(s);fights+=n
    nd=os.path.basename(f)[5:10]; md=datetime.datetime.fromtimestamp(os.path.getmtime(f),tz).strftime('%m-%d')
    namedate[nd]+=n; mt[md]+=n
    if nd!=md: nonmatch+=1
    dig[hashlib.md5(json.dumps(s,sort_keys=True).encode()).hexdigest()]+=1
    keys[json.dumps(d.get('settings'),sort_keys=True)]+=1
print('files',files,'runs',runs,'fights',fights,'name!=mtime',nonmatch)
print('dup seq digests',sum(c-1 for c in dig.values() if c>1),'dup settings',sum(c-1 for c in keys.values() if c>1))
print('by name date',sorted(namedate.items()))
print('by mtime',sorted(mt.items()))
lad=collections.Counter();m=0;fp=0
for l in open(R+'results/ladder/log.jsonl'):
    d=json.loads(l);m+=1;lad[d['when'][5:10]]+=2*d['pairs'];fp+=2*d['pairs']
rh=0
for f in glob.glob(R+'results/ladder/runhp/*.json'):
    d=json.load(open(f));m+=1;rh+=1;lad[d['when'][5:10]]+=2*d['pairs'];fp+=2*d['pairs']
print('ladder matches',m,'runhp',rh,'fights',fp,sorted(lad.items()))
