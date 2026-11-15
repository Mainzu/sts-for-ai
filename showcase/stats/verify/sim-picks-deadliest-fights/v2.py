import json, collections
G='results/gauntlet/'
seqs=[]
for f in ['net1029-hpe0.01-two-line-step-starter-simboss-a.json','net1029-hpe0.01-two-line-step-starter-simboss-500.json']:
    seqs+=json.load(open(G+f))['sequences']
for k in (5,8):
    h=[s['floors'][k]['hp_start'] for s in seqs if len(s['floors'])>k]
    l=collections.Counter(s['floors'][k]['encounter'] for s in seqs if len(s['floors'])>k and not s['floors'][k]['won'])
    print('floor',k+1,len(h),sum(h)/len(h),dict(l))
