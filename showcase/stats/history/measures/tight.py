import csv,statistics as S
xs=[];ys=[]
for r in csv.DictReader(open('runs/index.csv')):
    if r['bench_version']=='1' and r['date']>='2026-10-25':
        xs.append(float(r['tight_train_win']));ys.append(float(r['tight_held_out_win'])); print(r['run'][11:],r['tight_train_win'],r['tight_held_out_win'])
print('n',len(xs),'r %.2f'%S.correlation(xs,ys),'held min %.3f max %.3f'%(min(ys),max(ys)))
