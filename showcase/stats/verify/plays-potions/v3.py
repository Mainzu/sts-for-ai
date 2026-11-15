exec(open('v.py').read().split("def norm")[0])
def norm(s): return s[4:] if s and s.startswith('gen:') else s
import re, statistics as st
for A in (0,20):
    U=[]; held=0
    for a,fs,ds,r in runs:
        if a!=A: continue
        grp={f['floor']:f['group'] for f in fs}
        fd=[d for d in ds if 'line' in d and 'card_reward' not in d]
        for j,d in enumerate(fd):
            rp=d['view']['player'].get('potions') or []
            pots=Counter(norm(x) for x in rp if x)
            nxt=fd[j+1] if j+1<len(fd) else None
            lost=pots-Counter(norm(x) for x in (nxt['view']['player'].get('potions') or []) if x) if nxt else pots
            for x in d['line']:
                if x.startswith('Potion:'):
                    k=int(re.match(r'Potion:(\d+)',x).group(1)); nm=norm(rp[k]) if k<len(rp) else '?'
                    if lost[nm]>0:
                        lost[nm]-=1; p=d['view']['player']; U.append((nm,d['turn'],p['hp']/p['max_hp'],grp.get(d['floor'],'?')))
    print('A',A,len(U),'turn',sorted(Counter(min(u[1],4) for u in U).items()),'medhp %.3f'%st.median(u[2] for u in U),'<half',sum(u[2]<.5 for u in U),Counter(u[3] for u in U))
    print(Counter(u[0] for u in U).most_common(16))
