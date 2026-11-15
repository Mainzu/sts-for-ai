import json, collections
R=''
p=json.load(open(R+'data/bench/gen_powers_pack.json'))
print('gen_powers_pack powers',len(p['powers']),collections.Counter(x.get('split') for x in p['powers']),'cards',len(p['cards']))
for f in ['gen-enemies-train','gen-enemies-wide','gen-enemies-six']:
    d=json.load(open(R+'content/packs/%s.json'%f))
    print(f,{k:(len(v) if isinstance(v,list) else v) for k,v in d.items()})
    if 'powers' in d: print('  ',[x['id'] for x in d['powers']][:70])
