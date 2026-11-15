import pickle,collections
recs=pickle.load(open('recs.pkl','rb'))
EXTRA=('player','two_turn','start','rewards','sim_boss','pack','shape','rest','seed')
def fam(s):
    if [k for k in s if k not in EXTRA]: return None
    return (s['two_turn'],s.get('start'),s.get('rewards'),s.get('sim_boss'),(s.get('pack') or '').split('@')[0])
# best per period, one-turn starter+sim rewards+sim boss, no pack, block 0..499
for want in [(False,'starter','sim',True,''),(False,None,None,None,'')]:
  best={}
  for r in recs:
    if fam(r['settings'])!=want: continue
    q=[x for x in r['seqs'] if x[0]<500]
    if len({x[0] for x in q})<500: continue
    cr=sum(x[1] for x in q)/500; p=r['period']
    best.setdefault(p,[]).append((cr,r['settings']['player'],r['file'],r['when']))
  print(want)
  for p in sorted(best):
    v=sorted(best[p],reverse=True); print(' P',p,len(v),v[0][:1],v[0][1][-55:],v[0][3],'| heur',[x[0] for x in v if x[1]=='heuristic'])
# P6 encounters
seen=collections.Counter(); died=collections.Counter()
for r in recs:
    if r['period']!=6: continue
    for i,c,fl in r['seqs']:
        for e,a,b,w in fl:
            seen[e]+=1; died[e]+= (not w)
for e,n in seen.most_common(): print(e,n,died[e],round(100*died[e]/n,2))
