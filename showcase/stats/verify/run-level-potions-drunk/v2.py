import sys, os, json, collections, time, bisect
ROOT='.'
sys.path.insert(0, ROOT+'/scripts')
import real_game_report as R
runs = R.all_runs()
info = {(r['folder'], r['seed']): (i+1, r.get('ascension'), {f['floor']: f['group'] for f in r['fights']}) for i, r in enumerate(runs)}
fights = collections.Counter((r.get('ascension'), f['group']) for r in runs for f in r['fights'])
used = collections.Counter(); byg = collections.Counter(); perrun = collections.Counter(); refused = 0; unmatched = []
for folder in sorted({k[0] for k in info}):
    p = os.path.join(ROOT, 'results/real-game', folder)
    sts = []
    with open(p+'/states.jsonl', encoding='utf-8') as fh:
        for line in fh:
            if not line.strip(): continue
            row = json.loads(line); gs = row['msg'].get('game_state')
            if not gs or gs.get('seed') is None: continue
            sts.append((row['t'], gs['seed'], gs.get('floor'), [x.get('name') for x in gs.get('potions', [])], 'combat_state' in gs, [m['name'] for m in gs.get('combat_state', {}).get('monsters', [])]))
    ts = [s[0] for s in sts]
    day0 = time.mktime(time.strptime(folder[:8], '%Y%m%d')); last = -1; off = 0
    L = open(p+'/log.txt', encoding='utf-8', errors='replace').read().splitlines()
    for i, l in enumerate(L):
        hh = l[:8]
        try: sec = int(hh[:2])*3600+int(hh[3:5])*60+int(hh[6:8])
        except: continue
        if sec < last - 3600: off += 86400
        last = sec
        if 'send: potion use' not in l: continue
        if i+1 < len(L) and 'game error' in L[i+1] and L[i+1][:8] == hh: refused += 1; continue
        slot = int(l.split('potion use')[1].split()[0])
        t = day0 + off + sec + 0.999
        j = bisect.bisect_right(ts, t) - 1
        # walk back to a combat state whose slot is filled
        while j >= 0 and not (sts[j][4] and slot < len(sts[j][3]) and sts[j][3][slot] != 'Potion Slot'): j -= 1
        if j < 0: unmatched.append((folder, l)); continue
        _, seed, floor, pots, _, mons = sts[j]
        key = (folder, seed)
        if key not in info: unmatched.append((folder, l, 'norun')); continue
        n, asc, groups = info[key]
        used[(asc, pots[slot])] += 1; byg[(asc, groups.get(floor, '?'))] += 1; perrun[(asc, n)] += 1
print('refused', refused, 'unmatched', unmatched)
for asc in (0, 20):
    tot = sum(v for (a, _), v in used.items() if a == asc); nr = sum(1 for r in runs if r.get('ascension') == asc)
    rr = [r for r in runs if r.get('ascension') == asc]
    print('ASC', asc, 'potions', tot, 'runs', nr, 'per run %.2f' % (tot/nr), 'runs n', min(info[(r['folder'],r['seed'])][0] for r in rr), max(info[(r['folder'],r['seed'])][0] for r in rr))
    print('  ', [(nm, v) for (a, nm), v in used.most_common() if a == asc][:12])
    for g in ('hallway', 'elite', 'boss', '?'):
        print('  ', g, byg[(asc, g)], fights[(asc, g)], '%.3f' % (byg[(asc, g)]/max(1, fights[(asc, g)])))
