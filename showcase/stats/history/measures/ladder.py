import json
for l in open('results/ladder/log.jsonl'):
    r=json.loads(l)
    if r['when'][:10]<='2026-10-31': print(r['id'],r['when'][5:16],r['verdict'],r['pairs'],round(100*r['lead'],1),r['candidate'].split('/')[1],'vs',r['champion'].split('/')[-2] if '/' in r['champion'] else r['champion'])
