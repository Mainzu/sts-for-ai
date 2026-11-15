import json,glob,os,statistics as st,collections,datetime as dt
P=[("1","10-23","10-24"),("2","10-25","10-28"),("3","10-29","10-31"),("4","11-01","11-02"),("5","11-03","11-05"),("6","11-06","11-09"),("7","11-10","11-12"),("8","11-13","11-14")]
def per(d):
    for p,a,b in P:
        if a<=d<=b: return p
def kind(cmd):
    s=" ".join(cmd)
    toks=[os.path.basename(c) for c in cmd if c.endswith('.py') or c.endswith('.exe')]
    py=[t for t in toks if t.endswith('.py')]
    k=py[0] if py else toks[0] if toks else '?'
    if k=='cargo.exe' or 'cargo' in s and not py: k='cargo:'+(cmd[1] if len(cmd)>1 else '')
    return k
by=collections.defaultdict(lambda: collections.defaultdict(list))
ids=set()
for f in glob.glob(r"jobs/done/*.json"):
    j=json.load(open(f,encoding='utf-8'))
    if j.get('status')!='ok' or not j.get('estimate_min') or not j.get('started') or not j.get('ended'): continue
    s=dt.datetime.fromisoformat(j['started']); e=dt.datetime.fromisoformat(j['ended'])
    act=(e-s).total_seconds()/60
    p=per(s.strftime('%m-%d'))
    k=kind(j['cmd'])
    if k in('python.exe',) and '-c' in j['cmd']: k='python -c'
    by[p][k].append((act/j['estimate_min'],j['estimate_min'],act,j['id']))
    by[p]['ALL'].append((act/j['estimate_min'],))
for p in sorted(by):
    print('P',p,'n',len(by[p]['ALL']),'median',round(st.median(x[0] for x in by[p]['ALL']),2))
print()
for k,v in sorted(by['6'].items(),key=lambda kv:-len(kv[1])):
    if k=='ALL':continue
    print(k,len(v),round(st.median(x[0] for x in v),2),'est',st.median(x[1] for x in v),'act',round(st.median(x[2] for x in v),1))
m=by['6']['mutate_cards.py']+by['6']['mutate_monsters.py']
print('mutate',len(m),round(st.median(x[0] for x in m),2),st.median(x[1] for x in m),round(st.median(x[2] for x in m),1))
g=sorted(x[0] for p in by for x in by[p]['gauntlet.py'])
print('gauntlet all',len(g),'q25',round(g[len(g)//4],2), 'share<0.4',round(sum(x<0.4 for x in g)/len(g),2))
print('mutate_cards p6 note', [x[3] for x in by['6']['mutate_cards.py']][:3])
