import json,os,sys,collections,datetime as dt
R='results/gauntlet'
rows=[]
for f in sorted(os.listdir(R)):
    if not f.endswith('.json'): continue
    p=os.path.join(R,f); st=os.stat(p)
    t=dt.datetime.fromtimestamp(st.st_mtime); b=dt.datetime.fromtimestamp(getattr(st,'st_birthtime',st.st_mtime))
    try: d=json.load(open(p))
    except Exception as e: print('bad',f,e); continue
    if not isinstance(d,dict) or 'sequences' not in d: print('other',f,list(d)[:5] if isinstance(d,dict) else type(d)); continue
    s=d['settings']; seqs=d['sequences']
    n=len(seqs); clr=sum(all(fl['won'] for fl in q['floors']) and len(q['floors'])==len(s.get('shape',[])) for q in seqs)
    key=json.dumps({k:v for k,v in s.items() if k!='player'},sort_keys=True)
    rows.append((t.strftime('%m-%d %H:%M'),b.strftime('%m-%d %H:%M'),f,n,clr/n if n else 0,key,s.get('player')))
json.dump(rows,open('gauntlet_rows.json','w'))
c=collections.Counter(r[5] for r in rows)
for k,v in c.most_common(12): print(v,k[:300])
print(len(rows))
