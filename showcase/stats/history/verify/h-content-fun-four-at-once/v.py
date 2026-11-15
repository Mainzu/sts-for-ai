import json,statistics as st,math
R='results/mutate/'
def load(f):
    d=json.load(open(R+f)); hp=d['start_hp']; c=d['cells']
    par=[x for x in c if x['kind']=='parent'][0]
    ws=[x for x in c if x['kind']=='world' and x['pool']=='main' and x['k']==4]
    return d,hp,par,ws
def loss(r,hp,cap):
    out=[]
    for i,seeds in enumerate(r):
        for won,e in seeds:
            out.append(hp[i]-max(e,0) if cap else hp[i]-e)
    return out
res={}
for f in ['rw-nodeath.json','rw-nd-pns1-k4.json','rw-nd-gp1-k4.json']:
    d,hp,par,ws=load(f)
    for cap in (True,False):
        pn=loss(par['res']['one'],hp,cap); ph=loss(par['res']['heuristic'],hp,cap)
        per=[];deadn=[];deadh=[]
        for w in ws:
            n=loss(w['res']['one'],hp,cap); h=loss(w['res']['heuristic'],hp,cap)
            per.append(st.mean((a-b)-(c-e) for a,b,c,e in zip(n,pn,h,ph)))
            deadn+= [e<=0 for s in w['res']['one'] for _,e in s]; deadh+=[e<=0 for s in w['res']['heuristic'] for _,e in s]
        print(f,'cap' if cap else 'raw',len(ws),round(st.mean(per),2),round(st.stdev(per)/math.sqrt(len(per)),2),'deaths',round(st.mean(deadn),3),round(st.mean(deadh),3))
        res[(f,cap)]=per
    print(' items equal to base?', [w['items'] for w in ws][:2])
a=res[('rw-nd-gp1-k4.json',True)];b=res[('rw-nd-pns1-k4.json',True)];o=res[('rw-nodeath.json',True)]
dd=[x-y for x,y in zip(a,b)]; print('gp-pns paired',round(st.mean(dd),2),round(st.stdev(dd)/math.sqrt(40),2))
dd=[x-y for x,y in zip(a,o)]; print('gp-old paired',round(st.mean(dd),2),round(st.stdev(dd)/math.sqrt(40),2))
