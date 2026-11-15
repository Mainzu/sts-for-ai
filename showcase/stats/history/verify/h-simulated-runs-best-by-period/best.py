import json,glob,os,datetime,collections
R='results/gauntlet/'
P=[(1,'10-23','10-24'),(2,'10-25','10-28'),(3,'10-29','10-31'),(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
def per(md):
    for p,a,b in P:
        if a<=md<=b: return p
BASE={'player','two_turn','shape','rest','seed'}
rows=[]; star=[]
for f in sorted(glob.glob(R+'*.json')):
    d=json.load(open(f)); s=d['settings']; q=d['sequences']
    md=datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%m-%d %H:%M')
    idx=sorted(x['i'] for x in q)
    rate=sum(x['cleared'] for x in q)/len(q)
    rec=(per(md[:5]),md,os.path.basename(f),s['player'],s['two_turn'],len(q),idx==list(range(500)),round(rate,3))
    if set(s)==BASE: rows.append(rec)
    if set(s)>=BASE and s.get('start')=='starter': star.append(rec+(tuple(sorted(set(s)-BASE)),s.get('rewards'),s.get('sim_boss')))
import sys
mode=sys.argv[1] if len(sys.argv)>1 else 'plain'
L=rows if mode=='plain' else star
for r in L: print(*r,sep=' | ')
