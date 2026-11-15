import json,sys,os,collections
R=sys.argv[1]
def L(f): return json.load(open(os.path.join(R,'results/rollout',f)))['fights']
for f in ['never129.json','never129-n64.json','cleared30.json','cleared30-n64.json']:
    F=L(f); w=sum(x['won'] for x in F); ids=[x['i'] for x in F]
    print(f,len(F),'uniq',len(set(ids)),'won',w,round(100*w/len(F),1),'floors',set(x['floor'] for x in F),
      'play',min(x['playouts'] for x in F),max(x['playouts'] for x in F),'sec',min(x['seconds'] for x in F),max(x['seconds'] for x in F),
      collections.Counter(x['encounter'] for x in F))
a=L('never129.json');b=L('never129-n64.json')
print('same ids', [x['i'] for x in a]==[x['i'] for x in b])
c=L('cleared30.json');d=L('cleared30-n64.json')
print('same ids c', [x['i'] for x in c]==[x['i'] for x in d])
# won fights only at 64
for F,nm in [(b,'never64'),(d,'clr64')]:
    W=[x for x in F if x['won']]; print(nm,'won fights playouts',sorted(x['playouts'] for x in W))
    print(nm,'all playouts sorted ends',sorted(x['playouts'] for x in F)[:3],sorted(x['playouts'] for x in F)[-3:])
import statistics as S
bosses={'hexaghost','the_guardian','slime_boss'}
for nm,F in [('n16',a),('n64',b)]:
    for fl in sorted(set(x['floor'] for x in F)):
        G=[x for x in F if x['floor']==fl]; print(nm,'floor',fl,len(G),'won',sum(x['won'] for x in G),[x['encounter'] for x in G if x['won']])
for nm,F in [('never64',b),('clr64',d)]:
    p=sorted(x['playouts'] for x in F); s=sorted(x['seconds'] for x in F)
    q=lambda v,f: v[int(f*(len(v)-1))]
    print(nm,'playouts q25/med/q75',q(p,.25),S.median(p),q(p,.75),'sec q25/med/q75',q(s,.25),S.median(s),q(s,.75))
    B=[x for x in F if x['floor']==10]; p=sorted(x['playouts'] for x in B); s=sorted(x['seconds'] for x in B)
    print(nm,'floor10 n',len(B),'playouts q25/med/q75',q(p,.25),S.median(p),q(p,.75),'sec',q(s,.25),S.median(s),q(s,.75))
# turnover in cleared
print('clr flips', [(x['i'],x['won'],y['won']) for x,y in zip(c,d) if x['won']!=y['won']])
print('never flips', [(x['i'],x['encounter'],x['won'],y['won']) for x,y in zip(a,b) if x['won'] or y['won']])
