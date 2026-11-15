import json,glob,os
R='datasets/'
L=[]
for m in glob.glob(R+'*/manifest.json'):
    try: j=json.load(open(m))
    except Exception: continue
    L.append((j.get('n_games') or 0,os.path.basename(os.path.dirname(m)),j.get('config',{}).get('n_per_group')))
L.sort(reverse=True); print(len(L)); print(L[:8])
