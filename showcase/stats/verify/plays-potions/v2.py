exec(open('v.py').read().split("def norm")[0])
def norm(s): return s[4:] if s and s.startswith('gen:') else s
import re
for A in (0,20):
    lost=Counter(); lostturn=Counter(); confirmed=0; unconf=Counter(); total=0; lastfight=0
    for a,fs,ds,r in runs:
        if a!=A: continue
        fd=[d for d in ds if 'line' in d and 'card_reward' not in d]
        for j,d in enumerate(fd):
            pots=[norm(x) for x in d['view']['player'].get('potions') or [] if x]
            nxt=fd[j+1] if j+1<len(fd) else None
            npots=[norm(x) for x in (nxt['view']['player'].get('potions') or []) if x] if nxt else None
            if npots is not None:
                diff=Counter(pots)-Counter(npots)
                for k,v in diff.items(): lost[k]+=v; lostturn[min(d['turn'],4)]+=v
            planned=[int(re.match(r'Potion:(\d+)',x).group(1)) for x in d['line'] if x.startswith('Potion:')]
            for k in planned:
                total+=1
                rp=d['view']['player'].get('potions') or []
                nm=norm(rp[k]) if k<len(rp) else '?'
                if npots is None: lastfight+=1
                elif (Counter(pots)-Counter(npots))[nm]>0: confirmed+=1
                else: unconf[nm]+=1
    print('A',A,'belt-lost',sum(lost.values()),sorted(lostturn.items()))
    print(' lost names',lost.most_common(14))
    print(' planned',total,'confirmed by belt',confirmed,'no next',lastfight,'unconfirmed',sum(unconf.values()),unconf.most_common(10))
