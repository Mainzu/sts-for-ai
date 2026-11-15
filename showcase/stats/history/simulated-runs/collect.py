# Collect per-file summary of every results/gauntlet/*.json, dated by the job that wrote it (jobs/done --out), else file mtime.
import json,os,glob,collections,datetime,pickle
ROOT='.'
outmap={}
for f in sorted(glob.glob(ROOT+'/jobs/done/*.json')):
    d=json.load(open(f)); c=d['cmd']
    if 'scripts/gauntlet.py' in ' '.join(c) and '--out' in c:
        o=c[c.index('--out')+1].replace(chr(92),'/')
        outmap.setdefault(os.path.basename(o),[]).append(d.get('ended') or d.get('started'))
def period(md):
    m,d=int(md[:2]),int(md[3:5]); day=(d-23) if m==10 else d+8   # 10-23 -> 0, 11-01 -> 9
    for p,(a,b) in enumerate([(0,1),(2,5),(6,8),(9,10),(11,13),(14,17),(18,20),(21,22)],1):
        if a<=day<=b: return p
recs=[]
for f in sorted(glob.glob(ROOT+'/results/gauntlet/*.json')):
    b=os.path.basename(f)
    if b in outmap: when=outmap[b][-1][5:16].replace('T',' '); src='job'
    else: when=datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%m-%d %H:%M'); src='mtime'
    d=json.load(open(f)); s=d['settings']
    seqs=[]
    for q in d['sequences']:
        seqs.append((q['i'],q['cleared'],[(fl['encounter'],fl['hp_start'],fl['hp_end'],fl['won']) for fl in q['floors']]))
    recs.append(dict(file=b,when=when,src=src,period=period(when),settings=s,seqs=seqs,protocol=d.get('protocol')))
pickle.dump(recs,open('recs.pkl','wb'))
print(len(recs), collections.Counter(r['src'] for r in recs), sorted(collections.Counter(r['period'] for r in recs).items()))
