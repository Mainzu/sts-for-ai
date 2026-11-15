import json,os,subprocess,statistics,collections,datetime
R='.'
G=R+'/results/gauntlet'
# first add date per file (local time from git with tz)
out=subprocess.run(['git','-C',R,'log','--diff-filter=A','--name-only','--format=@%ad','--date=iso-strict','--','results/gauntlet'],capture_output=True,text=True).stdout
added={}
cur=None
for l in out.splitlines():
    if l.startswith('@'): cur=l[1:]
    elif l.strip(): added[os.path.basename(l.strip())]=cur
SH=['easy','easy','easy','hard','hard','elite','hard','hard','elite','hard','boss']
P=[(1,'10-23','10-24'),(2,'10-25','10-28'),(3,'10-29','10-31'),(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
def per(md):
    for p,a,b in P:
        if a<=md<=b: return p
rows=[];skip=collections.Counter()
for f in sorted(os.listdir(G)):
    if not f.endswith('.json'): continue
    try: d=json.load(open(os.path.join(G,f)))
    except Exception: skip['bad']+=1; continue
    if not isinstance(d,dict) or 'settings' not in d: skip['nosettings']+=1; continue
    s=d['settings']
    if s.get('shape')!=SH or s.get('two_turn') or s.get('rest')!=0.3 or s.get('seed')!=20261101: skip['settings']+=1; continue
    seqs=d['sequences']; idx=sorted(q['i'] for q in seqs)
    if idx!=list(range(500)): skip['idx '+str((idx[0],idx[-1],len(idx)))]+=1; continue
    cr=sum(q['cleared'] for q in seqs)/500
    if f not in added: skip['untracked']+=1; md=None
    else:
        dt=datetime.datetime.fromisoformat(added[f]).astimezone(datetime.timezone(datetime.timedelta(hours=0)))
        md=dt.strftime('%m-%d')
    rows.append((f,s['player'],cr,md,per(md) if md else None, len(set(str(k) for k in s))))
print(skip)
by=collections.defaultdict(list)
for r in rows: by[r[4]].append(r)
for p in sorted(by,key=str):
    v=[r[2] for r in by[p]]
    print(p,len(v),max(v),statistics.median(v))
# duplicate players
pc=collections.Counter(r[1] for r in rows)
print('dup players',[(k,c) for k,c in pc.items() if c>1][:20], sum(c-1 for c in pc.values()))
for r in rows:
    if 'net1029' in r[0] or 'genpack40k' in r[0] or r[1].startswith('heur') or 'heur' in r[0]: print(r)
print(sorted(rows,key=lambda r:-r[2])[:6])
print([r for r in rows if r[4]==8])
