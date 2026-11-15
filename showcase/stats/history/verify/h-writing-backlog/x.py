exec(open('v.py').read().split("print('commits'")[0])
import collections
for k in ('num','any'):
    p=PATS[k]; first={}; last={}; end={}; fin=None; mx=(0,'')
    for d,t in texts:
        c=cands(t,p)
        if not c: continue
        for n in c: first.setdefault(n,d); last[n]=d
        end[d]=len(c); fin=c
        if len(c)>mx[0]: mx=(len(c),d)
    op=collections.Counter(first.values()); rm=collections.Counter(d for n,d in last.items() if n not in fin)
    print('==',k,'distinct',len(first),'gone',sum(rm.values()),'final',len(fin),'max',mx)
    for d in sorted(end): print(' ',d,end[d],op[d],rm[d])
