import json,glob,os,re,datetime,collections,statistics
R='results/gauntlet/'
rows={}
for f in sorted(glob.glob(R+'rerank-*.json')):
    b=os.path.basename(f)
    try: d=json.load(open(f))
    except Exception as e: continue
    if not isinstance(d,dict) or 'sequences' not in d: continue
    s=d['sequences']; ids=[q['i'] for q in s]
    cl=sum(all(fl['won'] for fl in q['floors']) for q in s)/len(s)
    mt=datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%m-%d %H:%M')
    rows[b]=(len(s),min(ids),max(ids),round(cl,3),mt,d['settings'].get('player'),d['settings'].get('two_turn'),d['settings'].get('seed'))
for b,v in rows.items():
    if re.search(r'data20k|burst8|ycards',b): print(b,v)
