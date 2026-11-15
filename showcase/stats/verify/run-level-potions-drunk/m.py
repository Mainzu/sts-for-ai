import json, time, sys
ROOT='results/real-game/'
for folder in sys.argv[1:]:
    print('==', folder)
    for l in open(ROOT+folder+'/log.txt', encoding='utf-8', errors='replace'):
        if 'potion' in l: print('LOG', l.strip())
    prev=None
    for line in open(ROOT+folder+'/states.jsonl', encoding='utf-8'):
        if not line.strip(): continue
        row=json.loads(line); gs=row['msg'].get('game_state')
        if not gs: continue
        pots=[x.get('name') for x in gs.get('potions',[])]
        if prev and prev[1]!=pots:
            print(time.strftime('%H:%M:%S', time.localtime(row['t'])), 'fl', gs.get('floor'), 'combat' if 'combat_state' in prev[2] else '-', prev[2].get('screen_type'), prev[1], '->', pots, [m['name'] for m in gs.get('combat_state',{}).get('monsters',[])])
        prev=(row['t'],pots,gs)
