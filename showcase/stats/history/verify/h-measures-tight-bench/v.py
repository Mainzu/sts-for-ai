import csv,collections
rows=list(csv.DictReader(open(r'runs/index.csv')))
c=collections.Counter((r['bench_version'],r['date'][:10]) for r in rows)
for k in sorted(c): print(k,c[k])
b1=[r for r in rows if r['bench_version']=='1']
for r in b1: print(r['run'],r['date'],r['config'],r['switches'][:60],r['tight_train_win'][:40],r['tight_held_out_win'][:40])
s=[r for r in b1 if '10-25'<=r['date'][5:10]<='10-28']
x=[float(r['tight_train_win']) for r in s]; y=[float(r['tight_held_out_win']) for r in s]
import statistics as st
print(len(s), st.correlation(x,y), max(y))
print(s[0]['tight_held_out_win'], s[0]['tight_train_win'])
