import json, collections
REPO = "results/real-game/"
def dec(folder, idx, floor):
    k, prev, out = -1, None, []
    for l in open(REPO + folder + "/decisions.jsonl", encoding="utf-8"):
        if not l.strip(): continue
        d = json.loads(l)
        if prev is None or d["floor"] < prev: k += 1
        prev = d["floor"]
        if k == idx and d["floor"] == floor and "options" in d and "turn" in d: out.append(d)
    return out
for folder, idx, fl, lo, hi in (("20261114-205554", 1, 5, 14, 82), ("20261114-112420", 0, 2, 4, 28)):
    ds = dec(folder, idx, fl)
    print("==", folder, len(ds), "decisions; turns", ds[0]["turn"], ds[-1]["turn"])
    picks = collections.Counter(); spread = []
    for d in ds:
        if lo <= d["turn"] <= hi:
            o = d["options"][d["pick"]]; picks[str(o)] += 1
            sc = d["two"]; spread.append((round(max(sc), 3), round(sorted(sc)[-2], 3) if len(sc) > 1 else None, round(min(sc), 3)))
    print(picks.most_common(12))
    print(collections.Counter(spread).most_common(8))
    for d in ds:
        if d["turn"] in (lo, lo + 1, 50):
            print(d["turn"], d["view"]["hand"], [m["name"] + ":" + str(m["hp"]) + "/" + str(m["block"]) for m in d["view"]["monsters"]], list(zip(map(str, d["options"]), [round(x, 3) for x in d["two"]])), "pick", d["pick"], "line", d.get("line"))
