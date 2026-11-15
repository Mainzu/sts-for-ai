import json,sys,glob,os
root=sys.argv[1]
for f in sorted(glob.glob(os.path.join(root,'results/exact-puzzles/*.json'))):
    d=json.load(open(f))['sets']['puzzles']['halves']
    out=[os.path.basename(f)]
    for k in ['h0','h1','h2+','contested','all']:
        n=0;c=0;r=0
        for h in d.values():
            m=h['counts']['puzzles.'+k];n+=m;c+=round(h['metrics']['accuracy.'+k][0]*m);r+=h['metrics']['regret.'+k][0]*m
        out.append(f"{k}:{c}/{n}={100*c/n:.1f}% reg{r/n:.4f}")
    print(' | '.join(out))
