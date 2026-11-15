import json,os,glob,collections
R=''
g=collections.defaultdict(list)
for p in glob.glob(R+'datasets/*/manifest.json'):
    m=json.load(open(p)); k=os.path.basename(os.path.dirname(p))
    g[m.get('games_sha256')].append((k,m['n_games'],m.get('parent_model'),os.path.getsize(os.path.dirname(p)+'/manifest.json')))
ex=0
for s,l in g.items():
    if len(l)>1: print(l); ex+=sum(x[1] for x in l[1:])
print('extra',ex,'unique sets',len(g))
for k in ['daf87b2b715e','daf87b2b715e.tmp']:
    print(k, os.listdir(R+'datasets/'+k) if os.path.isdir(R+'datasets/'+k) else None)
