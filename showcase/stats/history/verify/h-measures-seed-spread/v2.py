import json,glob,os
R='results/gauntlet/'
ref=json.load(open(R+'rerank-2026-11-07-ycards-net-g100-s1-5efcaec-hpb0.01.json'))['settings']
def load(b):
    d=json.load(open(R+b)); s=d['sequences']
    return d['settings'],{q['i']:all(f['won'] for f in q['floors']) for q in s}
for b in ['heuristic-bcbb0e.json','heuristic-b500.json','net1029-hpb0.01.json','net1029s101-hpb0.01.json','net1029s201-hpb0.01.json','net1029-hpb0.01-tsl1.json','champion-hpb0.01-b500.json']:
    st,w=load(b); same={k:v for k,v in st.items() if k!='player'}=={k:v for k,v in ref.items() if k!='player'}
    print(b,len(w),min(w),max(w),round(sum(w.values())/len(w),3),st.get('player'),'same settings' if same else st)
# paired discordance between seeds
import itertools
def disc(fs):
    W=[load(f)[1] for f in fs]
    for a,b in itertools.combinations(range(len(W)),2):
        n=sum(W[a][i]!=W[b][i] for i in W[a]); d=(sum(W[a].values())-sum(W[b].values()))/500
        print(' pair',a,b,'diff %.3f'%d,'discordant',n,'SE(pure binomial resample) ~%.3f'%((n**0.5)/500))
disc([os.path.basename(x) for x in sorted(glob.glob(R+'rerank-2026-10-31-data20k-*-hpb0.01.json'))])
for a,b in [('genpack40k-s1-hpb0.01-cells.json','genpack40k-s1-hpb0.01-cells-r2.json')]:
    sa,wa=load(a); sb,wb=load(b); print(a,b,sa==sb, sum(wa.values()),sum(wb.values()), sum(wa[i]!=wb.get(i) for i in wa))
