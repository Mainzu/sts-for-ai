import sys, pickle
sys.path.insert(0, 'scripts')
import real_game_report as R
runs = R.all_runs()
info = [dict(n=i+1, seed=r['seed'], folder=r['folder'], asc=R.asc(r), rules=r['run_rules'], guard=r['fight_guard'],
   fights=[(f['floor'], f['group'], f['monsters'], f['hp_start'], f['hp_end'], f.get('hp_after'), f['won']) for f in r['fights']], lastfloor=r['last'].get('floor')) for i, r in enumerate(runs)]
pickle.dump(info, open('runs.pkl','wb'))
print(len(info)); print([(x['n'],x['asc'],x['rules'],x['guard']) for x in info])
