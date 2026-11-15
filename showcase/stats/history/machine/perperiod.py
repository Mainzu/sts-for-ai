import sys,statistics as S
sys.argv=['x','none'];exec(open('jobs_stats.py').read())
for p in range(3,9):
    s=[j for j in J if j['p']==p and j['s'] and j['e']]
    th=sum((j['e']-j['s']).total_seconds()/3600*j['threads'] for j in s)
    print(p,'jobs',sum(j['p']==p for j in J),'started',len(s),'thread-h %.0f'%th,'median min %.1f'%S.median((j['e']-j['s']).total_seconds()/60 for j in s),'th per job %.2f'%(th/len(s)))
