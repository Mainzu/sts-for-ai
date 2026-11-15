import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load import *
rs = runs()
print(len(rs))
bad = 0
for r in rs:
    ff = sorted({f["floor"] for f in r["fights"]})
    df = sorted({d["floor"] for d in r["decisions"] if "turn" in d})
    if ff != df:
        bad += 1; print(r["n"], r["folder"], ff, df, r["nsplit"], r["nwf"])
print("bad", bad)
import collections
c = collections.Counter()
for r in rs:
    for d in r["decisions"]:
        if "options" in d and "turn" in d:
            for o in d["options"]:
                c[len(o)] += 1
                for a in o: c[a.split("@")[0]] += 0
print(c.most_common(10))
keys=collections.Counter()
for r in rs:
    for f in r["fights"]: keys.update(f.keys())
print(keys)
