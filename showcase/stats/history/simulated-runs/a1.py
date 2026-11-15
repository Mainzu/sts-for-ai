import pickle,collections,json
recs=pickle.load(open('recs.pkl','rb'))
def key(s):
    return (s.get('two_turn'),s.get('start'),s.get('rewards'),s.get('sim_boss'),(s.get('pack') or '').split('@')[0],tuple(s['shape']),s['rest'],s['seed'],
            tuple(sorted((k,str(v)) for k,v in s.items() if k not in ('player','two_turn','start','rewards','sim_boss','pack','shape','rest','seed'))))
per=collections.defaultdict(lambda:[0,0,0,0])
for r in recs:
    p=per[r['period']]; p[0]+=1; p[1]+=len(r['seqs']); p[2]+=sum(len(q[2]) for q in r['seqs']); p[3]+=sum(q[1] for q in r['seqs'])
print('period files runs fights clears', sorted(per.items()))
sk=collections.Counter(key(r['settings']) for r in recs)
for k,v in sk.most_common(15): print(v,k[:5],k[6],k[8])
shapes=collections.Counter(tuple(r['settings']['shape']) for r in recs); print(shapes)
