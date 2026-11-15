import sys,collections,statistics as S
sys.argv=['x','none'];exec(open('jobs_stats.py').read())
# 06h additions on 11-07
x=[j for j in J if j['a'].strftime('%m-%d %H')=='11-07 06']
print('11-07 06h',len(x),collections.Counter(j['k'] for j in x),min(j['a'] for j in x),max(j['a'] for j in x))
print(collections.Counter(j['cmd'][3] if len(j['cmd'])>3 else '' for j in x).most_common(3))
# P6 estimate ratio by kind
d=collections.defaultdict(list)
for j in J:
    if j['p']==6 and j['status']=='ok' and j['s'] and j['e'] and j['estimate_min']:
        d[j['k']].append(((j['e']-j['s']).total_seconds()/60/j['estimate_min'],j['estimate_min'],(j['e']-j['s']).total_seconds()/60))
for k,v in sorted(d.items(),key=lambda x:-len(x[1])):
    print(k,len(v),'%.2f'%S.median(a for a,_,_ in v),'est %.0f act %.1f'%(S.median(b for _,b,_ in v),S.median(c for _,_,c in v)))
# failure causes
C={'out of memory':'0049d 0049e 0052 0987 0988 0997','process killed by Windows':'0565 0908 0927','stack overflow':'0975',
'file or module missing':'0005 0006 0082 0084 0085 0086 0117 0118 0334 0432 0821 0964 0053 0054',
'test suite found a fault':'0013 0072 0205 0295 0303 0548 0685 0744 0763 0943 0944',
'input from an earlier job missing or bad':'0977 0978 0979 0980 0909 0059d3 0059l2 0892',
'refused: control played with other settings':'0572 0811',
'other (bad argument, locked file, crash)':'0057a8z8 0059l7r3b1 0746 0057a6i 0059d4 1007 1013 1015'}
ix={j['id'].split('-')[0]:j for j in J if j['status']=='failed'}
tot=0
for c,ids in C.items():
    row=collections.Counter(ix[i]['p'] for i in ids.split());tot+=sum(row.values())
    print(c,[row[p] for p in range(3,9)],sum(row.values()))
print('tot',tot,len(ix))
fc=collections.Counter(j['p'] for j in J if j['status']=='failed');print('failed per p',fc)
cc=collections.Counter(j['p'] for j in J if j['status']=='cancelled');print('cancelled per p',cc)
print('all per p',collections.Counter(j['p'] for j in J))
