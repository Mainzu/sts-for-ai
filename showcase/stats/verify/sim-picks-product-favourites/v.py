import json, collections
R='results/gauntlet/'
off=collections.Counter(); tk=collections.Counter(); half=collections.defaultdict(set)
ids=[]; nrew=skip=0; dup=collections.Counter()
for f in ['net1029-hpe0.01-two-line-step-starter-simboss-a.json','net1029-hpe0.01-two-line-step-starter-simboss-500.json']:
    d=json.load(open(R+f))
    print(f, d['settings'] if len(str(d['settings']))<600 else str(d['settings'])[:600])
    for s in d['sequences']:
        ids.append(s['i'])
        for fl in s['floors']:
            o=fl.get('offer')
            if not o: continue
            nrew+=1
            if len(set(o))<len(o): dup[len(o)]+=1
            t=fl.get('took')
            if not t: skip+=1
            for c in set(o):
                c2=c.replace('gen:','');off[c2]+=1; half[c2].add(s['half'])
            if t: tk[t.replace('gen:','')]+=1
print(len(ids),min(ids),max(ids),len(set(ids)),'rewards',nrew,'skip',skip,'dupoffers',dup)
for c in sorted(off,key=lambda c:-tk[c]/off[c]): print(f'{c:22s}{tk[c]:5d}/{off[c]:5d} {100*tk[c]/off[c]:5.1f} halves={sorted(half[c])}')
