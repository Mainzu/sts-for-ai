import json,glob,datetime as dt,statistics as st
J=[]
for f in glob.glob('jobs/done/*.json'):
    j=json.load(open(f,encoding='utf-8'))
    if j.get('started') and j.get('ended'):
        s=dt.datetime.fromisoformat(j['started']);e=dt.datetime.fromisoformat(j['ended'])
        j['dur']=(e-s).total_seconds()/60;J.append(j)
print(len(J))
J.sort(key=lambda j:-j['dur'])
for j in J[:6]:
    est=j.get('estimates') or []
    first=est[0]['from'] if est else j.get('estimate_min')
    print(j['id'],round(j['dur']),round(j['dur']/60,2),j.get('threads'),j['started'],j['ended'],'est',j.get('estimate_min'),'first',first,[(e['at'][5:16],e['from'],e['to'],e['reason'][:50]) for e in est],j.get('status'),j.get('lane'))
print('wall h',sum(j['dur'] for j in J)/60,'thread h',sum(j['dur']*(j.get('threads') or 1) for j in J)/60)
r=[j['dur']/j['estimate_min'] for j in J if j.get('estimate_min') and j['dur']<60]
print('short n',len(r),'median ratio',st.median(r))
r2=[j['dur']/(j['estimates'][0]['from'] if j.get('estimates') else j['estimate_min']) for j in J if j.get('estimate_min') and j['dur']<60]
print('short median vs original',st.median(r2))
# jobs between 0083 and 0113 in lane
for j in sorted(J,key=lambda j:j['started']):
    if '2026-11-04T03' <= j['started'] <= '2026-11-05T15' and j['dur']>60: print(j['id'],j['started'][5:16],j['ended'][5:16],round(j['dur']),j.get('lane'))
