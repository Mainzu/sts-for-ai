import json,glob,os,collections,subprocess
R=''
keys=collections.Counter(); out=[]
# git first-add date
log=subprocess.run(['git','-C',R,'log','--diff-filter=A','--name-only','--format=@%ad','--date=format-local:%m-%d %H:%M','--','results/gauntlet'],capture_output=True,text=True,env=dict(os.environ,TZ='UTC')).stdout
added={};cur=None
for l in log.splitlines():
    if l.startswith('@'):cur=l[1:]
    elif l.strip(): added[os.path.basename(l.strip())]=cur
for f in sorted(glob.glob(R+'results/gauntlet/*.json')):
    b=os.path.basename(f)
    try:d=json.load(open(f))
    except Exception as e: out.append((b,'ERR')); continue
    if not isinstance(d,dict) or 'settings' not in d: out.append((b,'nos',type(d).__name__)); continue
    s=d['settings'];keys.update(s.keys())
    seqs=d['sequences'];ii=[q['i'] for q in seqs]
    out.append((b,added.get(b),json.dumps({k:v for k,v in s.items() if k not in('shape',)}),len(seqs),min(ii),max(ii)))
print(keys)
for o in out: print(o)
