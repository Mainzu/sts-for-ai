import sys, os, json, collections, time
ROOT='.'
sys.path.insert(0, ROOT+'/scripts')
import real_game_report as R
runs = R.all_runs()
print('runs', len(runs))
idx = {(r['folder'], r['seed']): i+1 for i, r in enumerate(runs)}
info = {}
for i, r in enumerate(runs):
    info[(r['folder'], r['seed'])] = (i+1, r.get('ascension'), r['run_rules'], r['fight_guard'], {f['floor']: f['group'] for f in r['fights']})
asc_of = collections.Counter((r.get('ascension')) for r in runs); print(asc_of)
used = collections.Counter(); bygroup = collections.Counter(); perrun = collections.Counter()
fights = collections.Counter()
for r in runs:
    for f in r['fights']: fights[(r.get('ascension'), f['group'])] += 1
logcount = collections.Counter()
for (folder, seed), (n, asc, rr, fg, groups) in info.items(): pass
folders = sorted({k[0] for k in info})
for folder in folders:
    p = os.path.join(ROOT, 'results/real-game', folder)
    lc = sum(1 for l in open(p+'/log.txt', encoding='utf-8', errors='replace') if 'send: potion use' in l)
    prev = None; c = 0
    with open(p+'/states.jsonl', encoding='utf-8') as fh:
        for line in fh:
            if not line.strip(): continue
            gs = json.loads(line)['msg'].get('game_state')
            if not gs or gs.get('seed') is None: continue
            key = (folder, gs['seed'])
            pots = [x.get('id') or x.get('name') for x in gs.get('potions', [])]
            if prev and prev[0] == key and 'combat_state' in prev[2] and key in info:
                for k, (a, b) in enumerate(zip(prev[1], pots)):
                    if a not in (None, 'Potion Slot') and b != a:
                        n, asc, rr, fg, groups = info[key]
                        name = [x.get('name') for x in prev[2].get('potions', [])][k]
                        g = groups.get(prev[2].get('floor'), '?')
                        used[(asc, name)] += 1; bygroup[(asc, g)] += 1; perrun[(asc, n)] += 1; c += 1
            prev = (key, pots, gs)
    logcount[folder] = (lc, c)
for f, v in logcount.items():
    if v[0] != v[1]: print('mismatch', f, v)
print('log total', sum(v[0] for v in logcount.values()), 'state total', sum(v[1] for v in logcount.values()))
for asc in (0, 20):
    tot = sum(v for (a, _), v in used.items() if a == asc)
    nr = sum(1 for r in runs if r.get('ascension') == asc)
    print('ASC', asc, 'potions', tot, 'runs', nr)
    for (a, nm), v in used.most_common():
        if a == asc: print('  ', nm, v)
    for g in ('hallway', 'elite', 'boss', '?'):
        print('  ', g, bygroup[(asc, g)], fights[(asc, g)], bygroup[(asc, g)]/max(1, fights[(asc, g)]))
