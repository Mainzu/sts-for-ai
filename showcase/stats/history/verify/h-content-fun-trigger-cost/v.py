import json, statistics as st
d=json.load(open(r'results/mutate/gen-enemies-b1.json'))
mods=d['settings']['mods']; rows=[r for r in d['rows'] if r['group']=='elite']
lad=['parent']+[m for m in mods if m.startswith('c-')]; ge=[m for m in mods if m.startswith('GE-')]
def get(r,m,p): return r['parent'][p] if m=='parent' else r['mods'][m][p]
rows=[r for r in rows if all(p in get(r,m,'heuristic') or True for m in lad+ge for p in [0])]
print(len(rows))
def lost(r,m,p): s=get(r,m,p); return sum((r['hp']-e) if w else r['hp'] for w,e in s)/len(s)
def win(r,m,p): s=get(r,m,p); return sum(w for w,_ in s)/len(s)
hl={m:st.mean(lost(r,m,'heuristic') for r in rows) for m in lad+ge}
gap={m:[lost(r,m,'one')-lost(r,m,'heuristic') for r in rows] for m in lad+ge}
res={}
for m in ge:
    c=min(lad,key=lambda x:(abs(hl[x]-hl[m]),lad.index(x)))
    cost=st.mean(a-b for a,b in zip(gap[m],gap[c]))
    hw=st.mean(win(r,m,'heuristic') for r in rows); nw=st.mean(win(r,m,'one') for r in rows)
    res[m]=cost; print(f"{m:26s} ctl={c:14s} hw={hw:.3f} nw={nw:.3f} hl={hl[m]:.2f} cost={cost:+.2f}")
    # per-encounter
    for e in ['gremlin_nob','lagavulin','three_sentries']:
        idx=[i for i,r in enumerate(rows) if r['encounter']==e]
        print('   ',e, round(st.mean(gap[m][i]-gap[c][i] for i in idx),2))
excl={'GE-OppCard-Weak','GE-OppCard-Vulnerable','GE-AttackLoss-Vulnerable'}
for t in ['TurnStart','TurnEnd','OppCard','AttackLoss']:
    v=[res[m] for m in ge if m.split('-')[1]==t and m not in excl]; va=[res[m] for m in ge if m.split('-')[1]==t]
    print(t,len(v),round(st.mean(v),2),'all',len(va),round(st.mean(va),2))
print('mean21',round(st.mean(res[m] for m in ge if m not in excl),2),'mean24',round(st.mean(res.values()),2))
