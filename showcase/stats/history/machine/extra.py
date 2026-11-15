import json,glob,collections,statistics as S,sys
from datetime import datetime
R='jobs/done/'
exec(open('jobs_stats.py').read().split("mode=")[0].split("R='")[0])  # imports only
sys.argv=['x','none'];exec(open('jobs_stats.py').read())
m=sys.argv0 if False else None
