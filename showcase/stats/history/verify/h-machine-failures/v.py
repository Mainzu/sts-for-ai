import json,glob,os,collections
R=''
P=[('10-23','10-24'),('10-25','10-28'),('10-29','10-31'),('11-01','11-02'),('11-03','11-05'),('11-06','11-09'),('11-10','11-12'),('11-13','11-14')]
def per(d):
    md=d[5:10]
    for i,(a,b) in enumerate(P):
        if a<=md<=b: return i+1
st=collections.Counter(); fails=[]; reasons=collections.Counter()
for f in sorted(glob.glob(R+'jobs/done/*.json')):
    j=json.load(open(f,encoding='utf-8'))
    s=j.get('status'); st[s]+=1
    if s=='cancelled': reasons[(j.get('reason') or '')[:50]]+=1
    if s=='failed': fails.append(j)
print(st); 
for r,c in reasons.most_common(15): print(c,r)
pc=collections.Counter()
for j in fails:
    t=j.get('started') or j.get('added'); p=per(t); pc[p]+=1
    log=j.get('log'); tail=''
    try:
        with open(log,encoding='utf-8',errors='replace') as fh: lines=[l.strip() for l in fh.readlines()[-40:] if l.strip()]
        tail=' | '.join(lines[-3:])[:260]
    except Exception as e: tail='NOLOG'
    print(p,j['id'],j.get('exit_code'),t[5:16],tail)
print(pc)
