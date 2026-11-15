# Luck of the draw: per sequence i (0..499) of a fixed setting, how many players of one period cleared it.
import pickle,collections,sys
recs=pickle.load(open('recs.pkl','rb'))
EXTRA=('player','two_turn','start','rewards','sim_boss','pack','shape','rest','seed')
def fam(s):
    if [k for k in s if k not in EXTRA]: return None
    return (s['two_turn'],s.get('start'),s.get('rewards'),s.get('sim_boss'),(s.get('pack') or '').split('@')[0])
for want,per in [((False,None,None,None,''),6),((False,'starter','sim',True,''),None)]:
    cl=collections.Counter(); n=0; info={}; players=set()
    for r in recs:
        if fam(r['settings'])!=want or (per and r['period']!=per): continue
        q={x[0]:x for x in r['seqs'] if x[0]<500}
        if len(q)<500: continue
        if r['settings']['player'] in players: continue
        players.add(r['settings']['player']); n+=1
        for i,x in q.items():
            cl[i]+=x[1]
            if i not in info: info[i]=[f[0] for f in x[2]]
            if not x[1]:
                info.setdefault(('kill',i),collections.Counter())[x[2][-1][0]]+=1
    print(want,per,'players',n)
    h=collections.Counter(cl[i] for i in range(500))
    print(' cleared by all',h[n],' by none',h[0])
    print(' hist',sorted(h.items()))
    none=[i for i in range(500) if cl[i]==0]
    kc=collections.Counter()
    for i in none: kc[info[('kill',i)].most_common(1)[0][0]]+=1
    print(' killers of never-cleared',kc)
    for i in none[:5]: print('  ',i,info[('kill',i)].most_common(3))
