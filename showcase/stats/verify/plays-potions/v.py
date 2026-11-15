import sys, os, json, re, statistics as st
from collections import Counter, defaultdict
R='.'
sys.path.insert(0, R+'/scripts')
import real_game_report as rg
REC=R+'/results/real-game'
runs=[]  # (asc, fights, decs)
for name in sorted(os.listdir(REC)):
    fo=os.path.join(REC,name)
    if not (os.path.isdir(fo) and name[:1].isdigit()): continue
    rs=[r for r in rg.runs_of(fo) if r['fights'] or r['end']]
    wf=[r for r in rs if r['combat']]
    # split decisions by floor drop
    groups=[]; prev=None
    with open(os.path.join(fo,'decisions.jsonl'),encoding='utf-8') as f:
        for l in f:
            if not l.strip(): continue
            d=json.loads(l)
            if prev is None or d['floor']<prev: groups.append([])
            prev=d['floor']; groups[-1].append(d)
    if len(groups)!=len(wf): print('MISMATCH',name,len(groups),len(wf),len(rs))
    for i,r in enumerate(rs):
        g=groups[wf.index(r)] if r in wf and wf.index(r)<len(groups) else []
        runs.append((rg.asc(r),r['fights'],g,r))
print('runs',len(runs), Counter(a for a,*_ in runs))
def norm(s): return s[4:] if s and s.startswith('gen:') else s
for A in (0,20):
    uses=[]; fights=Counter(); fairy=set(); fairyd=0
    for i,(a,fs,ds,r) in enumerate(runs):
        if a!=A: continue
        grp={f['floor']:f['group'] for f in fs}
        for f in fs: fights[f['group']]+=1
        for d in ds:
            if 'card_reward' in d or 'line' not in d: continue
            p=d['view']['player']; pots=p.get('potions') or []
            if any(norm(x)=='Fairy in a Bottle' for x in pots if x): fairy.add((i,d['floor'],d['turn'])); fairyd+=1
            for act in d['line']:
                m=re.match(r'Potion:(\d+)',act)
                if m:
                    k=int(m.group(1)); nm=norm(pots[k]) if k<len(pots) else '?'
                    uses.append((nm,d['turn'],p['hp']/p['max_hp'],grp.get(d['floor'],'?'),len([x for x in d['line'] if x.startswith('Potion')])))
    print('A',A,'fights',sum(fights.values()),dict(fights),'uses',len(uses))
    print(' turn',sorted(Counter(min(u[1],4) for u in uses).items()))
    print(' median hp',st.median(u[2] for u in uses),'below half',sum(u[2]<0.5 for u in uses))
    print(' group',Counter(u[3] for u in uses))
    print(' names',Counter(u[0] for u in uses).most_common(14))
    print(' multi-potion lines',sum(u[4]>1 for u in uses))
    print(' fairy turns',len(fairy),'decisions',fairyd)
