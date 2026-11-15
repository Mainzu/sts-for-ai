# Best clear rate per period on a fixed sequence block (i 0..499), per setting family.
import pickle,collections
recs=pickle.load(open('recs.pkl','rb'))
EXTRA=('player','two_turn','start','rewards','sim_boss','pack','shape','rest','seed')
def fam(s):
    ex=[k for k in s if k not in EXTRA]
    if ex: return None
    return ('two' if s['two_turn'] else 'one', 'starter-simboss' if s.get('start')=='starter' else 'cells', (s.get('pack') or '').split('/')[-1].split('@')[0])
best=collections.defaultdict(list)
for r in recs:
    f=fam(r['settings'])
    if f is None: continue
    q=[x for x in r['seqs'] if x[0]<500]
    if len({x[0] for x in q})!=500: continue
    cr=sum(x[1] for x in q)/500
    best[(f,r['period'])].append((cr,r['settings']['player'][-60:],r['file']))
for k in sorted(best):
    v=sorted(best[k],reverse=True)
    print(k,len(v),'best',v[0][0],v[0][1],'| worst',v[-1][0],v[-1][1][-30:])
