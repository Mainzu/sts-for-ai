import json,os,collections,datetime as dt
R='jobs/done/'
c=collections.Counter(); out=[]
for f in sorted(os.listdir(R)):
    j=json.load(open(R+f)); cmd=j.get('cmd')
    if isinstance(cmd,list): cmd=' '.join(cmd)
    s=[w for w in cmd.split() if w.endswith('.py')]
    c[s[0] if s else cmd[:40]]+=1
    if j.get('started') and j.get('ended'):
        h=(dt.datetime.fromisoformat(j['ended'])-dt.datetime.fromisoformat(j['started'])).total_seconds()/3600
        out.append((h,j['id'],cmd[:200],j.get('status'),j.get('threads')))
for k,v in c.most_common(25): print(v,k)
out.sort(reverse=True)
for o in out[:15]: print(round(o[0],2),o[1:])
