exec(open('v.py').read().split("import sys")[0])
r=[]
for e in ents:
    d=datetime.datetime.fromtimestamp(e[1],tz).strftime('%m-%d %H:%M')
    r.append((e[3],e[0][:70],d))
for x in sorted(r,reverse=True)[:6]: print(x)
print('---P1/P2')
for x in r[:28]: print(x)
# date mismatch: titled date vs blame date
import re
mm=0
for x in r:
    m=re.search(r'2026-(\d\d-\d\d)',x[1]) 
for e in ents:
    m=re.search(r'2026-(\d\d-\d\d)',e[0]); d=datetime.datetime.fromtimestamp(e[1],tz).strftime('%m-%d')
    if m and m.group(1)!=d: mm+=1; print('MISMATCH',m.group(1),d,e[0][:60])
print(mm)
