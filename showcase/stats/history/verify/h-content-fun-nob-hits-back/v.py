import json,collections
R='results/mutate/'
M='GE-AttackLoss-Damage'
for f in ['gen-enemies-b1.json','gen-b1-sharp399-s1.json','gen-b1-sharp399-s2.json']:
    d=json.load(open(R+f))
    enc=collections.Counter(r['encounter'] for r in d['rows'] if M in r['mods'])
    print(f,enc, d['settings']['net'])
    for pol in ['heuristic','one']:
      for nseed in ([16,4] if 'enemies' in f else [4]):
        w=n=0; lost=0; plost=0;pw=0
        for r in d['rows']:
            if r['encounter']!='gremlin_nob' or M not in r['mods']: continue
            for (ok,hp) in r['mods'][M][pol][:nseed]:
                n+=1; w+=ok; lost+= r['hp']-(hp if ok else 0)
            for (ok,hp) in r['parent'][pol][:nseed]:
                pw+=ok; plost+=r['hp']-(hp if ok else 0)
        print(' ',pol,nseed,n,round(w/n,3),'lost',round(lost/n,1),'parent win',round(pw/n,3),'lost',round(plost/n,1))
    nobstarts=len({r['i'] for r in d['rows'] if r['encounter']=='gremlin_nob'})
    print(' nob starts',nobstarts, 'with mod', sum(1 for r in d['rows'] if r['encounter']=='gremlin_nob' and M in r['mods']))
