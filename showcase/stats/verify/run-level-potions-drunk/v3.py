import sys, os, json, collections, time
ROOT='.'
sys.path.insert(0, ROOT+'/scripts')
import real_game_report as R
runs = R.all_runs()
info = {(r['folder'], r['seed']): (i+1, r.get('ascension'), {f['floor']: f['group'] for f in r['fights']}) for i, r in enumerate(runs)}
fights = collections.Counter((r.get('ascension'), f['group']) for r in runs for f in r['fights'])
used = collections.Counter(); byg = collections.Counter(); perrun = collections.Counter(); badcmd = []; auto = []
for folder in sorted({k[0] for k in info}):
    p = os.path.join(ROOT, 'results/real-game', folder)
    tr = []; prev = None
    with open(p+'/states.jsonl', encoding='utf-8') as fh:
        for line in fh:
            if not line.strip(): continue
            row = json.loads(line); gs = row['msg'].get('game_state')
            if not gs or gs.get('seed') is None: continue
            pots = [x.get('name') for x in gs.get('potions', [])]
            if prev and prev[1] == gs['seed'] and prev[3] and len(prev[2]) == len(pots):
                for k, (a, b) in enumerate(zip(prev[2], pots)):
                    if a != 'Potion Slot' and b == 'Potion Slot':
                        tr.append([row['t'], k, a, prev[4], gs['seed'], False])
            prev = (row['t'], gs['seed'], pots, 'combat_state' in gs and gs.get('screen_type') != 'GAME_OVER', gs.get('floor'))
    day0 = time.mktime(time.strptime(folder[:8], '%Y%m%d')); last = -1; off = 0
    for l in open(p+'/log.txt', encoding='utf-8', errors='replace'):
        try: sec = int(l[:2])*3600+int(l[3:5])*60+int(l[6:8])
        except: continue
        if sec < last - 3600: off += 86400
        last = sec
        if 'send: potion use' not in l: continue
        slot = int(l.split('potion use')[1].split()[0]); t = day0 + off + sec
        c = [x for x in tr if not x[5] and x[1] == slot and t - 1 <= x[0] <= t + 30]
        if not c: badcmd.append((folder, l.strip())); continue
        x = c[0]; x[5] = True
        n, asc, groups = info[(folder, x[4])]
        used[(asc, x[2])] += 1; byg[(asc, groups.get(x[3], '?'))] += 1; perrun[(asc, n)] += 1
    auto += [(folder, x[2], x[3]) for x in tr if not x[5]]
print('commands without a potion leaving:', badcmd)
print('potions leaving with no command:', auto)
for asc in (0, 20):
    tot = sum(v for (a, _), v in used.items() if a == asc); nr = sum(1 for r in runs if r.get('ascension') == asc)
    print('ASC', asc, 'potions', tot, 'runs', nr, 'per run %.2f' % (tot/nr), 'runs with 0:', sum(1 for r in runs if r.get('ascension')==asc and perrun[(asc, info[(r['folder'],r['seed'])][0])]==0))
    print('  ', [(nm, v) for (a, nm), v in used.most_common() if a == asc][:12])
    for g in ('hallway', 'elite', 'boss', '?'):
        print('  ', g, byg[(asc, g)], fights[(asc, g)], '%.3f' % (byg[(asc, g)]/max(1, fights[(asc, g)])))
