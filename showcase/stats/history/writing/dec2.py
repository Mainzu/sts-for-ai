import json,re,statistics,collections
s=json.load(open('secs.json'))
def cls(x):
    h=x['h']
    if re.match(r'Lane \S+ (opened|closed) \(\d{4}',h): return 'lane opened/closed records'
    if x['who']=='owner': return 'owner'
    if x['who']=='unmarked' and x['p']<=2: return 'owner'
    if x['who']=='owner away (Claude)': return 'Claude, owner away'
    if x['who']=="on the owner's behalf": return "roles, on the owner's behalf"
    return 'other unmarked'
rows=['owner','Claude, owner away',"roles, on the owner's behalf",'lane opened/closed records','other unmarked']
c=collections.Counter((cls(x),x['p']) for x in s)
for r in rows: print(r,[c[(r,p)] for p in range(1,9)], sum(c[(r,p)] for p in range(1,9)))
for x in s:
    if cls(x)=='other unmarked': print(' ',x['d'],x['h'][:90])
for p in range(1,9):
    w=[x['w'] for x in s if x['p']==p]; print(p,'median',statistics.median(w),'max',max(w),'n',len(w))
print('all median',statistics.median([x['w'] for x in s]),'total',sum(x['w'] for x in s))
