import json,glob,os,collections,datetime
R='results/gauntlet/'
BASE={'player','two_turn','shape','rest','seed'}
files=[]
shapes=collections.Counter()
for f in sorted(glob.glob(R+'*.json')):
    dt=datetime.datetime.fromtimestamp(os.path.getmtime(f))
    if not (datetime.date(2026,11,6)<=dt.date()<=datetime.date(2026,11,9)): continue
    d=json.load(open(f)); s=d['settings']
    extra=set(s)-BASE
    if extra or s['two_turn'] or s['seed']!=20261101: continue
    shapes[(tuple(s['shape']),s['rest'])]+=1
    seqs={q['i']:q for q in d['sequences'] if 0<=q['i']<500}
    if len(seqs)!=500: print('partial',os.path.basename(f),len(seqs)); continue
    files.append((os.path.basename(f),s,seqs,dt))
print('shapes',shapes)
byp=collections.defaultdict(list)
for x in files: byp[x[1]['player']].append(x)
print('files',len(files),'players',len(byp))
for p,l in byp.items():
    if len(l)>1:
        w=[sum(all(fl['won'] for fl in q['floors']) for q in x[2].values()) for x in l]
        print('dup',p,[x[0] for x in l],w)
# also check identical results across different players
sig=collections.defaultdict(list)
def won(q): return all(fl['won'] for fl in q['floors']) and len(q['floors'])==11
chosen={p:l[-1] for p,l in byp.items()}
for p,x in chosen.items():
    sig[tuple(won(x[2][i]) for i in range(500))].append(p)
print('identical result groups',[v for v in sig.values() if len(v)>1])
# consistency check: same cell per i across files
cells=collections.defaultdict(set)
for x in chosen.values():
    for i,q in x[2].items(): cells[i].add(q.get('cell'))
print('cell mismatch',sum(len(v)>1 for v in cells.values()))
cnt=[sum(won(x[2][i]) for x in chosen.values()) for i in range(500)]
N=len(chosen)
b=collections.Counter()
for c in cnt:
    b['all' if c==N else 'none' if c==0 else '40-49' if c>=40 else '11-39' if c>=11 else '1-10']+=1
print(N,b)
killer=collections.Counter()
for i in range(500):
    if cnt[i]==0:
        ks=collections.Counter(next((fl['encounter'] for fl in x[2][i]['floors'] if not fl['won']),'?') for x in chosen.values())
        killer[ks.most_common(1)[0][0]]+=1
        if ks.get('hexaghost')==N: print('all die to hex at',i)
print(killer)
print('winrates',sorted(round(sum(won(x[2][i]) for i in range(500))/500,3) for x in chosen.values()))
print(sorted(chosen))
