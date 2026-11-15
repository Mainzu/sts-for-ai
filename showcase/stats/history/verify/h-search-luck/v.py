import json,sys,statistics as st
R=sys.argv[1]
d=json.load(open(R+'/results/luck/luck-share-g1600.json'))
for k,s in d['slices'].items():
    print(k, 'rows',s['rows'],'games',s['games'],'noise/label %.3f'%(s['noise_var']/s['label_var']),'removed/noise %.3f se %.3f'%(s['removed_var']/s['noise_var'],s['noise_se']),'resid',round(s['residual_ms'],3))
print({k:v for k,v in d.items() if k!='slices'})
c=json.load(open(R+'/results/luck/luck-read-cells.json'))
a,b=c['sides']
raw=[x['end_hp']-y['end_hp'] for x,y in zip(a['rows'],b['rows'])]
cor=[(x['end_hp']-x['luck_hp'])-(y['end_hp']-y['luck_hp']) for x,y in zip(a['rows'],b['rows'])]
print(len(raw),st.pstdev(raw),st.stdev(raw),st.stdev(cor),st.stdev(cor)/st.stdev(raw),c['sd_raw'],c['sd_corrected'])
print([k for k in c if k not in('sides',)])
