import sys, statistics as S, collections
sys.path.insert(0, '.')
import load
from load import clean
D = [(n, s, d) for n, s, d in load.decisions() if 'turn' in d]
for A in (0, 20):
    xs = sorted(d['seconds'] for n, s, d in D if s[0] == A)
    cut = sum(d.get('cut', False) for n, s, d in D if s[0] == A)
    print(A, len(xs), 'median', S.median(xs), 'mean', round(S.mean(xs), 2), 'p90', xs[int(.9*len(xs))], 'p99', xs[int(.99*len(xs))], 'max', xs[-5:], 'cut', cut, 'total', round(sum(xs)))
    tot = sum(xs); top = sum(xs[-len(xs)//100:]); print('  top1% share', round(top/tot, 3), 'top10%', round(sum(xs[-len(xs)//10:])/tot, 3))
