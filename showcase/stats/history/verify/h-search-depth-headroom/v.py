import json,sys,math,os
d=sys.argv[1]
def load(n): return json.load(open(os.path.join(d,n)))
def st(xs):
    m=sum(xs)/len(xs); v=sum((x-m)**2 for x in xs)/(len(xs)-1); return m, math.sqrt(v/len(xs))
arms={}
for n in ['three-elite-all.json','two4-elite-all.json','two16-elite-all.json','two-adapt-elite-all.json']:
    j=load(n); arms[n]=(j['settings'],{f['i']:f for f in j['fights']})
r=load('rollout-elite.json'); r2=load('rollout-elite-rest.json')
print(r['settings']); print(r2['settings'])
rf={}
for f in r['fights']+r2['fights']:
    assert f['i'] not in rf, f['i']; rf[f['i']]=f
arms['rollout']=(r['settings'],rf)
two4=arms['two4-elite-all.json'][1]
for k,(s,F) in arms.items():
    fs=list(F.values())
    dd=[f['hp_end']-f['hp_end_obs'] for f in fs]
    m,se=st(dd)
    w=sum(f['won'] for f in fs); wo=sum(f['won_obs'] for f in fs)
    secs=s.get('seconds'); ps=sum(f.get('seconds',0) for f in fs)
    pl=sum(f.get('playouts',0) for f in fs)
    cut=sum(1 for f in fs if f.get('cut',0)>0); cuts=sum(f.get('cut',0) for f in fs); dec=sum(f['decisions'] for f in fs)
    print(k,len(fs),'d',round(m,3),round(se,3),'won',w,'obs',wo,'secs/f',secs and round(secs/len(fs),2),'sumsec/f',round(ps/len(fs),2),'pl/f',round(pl/len(fs)),'cutsum',cuts,'dec',dec,'mean end',round(sum(f['hp_end'] for f in fs)/len(fs),2),'obs end',round(sum(f['hp_end_obs'] for f in fs)/len(fs),2))
    # vs two4 paired
    common=[i for i in F if i in two4]
    if k!='two4-elite-all.json':
        x=[F[i]['hp_end']-two4[i]['hp_end'] for i in common]; print('  vs two4 n',len(common),[round(v,3) for v in st(x)])
