import json, collections
R=''
b=json.load(open(R+'data/bench/gen_powers.json'))['fights']
w=json.load(open(R+'results/gen_powers/first-check.json'))['won']
p=json.load(open(R+'data/bench/gen_powers_pack.json'))
pw={x['id']:x for x in p['powers']}; cd={x['id']:x for x in p['cards']}
H,N=w['heuristic'],w['champion']
# pair by (cell, seed, swapped, gen_card)
idx={}
for i,f in enumerate(b): idx[(f['cell'],f['seed'],f['set'])]=i
cards=collections.defaultdict(lambda:[0,0,0,[]])
cells=set()
for i,f in enumerate(b):
    if f['set']!='generated': continue
    j=idx[(f['cell'],f['seed'],'original')]
    o=b[j]; assert o['gen_card']==f['gen_card'] and o['swapped']==f['swapped']
    c=cards[f['gen_card']]; c[0]+=1; c[1]+=H[i]-H[j]; c[2]+=N[i]-N[j]; c[3].append(f['copies']); cells.add(f['cell'])
print(len(cards),len(cells),sum(c[0] for c in cards.values()))
up=dn=eq=0;hneg=0
for k,(n,h,nn,cp) in sorted(cards.items(),key=lambda t:t[1][1]/t[1][0]):
    h/=n;nn/=n
    if nn>h:up+=1
    elif nn<h:dn+=1
    else:eq+=1
    if h<0:hneg+=1
    card=cd[k]
    print(k,n,round(h,3),round(nn,3),'cost',card['cost'],'copies',set(cp),json.dumps(pw[card['power']]['hooks'])[:230],pw[card['power']]['lifetime'])
print('net lost less',up,'more',dn,'eq',eq,'heur neg',hneg)
