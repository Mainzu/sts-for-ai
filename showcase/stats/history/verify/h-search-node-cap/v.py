import json,sys,os,datetime
R=sys.argv[1]+'/results/depth/'
fs=['paired-held_out.json','paired-held_out-cap400k.json','paired-held_out-cap400k-fallback-m0.json','paired-net-held_out.json','paired-net-held_out-cap400k-fallback.json']
ones={}
for f in fs:
    d=json.load(open(R+f))
    F=d['fights']; n=len(F)
    a=sum(x['one']['won'] for x in F)/n; b=sum(x['two']['won'] for x in F)/n
    key=[(x['cell'],x['encounter'],x['seed']) for x in F]
    one=[x['one']['won'] for x in F]
    print(f, datetime.datetime.fromtimestamp(os.path.getmtime(R+f)).strftime('%m-%d %H:%M'), n, len(set(key)), round(a,4), round(b,4), round((b-a)*100,2), d['summary']['all']['won']['se'])
    print('  args',{k:v for k,v in d['args'].items() if k not in('out',)}, d['two'], d['cut_probe'])
    ones[f]=(key,one)
k0=ones[fs[0]][0]
for f in fs: print(f, ones[f][0]==k0, ones[f][1]==ones[fs[0]][1] if 'net' not in f else ones[f][1]==ones[fs[3]][1])
for f in fs:
    F=json.load(open(R+f))['fights'];D=sum(x['two'].get('decisions',0) for x in F);C=sum(x['two'].get('cut',0) for x in F)
    if D: print('in-play cut share',f,C,D,round(C/D,4))
