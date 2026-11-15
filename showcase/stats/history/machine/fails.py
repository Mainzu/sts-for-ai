import json,glob,os,collections
R=''
for f in sorted(glob.glob(R+'jobs/done/*.json')):
    j=json.load(open(f,encoding='utf-8'))
    if j['status'] not in('failed','lost','ended-unknown','killed'): continue
    lg=j['log'].replace(chr(92),'/'); tail=''
    if os.path.exists(lg):
        with open(lg,'rb') as h:
            h.seek(0,2);n=h.tell();h.seek(max(0,n-3000))
            L=[l for l in h.read().decode('utf-8','replace').splitlines() if l.strip()]
            err=[l for l in L if any(w in l for w in ('Error','error','FAILED','Traceback','exit','overflow','memory','Killed','assert'))]
            tail=(err[-1] if err else (L[-1] if L else ''))[:140]
    else: tail='(no log)'
    print(j['id'],j['status'],j.get('exit_code'),'|',j.get('reason',''),'|',tail)
