exec(open('v.py').read().split("print('commits'")[0])
a=PATS['any']; prev=None
for d,t in texts:
    c=cands(t,a)
    if d in('11-03','11-04','11-05') and c!=prev:
        print(d,len(c),sorted(c-(prev or set())),'-',sorted((prev or set())-c)); 
    prev=c
