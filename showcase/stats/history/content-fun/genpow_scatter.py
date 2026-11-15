# Generated Power cards (gen_powers bench, 10-31): per card, win change when it replaces Demon Form or Metallicize.
import json, collections
R=''
b=json.load(open(R+'data/bench/gen_powers.json')); r=json.load(open(R+'results/gen_powers/first-check.json'))
pack=json.load(open(R+'data/bench/gen_powers_pack.json'))
cards={c['id']:c for c in pack['cards']}; pw={p['id']:p for p in pack['powers']}
TR={'OwnerTurnEnd':'at your turn end','OwnerTurnStart':'at your turn start','CardPlayed:Owner':'when you play a card',
    'OwnerLostHp:Any':'when you lose HP','OwnerLostHp:Attack':'when attacked for HP','OwnerLostHp:Card':'when a card costs you HP'}
LT={'permanent':'all fight','this_turn':'this turn','used_up':'once per stack','wearing_down':'fading'}
def eff(e):
    if isinstance(e,str): return None
    k,v=next(iter(e.items()))
    if k in('RemoveSelf','ReduceSelf'): return None
    if k=='Apply': return f"{v['amount']} {v['power']}"+(' to all enemies' if v['target']=='AllOpponents' else '')
    if k in('Damage','PlainDamage'): return f"{v['amount']} damage to all"
    if k in('Block','GainBlock'): return f"{v if isinstance(v,int) else v.get('amount')} Block"
    if isinstance(v,int): return f'{v} {k}'
    return k
def desc(cid):
    c=cards[cid]; p=pw[c['power']]; parts=[]
    for h in p['hooks']:
        t=h['trigger']; t=t if isinstance(t,str) else ':'.join([list(t.keys())[0]]+[str(x) for x in list(t.values())[0].values()])
        es=[x for x in map(eff,h['effects']) if x]
        if es: parts.append(TR.get(t,t)+': '+', '.join(es))
    return f"{c['cost']} energy, {'; '.join(parts)} ({LT[p['lifetime']]})"
agg=collections.defaultdict(lambda:[0,0,0,0,0,0])
for f,h,n in zip(b['fights'],r['won']['heuristic'],r['won']['champion']):
    a=agg[f['gen_card']]; o=0 if f['set']=='original' else 3
    a[o]+=1;a[o+1]+=h;a[o+2]+=n
pts=[]
for k,a in agg.items():
    pts.append(dict(x=round(a[4]/a[3]-a[1]/a[0],3), y=round(a[5]/a[3]-a[2]/a[0],3), label=f"{k}: {desc(k)}, {a[3]} fights"))
pts.sort(key=lambda p:p['x'])
print(json.dumps(pts,indent=0))
print('cards',len(pts),'fights per set',sum(a[3] for a in agg.values()))
print('net better than heur on', sum(p['y']>p['x'] for p in pts), 'worse', sum(p['y']<p['x'] for p in pts))
