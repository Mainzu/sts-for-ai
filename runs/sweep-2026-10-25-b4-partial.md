# Learned-play sweep 2026-10-25

| run | target | branches | seed | run id (last round) | n/group | n_round | n_late | minutes (projected) |
|---|---|---|---|---|---|---|---|---|
| score-s0 | score | off | 0 | 2026-10-25-score-s0-r3-882c853 | 20000 | 908 | 909 | 40.7 (45.4) |
| score+branch-s0 | score | on | 0 | 2026-10-25-score+branch-s0-r3-9bdebe2 | 20000 | 908 | 909 | 179.6 (51.2) |


## mean over seeds

Point estimates averaged over the finished seeds (no interval).

| config | seeds | win train | win held-out | ranking train | ranking held-out |
|---|---|---|---|---|---|
| score | 1 | 0.448 | 0.444 | 0.854 | 0.880 |
| score+branch | 1 | 0.500 | 0.467 | 0.869 | 0.889 |

## tight / held_out

```
config                                 prediction           prediction           decisions            decisions            decisions            strength             strength            
                                       mse                  mse@dec              regret               ranking              rank(unc)            win                  hp lost             
-------------------------------------  -------------------  -------------------  -------------------  -------------------  -------------------  -------------------  --------------------
2026-10-25-score-s0-r3-882c853         0.877 [0.815,0.940]  0.573 [0.519,0.624]  0.048 [0.034,0.064]  0.880 [0.860,0.900]  0.911 [0.890,0.932]  0.444 [0.403,0.485]  9.469 [8.242,10.751]
2026-10-25-score+branch-s0-r3-9bdebe2  0.833 [0.783,0.884]  0.515 [0.466,0.565]  0.039 [0.027,0.053]  0.889 [0.869,0.910]  0.923 [0.903,0.941]  0.467 [0.426,0.509]  9.187 [7.951,10.391]
```

## tight / train

```
config                                 prediction           prediction           decisions            decisions            decisions            strength             strength            
                                       mse                  mse@dec              regret               ranking              rank(unc)            win                  hp lost             
-------------------------------------  -------------------  -------------------  -------------------  -------------------  -------------------  -------------------  --------------------
2026-10-25-score-s0-r3-882c853         0.824 [0.775,0.879]  0.545 [0.494,0.596]  0.087 [0.063,0.112]  0.854 [0.833,0.878]  0.896 [0.877,0.917]  0.448 [0.409,0.487]  9.172 [8.050,10.328]
2026-10-25-score+branch-s0-r3-9bdebe2  0.810 [0.762,0.860]  0.520 [0.466,0.575]  0.083 [0.062,0.106]  0.869 [0.849,0.891]  0.910 [0.892,0.928]  0.500 [0.460,0.540]  8.730 [7.675,9.844] 
```

## tight / gap:held_out

```
config                                 prediction            prediction             decisions               decisions             decisions             strength               strength            
                                       mse                   mse@dec                regret                  ranking               rank(unc)             win                    hp lost             
-------------------------------------  --------------------  ---------------------  ----------------------  --------------------  --------------------  ---------------------  --------------------
2026-10-25-score-s0-r3-882c853         0.052 [-0.034,0.132]  0.027 [-0.046,0.101]   -0.039 [-0.067,-0.009]  0.026 [-0.004,0.054]  0.015 [-0.015,0.043]  -0.004 [-0.061,0.053]  0.297 [-1.396,1.926]
2026-10-25-score+branch-s0-r3-9bdebe2  0.023 [-0.052,0.093]  -0.005 [-0.076,0.072]  -0.043 [-0.071,-0.016]  0.020 [-0.010,0.048]  0.012 [-0.014,0.037]  -0.033 [-0.090,0.025]  0.458 [-1.299,2.086]
```

## representation

```
config                                 probes pass          aliased/sibling pairs (effects)   aliased/sibling pairs (own)     
-------------------------------------  -------------------  --------------------------------  --------------------------------
2026-10-25-score-s0-r3-882c853         1.000 [0.785,1.000]  held_out 0/11112 / train 0/11011  held_out 0/11112 / train 0/11011
2026-10-25-score+branch-s0-r3-9bdebe2  1.000 [0.785,1.000]  held_out 0/11112 / train 0/11011  held_out 0/11112 / train 0/11011
```
