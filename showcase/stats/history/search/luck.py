# Luck studies (11-11): how much of a label's spread is luck, and the luck-corrected paired read.
import json, sys
R = sys.argv[1] + "/results/luck/"
a = json.load(open(R + "luck-share-g1600.json"))["slices"]["all"]
print("games", a["games"], "rows", a["rows"], "label var", round(a["label_var"], 3), "noise var", round(a["noise_var"], 3),
      "luck share of spread", round(a["noise_var"] / a["label_var"], 3), "noise removed by correction", round(a["noise_share"], 3), "se", round(a["noise_se"], 3))
b = json.load(open(R + "luck-read-cells.json"))
print("sequences", b["sequences"], "sd raw", round(b["sd_raw"], 2), "sd corrected", round(b["sd_corrected"], 2), "ratio", round(b["ratio"], 2), "se", round(b["ratio_se"], 2), "bar", b["bar"], "pass", b["pass"])
