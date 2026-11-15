import json, os, sys, pickle
sys.path.insert(0, 'scripts')
import real_game_report as R
REC = R.RECORDS
out = {}  # seed -> list of compact state rows around events
for name in sorted(os.listdir(REC)):
    folder = os.path.join(REC, name)
    if not (os.path.isdir(folder) and name[:1].isdigit()): continue
    p = os.path.join(folder, 'states.jsonl')
    if not os.path.exists(p): continue
    prev_event = {}
    with open(p, encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            row = json.loads(line)
            gs = row['msg'].get('game_state')
            if not gs or gs.get('seed') is None: continue
            seed = gs['seed']
            ev = gs.get('screen_type') == 'EVENT' or gs.get('room_phase') == 'EVENT'
            if ev or prev_event.get(seed):
                ss = gs.get('screen_state') or {}
                rec = dict(t=row['t'], folder=name, floor=gs.get('floor'), st=gs.get('screen_type'), rp=gs.get('room_phase'),
                    ev=ss.get('event_name') if gs.get('screen_type')=='EVENT' else None,
                    body=(ss.get('body_text') or '')[:200] if gs.get('screen_type')=='EVENT' else None,
                    opts=[(o.get('text'), o.get('disabled')) for o in ss.get('options', [])] if gs.get('screen_type')=='EVENT' else None,
                    hp=gs.get('current_hp'), mhp=gs.get('max_hp'), gold=gs.get('gold'),
                    relics=[r['name'] for r in gs.get('relics', [])], deck=sorted(R.card(c) for c in gs.get('deck', [])),
                    asc=gs.get('ascension_level'), combat='combat_state' in gs,
                    mons=[m['id'] for m in gs['combat_state']['monsters']] if 'combat_state' in gs else None)
                out.setdefault(seed, []).append(rec)
            prev_event[seed] = ev
pickle.dump(out, open('dump.pkl', 'wb'))
print(len(out))
