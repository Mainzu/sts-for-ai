import json,glob,os,re,collections,statistics
R='results/gauntlet/'
ref={k:v for k,v in json.load(open(R+'heuristic-bcbb0e.json'))['settings'].items() if k!='player'}
g=collections.defaultdict(dict)
for f in glob.glob(R+'rerank-*.json'):
    b=os.path.basename(f)
    if b.endswith('-b500.json'): continue
    d=json.load(open(f)); st=d['settings']
    if {k:v for k,v in st.items() if k!='player'}!=ref: continue
    ids=[q['i'] for q in d['sequences']]
    if len(ids)!=500 or min(ids)!=0: continue
    m=re.match(r'rerank-(\d{4}-\d\d-\d\d)-(.+?)-s(\d+)-(?:r\d+-)?[0-9a-f]{7}-(.*)\.json',b)
    if not m: print('skip',b); continue
    key=(m.group(2),m.group(4)); cl=sum(all(x['won'] for x in q['floors']) for q in d['sequences'])/500
    g[key][m.group(3)]=cl
gaps=[]
for k,v in sorted(g.items()):
    if len(v)>=2: gaps.append(round(100*(max(v.values())-min(v.values())),1)); print(k,len(v),gaps[-1])
print(len(gaps),statistics.median(gaps))
