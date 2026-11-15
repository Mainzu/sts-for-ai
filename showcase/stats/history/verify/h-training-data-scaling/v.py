import json,glob,os,re
R='runs/'
rows={}
for d in sorted(glob.glob(R+'*-data*k-s*-r1-*')):
    if not os.path.exists(d+'/round.json'): print('MISSING',d); continue
    rj=json.load(open(d+'/round.json')); cf=json.load(open(d+'/config.json')); run=json.load(open(d+'/run.json'))
    g=rj.get('gate',{}).get('halves',{})
    ho=g.get('held_out',{}); tr=g.get('train',{})
    bench=[k for k in rj if 'bench' in k.lower()]
    m=re.search(r'data(\d+)k-s(\d+)',d)
    print(os.path.basename(d), run['created'], cf['n_train'], cf['seed'], cf['train_seed'], cf['round0_seed'], cf.get('solve_threads'), rj.get('finished'), ho.get('net',[None])[0], tr.get('net',[None])[0], ho.get('n'), rj.get('bench'), run.get('datasets'))
