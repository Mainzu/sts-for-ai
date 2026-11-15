import json,os,collections,datetime as dt
R='jobs/done/'
out=[]
for f in sorted(os.listdir(R)):
    j=json.load(open(R+f)); cmd=j.get('cmd'); cmd=' '.join(cmd) if isinstance(cmd,list) else cmd
    if not any(s in cmd for s in ('learn.py','finetune.py','family.py','two_turn_round.py')): continue
    if not (j.get('started') and j.get('ended')): continue
    h=(dt.datetime.fromisoformat(j['ended'])-dt.datetime.fromisoformat(j['started'])).total_seconds()/3600
    out.append(dict(h=h,id=j['id'],cmd=cmd,status=j.get('status'),threads=j.get('threads'),started=j['started'],note=j.get('note')))
json.dump(out,open('trainjobs.json','w'),indent=0)
print(len(out), round(sum(o['h']*(o['threads'] or 1) for o in out),1),'thread-h')
for o in sorted(out,key=lambda o:-o['h'])[:10]: print(round(o['h'],2),o['id'],o['status'],o['threads'],o['started'][:16],o['cmd'][30:230],'|',(o['note'] or '')[:150])
