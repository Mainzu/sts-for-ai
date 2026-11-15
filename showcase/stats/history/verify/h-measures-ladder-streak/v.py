import json
for l in open(r'results/ladder/log.jsonl'):
    r=json.loads(l)
    print(r['id'],r['when'][:16],r['candidate'].replace('runs/','')[:50],'|',r['champion'].replace('runs/','')[:30],r['verdict'],r['promoted'],r['pairs'],round(r['lead']*100,1))
