/* The statistics tab's data, by period: each statistic mined by one script and recomputed by an independent
   second one (workflows sts-fun-stats and sts-history-stats, 2026-11-14; scripts in showcase/stats/);
   written by stats/build_data.py, don't edit by hand. */
window.STATS = [
 {
  "key": "all",
  "name": "Across the whole project",
  "dates": "23 October to 14 November",
  "parts": [
   {
    "name": "",
    "items": [
     {
      "id": "h-training-nets-per-period",
      "title": "521 nets in 23 days, and the kind of training flipped twice",
      "claim": "The project trained 521 value nets that were saved with weights. Up to the end of period 4 almost all were trained from scratch (285 of 331). In periods 5 and 6 short fine-tunes of an existing net took over (145 of 153). In period 7 the new content brought back training from scratch (20 of 29). The busiest stretch was period 3, the first three days with the owner away: 155 nets, about 52 a day.",
      "tag": "project history · all 23 days",
      "setting": "Every runs/2026-* folder that holds a model.pt. 'Fine-tune' means the config names a parent net or a games count (scripts/finetune.py and family.py bursts). 'From scratch' means the config has n_train: scripts/learn.py in rounds of self-play, or the single-shot baseline trainings of 10-24 (P1, no rounds). Dated by created in run.json (local time). · n: 521 nets (P1 8, P2 112, P3 155, P4 56, P5 17, P6 136, P7 29, P8 8)",
      "caveat": "Five more run folders have no saved model (unfinished or failed) and are not counted. Periods differ in length (2 to 4 days); per day, P3 is still the busiest. The 8 P1 nets were single trainings, not rounds of self-play. The longest single training job was a fine-tune on 11-07 (0278-finetune, 3.95 hours on 3 threads); the one that used the most machine time was allcontent40k-s101 on 11-08 (3.4 hours on 6 threads, about 20 thread-hours).",
      "checked": "corrected",
      "viz": {
       "kind": "line",
       "unit": "nets trained",
       "x_label": "period",
       "y_label": "nets",
       "series": [
        {
         "name": "from scratch",
         "points": [
          {
           "x": "P1",
           "y": 8
          },
          {
           "x": "P2",
           "y": 112
          },
          {
           "x": "P3",
           "y": 128
          },
          {
           "x": "P4",
           "y": 37
          },
          {
           "x": "P5",
           "y": 0
          },
          {
           "x": "P6",
           "y": 8
          },
          {
           "x": "P7",
           "y": 20
          },
          {
           "x": "P8",
           "y": 2
          }
         ]
        },
        {
         "name": "fine-tune of an existing net",
         "points": [
          {
           "x": "P1",
           "y": 0
          },
          {
           "x": "P2",
           "y": 0
          },
          {
           "x": "P3",
           "y": 27
          },
          {
           "x": "P4",
           "y": 19
          },
          {
           "x": "P5",
           "y": 17
          },
          {
           "x": "P6",
           "y": 128
          },
          {
           "x": "P7",
           "y": 9
          },
          {
           "x": "P8",
           "y": 6
          }
         ]
        }
       ]
      }
     },
     {
      "id": "h-training-games-per-day",
      "title": "4.4 million practice fights, a quarter of them on one day",
      "claim": "The engine played 4,370,543 distinct practice fights to make training data, stored in 268 distinct datasets. 31 October alone produced 1,132,230 fights, more than periods 1, 2, 5, 6 and 8 together (1,082,768). Most of the data (3.57 million fights, 82%) came from round-0 pools that the search played with its hand-written heuristic. Only 0.80 million fights were played by a net, which is self-play in the strict sense.",
      "tag": "project history · all 23 days",
      "setting": "Every datasets/<id>/manifest.json (n_games), counted once per distinct games file (games_sha256). This drops 17 byte-identical regenerated copies (104,069 fights) and the leftover daf87b2b715e.tmp folder. Each dataset is dated by the first run that trained on it; datasets no run used are dated by their file time. · n: 268 distinct datasets, 4,370,543 fights",
      "caveat": "A dataset counts once, on the day it was first used, even if later nets trained on it again. Copies whose games file is identical to an earlier one (the same seeds regenerated) are counted only once. Pools played by the heuristic are cheap and large (up to 240,000 fights). Sets played by a net are small (a few thousand per round).",
      "checked": "corrected",
      "viz": {
       "kind": "line",
       "unit": "fights generated",
       "x_label": "day (2026)",
       "y_label": "fights",
       "series": [
        {
         "name": "fights in new datasets",
         "points": [
          {
           "x": "10-24",
           "y": 35241
          },
          {
           "x": "10-25",
           "y": 298519
          },
          {
           "x": "10-26",
           "y": 64740
          },
          {
           "x": "10-27",
           "y": 23858
          },
          {
           "x": "10-28",
           "y": 95325
          },
          {
           "x": "10-29",
           "y": 0
          },
          {
           "x": "10-30",
           "y": 279588
          },
          {
           "x": "10-31",
           "y": 1132230
          },
          {
           "x": "11-01",
           "y": 709761
          },
          {
           "x": "11-02",
           "y": 18423
          },
          {
           "x": "11-03",
           "y": 7050
          },
          {
           "x": "11-04",
           "y": 0
          },
          {
           "x": "11-05",
           "y": 1900
          },
          {
           "x": "11-06",
           "y": 11700
          },
          {
           "x": "11-07",
           "y": 38100
          },
          {
           "x": "11-08",
           "y": 254312
          },
          {
           "x": "11-09",
           "y": 3198
          },
          {
           "x": "11-10",
           "y": 595481
          },
          {
           "x": "11-11",
           "y": 294747
          },
          {
           "x": "11-12",
           "y": 257545
          },
          {
           "x": "11-13",
           "y": 248825
          }
         ]
        }
       ]
      }
     },
     {
      "id": "h-machine-wait",
      "title": "How long a job waited in the queue before it started",
      "claim": "In period 5 the median job started 5.5 minutes after it was queued. In period 6, when family chains queued hundreds of reads at once, the median wait rose to 124 minutes, and one job in ten waited more than 4.7 hours. The longest wait in the queue's history was 30.6 hours: 0059l8b-bash, queued 11-01 15:48 and started 11-02 22:21. It was waiting for memory, not for another job: its 6 GB reservation never fit in the free RAM, and it started one minute after a manager cut the reservation to 3.5 GB.",
      "tag": "project history · all 23 days",
      "setting": "started jobs; wait = started minus added; period by start time · n: 1,091 started jobs (P3 105, P4 168, P5 120, P6 470, P7 182, P8 46)",
      "caveat": "Part of each wait is deliberate. About 3 in 10 started jobs were queued to run only after another job (--after) or only if another passed (--if-passed). Others waited for their memory reservation to fit, so a wait does not only mean waiting for free threads. Periods 1 and 2 had no queue.",
      "checked": "corrected",
      "viz": {
       "kind": "line",
       "unit": "minutes",
       "x_label": "period",
       "y_label": "minutes from queued to started",
       "series": [
        {
         "name": "median wait",
         "points": [
          {
           "x": "P3",
           "y": 122.7
          },
          {
           "x": "P4",
           "y": 17.8
          },
          {
           "x": "P5",
           "y": 5.5
          },
          {
           "x": "P6",
           "y": 124.4
          },
          {
           "x": "P7",
           "y": 97.5
          },
          {
           "x": "P8",
           "y": 30.7
          }
         ]
        },
        {
         "name": "90th percentile wait",
         "points": [
          {
           "x": "P3",
           "y": 528
          },
          {
           "x": "P4",
           "y": 228
          },
          {
           "x": "P5",
           "y": 183
          },
          {
           "x": "P6",
           "y": 284
          },
          {
           "x": "P7",
           "y": 607
          },
          {
           "x": "P8",
           "y": 304
          }
         ]
        }
       ]
      }
     },
     {
      "id": "h-machine-hours",
      "title": "The machine did not sleep: busy threads by hour of day",
      "claim": "The queue ran day and night. Between midnight and 08:00, it used 31.5% of all queue thread-hours, close to the 33.3% an even spread would give. Over the whole queue the quietest hour, 07:00, still averaged 3.7 busy threads against 5.5 at the busiest, 10:00. In period 3 the machine was busy around the clock (12 threads at midnight, 01:00 and 08:00). In period 5 the nights were the quiet part (about 2 threads, 1.6 to 2.3, from 22:00 to 04:00), while the long mutated-monster jobs ran in the day.",
      "tag": "project history · all 23 days",
      "setting": "started jobs; each job's threads spread over the clock hours it ran; value = average busy threads in that clock hour for that period (thread-hours divided by the number of such hours the queue existed, 10-30 12:00 to 11-14 06:00) · n: 1,091 started jobs, 1,710 thread-hours",
      "caveat": "Threads are what each job declared, not measured CPU use. Work run outside the queue (training in periods 1 and 2, the real game, builds) is not counted. P3 covers only 10-30 12:00 to 10-31, and P8 ends with the last finished job on 11-14 06:07, so each of their cells averages over one or two days (P8's 07:00 to 23:00 cells come from 11-13 alone).",
      "checked": "corrected",
      "viz": {
       "kind": "heat",
       "unit": "average busy threads",
       "xs": [
        "00",
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
        "16",
        "17",
        "18",
        "19",
        "20",
        "21",
        "22",
        "23"
       ],
       "ys": [
        "P3",
        "P4",
        "P5",
        "P6",
        "P7",
        "P8"
       ],
       "cells": [
        [
         12,
         12,
         9.8,
         9.8,
         6,
         7.8,
         11.2,
         9,
         12,
         11.1,
         11,
         9.4,
         6.8,
         5.9,
         7.8,
         6.8,
         9.3,
         6.9,
         9.1,
         9.4,
         8.4,
         10.2,
         10.7,
         10.8
        ],
        [
         8,
         7.9,
         7.4,
         7.8,
         8.2,
         8.5,
         7.9,
         6.5,
         7.8,
         5.9,
         6.6,
         4.4,
         5.8,
         6,
         8.5,
         4.6,
         3.5,
         5.6,
         7.9,
         7.7,
         6.3,
         4.1,
         5.8,
         3.9
        ],
        [
         1.7,
         1.8,
         2,
         1.9,
         2.1,
         2.7,
         3,
         2.7,
         4.7,
         5,
         5.3,
         5.3,
         5.7,
         6.2,
         5.6,
         4.1,
         4,
         3.7,
         2.8,
         3.9,
         4.7,
         2.5,
         1.6,
         2.3
        ],
        [
         3.6,
         4,
         3.2,
         3,
         3.1,
         3.8,
         2.9,
         3,
         3.8,
         3.1,
         3.6,
         3,
         3.5,
         3,
         2.3,
         1.9,
         2.1,
         3,
         4.7,
         4.4,
         3.9,
         3.6,
         4.5,
         3.5
        ],
        [
         4.1,
         5,
         6.2,
         5.4,
         6.6,
         6.7,
         5.2,
         3.2,
         5.3,
         6.6,
         6.7,
         7.4,
         5.4,
         5.5,
         4.9,
         5.8,
         5.5,
         5.3,
         6.2,
         5.7,
         5.1,
         4.4,
         4,
         4
        ],
        [
         3.2,
         2.4,
         3.7,
         5,
         4.8,
         4,
         1.8,
         0.6,
         1.4,
         5.1,
         2.2,
         5.9,
         7.9,
         7.1,
         2.4,
         7.6,
         6.1,
         6,
         1.7,
         0,
         0,
         0,
         0,
         0
        ]
       ]
      }
     },
     {
      "id": "h-machine-failures",
      "title": "Why jobs failed, period by period",
      "claim": "Of 1,224 jobs, 1,031 ended ok, 131 were cancelled before they started (20 of them automatically, because a job they depended on failed), 53 failed and 9 were killed, lost or ended without a status. The most common cause of failure was a missing file or module (14), often a job pinned to a code snapshot that lacked a file it needed. A test run found a fault 11 times (10 full-suite runs and one single test file), 6 of them in period 6. Out of memory struck in two bursts: three self-play learn jobs in period 3 and three in period 8, when the wide recipe's re-runs died one after another (0987, 0988, 0997) right after 0975 died of a stack overflow.",
      "tag": "project history · all 23 days",
      "setting": "jobs/done with status failed; cause read by hand from each job's log tail, reason field and exit code; period by start time (added time for two jobs that never started) · n: 53 failed jobs (P3 10, P4 4, P5 7, P6 11, P7 9, P8 12)",
      "caveat": "The causes are a hand classification of the last error lines in each log, so a few could belong to a neighbouring group (0057a6i shares its log file with another job, so its cause can't be checked). A failed test run counts as a job doing its job. The 'refused' failures are the gauntlet's own guard stopping a comparison with a differently-played control, which is also a check working as intended. Most cells hold 0 to 3 jobs; read the grid as where failures happened, not as rates.",
      "checked": "corrected",
      "viz": {
       "kind": "heat",
       "unit": "failed jobs",
       "xs": [
        "P3",
        "P4",
        "P5",
        "P6",
        "P7",
        "P8"
       ],
       "ys": [
        "file or module missing",
        "tests found a fault",
        "input from an earlier job missing or bad",
        "out of memory",
        "process ended by Windows (exit 0x40010004)",
        "refused: control played with other settings",
        "stack overflow",
        "other (bad argument, locked file, crash)"
       ],
       "cells": [
        [
         4,
         0,
         6,
         2,
         1,
         1
        ],
        [
         1,
         0,
         1,
         6,
         3,
         0
        ],
        [
         0,
         2,
         0,
         0,
         2,
         4
        ],
        [
         3,
         0,
         0,
         0,
         0,
         3
        ],
        [
         0,
         0,
         0,
         1,
         2,
         0
        ],
        [
         0,
         0,
         0,
         1,
         1,
         0
        ],
        [
         0,
         0,
         0,
         0,
         0,
         1
        ],
        [
         2,
         2,
         0,
         1,
         0,
         3
        ]
       ]
      }
     },
     {
      "id": "h-measures-count-heat",
      "title": "What got measured when: training runs first, gauntlets from 1 Nov",
      "claim": "The project changed which ruler it used. In periods 2 and 3 the measurements were mostly training runs (111 and 134). The paired ladder lived only from 30 Oct to 1 Nov (39 tests). From 1 Nov the 11-floor gauntlet took over (347 files), and from period 5 the mutated benches (167 files). Period 6, when real Act 1 went in, was the busiest stretch: 412 result files and training runs, against 32 in the final two days.",
      "tag": "project history · all 23 days",
      "setting": "Training runs from runs/index.csv (by run date; 498 of the 535 run folders are indexed); ladder tests from results/ladder/log.jsonl; result files (.json, top level only) in results/<kind>/ by file modification time. 'other' = exact-puzzles, adapt, packs, gen_powers, depth_probe. Real-game files and smaller kinds (r0-scores, bosses, power_exposure, rollout, baseline, warm-start and others, about 40 files) are left out. · n: 1,206 measurements (498 runs, 39 ladder tests, 669 result files)",
      "caveat": "Result files are dated by modification time, so a file rewritten later counts in the later period. One file can hold 500 fights or 20; this counts files, not fights. results/ is not in git, so there is no commit date to cross-check. Files in subfolders and minor result kinds are not counted.",
      "checked": "corrected",
      "viz": {
       "kind": "heat",
       "unit": "measurements",
       "xs": [
        "P1",
        "P2",
        "P3",
        "P4",
        "P5",
        "P6",
        "P7",
        "P8"
       ],
       "ys": [
        "training runs",
        "ladder tests",
        "gauntlet",
        "mutated benches",
        "boss replays",
        "depth",
        "probes",
        "families",
        "other"
       ],
       "cells": [
        [
         7,
         111,
         134,
         56,
         17,
         136,
         29,
         8
        ],
        [
         0,
         0,
         18,
         21,
         0,
         0,
         0,
         0
        ],
        [
         0,
         0,
         0,
         78,
         38,
         136,
         85,
         10
        ],
        [
         0,
         0,
         0,
         1,
         14,
         101,
         39,
         12
        ],
        [
         0,
         0,
         0,
         1,
         21,
         12,
         0,
         0
        ],
        [
         0,
         0,
         32,
         9,
         1,
         0,
         0,
         0
        ],
        [
         0,
         0,
         5,
         14,
         1,
         0,
         0,
         0
        ],
        [
         0,
         0,
         0,
         0,
         0,
         18,
         2,
         2
        ],
        [
         0,
         4,
         2,
         5,
         17,
         9,
         0,
         0
        ]
       ]
      }
     },
     {
      "id": "h-measures-cell-gauntlet-best",
      "title": "The cell gauntlet's best barely moved after the first week of November",
      "claim": "On the cell gauntlet (11 floors, one-turn search, the first 500 fight sequences), the best clear rate any player reached rose from 0.646 in period 4 to 0.682 in period 7, and the typical read (median) from 0.612 to 0.648. For scale: the hand-written heuristic reads 0.596, and the 10-29 net, the one the product kept using, reads 0.634. The record 0.682 came from one training seed of the genpack40k recipe (a rerun gave the identical result); its sister seeds read 0.642 and 0.676. Period 8 has only 2 reads.",
      "tag": "project history · all 23 days",
      "setting": "Cell gauntlet: settings exactly {player, two_turn=false, 11-floor shape, rest 0.3, seed 20261101}, fight sequences 0-499 (no -b500 files). Every player measured, an identical rerun counted once, best and median per period, period taken from the result file's time (local time) · n: 126 reads: P4 29, P5 13, P6 50, P7 32, P8 2; 500 sequences each",
      "caveat": "Period 8 rests on 2 reads (0.670 and 0.652), so its best and median are not comparable with the other periods (13 to 50 reads). Periods are dated from the result files' modification times because results/ is not in git. The second block (sequences 500-999, the -b500 files) is easier (the 10-29 net reads 0.686 there against 0.634 here) and is kept off this chart. The best of many reads is pulled upward by luck: seeds of one recipe differ by up to 0.05. Players differ in leaf options (plain or @tsl1).",
      "checked": "corrected",
      "viz": {
       "kind": "line",
       "unit": "clear rate (share of 500 sequences cleared)",
       "x_label": "period",
       "y_label": "clear rate",
       "series": [
        {
         "name": "best read of the period",
         "points": [
          {
           "x": "P4",
           "y": 0.646
          },
          {
           "x": "P5",
           "y": 0.664
          },
          {
           "x": "P6",
           "y": 0.668
          },
          {
           "x": "P7",
           "y": 0.682
          },
          {
           "x": "P8",
           "y": 0.67
          }
         ]
        },
        {
         "name": "median read of the period",
         "points": [
          {
           "x": "P4",
           "y": 0.612
          },
          {
           "x": "P5",
           "y": 0.644
          },
          {
           "x": "P6",
           "y": 0.627
          },
          {
           "x": "P7",
           "y": 0.648
          },
          {
           "x": "P8",
           "y": 0.661
          }
         ]
        }
       ]
      }
     },
     {
      "id": "h-engine-loc",
      "title": "Lines of Rust and Python, day by day",
      "claim": "Python overtook Rust on 27 Oct and pulled far ahead while the lab ran experiments, ending at 68,068 lines. Rust grew in bursts: the rules-engine series on 1-2 Nov (16,316 to 20,158), almost nothing while the AI roles took over (20,158 to 20,595 over 3-5 Nov), then real Act 1 content, relics, potions and the real-game bridge, which took it from 25,890 on 9 Nov to 49,600 on 14 Nov.",
      "tag": "project history · all 23 days",
      "setting": "every .rs and every .py file in main's tree (engine, binding crate, solved-position DB, scripts, tests) at the last main commit before local midnight each day · n: 2,591 commits, 23 days",
      "caveat": "Lines include tests and blank lines; JSON content files and docs are not counted. Work on lane branches counts on the day it was merged into main. The 14 Nov Python jump includes about 5,150 lines of the showcase's own statistics scripts. More lines is not more capability.",
      "checked": "corrected",
      "viz": {
       "kind": "line",
       "unit": "lines",
       "x_label": "day (2026)",
       "y_label": "lines in the repository",
       "series": [
        {
         "name": "Rust",
         "points": [
          {
           "x": "10-23",
           "y": 5821
          },
          {
           "x": "10-24",
           "y": 8341
          },
          {
           "x": "10-25",
           "y": 8885
          },
          {
           "x": "10-26",
           "y": 11786
          },
          {
           "x": "10-27",
           "y": 11786
          },
          {
           "x": "10-28",
           "y": 12770
          },
          {
           "x": "10-29",
           "y": 12894
          },
          {
           "x": "10-30",
           "y": 13720
          },
          {
           "x": "10-31",
           "y": 15482
          },
          {
           "x": "11-01",
           "y": 16316
          },
          {
           "x": "11-02",
           "y": 20158
          },
          {
           "x": "11-03",
           "y": 20348
          },
          {
           "x": "11-04",
           "y": 20595
          },
          {
           "x": "11-05",
           "y": 20595
          },
          {
           "x": "11-06",
           "y": 21986
          },
          {
           "x": "11-07",
           "y": 23730
          },
          {
           "x": "11-08",
           "y": 24875
          },
          {
           "x": "11-09",
           "y": 25890
          },
          {
           "x": "11-10",
           "y": 29939
          },
          {
           "x": "11-11",
           "y": 31803
          },
          {
           "x": "11-12",
           "y": 36134
          },
          {
           "x": "11-13",
           "y": 43126
          },
          {
           "x": "11-14",
           "y": 49600
          }
         ]
        },
        {
         "name": "Python",
         "points": [
          {
           "x": "10-23",
           "y": 964
          },
          {
           "x": "10-24",
           "y": 5648
          },
          {
           "x": "10-25",
           "y": 8027
          },
          {
           "x": "10-26",
           "y": 10028
          },
          {
           "x": "10-27",
           "y": 12286
          },
          {
           "x": "10-28",
           "y": 12985
          },
          {
           "x": "10-29",
           "y": 15089
          },
          {
           "x": "10-30",
           "y": 23800
          },
          {
           "x": "10-31",
           "y": 27368
          },
          {
           "x": "11-01",
           "y": 30520
          },
          {
           "x": "11-02",
           "y": 32055
          },
          {
           "x": "11-03",
           "y": 39821
          },
          {
           "x": "11-04",
           "y": 41857
          },
          {
           "x": "11-05",
           "y": 42351
          },
          {
           "x": "11-06",
           "y": 43844
          },
          {
           "x": "11-07",
           "y": 47832
          },
          {
           "x": "11-08",
           "y": 52572
          },
          {
           "x": "11-09",
           "y": 54208
          },
          {
           "x": "11-10",
           "y": 55504
          },
          {
           "x": "11-11",
           "y": 57396
          },
          {
           "x": "11-12",
           "y": 57881
          },
          {
           "x": "11-13",
           "y": 60165
          },
          {
           "x": "11-14",
           "y": 68068
          }
         ]
        }
       ]
      }
     },
     {
      "id": "h-engine-tests",
      "title": "Tests grew ninefold in Rust, seventyfold in Python",
      "claim": "The Rust test count went from 90 on the first night to 822, and the Python test count from 14 to 1,015. Rust tests were nearly flat from 24 Oct to 2 Nov (149 to 222) and grew fastest in the last five days (414 to 822). Those were the days real Act 1 content, relics, potions and the real-game rule fixes went in, and each came with tests.",
      "tag": "project history · all 23 days",
      "setting": "test functions in git on main at the end of each local day (main's reflog, local time): #[test] lines in .rs files, def test_ lines in .py files · n: 23 daily snapshots",
      "caveat": "These are test functions found by text search, not tests that ran or passed. One golden test replays about 9,000 recorded games (engine/tests/data/golden.txt), so the count says little about coverage. Days are where main stood at local midnight, so work on lane branches counts only from the day it landed.",
      "checked": "corrected",
      "viz": {
       "kind": "line",
       "unit": "test functions",
       "x_label": "day (2026)",
       "y_label": "test functions",
       "series": [
        {
         "name": "Rust #[test]",
         "points": [
          {
           "x": "10-23",
           "y": 90
          },
          {
           "x": "10-24",
           "y": 149
          },
          {
           "x": "10-25",
           "y": 149
          },
          {
           "x": "10-26",
           "y": 174
          },
          {
           "x": "10-27",
           "y": 174
          },
          {
           "x": "10-28",
           "y": 183
          },
          {
           "x": "10-29",
           "y": 184
          },
          {
           "x": "10-30",
           "y": 198
          },
          {
           "x": "10-31",
           "y": 217
          },
          {
           "x": "11-01",
           "y": 222
          },
          {
           "x": "11-02",
           "y": 222
          },
          {
           "x": "11-03",
           "y": 287
          },
          {
           "x": "11-04",
           "y": 293
          },
          {
           "x": "11-05",
           "y": 293
          },
          {
           "x": "11-06",
           "y": 332
          },
          {
           "x": "11-07",
           "y": 371
          },
          {
           "x": "11-08",
           "y": 390
          },
          {
           "x": "11-09",
           "y": 414
          },
          {
           "x": "11-10",
           "y": 485
          },
          {
           "x": "11-11",
           "y": 512
          },
          {
           "x": "11-12",
           "y": 595
          },
          {
           "x": "11-13",
           "y": 708
          },
          {
           "x": "11-14",
           "y": 822
          }
         ]
        },
        {
         "name": "Python def test_",
         "points": [
          {
           "x": "10-23",
           "y": 14
          },
          {
           "x": "10-24",
           "y": 95
          },
          {
           "x": "10-25",
           "y": 159
          },
          {
           "x": "10-26",
           "y": 193
          },
          {
           "x": "10-27",
           "y": 215
          },
          {
           "x": "10-28",
           "y": 226
          },
          {
           "x": "10-29",
           "y": 258
          },
          {
           "x": "10-30",
           "y": 324
          },
          {
           "x": "10-31",
           "y": 391
          },
          {
           "x": "11-01",
           "y": 447
          },
          {
           "x": "11-02",
           "y": 500
          },
          {
           "x": "11-03",
           "y": 609
          },
          {
           "x": "11-04",
           "y": 641
          },
          {
           "x": "11-05",
           "y": 652
          },
          {
           "x": "11-06",
           "y": 676
          },
          {
           "x": "11-07",
           "y": 746
          },
          {
           "x": "11-08",
           "y": 801
          },
          {
           "x": "11-09",
           "y": 821
          },
          {
           "x": "11-10",
           "y": 848
          },
          {
           "x": "11-11",
           "y": 887
          },
          {
           "x": "11-12",
           "y": 911
          },
          {
           "x": "11-13",
           "y": 950
          },
          {
           "x": "11-14",
           "y": 1015
          }
         ]
        }
       ]
      }
     },
     {
      "id": "h-engine-rules-version",
      "title": "The rules version held for 21 days, then moved five times in one day",
      "claim": "Every dataset and run is stamped with a rules version: a hash of 9,000 seeded random games recorded on 24 Oct (golden.txt). It stayed 7042d1d6 for three weeks: a 2 Nov change was undone 9 minutes later, and a 10 Nov rewrite was declared the same rules. Then the real game exposed rule gaps, and the version moved five times between 01:08 and 22:56 on 14 Nov. The first move rewrote 139 of the 9,000 games (random-spot card inserts). Each of the other four added cover games for rules fixed that day: 5 at once (turn-end order, Duplication, Guardian, Feed and others), then one each for Lagavulin's wake, Pocketwatch and Fire Breathing on a Curse.",
      "tag": "project history · all 23 days",
      "setting": "commits that changed engine/tests/data/golden.txt; hash as scripts/registry.py rules_version computes it · n: 9 commits touching golden.txt; 5 real version moves",
      "caveat": "The hash only moves when a rule change alters a golden game. Several rule fixes (Perfected Strike, Mode Shift block, turn-end order of Burn and Metallicize, and others) left golden unchanged until the cover games of 14 Nov were added, so 'rules version unchanged' did not mean 'rules unchanged'. Times are author times; for the four later commits on 14 Nov, the commit times are 4 to 16 minutes later.",
      "checked": "corrected",
      "viz": {
       "kind": "timeline",
       "unit": "golden games",
       "events": [
        {
         "x": "10-24 01:04",
         "label": "9,000 seeded random games recorded; version 7042d1d6",
         "value": 9000
        },
        {
         "x": "11-02 01:36",
         "label": "1,200 proving games appended (55bba64a)",
         "value": 10200
        },
        {
         "x": "11-02 01:45",
         "label": "moved to their own file 9 minutes later; back to 7042d1d6",
         "value": 9000
        },
        {
         "x": "11-10 22:15",
         "label": "ended fights recorded differently; e9c10f64 mapped to 7042d1d6 as the same rules",
         "value": 9000
        },
        {
         "x": "11-14 01:08",
         "label": "random-spot card inserts go under the top card; 139 games change (e47bcfcd)",
         "value": 9000
        },
        {
         "x": "11-14 15:39",
         "label": "5 cover games for the 14 Nov rule fixes, Duplication among them (f59b662a)",
         "value": 9005
        },
        {
         "x": "11-14 18:10",
         "label": "Lagavulin's wake takes 8 Metallicize (696d607b)",
         "value": 9006
        },
        {
         "x": "11-14 19:32",
         "label": "Pocketwatch counted as the game counts (32f1971b)",
         "value": 9007
        },
        {
         "x": "11-14 22:56",
         "label": "Fire Breathing fires on a Curse draw (d08bc2b7)",
         "value": 9008
        }
       ]
      }
     },
     {
      "id": "h-engine-hot-files",
      "title": "Which code files were edited most, and when",
      "claim": "The engine's state file (state.rs) is the most-edited code file, with 117 commits. Over two thirds of them (79) came in the last five days, while relics, potions and the real game were going in. The registry (registry.rs, 107) was only created on day 9 (10-31), and almost all of its edits came from 11-06 on. The training script learn.py went the other way: 49 of its 59 edits came in the first nine days (to 10-31), and after that it was edited only 10 more times.",
      "tag": "project history · all 23 days",
      "setting": "commits on main touching each .rs or .py file, by period (author time, local time); top 10 code files by total commits · n: 2,591 commits; top 10 of all code files",
      "caveat": "Periods differ in length (2 to 4 days) and in commit count (61 in P1, 763 in P6), and a commit count says nothing about the size of the edit. engine/src/effects.rs ties hooks.rs at 38 for tenth place, and scripts/real_game.py (37, all in P8) falls just outside the top 10. The chart shows timing only, not why a file stopped or started changing. Docs dwarf code: docs/decisions.md alone was edited in 558 commits.",
      "checked": "corrected",
      "viz": {
       "kind": "heat",
       "unit": "commits touching the file",
       "xs": [
        "P1",
        "P2",
        "P3",
        "P4",
        "P5",
        "P6",
        "P7",
        "P8"
       ],
       "ys": [
        "engine/src/state.rs (117)",
        "engine/src/registry.rs (107)",
        "py/src/lib.rs (96)",
        "py/src/features.rs (74)",
        "scripts/explore.py (65)",
        "scripts/learn.py (59)",
        "engine/src/codec.rs (56)",
        "scripts/stsnet.py (48)",
        "scripts/registry.py (39)",
        "engine/src/hooks.rs (38)"
       ],
       "cells": [
        [
         9,
         0,
         4,
         8,
         1,
         16,
         36,
         43
        ],
        [
         0,
         0,
         1,
         6,
         1,
         27,
         32,
         40
        ],
        [
         8,
         12,
         12,
         10,
         2,
         14,
         17,
         21
        ],
        [
         5,
         0,
         6,
         10,
         1,
         6,
         23,
         23
        ],
        [
         0,
         5,
         0,
         0,
         0,
         27,
         18,
         15
        ],
        [
         9,
         23,
         17,
         4,
         1,
         3,
         0,
         2
        ],
        [
         0,
         1,
         5,
         6,
         0,
         9,
         10,
         25
        ],
        [
         11,
         11,
         7,
         8,
         1,
         6,
         2,
         2
        ],
        [
         8,
         15,
         5,
         3,
         3,
         2,
         3,
         0
        ],
        [
         3,
         0,
         1,
         3,
         1,
         5,
         11,
         14
        ]
       ]
      }
     },
     {
      "id": "h-engine-speed",
      "title": "Engine speed changes, each measured before vs after",
      "claim": "The biggest speed-up came on 25 Oct, when the net's forward pass moved from Python to Rust: self-play went from 23.5 to 179 games per second (Python on 4 threads vs Rust on all threads, so part of the gain is threads). Later work moved speed both ways. On 2 Nov the new rule machinery cost one-turn search 7.5% at 1 thread, and the same day a search memo that stores each state once gained it back 52%. On 6 Nov, shrinking the combat state from 1,292 to 744 bytes added 17.6%.",
      "tag": "project history · all 23 days",
      "setting": "speed checks recorded in docs/decisions.md and the sparse-piles spec; each event is its own before-vs-after measurement on the laptop, with its own workload · n: 5 measured changes; 3 to 22 interleaved runs each",
      "caveat": "Each check used its own workload and machine load, so the numbers are not on one scale and cannot be added up. The 25 Oct figure compares different thread counts. The 13 Nov jobs crashed out of memory partway through.",
      "checked": "corrected",
      "viz": {
       "kind": "timeline",
       "unit": "",
       "events": [
        {
         "x": "10-25",
         "label": "Rust inference: self-play 23.5 to 179 games/s (7.6x; Python on 4 threads vs Rust on all threads, median of 5)"
        },
        {
         "x": "11-02",
         "label": "Rules-engine series (specs 2-9): one-turn search -7.5% at 1 thread, -13.7% at all threads; state grew 1,028 to 1,268 bytes"
        },
        {
         "x": "11-02",
         "label": "Search memo stores each state once: one-turn search +52% at 1 thread, +32% at all threads (5 runs)"
        },
        {
         "x": "11-06",
         "label": "Sparse state: 1,292 to 744 bytes; search +17.6% at 1 thread, +35.5% at all threads (11 runs)"
        },
        {
         "x": "11-13",
         "label": "Sparse piles (u16 card ids, shared 64-entry pile list): search +0.7% to +3.6%, level with main (16 and 22 runs, loaded machine)"
        }
       ]
      }
     },
     {
      "id": "h-writing-decisions-who",
      "title": "Who wrote the decisions, period by period",
      "claim": "docs/decisions.md holds 499 dated entries. While the owner sat at the desk (periods 1-2), every entry came from their session (25). From 10-29 Claude wrote 125 entries marked 'owner away' in five days. From 11-03 the AI roles took over and wrote 213 entries marked 'on the owner's behalf', 97 of them in period 6 alone. The owner signed 55 entries from 10-29 on (8 of them tagged 'owner present', 10-31 to 11-02): 1 in period 3, then 10-14 per period in periods 4-7 and 5 in the two-day period 8. Period 6 (11-06..11-09) was the busiest stretch with 149 entries. The busiest single day was 11-02, with 55.",
      "tag": "project history · all 23 days",
      "setting": "Every '## ' heading in docs/decisions.md at HEAD. Date = git blame author time of the heading line (local time). Who = the heading's own tag. A tag starting '(owner' or containing 'owner present', or an untagged entry before 10-29, counts as owner. '(owner away...)' counts as Claude while the owner was away, and '(on the owner's behalf...)' as the roles. 'Lane X opened/closed' headings are lane records. The rest are untagged build notes; half of those (11 of 22) are the rules-engine series built overnight on 11-02, 01:36-05:26. · n: 499 entries",
      "caveat": "The tag is the writer's own label, not a check of who typed it. Entries marked 'owner present' were likely typed by Claude with the owner at the desk. Blame dates an entry by the last change to its heading line, so a retitled entry moves to the day of the retitle. Periods differ in length (2 to 4 days).",
      "checked": "corrected",
      "viz": {
       "kind": "heat",
       "unit": "decision entries",
       "xs": [
        "P1",
        "P2",
        "P3",
        "P4",
        "P5",
        "P6",
        "P7",
        "P8"
       ],
       "ys": [
        "owner",
        "Claude, owner away",
        "roles, on the owner's behalf",
        "lane opened/closed records",
        "untagged build notes"
       ],
       "cells": [
        [
         12,
         13,
         1,
         11,
         10,
         14,
         14,
         5
        ],
        [
         0,
         0,
         47,
         69,
         9,
         0,
         0,
         0
        ],
        [
         0,
         0,
         0,
         0,
         40,
         97,
         54,
         22
        ],
        [
         0,
         0,
         0,
         0,
         12,
         34,
         11,
         2
        ],
        [
         0,
         0,
         2,
         13,
         1,
         4,
         1,
         1
        ]
       ]
      }
     },
     {
      "id": "h-writing-entry-length",
      "title": "Decision entries got short, then long again",
      "claim": "With the owner at the desk a decision entry ran about 480-540 words (median), and the two longest of the whole project came on day 2 (10-24): 'Triggers and conditions (SPEC.md Amendment 4)' at 1,976 words and 'Learned play as built' at 1,911. When Claude ran the lab alone (period 3) the median fell to 113 words: many small calls, written fast. Once the roles wrote the record (period 5 on) it settled near 290 words, with 'After' entries that explain a lane's result and the next step reaching 1,585 words (11-05).",
      "tag": "project history · all 23 days",
      "setting": "Words in each decisions.md entry (heading to next heading), grouped by the period of its heading's blame date. · n: 499 entries, 152,823 words; per period n = 12, 13, 50, 93, 72, 149, 80, 30",
      "caveat": "Periods 1-2 have only 12 and 13 entries, so their medians are rough. Early entries are 'as built' summaries of whole specs, a different kind of entry from the later one-decision notes. Word counts are of each entry as it reads today; an entry extended later still counts in the period of its heading.",
      "checked": "confirmed",
      "viz": {
       "kind": "line",
       "unit": "words per entry",
       "series": [
        {
         "name": "median entry",
         "points": [
          {
           "x": "P1",
           "y": 478.5
          },
          {
           "x": "P2",
           "y": 536
          },
          {
           "x": "P3",
           "y": 113
          },
          {
           "x": "P4",
           "y": 153
          },
          {
           "x": "P5",
           "y": 284
          },
          {
           "x": "P6",
           "y": 292
          },
          {
           "x": "P7",
           "y": 295.5
          },
          {
           "x": "P8",
           "y": 294.5
          }
         ]
        },
        {
         "name": "longest entry",
         "points": [
          {
           "x": "P1",
           "y": 1976
          },
          {
           "x": "P2",
           "y": 1574
          },
          {
           "x": "P3",
           "y": 516
          },
          {
           "x": "P4",
           "y": 628
          },
          {
           "x": "P5",
           "y": 1585
          },
          {
           "x": "P6",
           "y": 1581
          },
          {
           "x": "P7",
           "y": 855
          },
          {
           "x": "P8",
           "y": 735
          }
         ]
        }
       ]
      }
     },
     {
      "id": "h-writing-words",
      "title": "1.24 million words written into docs/",
      "claim": "Over 23 days the commits added about 1.24 million words to Markdown files under docs/ (the repo's Markdown today holds about 995,000 words). Research notes are the biggest share: a 13-note literature survey on days 1 and 2 (backgammon afterstates, expert iteration, card-game AI...), 20 new notes in period 3, and 182,000 words in the last two days alone. Specs peaked in period 4 at 107,000 words, when 43 new specs were written: run-level features (rest site, card rewards, elite skip, gauntlet), rules-engine pieces (hooks, modifiers, monster patterns) and a 9-part review-fixes series. The backlog file appears only in period 5, when the navigator role starts keeping it.",
      "tag": "project history · all 23 days",
      "setting": "git log -p --no-merges --no-renames over every *.md, words on added lines, grouped by commit date (local time) and folder. Thousands of words. · n: every commit touching a .md file; 1,237,961 words added under docs/ (plus 20,192 outside docs/)",
      "caveat": "Gross words added: a rewritten line, or a file deleted and added again, counts again, so this measures writing effort, not the size of the docs (about 182,000 words were also deleted under docs/). Periods have different lengths. New research files per period, each path counted once: 15, 1, 20, 16, 1, 23, 15, 17.",
      "checked": "corrected",
      "viz": {
       "kind": "heat",
       "unit": "thousand words added",
       "xs": [
        "P1",
        "P2",
        "P3",
        "P4",
        "P5",
        "P6",
        "P7",
        "P8"
       ],
       "ys": [
        "research notes",
        "specs",
        "decisions",
        "backlog",
        "other docs"
       ],
       "cells": [
        [
         38.9,
         4.5,
         76.3,
         83.9,
         26.2,
         96.7,
         48.5,
         182.4
        ],
        [
         7.1,
         28.8,
         29,
         107.2,
         19.5,
         54.4,
         32.6,
         17.3
        ],
        [
         8.7,
         9.9,
         8.5,
         18.9,
         27,
         55.2,
         26.7,
         10
        ],
        [
         0,
         0,
         0,
         0,
         27.7,
         40.4,
         26.6,
         10.7
        ],
        [
         2,
         2.2,
         21.4,
         25.4,
         37.3,
         4.2,
         8.9,
         12.9
        ]
       ]
      }
     },
     {
      "id": "h-writing-backlog",
      "title": "The backlog kept growing",
      "claim": "The navigator's backlog of candidate lanes started on 11-03 with 12 entries and peaked at 24 the next morning. A prune on 11-04 cut it to 13. Over the 12 days, 130 named candidates passed through it and 83 left it (opened as a lane, merged into another, or answered). Yet the list never shrank for long: from a low of 17 on 11-07 it grew every day and ended the project at 47 open candidates. The last two days added 20 and removed 2, as the real-game runs and the owner's return brought new questions faster than the one remaining lane could take them.",
      "tag": "project history · all 23 days",
      "setting": "Bold slug-named entries ('- **name**' or 'N. **name**') under '## Candidates' in docs/backlog.md, read at every commit that changed the file (230 commits). A name is opened on the day it first appears and removed on the day it last appears, if it is absent at the end. Days are commit dates in local time (local time). · n: 130 distinct candidate names, 11-03..11-14",
      "caveat": "A renamed candidate counts as one removed and one opened, so both flows run somewhat high. Entries marked 'merged into' that stay in the list as a stub still count as open. Three entries added on 11-13 as bullets that wait only for code count as candidates. Without them the end count is 44. Parked items, the ideas-triage list, the open-questions list and the ranked shortlist inside the section ('0. **76 `hpe-leaf-cap`**') are not counted. The 11-04 intraday peak of 24 does not show at day's end.",
      "checked": "corrected",
      "viz": {
       "kind": "line",
       "unit": "candidates",
       "series": [
        {
         "name": "open at day's end",
         "points": [
          {
           "x": "11-03",
           "y": 16
          },
          {
           "x": "11-04",
           "y": 13
          },
          {
           "x": "11-05",
           "y": 14
          },
          {
           "x": "11-06",
           "y": 22
          },
          {
           "x": "11-07",
           "y": 17
          },
          {
           "x": "11-08",
           "y": 22
          },
          {
           "x": "11-09",
           "y": 23
          },
          {
           "x": "11-10",
           "y": 25
          },
          {
           "x": "11-11",
           "y": 26
          },
          {
           "x": "11-12",
           "y": 29
          },
          {
           "x": "11-13",
           "y": 38
          },
          {
           "x": "11-14",
           "y": 47
          }
         ]
        },
        {
         "name": "opened",
         "points": [
          {
           "x": "11-03",
           "y": 19
          },
          {
           "x": "11-04",
           "y": 9
          },
          {
           "x": "11-05",
           "y": 13
          },
          {
           "x": "11-06",
           "y": 12
          },
          {
           "x": "11-07",
           "y": 7
          },
          {
           "x": "11-08",
           "y": 15
          },
          {
           "x": "11-09",
           "y": 10
          },
          {
           "x": "11-10",
           "y": 10
          },
          {
           "x": "11-11",
           "y": 9
          },
          {
           "x": "11-12",
           "y": 6
          },
          {
           "x": "11-13",
           "y": 11
          },
          {
           "x": "11-14",
           "y": 9
          }
         ]
        },
        {
         "name": "removed",
         "points": [
          {
           "x": "11-03",
           "y": 3
          },
          {
           "x": "11-04",
           "y": 12
          },
          {
           "x": "11-05",
           "y": 13
          },
          {
           "x": "11-06",
           "y": 3
          },
          {
           "x": "11-07",
           "y": 12
          },
          {
           "x": "11-08",
           "y": 11
          },
          {
           "x": "11-09",
           "y": 9
          },
          {
           "x": "11-10",
           "y": 7
          },
          {
           "x": "11-11",
           "y": 8
          },
          {
           "x": "11-12",
           "y": 3
          },
          {
           "x": "11-13",
           "y": 2
          },
          {
           "x": "11-14",
           "y": 0
          }
         ]
        }
       ]
      }
     },
     {
      "id": "h-simulated-runs-fights-per-day",
      "title": "Two million test fights, almost all in the last two weeks",
      "claim": "The gauntlet played 1,775,729 fights in 165,940 eleven-floor runs, and the champion ladder played 272,360 fights in its pairs. Neither existed in periods 1 and 2, when nets were tested on a smaller fixed bench of games. The ladder started on 10-30 and the gauntlet on 11-01. The busiest day was 11-07, with 471,963 gauntlet fights, when dozens of new nets were re-ranked on the same 500 runs.",
      "tag": "project history · all 23 days",
      "setting": "Every results/gauntlet/*.json file (347 files; only floors actually played count, since a run stops at its first loss) and every ladder match in results/ladder/log.jsonl and results/ladder/runhp/*.json (each pair = 2 fights, one per player; aborted .partial files excluded). · n: 347 gauntlet files, 165,940 runs, 1,775,729 fights; 79 ladder matches, 272,360 fights",
      "caveat": "Result files are not in git. Gauntlet days come from file modification time (local time); for the files a queue job wrote, the job's date agrees with it. A later rewrite could have moved a date. Files deleted before today are not counted. About 13,000 fights (under 1%) are deterministic reruns that repeat another file's runs exactly. Earlier bench tests (results/baseline, runs/*/bench.json, 10-24 to 10-28) and training self-play fights are not counted.",
      "checked": "corrected",
      "viz": {
       "kind": "line",
       "unit": "fights per day",
       "x_label": "day (2026)",
       "y_label": "fights",
       "series": [
        {
         "name": "gauntlet fights",
         "points": [
          {
           "x": "10-30",
           "y": 0
          },
          {
           "x": "10-31",
           "y": 0
          },
          {
           "x": "11-01",
           "y": 58054
          },
          {
           "x": "11-02",
           "y": 245498
          },
          {
           "x": "11-03",
           "y": 17322
          },
          {
           "x": "11-04",
           "y": 46051
          },
          {
           "x": "11-05",
           "y": 96796
          },
          {
           "x": "11-06",
           "y": 300147
          },
          {
           "x": "11-07",
           "y": 471963
          },
          {
           "x": "11-08",
           "y": 31667
          },
          {
           "x": "11-09",
           "y": 13714
          },
          {
           "x": "11-10",
           "y": 256520
          },
          {
           "x": "11-11",
           "y": 177023
          },
          {
           "x": "11-12",
           "y": 10724
          },
          {
           "x": "11-13",
           "y": 43166
          },
          {
           "x": "11-14",
           "y": 7084
          }
         ]
        },
        {
         "name": "ladder fights",
         "points": [
          {
           "x": "10-30",
           "y": 13090
          },
          {
           "x": "10-31",
           "y": 36026
          },
          {
           "x": "11-01",
           "y": 215244
          },
          {
           "x": "11-02",
           "y": 8000
          },
          {
           "x": "11-03",
           "y": 0
          },
          {
           "x": "11-04",
           "y": 0
          },
          {
           "x": "11-05",
           "y": 0
          },
          {
           "x": "11-06",
           "y": 0
          },
          {
           "x": "11-07",
           "y": 0
          },
          {
           "x": "11-08",
           "y": 0
          },
          {
           "x": "11-09",
           "y": 0
          },
          {
           "x": "11-10",
           "y": 0
          },
          {
           "x": "11-11",
           "y": 0
          },
          {
           "x": "11-12",
           "y": 0
          },
          {
           "x": "11-13",
           "y": 0
          },
          {
           "x": "11-14",
           "y": 0
          }
         ]
        }
       ]
      }
     },
     {
      "id": "h-simulated-runs-killers",
      "title": "Hexaghost and The Guardian were the run-killers",
      "claim": "Across 58,546 lost gauntlet runs (duplicate files removed), Hexaghost ended 16,962 (29%), The Guardian 12,545 (21%) and Slime Boss 6,581 (11%). Together the three bosses ended 62% of all failed runs. In P4 to P7 a player who reached Hexaghost lost to him 33% to 38% of the time. In P8 The Guardian edged ahead, 28.7% against 27.1%. Slime Boss cost 10% to 14%, and each of the three elites only 3% to 6% of the fights against it.",
      "tag": "project history · all 23 days",
      "setting": "335 gauntlet files with distinct sequences (12 copy or rerun files dropped), all players mixed, one shape and rest 0.3; share of fights against each encounter that were lost, per period · n: P4 302,414 fights, P5 159,071, P6 815,731, P7 438,870, P8 50,250; Hexaghost reached 47,950 times",
      "caveat": "Each period mixes different players, decks and nets, so change across periods is not a measure of progress. P8 is small, about 1,400 fights per boss. The boss comes after a fixed rest, but elites come at whatever HP is left, so their lower loss rate partly reflects when they appear. Copies of the same results (sanity, thread and scale checks, a rerun) are counted once.",
      "checked": "corrected",
      "viz": {
       "kind": "heat",
       "unit": "% of fights against it lost",
       "xs": [
        "P4",
        "P5",
        "P6",
        "P7",
        "P8"
       ],
       "ys": [
        "Hexaghost",
        "The Guardian",
        "Slime Boss",
        "Lagavulin",
        "Three Sentries",
        "Gremlin Nob"
       ],
       "cells": [
        [
         35.4,
         33,
         37.7,
         32.8,
         27.1
        ],
        [
         32.4,
         25.5,
         27.7,
         26.8,
         28.7
        ],
        [
         13,
         11.3,
         14,
         12.7,
         10.4
        ],
        [
         5.8,
         3.8,
         4.9,
         4.8,
         2.8
        ],
        [
         5.5,
         3.7,
         4.4,
         4.4,
         3.1
        ],
        [
         4.8,
         3.5,
         4.5,
         4.4,
         3.3
        ]
       ]
      }
     }
    ]
   }
  ]
 },
 {
  "key": "p1",
  "name": "Period 1 (P1): The engine and the first question",
  "dates": "23 to 24 October",
  "parts": [
   {
    "name": "",
    "items": [
     {
      "id": "h-engine-first-evening",
      "title": "The first evening: from spec to trained nets in 91 minutes of commits",
      "claim": "On 23 Oct the first commit (the spec) landed at 22:05. The eighth landed at 23:36: self-play data and the first two value nets, which its message reports as trained and compared. By midnight the repository held 5,821 lines of Rust (1,610 of them tests), 964 lines of Python and 90 Rust tests. One commit at 22:35 added every in-scope Act 1 card, power and monster. These are commit times, so much of the work was likely written before it was committed.",
      "tag": "project history · 23 to 24 October",
      "setting": "git history, commits dated 10-23 (author time, local time) · n: 8 commits on 10-23; lines are file lengths at 39de9ebf (equal to the summed git numstat, added minus deleted), all .rs and .py files",
      "caveat": "These are commit timestamps, not working time. They show how the work was committed, not how fast it was written. The trained nets are not in the repo; the 39de9ebf commit message reports their training and test result.",
      "checked": "corrected",
      "viz": {
       "kind": "bignum",
       "unit": "",
       "rows": [
        {
         "label": "commits, spec to first nets",
         "value": 8,
         "note": "22:05 to 23:36, 91 minutes"
        },
        {
         "label": "Rust lines by midnight",
         "value": 5821,
         "note": "engine core 1,903 + Act 1 content 1,777 + search and agents 1,076 + Python bindings 1,065; 1,610 are tests"
        },
        {
         "label": "Rust tests by midnight",
         "value": 90,
         "note": "#[test] functions at 39de9ebf"
        },
        {
         "label": "Python lines by midnight",
         "value": 964,
         "note": "binding tests, eval/replay scripts, self-play, train.py, stsnet.py, test_net.py"
        }
       ]
      }
     }
    ]
   }
  ]
 },
 {
  "key": "p2",
  "name": "Period 2 (P2): Self-play, with the owner at the desk",
  "dates": "25 to 28 October",
  "parts": [
   {
    "name": "",
    "items": [
     {
      "id": "h-measures-tight-bench",
      "title": "The first ruler: hard fights, with unseen cards held out",
      "claim": "Before the gauntlet existed, nets were scored on a 'tight' bench of hard single fights. The bench had two halves: decks built from the training card pool, and decks that hold cards the net never trained with (held out). From 25 to 28 Oct, 22 runs were scored on it. The best held-out win rate was 0.511 (score+branch, seed 1, 10 rounds, 28 Oct), against 0.460 for the 24 Oct baseline. That best result's 95% range is 0.47-0.55 over 550 games, and it is the top of 22 tries, so the gain is modest. Runs that won more with training-pool decks also won more with held-out-card decks (correlation 0.86): a run's ranking carried over to cards it had not seen. The bench last appears in the run index on 28 Oct; after that the project moved to the ladder and the gauntlet.",
      "tag": "project history · 25 to 28 October",
      "setting": "runs/index.csv rows with bench_version 1 dated 25-28 Oct; tight bench win rate, train half (training card pool) vs held_out half (decks with held-out cards) · n: 22 training runs; 550 held-out games per run",
      "caveat": "Win rates on this bench are not comparable with the gauntlet's clear rates: it scores single hard fights, not 11-floor sequences. The two halves use the same encounters and the same net, so part of the 0.86 correlation is shared fight difficulty, not proof the net generalizes. Each held-out rate rests on 550 games (about +/-0.04), and 0.511 is the best of 22 runs.",
      "checked": "corrected",
      "viz": {
       "kind": "scatter",
       "unit": "win rate on tight fights",
       "x_label": "win rate, training-pool decks",
       "y_label": "win rate, decks with held-out cards",
       "points": [
        {
         "x": 0.4246,
         "y": 0.4236,
         "label": "f-base r3"
        },
        {
         "x": 0.3738,
         "y": 0.3982,
         "label": "f-1 r3"
        },
        {
         "x": 0.4475,
         "y": 0.4618,
         "label": "f-3 r3"
        },
        {
         "x": 0.4787,
         "y": 0.4364,
         "label": "f-6 r3"
        },
        {
         "x": 0.4754,
         "y": 0.4673,
         "label": "f-13 r3"
        },
        {
         "x": 0.4475,
         "y": 0.4364,
         "label": "f-16 r3"
        },
        {
         "x": 0.4115,
         "y": 0.4182,
         "label": "f-36 r3"
        },
        {
         "x": 0.4525,
         "y": 0.4673,
         "label": "f-136 r3"
        },
        {
         "x": 0.4475,
         "y": 0.4436,
         "label": "score s0 r3"
        },
        {
         "x": 0.5,
         "y": 0.4673,
         "label": "score+branch s0 r3"
        },
        {
         "x": 0.4656,
         "y": 0.4382,
         "label": "score s0 r3 (b)"
        },
        {
         "x": 0.4492,
         "y": 0.4345,
         "label": "score+branch s0 r3 (b)"
        },
        {
         "x": 0.4918,
         "y": 0.4655,
         "label": "hp s0 r3"
        },
        {
         "x": 0.4754,
         "y": 0.4473,
         "label": "hp+branch s0 r3"
        },
        {
         "x": 0.4508,
         "y": 0.4509,
         "label": "score s1 r3"
        },
        {
         "x": 0.4934,
         "y": 0.4927,
         "label": "score+branch s1 r3"
        },
        {
         "x": 0.4869,
         "y": 0.4545,
         "label": "hp s1 r3"
        },
        {
         "x": 0.4459,
         "y": 0.4345,
         "label": "hp+branch s1 r3"
        },
        {
         "x": 0.4738,
         "y": 0.4382,
         "label": "score s1 r10"
        },
        {
         "x": 0.4754,
         "y": 0.4527,
         "label": "score s0 r10"
        },
        {
         "x": 0.5082,
         "y": 0.4764,
         "label": "score+branch s0 r10"
        },
        {
         "x": 0.5344,
         "y": 0.5109,
         "label": "score+branch s1 r10"
        }
       ]
      }
     },
     {
      "id": "h-search-exact-puzzles",
      "title": "The last turn is easy; one turn before it is not",
      "claim": "On 10-26 an exact solver (up to 1 million positions per puzzle, every random event listed) gave the true value of every option in 2,000 end-of-fight decisions. The heuristic's one-turn search picked an exactly best option on all 1,552 last-turn puzzles, but on 9 to 10% of the puzzles one or more turns before the end it picked worse, giving up about 3 HP (0.03 score) on average there. The project's nets of that day scored the same as the heuristic within error: 13 of the 448 deeper puzzles fooled all four evaluators.",
      "tag": "project history · 25 to 28 October",
      "setting": "Heuristic evaluator, one-turn search (limit 16) against exact values; tight-fight puzzles, train and held-out halves pooled (1,000 each). Horizon = turns left in the fight. · n: 2,000 puzzles (1,552 last turn, 313 one turn out, 135 two or more out)",
      "caveat": "End-of-fight decisions only, from games the heuristic itself played; 77% of puzzles are last-turn ones where any evaluator scores 100% by construction. The 'all four evaluators' count comes from docs/research/exact-puzzles.md, the rest from the heuristic's result file.",
      "checked": "confirmed",
      "viz": {
       "kind": "bars",
       "unit": "% best pick",
       "rows": [
        {
         "label": "Last turn (horizon 0)",
         "value": 100,
         "note": "1,552 of 1,552; one turn of search sees the end of the fight"
        },
        {
         "label": "One turn before the end",
         "value": 90.1,
         "note": "282 of 313; mean regret 0.033 (about 3 HP)"
        },
        {
         "label": "Two or more turns before",
         "value": 91.1,
         "note": "123 of 135; mean regret 0.027"
        },
        {
         "label": "Contested (best beats 2nd by 0.05+)",
         "value": 92.7,
         "note": "240 of 259; mean regret 0.037"
        }
       ]
      }
     },
     {
      "id": "h-content-fun-puzzle-endings",
      "title": "2,000 endgame puzzles, and what the right move is worth",
      "claim": "On 26 October the exact solver turned 2,000 near-the-end positions from close fights into puzzles and worked out the true value of every move. In 1,111 of them the fight was already lost whatever you played, and in 133 it was won whatever you played. In 97 puzzles exactly one move out of three or more wins for certain and every other move loses for certain. The biggest knife edge has nine moves against three Louses at 7 HP, and only Clothesline+ on the second target wins. In one Lots of Slimes puzzle plain Thunderclap wins and Thunderclap+ loses. The likely reason is order: playing the plain one first means its Vulnerable makes the upgraded one hit harder.",
      "tag": "project history · 25 to 28 October",
      "setting": "data/bench/puzzles.json: 1,000 train and 1,000 held-out puzzles, one per tight-fight game played by search plus the hand-written player on fresh seeds; exact values from sts.solve with a 1M-node budget; a loss chance within 1e-9 of 0 or 1 counts as certain · n: 2,000 puzzles (1,552 on the fight's last turn, 448 one turn or more from the end)",
      "caveat": "The positions come from close fights played by the hand-written player, so lost positions are over-represented. A 'certain' loss or win means a loss chance of 1 or 0 under best play. The file stores 26 certain losses as 0.9999999999999998, so the counts use a 1e-9 tolerance. The Thunderclap order explanation is my reading of the card numbers (4 + 7x1.5 = 14 against 7 + 4x1.5 = 13); the solver doesn't record it.",
      "checked": "corrected",
      "viz": {
       "kind": "tally",
       "unit": "puzzles",
       "rows": [
        {
         "label": "Lost whatever you play",
         "value": 1111
        },
        {
         "label": "The move changes the odds or the HP left",
         "value": 659
        },
        {
         "label": "Won whatever you play",
         "value": 133
        },
        {
         "label": "Only one of 3+ moves wins; all others lose for certain",
         "value": 97
        }
       ]
      }
     }
    ]
   }
  ]
 },
 {
  "key": "p3",
  "name": "Period 3 (P3): Claude runs the lab day to day",
  "dates": "29 to 31 October",
  "parts": [
   {
    "name": "",
    "items": [
     {
      "id": "h-training-product-family",
      "title": "The product's net was trained on 10-29 and has held the product role since 11-02",
      "claim": "The product's net was trained on the evening of 29 October. (The real game on 14 November was played by another net, pack net seed 201, trained from scratch on 10 November on games with the real Act 1 cards.) Its family tree is short. A 60,000-fight pool played by the heuristic trained a first net. That net's 5,775 fights trained a second, whose 6,013 fights made up round 2. The seed-check run then retrained round 2 from scratch at three training seeds, and seed 1 became the product net. It learned from all 11,788 self-play fights plus a random sixth of the examples from the heuristic pool. On 11-01 two fine-tunes of it (burst8, then burst8hp2) took over for a day. On 11-02 it beat them on HP kept at the end of a run and became the product net, and none of the 383 nets trained after it has replaced it since. 167 runs started from it, trained on data it played, or used it to play.",
      "tag": "project history · 29 to 31 October",
      "setting": "Lineage from round.json parent_run and dataset manifest parent_model fields. Round-0 sampling from round.json window.round0_sample (1/6 for rounds 1 and up; seed_check.py retrains on the same window). Product history from configs/product.json 'previous' and the docs/decisions.md entries of 11-01 and 11-02. Later nets are runs with a model.pt whose run.json created time is after 10-29 22:32:39 (local time). · n: 1 product net; 11,788 self-play fights + 1/6 of the examples from a 60,000-fight heuristic pool (+3,000 validation fights); 383 later nets (including its 2 seed siblings); 167 runs that refer to it directly (173 counting their descendants)",
      "caveat": "Seeds 101 and 201 of the same retrain are its siblings and are counted among the 383. Most later nets were experiments judged on their own yardsticks, not challengers. 'Not replaced since 11-02' means none passed the rule for becoming the product, not that every one played worse. The 1/6 sample is of examples spread across all 60,000 pool fights, so the pool still shaped it.",
      "checked": "corrected",
      "viz": {
       "kind": "timeline",
       "unit": "event",
       "events": [
        {
         "x": "10-25",
         "label": "Round-0 pool: 60,000 fights played by the heuristic search (dataset 2bad7e)",
         "value": 60000
        },
        {
         "x": "10-27 21:28",
         "label": "score+branch-s0-r0 trains on half of that pool's examples"
        },
        {
         "x": "10-28 04:03",
         "label": "r0's 5,775 fights train score+branch-s1-r1, the first round of a night loop",
         "value": 5775
        },
        {
         "x": "10-28 04:23",
         "label": "r1's 6,013 fights are added and round 2 trains (with a sixth of the pool); the loop reaches round 10 by 06:55, about one round every 19 minutes",
         "value": 6013
        },
        {
         "x": "10-29 22:32",
         "label": "Seed-check retrains round 2 at seed 1 on the same data: the future product net"
        },
        {
         "x": "11-01",
         "label": "Fine-tunes of it take over: burst8 becomes champion, then burst8hp2 becomes the product"
        },
        {
         "x": "11-02",
         "label": "It beats burst8hp2 on HP kept at the end of a run and becomes the product net"
        },
        {
         "x": "11-13",
         "label": "Still the product net, now with the chooser and new search flags; 383 nets trained since 10-29"
        },
        {
         "x": "11-14",
         "label": "Plays the real game"
        }
       ]
      }
     },
     {
      "id": "h-measures-ladder-streak",
      "title": "After the first net beat the heuristic, the next 17 challengers all failed to beat it",
      "claim": "On 30 Oct the 10-29 net passed the paired ladder against the heuristic (+3.7 points of the same fights won, 1,150 pairs) and became champion. None of the next 17 candidates (30-31 Oct) beat it: its two seed twins, three nets trained on 40k positions, five lean-threshold seeds, three distilled nets, three cover21 nets and an ensemble. The best two were dead even (ensemble +0.2, seed twin s201 0.0). The cover21 nets did worst, about 6 to 7 points behind. The more-data nets (data40k) were 1.4 to 2.6 points behind, so more data did not help here. The streak ended on 1 Nov, when the burst8 nets passed against it.",
      "tag": "project history · 29 to 31 October",
      "setting": "Paired ladder, one-turn net player: candidate and champion (the 10-29 net) play the same fight with the same seed; lead = candidate's fight wins minus champion's, per pair; a sequential test stops at a verdict (pass needs evidence of a 1-point gain) · n: 17 tests against the 10-29 net, 482 to 4,274 pairs each (30-31 Oct); plus the promoting test against the heuristic",
      "caveat": "The test stops early once a verdict is clear, so big losses come from few pairs and their size is rough. A fail means no proof of a 1-point gain, not proof of a loss. The promoting +3.7 against the heuristic is a different comparison and is left off the bars; on its held-out half of fights the lead was only +1.0 (interval -1.7 to +3.8). The ladder measures one-turn play on single fights. The product later kept the 10-29 net because of whole-run end-HP reads, not because of this ladder (decisions 2026-11-02), and the ladder itself crowned an 11-01 net (burst8hp2) in the meantime.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "unit": "lead over the 10-29 net in fights won (percentage points)",
       "rows": [
        {
         "label": "ensemble with 10-29 net",
         "value": 0.2,
         "note": "fail, 4,274 pairs"
        },
        {
         "label": "10-29 net s201",
         "value": 0,
         "note": "fail, 4,090 pairs"
        },
        {
         "label": "lean-thr s201",
         "value": -0.7,
         "note": "fail, 1,880 pairs"
        },
        {
         "label": "10-29 net s101",
         "value": -1.3,
         "note": "fail, 1,305 pairs"
        },
        {
         "label": "lean-thr s101",
         "value": -1.3,
         "note": "fail, 1,349 pairs"
        },
        {
         "label": "lean-distil s101",
         "value": -1.3,
         "note": "fail, 1,349 pairs"
        },
        {
         "label": "data40k s101",
         "value": -1.4,
         "note": "fail, 1,305 pairs"
        },
        {
         "label": "lean-thr s401",
         "value": -1.6,
         "note": "fail, 1,120 pairs"
        },
        {
         "label": "data40k s201",
         "value": -1.8,
         "note": "fail, 1,152 pairs"
        },
        {
         "label": "lean-thr s301",
         "value": -1.8,
         "note": "fail, 1,257 pairs"
        },
        {
         "label": "data40k s1",
         "value": -2.6,
         "note": "fail, 847 pairs"
        },
        {
         "label": "lean-distil s1",
         "value": -3,
         "note": "fail, 771 pairs"
        },
        {
         "label": "lean-thr s1",
         "value": -3.2,
         "note": "fail, 570 pairs"
        },
        {
         "label": "lean-distil s201",
         "value": -4.7,
         "note": "fail, 580 pairs"
        },
        {
         "label": "cover21 s201",
         "value": -5.8,
         "note": "fail, 502 pairs"
        },
        {
         "label": "cover21 s101",
         "value": -5.9,
         "note": "fail, 575 pairs"
        },
        {
         "label": "cover21 s1",
         "value": -7.1,
         "note": "fail, 482 pairs"
        }
       ]
      }
     },
     {
      "id": "h-search-node-cap",
      "title": "Two-turn search lost until it was allowed to think longer",
      "claim": "In the first paired test of two-turn search (10-30), capped at 50,000 positions per decision, it won 4.8 points fewer elite and boss fights than plain one-turn search. Raising the cap to 400,000 turned that to +1.6. Making it fall back to the one-turn pick whenever the tree was still cut off (about 1 decision in 21 in play) gave +6.1. With the 10-29 net scoring the leaves, the same fixes moved it from -1.0 to +5.5. Most of the early loss came from cut-off trees, not from searching deeper.",
      "tag": "project history · 29 to 31 October",
      "setting": "Held-out decks, elite and boss fights. Every row uses the same 1,336 fights, and the one-turn results are identical fight for fight within each leaf scorer. Two-turn limit 16, sample k 4. Value = two-turn minus one-turn win rate. · n: 1,336 paired fights per row (se 0.013 to 0.015)",
      "caveat": "The cut shares in the notes come from a small probe of every third decision (61 to 133 decisions per run). In full play at 400k, 4.7 to 4.8% of decisions were cut, mostly in Sentries and Slime Boss. The research doc's '1%' figure disagrees with its own per-encounter table. The net rows have no plain cap-400k run, so for them the cap increase and the fallback can't be separated. Lagavulin was still slightly negative (about -3) with the fallback. Thread counts differed between runs (6, 4, 6), which affects timing, not wins.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "unit": "win-rate points, two-turn minus one-turn",
       "rows": [
        {
         "label": "Heuristic leaves, cap 50k",
         "value": -4.8,
         "note": "probe: mean 11,535 positions per decision, 13.5% of probed decisions cut"
        },
        {
         "label": "Heuristic leaves, cap 400k",
         "value": 1.6,
         "note": "mean 76,372 positions, 16% of probed (hard) decisions cut"
        },
        {
         "label": "Heuristic leaves, cap 400k + fall back when cut",
         "value": 6.1,
         "note": "one-turn 49.8% -> two-turn 55.8%; 4.7% of decisions in play were cut"
        },
        {
         "label": "10-29 net leaves, cap 50k",
         "value": -1,
         "note": "mean 16,341 positions, 23% of probed decisions cut"
        },
        {
         "label": "10-29 net leaves, cap 400k + fall back",
         "value": 5.5,
         "note": "one-turn 53.5% -> two-turn 59.1%; 4.8% of decisions in play were cut"
        }
       ]
      }
     },
     {
      "id": "h-content-fun-generated-powers",
      "title": "43 made-up Power cards: who coped better?",
      "claim": "On 31 October the project built Power cards from building blocks and swapped each one in for Demon Form or Metallicize in held-out fights. The hand-written player won less with 31 of the 43 cards. The 29 October net lost less than the hand-written player with 21 cards and more with 14. The hand-written player's two worst cards were defensive ones whose payoff comes later. One was '1 energy: this turn, when you lose HP, give all enemies 1 Weak' (-0.31 wins for the hand-written player, -0.19 for the net). With '2 energy: deal 1 damage to all enemies at the end of this turn', a card that does almost nothing, the hand-written player lost 0.225 wins and the net lost 0.05.",
      "tag": "project history · 29 to 31 October",
      "setting": "gen_powers bench: tight2 held-out cells, first 4 fights per cell, one turn deep. Each generated card replaces the Demon Form or Metallicize in the same fight (paired). Hand-written player vs the 29 October net (r2 s1). · n: 326 cells, 1,304 fights per set; 43 cards with 12 to 52 fights each",
      "caveat": "Each card has only 12 to 52 fights, so chance alone moves a single card's point by about 0.1 wins. Read the cloud, not one dot. 8 cards tie (the point sits on the diagonal). Labels don't show how many copies of the card the deck holds (1 to 3). Over all 326 cells, the net's lead over the hand-written player grew by +0.021 (se 0.011) on generated cards. The hand-written player rates only Strength powers, so it is a weak yardstick on generated content.",
      "checked": "corrected",
      "viz": {
       "kind": "scatter",
       "unit": "wins (share of fights)",
       "x_label": "Hand-written player: win rate with the generated card minus with the original",
       "y_label": "29 October net: win rate with the generated card minus with the original",
       "points": [
        {
         "x": -0.312,
         "y": -0.188,
         "label": "gc1_013: 1 energy, this turn: when you lose HP, 1 Weak to all enemies (16 fights)"
        },
        {
         "x": -0.25,
         "y": -0.125,
         "label": "gc1_017: 1 energy, once per stack: when attacked for HP, 1 Weak to all enemies (32 fights)"
        },
        {
         "x": -0.225,
         "y": -0.05,
         "label": "gc1_127: 2 energy, this turn: 1 damage to all at your turn end (40 fights)"
        },
        {
         "x": -0.208,
         "y": -0.167,
         "label": "gc1_105: 1 energy, fading: draw 1 when you play an Attack (24 fights)"
        },
        {
         "x": -0.208,
         "y": -0.083,
         "label": "gc1_028: 1 energy, all fight: when you play an Attack, draw 1 and lose 2 HP (24 fights)"
        },
        {
         "x": -0.188,
         "y": 0,
         "label": "gc1_110: 2 energy, all fight: when you play a card, lose 1 HP and draw 1 (16 fights)"
        },
        {
         "x": -0.179,
         "y": -0.214,
         "label": "gc1_090: 1 energy, once per stack: when attacked for HP, 1 Weak to all enemies (28 fights)"
        },
        {
         "x": -0.167,
         "y": -0.333,
         "label": "gc1_052: 1 energy, all fight: 1 Strength at turn start; 3 Block when a card costs you HP (12 fights)"
        },
        {
         "x": -0.125,
         "y": -0.083,
         "label": "gc1_123: 1 energy, fading: at turn start 1 energy and 1 Vulnerable to all enemies (24 fights)"
        },
        {
         "x": -0.125,
         "y": 0.042,
         "label": "gc1_079: 2 energy, all fight: draw 1 when you play a Power (24 fights)"
        },
        {
         "x": -0.125,
         "y": -0.075,
         "label": "gc1_011: 2 energy, once per stack: 2 damage to all at turn end; 1 Weak to all when you lose HP (40 fights)"
        },
        {
         "x": -0.125,
         "y": -0.083,
         "label": "gc1_047: 1 energy, all fight: when attacked for HP, 1 Weak to all enemies (24 fights)"
        },
        {
         "x": -0.1,
         "y": 0.05,
         "label": "gc1_062: 1 energy, once per stack: 1 Vulnerable to all enemies at turn start (20 fights)"
        },
        {
         "x": -0.083,
         "y": 0,
         "label": "gc1_048: 1 energy, this turn: when you lose HP, 3 damage and 1 Weak to all (36 fights)"
        },
        {
         "x": -0.083,
         "y": -0.083,
         "label": "gc1_026: 1 energy, fading: 2 damage to all when a card costs you HP (24 fights)"
        },
        {
         "x": -0.075,
         "y": -0.075,
         "label": "gc1_019: 1 energy, once per stack: 1 Weak to all when you lose HP; 1 Strength at turn start (40 fights)"
        },
        {
         "x": -0.071,
         "y": -0.036,
         "label": "gc1_016: 1 energy, all fight: 1 energy and 1 Strength at turn start (28 fights)"
        },
        {
         "x": -0.062,
         "y": -0.062,
         "label": "gc1_080: 1 energy, all fight: when you play a Power, lose 2 HP and draw 1 (32 fights)"
        },
        {
         "x": -0.062,
         "y": -0.062,
         "label": "gc1_020: 1 energy, once per stack: 1 energy and 1 Vulnerable to all at turn start (16 fights)"
        },
        {
         "x": -0.056,
         "y": -0.083,
         "label": "gc1_103: 1 energy, once per stack: 1 energy and 1 Strength at turn start (36 fights)"
        },
        {
         "x": -0.05,
         "y": -0.025,
         "label": "gc1_024: 2 energy, fading: lose 2 HP when you play a Skill (40 fights)"
        },
        {
         "x": -0.045,
         "y": -0.045,
         "label": "gc1_111: 2 energy, once per stack: 2 Block when a card costs you HP (44 fights)"
        },
        {
         "x": -0.042,
         "y": 0,
         "label": "gc1_086: 1 energy, fading: 1 energy at turn start (24 fights)"
        },
        {
         "x": -0.042,
         "y": -0.083,
         "label": "gc1_032: 1 energy, once per stack: 3 damage to all when you lose HP (24 fights)"
        },
        {
         "x": -0.036,
         "y": -0.071,
         "label": "gc1_018: 1 energy, all fight: 1 Dexterity and 3 damage to all at turn end (28 fights)"
        },
        {
         "x": -0.036,
         "y": 0.036,
         "label": "gc1_057: 2 energy, this turn: damage to all when you lose HP; draw 1 when you play a card (28 fights)"
        },
        {
         "x": -0.036,
         "y": -0.107,
         "label": "gc1_033: 2 energy, fading: 1 Dexterity at turn end; 1 Weak to all when attacked for HP (28 fights)"
        },
        {
         "x": -0.031,
         "y": -0.125,
         "label": "gc1_104: 1 energy, fading: 1 damage to all and 1 Dexterity at turn end (32 fights)"
        },
        {
         "x": -0.031,
         "y": -0.094,
         "label": "gc1_029: 1 energy, this turn: 1 Weak to all when you lose HP or are attacked (32 fights)"
        },
        {
         "x": -0.028,
         "y": 0,
         "label": "gc1_041: 2 energy, once per stack: 1 Weak to all when attacked for HP (36 fights)"
        },
        {
         "x": -0.023,
         "y": 0,
         "label": "gc1_095: 2 energy, once per stack: 1 energy and 1 Strength at turn start (44 fights)"
        },
        {
         "x": 0,
         "y": 0,
         "label": "gc1_069: 2 energy, fading: 2 damage to all at turn end (40 fights)"
        },
        {
         "x": 0,
         "y": 0.125,
         "label": "gc1_125: 1 energy, all fight: 5 damage to all when you lose HP (32 fights)"
        },
        {
         "x": 0,
         "y": -0.031,
         "label": "gc1_000: 2 energy, this turn: lose 2 HP when you play a Skill (32 fights)"
        },
        {
         "x": 0,
         "y": 0.094,
         "label": "gc1_025: 2 energy, this turn: 1 Dexterity and 2 damage to all at turn end (32 fights)"
        },
        {
         "x": 0,
         "y": 0,
         "label": "gc1_087: 2 energy, this turn: 1 Weak to all when attacked or when you lose HP (28 fights)"
        },
        {
         "x": 0,
         "y": 0.042,
         "label": "gc1_050: 2 energy, this turn: 3 damage to all at turn end (48 fights)"
        },
        {
         "x": 0,
         "y": -0.028,
         "label": "gc1_102: 2 energy, once per stack: when you play a card, draw 1 and lose 2 HP (36 fights)"
        },
        {
         "x": 0.036,
         "y": -0.036,
         "label": "gc1_030: 2 energy, once per stack: 1 Weak to all when you lose HP (28 fights)"
        },
        {
         "x": 0.038,
         "y": 0.038,
         "label": "gc1_082: 2 energy, fading: 1 Vulnerable to all and 1 Strength at turn start (52 fights)"
        },
        {
         "x": 0.062,
         "y": 0,
         "label": "gc1_049: 2 energy, once per stack: 1 Dexterity and 3 damage to all at turn end (32 fights)"
        },
        {
         "x": 0.083,
         "y": 0,
         "label": "gc1_065: 2 energy, fading: 1 Dexterity at turn end (12 fights)"
        },
        {
         "x": 0.111,
         "y": 0.028,
         "label": "gc1_109: 1 energy, fading: 1 Dexterity and 4 damage to all at turn end (36 fights)"
        }
       ]
      }
     }
    ]
   }
  ]
 },
 {
  "key": "p4",
  "name": "Period 4 (P4): From single fights to an Act",
  "dates": "1 to 2 November",
  "parts": [
   {
    "name": "",
    "items": [
     {
      "id": "h-training-data-scaling",
      "title": "More data helped, until 40,000 fights a group",
      "claim": "The lab tested whether more training fights make a better net. Going from 5,000 to 20,000 fights per group raised the held-out won share by +0.011. Going from 20,000 to 40,000 added +0.009. Going from 40,000 to 80,000 (a 240,000-fight dataset, the biggest the project ever made) added only +0.003, and the two seeds disagreed (+0.024 and -0.019). On 1 November the lab stopped scaling data and kept the 20k default for experiments. 40k became the usual size for new from-scratch nets only from 8 November.",
      "tag": "project history · 1 to 2 November",
      "setting": "Round-1 nets on the tight2 bench, one turn deep, held-out half (12,200 fights per net). Won-share differences are paired by seed. Only n_train differs between arms. · n: 5k vs 20k: 5 seeds; 20k vs 40k: 3 seeds; 40k vs 80k: 2 seeds",
      "caveat": "The first step is a fourfold increase and the other two are doublings. With only 2 seeds at 80k, the flat result is weak evidence. Both 80k nets also failed the ladder against the 10-29 champion (-0.018, -0.024). The 80k training jobs took 2.9 hours (s1) and 1.0 hours (s101) on 6 threads. The 5k/20k/40k results were read on 31 October; the 80k results and the stop decision came on 1 November.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "unit": "held-out won share gained",
       "rows": [
        {
         "label": "5k to 20k fights per group",
         "value": 0.011,
         "note": "5 seeds, se 0.006"
        },
        {
         "label": "20k to 40k",
         "value": 0.009,
         "note": "3 seeds, se 0.003"
        },
        {
         "label": "40k to 80k",
         "value": 0.003,
         "note": "2 seeds: +0.024 and -0.019"
        }
       ]
      }
     },
     {
      "id": "h-search-first-card",
      "title": "The first card of a turn costs more than the rest together",
      "claim": "Two-turn search re-plans after every card. On 11-02 a probe over 20 fights measured how big each search was: the turn's first decision explored 22,800 positions on average (0.34 s), the second 9,860, the third 4,270 and the fourth 1,430. The first decision took 61% of all positions searched. A follow-up on 11-03 reused the tree from the previous card instead of rebuilding it: 30% fewer positions (4.81 million down to 3.38 million), with the same pick on every compared decision (526).",
      "tag": "project history · 1 to 2 November",
      "setting": "10-29 net, two-turn search (limit 16, sample k 4, cap 400,000), 20 fights: 16 elite (Gremlin Nob, Lagavulin, Three Sentries) and 4 Slime Boss, 5 deck families; 502 searches over 139 turns. Positions = search tree nodes. · n: 502 searches (139 / 134 / 122 / 85 / 18 / 4 by place in turn)",
      "caveat": "20 fights (16 elite, 4 Slime Boss) over 5 deck families; milliseconds are wall time on the dev machine. The 5th and 6th rows rest on 18 and 4 searches. The tree-reuse figure is from results/depth/line-step-compare.json (same 20 fights, run just after midnight on 11-03).",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "unit": "positions searched per decision (mean)",
       "rows": [
        {
         "label": "1st decision of the turn",
         "value": 22801,
         "note": "n 139; 4,101 leaves scored; 345 ms"
        },
        {
         "label": "2nd",
         "value": 9859,
         "note": "n 134; 169 ms"
        },
        {
         "label": "3rd",
         "value": 4271,
         "note": "n 122; 73 ms"
        },
        {
         "label": "4th",
         "value": 1435,
         "note": "n 85; 20 ms"
        },
        {
         "label": "5th",
         "value": 1694,
         "note": "n 18; small n"
        },
        {
         "label": "6th",
         "value": 145,
         "note": "n 4; small n"
        }
       ]
      }
     },
     {
      "id": "h-search-rollout-bosses",
      "title": "Playing each option out 64 times saved 2 of 69 lost boss fights",
      "claim": "On 11-02 the lab ran a ceiling probe: at every decision of a replayed fight, play each option to the end of the fight with the one-turn net and pick the best average. It replayed the fatal fight of the 117 sequences no player had cleared. With 16 playouts per option it won 3 of them, and with 64 it won 7 (6%). Only 2 of those 7 were among the 69 boss fights (0 at 16 playouts). The other 5 were elites or hallway fights. On 30 boss fights the product had won, the rollout player lost 7 (16 playouts) and 3 (64 playouts). With 64 playouts, a fight took on average 5,300 playouts and 7 s on the lost set, and 7,700 playouts and 52 s on the won set. The result was under the 10% bar, so the lab read it as little headroom left in the fatal fight: losses are decided earlier, by HP spent on the way and by the deck.",
      "tag": "project history · 1 to 2 November",
      "setting": "Fatal fights of the 117 never-cleared sequences (69 floor-10 bosses, 48 earlier fights, mostly floor-9 elites), replayed at the entry HP of the product's run (champion-hpe0.01-two). Also 30 floor-10 boss fights the product won. Playout and decision player: 11-01 burst8hp2 net @hpb0.01, one turn deep. 4 threads, seed 0. Value: share of fights the rollout player won. · n: 69 lost boss fights, 48 lost non-boss fights, 30 won boss fights, each replayed at 16 and at 64 playouts per option",
      "caveat": "The fights were chosen by their outcome, so part of each change comes from selection (regression to the mean), not from the rollouts. n is small: 2 boss rescues and 30 won fights. The rollout player is the one-turn net, which is weaker than the product on bosses (all 3 losses at 64 playouts were Hexaghost at 80 HP), so this sets a lower bound on headroom, not a ceiling. It replays only the fatal fight, not the whole run.",
      "checked": "corrected",
      "viz": {
       "kind": "slope",
       "unit": "% fights won by the rollout player",
       "a_label": "16 playouts per option",
       "b_label": "64 playouts per option",
       "rows": [
        {
         "label": "Lost boss fights (69)",
         "a": 0,
         "b": 2.9
        },
        {
         "label": "Lost elite and hallway fights (48)",
         "a": 6.3,
         "b": 10.4
        },
        {
         "label": "Boss fights the product won (30)",
         "a": 76.7,
         "b": 90
        }
       ]
      }
     }
    ]
   }
  ]
 },
 {
  "key": "p5",
  "name": "Period 5 (P5): The AI roles take over",
  "dates": "3 to 5 November",
  "parts": [
   {
    "name": "",
    "items": [
     {
      "id": "h-machine-longest",
      "title": "The three longest jobs ran 34 hours in one lane, far past their first estimates",
      "claim": "The longest job in the queue's history is 0083-mutate-monsters: 13 h 56 min on 3 threads (11-04 03:24 to 17:21). It ran the two-turn product player on a stage-A table of mutated monsters, widened from 40x4 to 200x4. The second and third longest (0092, 10 h 11 min; 0113, 10 h 00 min) came from the same goal1-yardstick lane and followed it with gaps of 56 and 6 minutes. That lane kept 3 threads busy from 11-04 03:24 to 11-05 14:35. All three outran their first estimates (340, 450 and 330 min) by 1.4x to 2.5x. The steward raised each estimate mid-run from the job's pace, the last time when the job was 97-99% done. Short jobs (under an hour) usually finished in about half their estimate (median 0.50x, n=954).",
      "tag": "project history · 3 to 5 November",
      "setting": "jobs that started and ended; wall time from started to ended; first estimate = the 'from' of the first entry in the job's estimates list, or estimate_min if it was never revised · n: 1,091 started jobs; the top 3 shown",
      "caveat": "Wall time includes any slowdown from other jobs sharing the machine (other lanes ran alongside). The stored estimate_min is the last estimate, revised from pace near the end of each run, so comparing against it makes the estimates look accurate when they weren't. Three jobs is too few to say that long jobs are estimated worse in general.",
      "checked": "corrected",
      "viz": {
       "kind": "slope",
       "unit": "hours",
       "a_label": "first estimate",
       "b_label": "actual wall time",
       "rows": [
        {
         "label": "0083-mutate-monsters",
         "a": 5.67,
         "b": 13.94
        },
        {
         "label": "0092-mutate-monsters",
         "a": 7.5,
         "b": 10.19
        },
        {
         "label": "0113-mutate-monsters",
         "a": 5.5,
         "b": 10
        }
       ]
      }
     },
     {
      "id": "h-search-depth-headroom",
      "title": "Seventeen times the thinking for less than one HP",
      "claim": "On 11-04 the lab tested whether searching deeper than two turns pays off on floor-9 elites. A third turn of search (cap 1.6 million positions) took 44.5 s per fight, about 17 times the two-turn product's 2.5 s, and saved 0.75 HP per fight (se 0.81; all 48 fights won either way). A rollout leaf (16 playouts per option, about 1,160 playouts per fight, 10.4 s) lost 0.67 HP more per fight than the product (se 0.31) and lost 4 more fights out of 498. Neither reached the 1.5 HP bar, so the depth family was closed: on this laptop, searching past two turns stopped paying.",
      "tag": "project history · 3 to 5 November",
      "setting": "Floor-9 elite fights from the headline control's runs. Each fight is paired against the two-turn product's own play on the same fight. Player: the 10-29 net @hpe0.01. The three-turn arm ran on the first 48 fights only. The two-turn k 4 and k 16 points come from an 11-07 rerun of the same 498 fights. · n: 498 elite fights (three-turn arm: 48)",
      "caveat": "The two-turn timings come from the 11-07 rerun of the same 498 fights (files two4 and two16). The two4 rerun reproduces the product's play exactly, fight for fight. The k 16 point is a paired difference: 40.65 against 40.31 HP left, +0.34 HP, se 0.16. It came after the 11-04 decision and changes search width, not depth. Rollout seconds are summed per fight. The three-turn arm's 48 fights recorded 130 cap cuts over 1,027 decisions.",
      "checked": "corrected",
      "viz": {
       "kind": "scatter",
       "unit": "HP",
       "x_label": "seconds per elite fight",
       "y_label": "HP saved per fight vs the two-turn product",
       "points": [
        {
         "x": 2.5,
         "y": 0,
         "label": "Two-turn product (cap 400k, k 4)"
        },
        {
         "x": 4.1,
         "y": 0.34,
         "label": "Two-turn, k 16 (+0.34, se 0.16; 485/498 won, same as product)"
        },
        {
         "x": 10.4,
         "y": -0.67,
         "label": "Rollout leaf, 16 playouts (481/498 won)"
        },
        {
         "x": 44.5,
         "y": 0.75,
         "label": "Three-turn, cap 1.6M (48 fights)"
        }
       ]
      }
     }
    ]
   },
   {
    "name": "The 1,000-run test of the product",
    "items": [
     {
      "id": "sim-picks-product-favourites",
      "title": "The net's favourite and least favourite cards",
      "claim": "Offered Clash, the product took it 58% of the time, more than any other card; Spot Weakness, Anger and Inflame were also taken more often than not. At the bottom, Body Slam was taken only 5% of the time and Bloodletting 9%.",
      "tag": "simulated test · runs 0–999",
      "setting": "Simulated headline runs 0-999, product (the 10-29 net searching two turns deep), curated Act 1 test cards; 9,903 card rewards, 1,401 skipped (14%) · n: 9,903 card rewards over 1,000 runs; each card offered 442-1,239 times",
      "caveat": "These are the curated test cards, not the real game's card pool. Some cards (FTL, Metallicize, Demon Form, Uppercut, Iron Wave and others) can only be offered in the held-out half of the runs, so they were offered about 440-530 times instead of about 1,150-1,240. Each reward offers three cards, so a card's take rate also depends on what it was offered next to. FTL is the Defect's card (0 cost, 5 damage, draw 1 if you've played fewer than 3 cards this turn), added to the Ironclad's test pool; it is not Flash of Steel.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Clash",
         "value": 58.3,
         "note": "661 of 1,134 offers"
        },
        {
         "label": "Spot Weakness",
         "value": 54.5,
         "note": "615 of 1,129"
        },
        {
         "label": "Anger",
         "value": 53.2,
         "note": "630 of 1,185"
        },
        {
         "label": "Inflame",
         "value": 50.8,
         "note": "615 of 1,211"
        },
        {
         "label": "FTL (the Defect card, as an Ironclad test card)",
         "value": 47.3,
         "note": "228 of 482; held-out half only"
        },
        {
         "label": "Metallicize",
         "value": 43.3,
         "note": "198 of 457; held-out half only"
        },
        {
         "label": "Combust",
         "value": 39.3,
         "note": "475 of 1,210"
        },
        {
         "label": "Wild Strike",
         "value": 13.2,
         "note": "163 of 1,238"
        },
        {
         "label": "Brutality",
         "value": 10.9,
         "note": "131 of 1,207"
        },
        {
         "label": "Bloodletting",
         "value": 9,
         "note": "104 of 1,161"
        },
        {
         "label": "Body Slam",
         "value": 5.3,
         "note": "62 of 1,174"
        }
       ],
       "unit": "% of offers where the card was taken"
      }
     },
     {
      "id": "sim-picks-demon-form",
      "title": "Demon Form: the hand-written player loves it, the net doesn't",
      "claim": "The biggest disagreement between the two players is Demon Form. The hand-written player took it 68% of the time it was offered; the net took it 20% of the time. On almost every other card the two players' take rates were within 10 points of each other.",
      "tag": "simulated test · runs 0–499",
      "setting": "Simulated headline runs 0-499, product (net, two turns deep) against the hand-written player (one turn deep), on the same seeded runs; cards offered at least 30 times to each · n: Demon Form offered 250 times to the product and 238 times to the hand-written player; 4,958 and 4,812 rewards in all",
      "caveat": "Demon Form is a held-out card: the net never saw it in training. The hand-written player's runs that took Demon Form cleared 82 of 140 times (59%). Only 15 of its runs saw Demon Form offered and never took it, too few to compare against. The two players reach different decks and HP, so the same seed can give different offers later in a run.",
      "checked": "confirmed",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Demon Form, hand-written",
         "value": 68.1,
         "note": "162 of 238"
        },
        {
         "label": "Demon Form, net",
         "value": 19.6,
         "note": "49 of 250"
        },
        {
         "label": "Uppercut, hand-written",
         "value": 29.3,
         "note": "68 of 232"
        },
        {
         "label": "Uppercut, net",
         "value": 38.3,
         "note": "92 of 240"
        },
        {
         "label": "Combust, hand-written",
         "value": 34,
         "note": "207 of 609"
        },
        {
         "label": "Combust, net",
         "value": 41.7,
         "note": "260 of 623"
        },
        {
         "label": "Clash, hand-written",
         "value": 48.1,
         "note": "261 of 543"
        },
        {
         "label": "Clash, net",
         "value": 55.4,
         "note": "308 of 556"
        }
       ],
       "unit": "% of offers where the card was taken"
      }
     },
     {
      "id": "sim-picks-clear-correlation",
      "title": "Picks that go with more clears",
      "claim": "Of the runs where Metallicize was offered, the runs where the net took it cleared 93% of the time, against 82% when it didn't. At the other end, runs that took Bloodletting cleared 67% of the time, against 80% when they passed on it. This is a correlation, not a cause: a run that can afford Metallicize may already be going well.",
      "tag": "simulated test · runs 0–999",
      "setting": "Simulated headline runs 0-999, product (net, two turns deep); for each card, only runs where it was offered at least once; at least 40 runs on each side; every card whose gap is 5 points or more is shown; overall clear rate 80.7% · n: 1,000 runs; for each shown card, 58-520 runs took it and 152-657 did not",
      "caveat": "This is a correlation only. The net picks according to the state of the run, so a weak run may grab Bloodletting or Body Slam out of need. A gap of about 5 points is within noise for a card taken in 100-150 runs, so the rows near plus or minus 5 (Anger, Twin Strike, Pommel Strike) are not meaningful on their own. Each run picks several cards, so the rows overlap. A card counts as \"taken\" if the run took it on any floor where it was offered.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Clash",
         "value": 13.2,
         "note": "took: 414/475 (87%); passed: 159/215 (74%)"
        },
        {
         "label": "Metallicize",
         "value": 11,
         "note": "took: 151/162 cleared (93%); passed: 125/152 (82%)"
        },
        {
         "label": "Go for the Eyes",
         "value": 7,
         "note": "took: 148/167 (89%); passed: 133/163 (82%)"
        },
        {
         "label": "Inflame",
         "value": 6,
         "note": "took: 404/479 (84%); passed: 184/235 (78%)"
        },
        {
         "label": "Iron Wave",
         "value": 6,
         "note": "took: 88/99 (89%); passed: 179/216 (83%)"
        },
        {
         "label": "Twin Strike",
         "value": 5.4,
         "note": "took: 122/137 (89%); passed: 174/208 (84%)"
        },
        {
         "label": "Anger",
         "value": 5,
         "note": "took: 431/520 (83%); passed: 148/190 (78%)"
        },
        {
         "label": "Pommel Strike",
         "value": -5.3,
         "note": "took: 96/116 (83%); passed: 163/185 (88%)"
        },
        {
         "label": "Dropkick",
         "value": -6.2,
         "note": "took: 183/240 (76%); passed: 395/479 (82%)"
        },
        {
         "label": "Combust",
         "value": -6.9,
         "note": "took: 309/401 (77%); passed: 251/299 (84%)"
        },
        {
         "label": "Flex",
         "value": -7.2,
         "note": "took: 152/199 (76%); passed: 443/530 (84%)"
        },
        {
         "label": "Wild Strike",
         "value": -9.3,
         "note": "took: 108/149 (72%); passed: 471/576 (82%)"
        },
        {
         "label": "Demon Form",
         "value": -9.8,
         "note": "took: 62/81 (77%); passed: 196/227 (86%)"
        },
        {
         "label": "Brutality",
         "value": -9.8,
         "note": "took: 92/126 (73%); passed: 477/576 (83%)"
        },
        {
         "label": "Body Slam",
         "value": -11.9,
         "note": "took: 40/58 (69%); passed: 531/657 (81%)"
        },
        {
         "label": "Bloodletting",
         "value": -13.8,
         "note": "took: 66/99 (67%); passed: 485/603 (80%)"
        }
       ],
       "unit": "clear-rate points: runs that took the card minus runs that were offered it and passed"
      }
     },
     {
      "id": "sim-picks-boss-nemesis",
      "title": "Each player's nemesis boss",
      "claim": "Slime Boss is barely a threat to the net, which won 96% of its arrivals; Hexaghost (78%) and The Guardian (81%) are about level for it. The Guardian was the hand-written player's nightmare: it won only 52% of its fights against him. On the same seeds, the net beat him 86% of the time.",
      "tag": "simulated test · runs 0–999",
      "setting": "Simulated headline runs; product (net, two turns deep) runs 0-999; hand-written player (one turn deep) runs 0-499; fights started on the boss floor (floor 11 of 11). Both players see identical encounters on the same seed. · n: Product: 947 boss arrivals; hand-written: 401 boss arrivals; 389 seeds (0-499) where both reached the boss",
      "caveat": "The two players were tested on different run counts (1,000 against 500), and the weaker player reaches the boss with a weaker deck, so this is not a pure boss-skill comparison. The net's Hexaghost-vs-Guardian gap is within noise: on runs 0-499 it is 82% vs 81%, and on runs 500-999 it is 73% vs 81%. Same seeds where both players reached the boss: Guardian 112/130 (net) vs 67/130 (hand-written); Hexaghost 109/127 vs 80/127; Slime Boss 131/132 vs 111/132.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Slime Boss, net",
         "value": 96.1,
         "note": "323 of 336"
        },
        {
         "label": "The Guardian, net",
         "value": 80.9,
         "note": "242 of 299"
        },
        {
         "label": "Hexaghost, net",
         "value": 77.6,
         "note": "242 of 312"
        },
        {
         "label": "Slime Boss, hand-written",
         "value": 84.8,
         "note": "117 of 138"
        },
        {
         "label": "Hexaghost, hand-written",
         "value": 62.3,
         "note": "81 of 130"
        },
        {
         "label": "The Guardian, hand-written",
         "value": 51.9,
         "note": "69 of 133"
        }
       ],
       "unit": "% of boss arrivals won"
      }
     },
     {
      "id": "sim-picks-how-runs-end",
      "title": "How runs end",
      "claim": "81% of the net's runs clear the act. Of the ones that don't, nearly three in four die to the boss (140 of 193), and most of the rest die to the second elite on floor 9. The hand-written player clears only 53% of the time, dies to the boss about twice as often and dies in hallway fights about four times as often.",
      "tag": "simulated test · runs 0–999",
      "setting": "Simulated headline runs, 11-fight test act (hallways, elites on floors 6 and 9, boss on 11); product (net, two turns deep) runs 0-999; hand-written player (one turn deep) runs 0-499 · n: 1,000 product runs, 500 hand-written runs",
      "caveat": "This is the curated 11-fight test act, not a real Act 1 map: there are no shops or events, and the rests are simulated. Neither player died on floors 1-5. The net's cleared runs ended with 34 HP on average (lowest 7), against 30 for the hand-written player (lowest 7). The two players differ in both the evaluator (net vs hand-written) and the search depth (two turns vs one), so the gap can't be put down to either one alone.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Net: cleared",
         "value": 80.7,
         "note": "807 of 1,000"
        },
        {
         "label": "Net: died to the boss",
         "value": 14,
         "note": "140"
        },
        {
         "label": "Net: died to an elite",
         "value": 3.6,
         "note": "36 (34 of them on floor 9)"
        },
        {
         "label": "Net: died in a hallway fight",
         "value": 1.7,
         "note": "17 (16 on floor 10)"
        },
        {
         "label": "Hand-written: cleared",
         "value": 53.4,
         "note": "267 of 500"
        },
        {
         "label": "Hand-written: died to the boss",
         "value": 26.8,
         "note": "134"
        },
        {
         "label": "Hand-written: died to an elite",
         "value": 12.2,
         "note": "61 (59 of them on floor 9)"
        },
        {
         "label": "Hand-written: died in a hallway fight",
         "value": 7.6,
         "note": "38 (28 on floor 10)"
        }
       ],
       "unit": "% of runs"
      }
     },
     {
      "id": "sim-picks-deadliest-fights",
      "title": "Fights that never killed the net",
      "claim": "Jaw Worm, Cultist, the louse packs, Fungi Beasts and Small Slimes went a combined 4,394 fights without killing the net once. Among non-boss fights, Lagavulin was the deadliest, but it still lost only 16 of 668.",
      "tag": "simulated test · runs 0–999",
      "setting": "Simulated headline runs 0-999, product (net, two turns deep); every fight played, by encounter · n: 10,903 fights over 1,000 runs",
      "caveat": "These are the curated test monsters, played as fixed 'easy' and 'hard' hallway slots. Where a fight sits in the run matters: elites on floor 9 start with less HP than on floor 6 (54 vs 74 on average) and account for 34 of the 36 elite losses. Three Louse (676 fights) and Two Fungi Beasts (718) also had 0 losses but are left out of the chart for space. Exordium Wildlife, Large Slime and Looter (2 losses each) are not shown. Bosses were reached in 947 of the 1,000 runs.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Lagavulin",
         "value": 2.4,
         "note": "16 of 668"
        },
        {
         "label": "Gremlin Nob",
         "value": 1.7,
         "note": "11 of 658"
        },
        {
         "label": "3 Sentries",
         "value": 1.3,
         "note": "9 of 671"
        },
        {
         "label": "Exordium Thugs",
         "value": 0.9,
         "note": "6 of 701"
        },
        {
         "label": "Lots of Slimes",
         "value": 0.7,
         "note": "5 of 710"
        },
        {
         "label": "Jaw Worm",
         "value": 0,
         "note": "0 of 755"
        },
        {
         "label": "Cultist",
         "value": 0,
         "note": "0 of 738"
        },
        {
         "label": "Small Slimes",
         "value": 0,
         "note": "0 of 762"
        },
        {
         "label": "Two Louse",
         "value": 0,
         "note": "0 of 745"
        }
       ],
       "unit": "% of fights lost"
      }
     }
    ]
   }
  ]
 },
 {
  "key": "p6",
  "name": "Period 6 (P6): Real Act 1 goes in",
  "dates": "6 to 9 November",
  "parts": [
   {
    "name": "",
    "items": [
     {
      "id": "h-training-burst-sizes",
      "title": "Fine-tunes on as few as 11 fights",
      "claim": "In period 6 the lab mostly stopped training nets from scratch. Instead it fine-tuned one existing net in short bursts on new content's fights: 127 fine-tunes against 8 from-scratch runs. Of the 127 bursts, 94 used 99 fights or fewer, and 12 used just 11. The question had shifted from 'what is the best net?' to 'how few fights does the net need to adapt to new content?'.",
      "tag": "project history · 6 to 9 November",
      "setting": "Fine-tune runs created 11-06 to 11-09 (run.json created, local time) whose run.json has a parent net; the games value from each config.json. One memory-check rerun with an identical config (ycards-heur-g400-s1-memcheck) is left out. · n: 127 fine-tune nets (one parent net); 8 from-scratch runs in the same days",
      "caveat": "Burst sizes count fights of new content mixed into a 10,000-position replay pool, not the whole training set. The from-scratch runs in the same days used 5,000 or 40,000 training positions, a different unit, so the page doesn't compare the two. Small bursts are cheap, so many seeds and variants were run; that partly explains the counts.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "unit": "nets",
       "rows": [
        {
         "label": "11 fights",
         "value": 12
        },
        {
         "label": "33 fights",
         "value": 44
        },
        {
         "label": "50 fights",
         "value": 2
        },
        {
         "label": "99 fights",
         "value": 36
        },
        {
         "label": "100 fights",
         "value": 3
        },
        {
         "label": "400 fights",
         "value": 19
        },
        {
         "label": "1,600 fights",
         "value": 5
        },
        {
         "label": "4,000 fights",
         "value": 6
        }
       ]
      }
     },
     {
      "id": "h-measures-seed-spread",
      "title": "Retraining the same recipe with a new seed moves the score as much as most ideas did",
      "claim": "On 6-7 Nov the lanes read 9 training recipes, each trained with 3 to 5 different seeds, on the same 500 gauntlet sequences. For three recipes they also read the same nets a second way (@tsl1). Seeds of the same recipe differed by 1.4 to 5.2 points of clear rate (median 2.0). The 10-29 net's whole lead over the heuristic on these sequences is 3.8 points (0.634 vs 0.596). So the luck of a single training seed could make an idea look like it gained or lost most of that lead. This is why the project read seed twins before believing a result.",
      "tag": "project history · 6 to 9 November",
      "setting": "Cell gauntlet (seed 20261101, rest 0.3), one-turn search, sequences 0-499, 500 sequences per read. Recipes with 3 or more training seeds whose reads all fall on 6-9 Nov (data20k was trained 10-31 and burst8 on 11-01; both were re-read 11-06/07). Rows marked @tsl1 are the same nets read with the tsl1 search option. · n: 9 recipes, 29 nets, 35 reads (11 recipe-and-read groups)",
      "caveat": "Reading the same net again gives exactly the same result, so the gap comes from the training seed. But how big it is depends on which 500 sequences are used: on sequences 500-999 the data20k seeds differ by 3.4 points, not 5.2. With only 3 seeds the gap understates the full range. On this gauntlet, across all 24 recipe-and-read groups with 2 or more seeds from every period, the median gap is 1.6 points.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "unit": "gap between best and worst seed (clear-rate points)",
       "rows": [
        {
         "label": "data20k (5 seeds)",
         "value": 5.2,
         "note": "0.586 to 0.638"
        },
        {
         "label": "ycards heur-g400",
         "value": 3.4,
         "note": "0.600 to 0.634"
        },
        {
         "label": "burst8 'neither'",
         "value": 3.2,
         "note": "0.588 to 0.620"
        },
        {
         "label": "ycards net-g1600, read @tsl1",
         "value": 3,
         "note": "0.638 to 0.668 (same nets as the row below)"
        },
        {
         "label": "ycards net-g400",
         "value": 2.6,
         "note": "0.596 to 0.622"
        },
        {
         "label": "ycards net-g1600",
         "value": 2,
         "note": "0.628 to 0.648"
        },
        {
         "label": "burst8, read @tsl1",
         "value": 1.6,
         "note": "0.646 to 0.662"
        },
        {
         "label": "burst8 'parts'",
         "value": 1.6,
         "note": "0.590 to 0.606"
        },
        {
         "label": "ycards net-g100",
         "value": 1.6,
         "note": "0.612 to 0.628"
        },
        {
         "label": "ycards two-g400",
         "value": 1.4,
         "note": "0.614 to 0.628"
        },
        {
         "label": "ycards two-g400, read @tsl1",
         "value": 1.4,
         "note": "0.616 to 0.630 (same nets as the row above)"
        }
       ]
      }
     },
     {
      "id": "h-content-fun-zero-shot-act1-cards",
      "title": "22 new Ironclad cards the net had never seen",
      "claim": "When the real Act 1 Ironclad cards went in on 7 November, the 29 October net was tested on 22 cards it had never trained on, with three copies of each card put into the deck. On 19 of them it lost nothing against the hand-written player: 18 read level, and with Berserk it pulled ahead (+0.066 wins). Berserk made both players worse, but the hand-written player got worse by more, and it played Berserk on only 15% of the turns it held one. Three cards cost the net: Impervious (-0.122 wins), Disarm (-0.118) and Intimidate (-0.062). All three are Exhaust skills whose whole value is a number the net must read: 30 Block, negative enemy Strength, Weak on every enemy.",
      "tag": "project history · 6 to 9 November",
      "setting": "tight2 held-out elite and boss cells (126 elite, 41 boss), three fights each, three copies of the card in place of three Strikes (then Defends), paired with the same fights without the card; 29 October net @hpb0.01 one turn deep (@tsl1 on decks with a turn-start power) minus the hand-written player · n: 167 cells x 3 fights per card, 22 cards; se 0.026 to 0.034 wins",
      "caveat": "With 22 cards read at 2 se, about one false hit is expected by chance. Disarm and Impervious are well past that; Intimidate and Berserk sit right at 2 se, and Berserk's gain comes from the 41 boss cells alone. 'Why' (inputs outside the training range) is the lane's hypothesis, not a measurement: Shockwave also applies Weak and reads level. A lead measures the net against the hand-written player, not whether the card is good (Burning Pact and Exhume hurt both players about equally and read level).",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "unit": "change in the net's win-rate lead over the hand-written player",
       "rows": [
        {
         "label": "Impervious",
         "value": -0.122,
         "note": "se 0.034; -1.58 HP"
        },
        {
         "label": "Disarm",
         "value": -0.118,
         "note": "se 0.032; -2.16 HP"
        },
        {
         "label": "Intimidate",
         "value": -0.062,
         "note": "se 0.029; -1.08 HP"
        },
        {
         "label": "Seeing Red",
         "value": -0.042,
         "note": "se 0.032"
        },
        {
         "label": "True Grit",
         "value": -0.032,
         "note": "se 0.029"
        },
        {
         "label": "Second Wind",
         "value": -0.03,
         "note": "se 0.032"
        },
        {
         "label": "Immolate",
         "value": -0.03,
         "note": "se 0.028"
        },
        {
         "label": "Exhume",
         "value": -0.028,
         "note": "se 0.031"
        },
        {
         "label": "Feed",
         "value": -0.022,
         "note": "se 0.028"
        },
        {
         "label": "Bludgeon",
         "value": -0.02,
         "note": "se 0.026"
        },
        {
         "label": "Power Through",
         "value": -0.016,
         "note": "se 0.028"
        },
        {
         "label": "Offering",
         "value": -0.008,
         "note": "se 0.034"
        },
        {
         "label": "Shockwave",
         "value": -0.006,
         "note": "se 0.030"
        },
        {
         "label": "Flame Barrier",
         "value": -0.002,
         "note": "se 0.031"
        },
        {
         "label": "Ghostly Armor",
         "value": 0.002,
         "note": "se 0.027"
        },
        {
         "label": "Searing Blow",
         "value": 0.008,
         "note": "se 0.028"
        },
        {
         "label": "Fiend Fire",
         "value": 0.012,
         "note": "se 0.031"
        },
        {
         "label": "Burning Pact",
         "value": 0.014,
         "note": "se 0.031"
        },
        {
         "label": "Double Tap",
         "value": 0.018,
         "note": "se 0.031"
        },
        {
         "label": "Reckless Charge",
         "value": 0.026,
         "note": "se 0.030"
        },
        {
         "label": "Sever Soul",
         "value": 0.032,
         "note": "se 0.029"
        },
        {
         "label": "Berserk",
         "value": 0.066,
         "note": "se 0.033 (2.0 se); all in the 41 boss cells; hand-written player plays it 15% of turns held"
        }
       ]
      }
     },
     {
      "id": "h-content-fun-trigger-cost",
      "title": "Made-up monster powers: the trigger orders the cost",
      "claim": "The 24 made-up elite powers combine 4 triggers with 7 effects (Strength, Block, Damage, PlainDamage, Weak, Vulnerable, Frail), minus the 4 pairs that real monsters already have. On average, the time a power fires orders its cost more than what it does. Powers that fire at the monster's own turn start or end cost the net 0.39 and 0.53 HP per elite fight, measured beyond a stat-only fight of matching difficulty. Powers that punish the player's own actions cost 1.62 (playing a card) and 2.98 (hitting the monster). The effect still matters: Weak costs over 2 HP on every trigger. Three mechanics are left out because the hand-written player collapsed on them. Against 'Vulnerable to the player on every card played' it won only 69% of elite fights, while the net won 85%.",
      "tag": "project history · 6 to 9 November",
      "setting": "Generated-enemies bench: official Act 1 elites (Gremlin Nob, Lagavulin, three Sentries), each carrying one generated power. Cost = (29 October net @hpb0.01@tsl1, one turn deep, minus the hand-written player) on the mechanic, minus the same gap on the stat-only control nearest in difficulty, paired by start. · n: 675 elite starts x 16 seeds per mechanic; 21 mechanics (7 + 5 + 4 + 5) of the 24",
      "caveat": "Each bar is a mean over 4 to 7 mechanics, and much of a mechanic's cost depends on which elite carries it. Nob alone drives the attack-trigger mean: 'damage when hit' costs +12.8 on Nob and under 2 on the others. The three left-out mechanics all sit on the player-action triggers and all read negative, because the hand-written player collapsed there, not because the net did well. Including them would lower those two bars. Turn-start and turn-end versions of one effect read almost alike, so there are about 19 distinct mechanics, not 24. The page's 1.28 HP headline is the mean of these 21.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "unit": "HP lost per elite fight beyond the hand-written player and the control (mean over mechanics)",
       "rows": [
        {
         "label": "Monster's turn start",
         "value": 0.39,
         "note": "7 mechanics; range -1.76 to +2.21 (Weak)"
        },
        {
         "label": "Monster's turn end",
         "value": 0.53,
         "note": "5 mechanics; range -0.46 to +2.55 (Weak)"
        },
        {
         "label": "Player plays a card",
         "value": 1.62,
         "note": "4 mechanics (Weak and Vulnerable left out; with them -1.00)"
        },
        {
         "label": "Player's attack takes the monster's HP",
         "value": 2.98,
         "note": "5 mechanics (Vulnerable left out; with it +1.39)"
        }
       ]
      }
     }
    ]
   }
  ]
 },
 {
  "key": "p7",
  "name": "Period 7 (P7): New nets for new content; relics and potions",
  "dates": "10 to 12 November",
  "parts": [
   {
    "name": "",
    "items": [
     {
      "id": "h-search-luck",
      "title": "Luck is a fifth of the noise, and subtracting it didn't help",
      "claim": "On 11-11 the lab measured how much of a training label is luck. Replaying 1,200 positions 8 times each showed that luck after the decision is 19% of the labels' spread, not most of it. Subtracting the net's estimate of that luck removed only 13% of it (1% on Demon Form decks). On paired comparisons of two players over 100 card sequences, the luck-corrected difference was more spread out than the raw one (standard deviation 12.0 HP against 8.5). It needed a ratio of 0.75 or lower and got 1.41.",
      "tag": "project history · 10 to 12 November",
      "setting": "3,200 one-turn fights (1,600 elite, 1,600 boss) of the g1600 recipe, played by the 10-29 net @hpb0.01 on held-out decks; luck valued by the 10-29 net. Paired read: the same net with and without one setting, 100 sequences. · n: 22,813 labelled rows; 1,200 rows replayed 8 times; 100 paired sequences",
      "caveat": "One net values the luck. Its own error (0.147) is about twice the label noise, so a better net might price more of it. The 19% pools elite and boss fights: luck is 37% of the elite label spread and 20% of the boss spread. The ratio's se is wide (0.50): 1.41 is clearly above the 0.75 bar, but not clearly above 1.0, so 'no help' is firmer than 'worse'.",
      "checked": "corrected",
      "viz": {
       "kind": "bignum",
       "unit": "",
       "rows": [
        {
         "label": "Luck's share of label spread",
         "value": 19,
         "note": "% (noise variance 0.071 of 0.364)"
        },
        {
         "label": "Luck removed by the correction",
         "value": 13,
         "note": "% (se 5); 1% on Demon Form decks"
        },
        {
         "label": "Paired-read spread, corrected / raw",
         "value": 1.41,
         "note": "ratio (se 0.50); bar was 0.75 or lower"
        }
       ]
      }
     },
     {
      "id": "h-content-fun-four-at-once",
      "title": "Four made-up powers on one elite at once",
      "claim": "Around midnight of 10-11 November the lab stacked four made-up monster powers on a single official elite, on 40 different random combinations. The 29 October net and a net trained from scratch on the real Act 1 pack both lost about 6 HP per fight more than the hand-written player, beyond what the plain elite costs. The net trained on a pack of made-up mechanics lost about half as much, 3.16 HP, on combinations it had never met together.",
      "tag": "project history · 10 to 12 November",
      "setting": "Random-world bench, no-death mode: 40 worlds of 4 generated mechanics drawn from the 21-mechanic main pool, on 50 shared official elite starts x 4 seeds; each net @tsl1 one turn deep, cost = net's HP lost beyond the plain elite minus the hand-written player's, a death counted as the whole start HP · n: 40 worlds x 50 starts x 4 seeds per net (8,000 fights per player per net)",
      "caveat": "One seed per new net. The generated-pack net trained on these mechanics singly, so the test is new combinations, not new mechanics. The 29 October net's worlds were played on 9 November (same worlds and starts); the two new nets' runs ran 10 Nov 23:41 to 11 Nov 00:14. With the start-HP cap, deaths dominate the remaining cost: the generated-pack net dies about as often as the hand-written player (0.49 vs 0.51 of games).",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "unit": "HP lost per elite fight beyond the hand-written player",
       "rows": [
        {
         "label": "29 October net",
         "value": 6.38,
         "note": "se 0.20"
        },
        {
         "label": "Net trained from scratch on the real Act 1 pack (seed 1)",
         "value": 6.16,
         "note": "se 0.23"
        },
        {
         "label": "Net trained on the made-up mechanics pack (seed 1)",
         "value": 3.16,
         "note": "se 0.18; paired cut -3.01 (0.18)"
        }
       ]
      }
     }
    ]
   }
  ]
 },
 {
  "key": "p8",
  "name": "Period 8 (P8): The product changes; the real game",
  "dates": "13 to 14 November",
  "parts": [
   {
    "name": "Behind the scenes",
    "items": [
     {
      "id": "h-writing-kb",
      "title": "636 stored facts, 48 now suspect",
      "claim": "By 11-14 the project's fact store (docs/claims) held 636 facts: 426 active, 210 retired. Measurements are the bulk (246 active). Lane facts are almost all retired (161 of 169) because a lane's facts retire when it closes. The real-game day left 48 active facts suspect: the store flags a fact automatically when a file it cites changes. 13 of the 34 'how' facts (how the code works) went suspect, because the day's rule fixes touched engine files (state.rs, monsters.rs, registry.rs) and scripts/gauntlet.py. Every file those facts cite was last changed on 11-14. The most-rewritten fact is lane/act1-content/step, revised 59 times as the Act 1 content work moved block by block.",
      "tag": "project history · 13 to 14 November",
      "setting": "Every JSON fact under docs/claims (recursive) at the working tree of 11-14; suspect = listed by 'kb.py check'; one bar per area, value = active facts. · n: 636 facts (426 active, 210 retired, 48 suspect)",
      "caveat": "Suspect is a snapshot taken on the last day, right after many rule fixes, so it is higher than on a quiet day. A suspect fact may still be true; it only needs a re-check. The store started late on 11-02 (80 seeded facts), so facts were created in periods 4-8 only (85, 133, 201, 86, 131).",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "unit": "active facts",
       "rows": [
        {
         "label": "measurement",
         "value": 246,
         "note": "18 suspect, 33 retired, 176 revised at least once (retired included)"
        },
        {
         "label": "decision",
         "value": 67,
         "note": "5 suspect, 9 retired"
        },
        {
         "label": "cause",
         "value": 48,
         "note": "9 suspect, 1 retired"
        },
        {
         "label": "how",
         "value": 34,
         "note": "13 suspect (38%), all citing files changed on 11-14"
        },
        {
         "label": "yardstick",
         "value": 15,
         "note": "1 suspect"
        },
        {
         "label": "lane",
         "value": 8,
         "note": "2 suspect, 161 retired"
        },
        {
         "label": "owner",
         "value": 6,
         "note": "0 suspect"
        },
        {
         "label": "context / product",
         "value": 2,
         "note": "0 suspect; spec facts: 5, all retired"
        }
       ]
      }
     }
    ]
   },
   {
    "name": "What it thinks hardest about",
    "items": [
     {
      "id": "thinking-blink-or-ponder",
      "title": "Mostly instant, now and then a long think",
      "claim": "At Ascension 20 the AI makes a typical move in 0.15 seconds, and three moves in four take under a second. The slowest 10% of moves, though, used 73% of all its thinking time, and one move in a hundred took more than 28 seconds.",
      "tag": "real game · A0 and A20, shown apart",
      "setting": "Real game, A20, all run-rule versions pooled, runs 28-90 (63 runs, 3,579 fight decisions); A0 shown separately, runs 1-27 (27 runs, 1,739 fight decisions) · n: 3,579 A20 decisions; 1,739 A0 decisions",
      "caveat": "These are wall-clock seconds on a laptop that other jobs shared, so single times are noisy. A0 and A20 used different net and search versions and different decks, so the two settings aren't a like-for-like comparison. In total the AI thought for about 2.4 hours in the A20 runs and 1.7 hours in the A0 runs. Percentiles take the sorted value at position p*N (linear interpolation gives values up to 0.1 s lower). The slowest-10% share is 72.5%, rounded to 73%.",
      "checked": "confirmed",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "A20 median",
         "value": 0.15
        },
        {
         "label": "A20 90th percentile",
         "value": 7.63
        },
        {
         "label": "A20 99th percentile",
         "value": 28.29
        },
        {
         "label": "A0 median",
         "value": 0.31
        },
        {
         "label": "A0 90th percentile",
         "value": 12.37
        },
        {
         "label": "A0 99th percentile",
         "value": 28.43
        }
       ],
       "unit": "seconds per decision"
      }
     },
     {
      "id": "thinking-slime-boss-headache",
      "title": "Slime Boss is the fight it thinks hardest about",
      "claim": "In a typical Slime Boss fight the AI thought for 81 seconds in total. In a typical Hexaghost fight it thought for 2 seconds, and against Gremlin Nob for about 1. Four of the five A20 fights with the most total thinking time were Slime Boss fights, and one of them took 7 minutes 20 seconds.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20, all run-rule versions pooled, runs 28-90; median total thinking seconds per fight for selected encounters, each seen at least 14 times (Gremlin Gang pooled over all its gremlin mixes) · n: 582 A20 fights; per row: Slime Boss 20, Gremlin Gang 20, Large Acid Slime 14, Sentries 15, The Guardian 14, Hexaghost 17, Lagavulin 18, Gremlin Nob 21, Jaw Worm 49, Cultist 52",
      "caveat": "These are totals for each fight, so longer fights add up more time. The median number of decisions was 12.5 for Slime Boss, 10 for Hexaghost and 13.5 for The Guardian, so fight length alone doesn't explain the gap. The slimes that split off also count toward the Slime Boss fight. The rows are a selection of encounters, not all of them. The fifth fight in the top five was Jaw Worm + Spike Slime (M) at 434 s.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Slime Boss (boss)",
         "value": 80.9,
         "note": "n=20, worst 440 s"
        },
        {
         "label": "Gremlin Gang (hallway)",
         "value": 30.7,
         "note": "n=20, any 4 gremlins"
        },
        {
         "label": "Acid Slime (L) (hallway)",
         "value": 23.6,
         "note": "n=14"
        },
        {
         "label": "3 Sentries (elite)",
         "value": 16.6,
         "note": "n=15"
        },
        {
         "label": "The Guardian (boss)",
         "value": 5.4,
         "note": "n=14"
        },
        {
         "label": "Hexaghost (boss)",
         "value": 2.1,
         "note": "n=17"
        },
        {
         "label": "Lagavulin (elite)",
         "value": 1.2,
         "note": "n=18"
        },
        {
         "label": "Gremlin Nob (elite)",
         "value": 1.1,
         "note": "n=21"
        },
        {
         "label": "Jaw Worm (hallway)",
         "value": 0.3,
         "note": "n=49"
        },
        {
         "label": "Cultist (hallway)",
         "value": 0.1,
         "note": "n=52"
        }
       ],
       "unit": "median seconds of thinking per fight"
      }
     },
     {
      "id": "thinking-crowded-board",
      "title": "Every extra monster slows it down",
      "claim": "With one monster left, the AI averages 1.22 seconds a move and only 4% of moves hit the search's node cap. With four on the board (gremlin gangs, slime splits) it averages 7.57 seconds, and 39% of those moves hit the cap.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20, all run-rule versions pooled, runs 28-90; fight decisions grouped by the number of living monsters that have not escaped · n: 3,579 A20 decisions (1 alive: 2,323; 2: 883; 3: 280; 4: 72; 5: 21 decisions over 10 runs, all in the Lots of Slimes fight)",
      "caveat": "There are only 21 decisions with five monsters, and all of them come from one fight, the Lots of Slimes hallway. Each extra monster adds a target for every attack card: the average number of options goes from 4.2 with one monster to 14.7 with five, so the search has more to weigh. These numbers show that the two go together, not that the monster count alone causes the slowdown. The crowded fights also differ in other ways, such as the monsters' types and the turn number.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "1 monster",
         "value": 1.22,
         "note": "n=2,323; median 0.08 s; 4% hit the cap"
        },
        {
         "label": "2 monsters",
         "value": 3.75,
         "note": "n=883; median 0.45 s; 12% hit the cap"
        },
        {
         "label": "3 monsters",
         "value": 5.77,
         "note": "n=280; median 3.15 s; 29% hit the cap"
        },
        {
         "label": "4 monsters",
         "value": 7.57,
         "note": "n=72 (gremlin gangs, slime splits); median 6.0 s; 39% hit the cap"
        }
       ],
       "unit": "mean seconds per decision"
      }
     },
     {
      "id": "thinking-node-cap",
      "title": "When the search runs out of room",
      "claim": "The search stops when it reaches a fixed number of positions (its node cap). At A20 that happened on 8.7% of moves (13.9% at A0). It hit the cap on 43% of the moves where it drank a potion, against 5% of the moves that played a Strike.",
      "tag": "real game · A0 and A20, shown apart",
      "setting": "Real game, A20, all run-rule versions pooled, runs 28-90; share of fight decisions where the search hit its node cap (cut = true). A0 runs 1-27 shown separately for comparison. · n: 3,579 A20 decisions, 313 hit the cap; A0 runs 1-27: 241 of 1,739",
      "caveat": "Evolve and Juggernaut each come from only 4 runs, and one run (89, which had both) gives about half of their decisions and most of their capped ones. Without it both rates are about 39%, and one Juggernaut run never hit the cap. A potion adds its own targets to the options, and the AI tends to drink one in hard spots, so the 43% is about the spot as much as the potion. These are associations, not causes, and a capped move isn't necessarily a worse move.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "All A20 decisions",
         "value": 8.7,
         "note": "313 of 3,579"
        },
        {
         "label": "All A0 decisions",
         "value": 13.9,
         "note": "241 of 1,739, A0 runs 1-27"
        },
        {
         "label": "Move was a potion",
         "value": 43,
         "note": "91 decisions, 51 runs; mean 9.7 s"
        },
        {
         "label": "Move was Strike",
         "value": 5,
         "note": "about 1,730 decisions"
        }
       ],
       "unit": "% of decisions that hit the node cap"
      }
     },
     {
      "id": "thinking-hardest-moves",
      "title": "The single hardest moves",
      "claim": "Three of the AI's five slowest A20 moves came against Slime Boss on turn 3, though two of them were back-to-back moves in the same turn of one fight. In that turn it held Ascender's Bane, Bash+, a Strike and two Defends and thought for 96 seconds before playing Strike. Its slowest move overall was at A0, against three Red Louses, two still with Curl Up: it thought for 111 seconds and then played a single Strike.",
      "tag": "real game · A0 and A20, shown apart",
      "setting": "Real game, single fight decisions (card rewards excluded); A20 runs 28-90 (all run-rule versions pooled) and A0 runs 1-27 listed separately · n: the 6 slowest of 3,579 A20 decisions and the slowest of 1,739 A0 decisions",
      "caveat": "These are single moves on a shared laptop, so other jobs running at the same time may have added seconds. Two of the five A20 moves come from one turn of one fight. The rows show what was on the board, not why the move took long.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "A20 run 44, Slime Boss 88 HP, turn 3",
         "value": 96.14,
         "note": "hand Bash+, Strike, 2 Defend, Ascender's Bane; hit the cap; played Strike"
        },
        {
         "label": "A20 run 57, Acid Slime (L) + Spike Slime (M)",
         "value": 91.24,
         "note": "hand 2 Slimed, Anger, 2 Strike; Strength 3; Pen Nib + Shuriken; played Strike"
        },
        {
         "label": "A20 run 70, Spike Slime (L) + Acid Slime (L)",
         "value": 78.79,
         "note": "hand 2 Slimed, Anger+, Reckless Charge; Juggernaut 5, Feel No Pain 7; played Slimed"
        },
        {
         "label": "A20 run 44, Slime Boss 79 HP, same turn",
         "value": 76.57,
         "note": "next move of the same turn: Bash+, then a Fire Potion"
        },
        {
         "label": "A20 run 89, Slime Boss 120 HP, turn 3",
         "value": 66.78,
         "note": "Juggernaut 5, Evolve in hand; drank a Swift Potion"
        },
        {
         "label": "A20 run 69, 2 Green Louses + Red Louse",
         "value": 64.19,
         "note": "Curl Up 12 on two louses; Reckless Charge in hand"
        },
        {
         "label": "A0 run 2, 3 Red Louses",
         "value": 110.66,
         "note": "Curl Up 5 and 6; Armaments in hand; hit the cap; played Strike"
        }
       ],
       "unit": "seconds for one decision"
      }
     }
    ]
   },
   {
    "name": "What it picks in the real game",
    "items": [
     {
      "id": "real-picks-a20-favourites",
      "title": "A20: the cards it grabs when offered",
      "claim": "At Ascension 20 the AI takes Juggernaut (6 of 8 offers), Impervious (6 of 9) and Rampage (6 of 10) more often than not. Its most-taken card overall is the common Armaments, picked 25 times out of 46 offers, more than any other card.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20, runs 28-90, all run-rule versions pooled (run-level stat: settings mixed). Cards offered at least 5 times. An offer counts only when the engine could load the card and so the AI could pick it (options list). · n: 554 card rewards (100 skipped), 63 runs; per-card offer counts in notes",
      "caveat": "Most cards at the top have only 5-22 offers, so one or two picks move them a lot. Armaments (46 offers) is the only top card with a large sample. Many other cards were offered 40-60 times but are taken less often (Warcry 6 of 60, Headbutt 6 of 50, Flex 9 of 51). A card's pick rate also depends on what it was offered next to and on the deck at the time. Run-rule versions 1-5 are pooled.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Immolate",
         "value": 80,
         "note": "4 of 5 offers"
        },
        {
         "label": "Juggernaut",
         "value": 75,
         "note": "6 of 8 (2 more offers in run 29 couldn't be picked: card not loaded)"
        },
        {
         "label": "Impervious",
         "value": 67,
         "note": "6 of 9"
        },
        {
         "label": "Rampage",
         "value": 60,
         "note": "6 of 10"
        },
        {
         "label": "Bludgeon",
         "value": 56,
         "note": "5 of 9"
        },
        {
         "label": "Armaments",
         "value": 54,
         "note": "25 of 46"
        },
        {
         "label": "Disarm",
         "value": 53,
         "note": "9 of 17"
        },
        {
         "label": "Spot Weakness",
         "value": 50,
         "note": "11 of 22"
        },
        {
         "label": "Fire Breathing",
         "value": 50,
         "note": "11 of 22"
        },
        {
         "label": "Carnage",
         "value": 50,
         "note": "9 of 18"
        },
        {
         "label": "Blood for Blood",
         "value": 50,
         "note": "5 of 10"
        }
       ],
       "unit": "% picked when offered"
      }
     },
     {
      "id": "real-picks-a20-snubs",
      "title": "A20: the cards it won't touch",
      "claim": "Warcry was the card it was offered most at Ascension 20 (60 times) and it took it only 6 times. Limit Break, Entrench, Sentinel, Dark Embrace and Dual Wield were offered 14-17 times each and never taken. Barricade and Bloodletting got picked once each in 14 offers.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20, runs 28-90, all run-rule versions pooled (run-level stat: settings mixed). Every card offered at least 14 times with a pick rate of 12.5% or less. · n: 554 card rewards, 63 runs; per-card offer counts in notes (offers = times the card was a choosable option)",
      "caveat": "Runs stop at the start of Act 2, so slow combo cards (Barricade, Limit Break, Dark Embrace) have little time to pay off. This measures what this net values over one act, not how good the cards are. Each pick is also made against the other cards in the same reward. Offers count only the times the card could actually be chosen.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Limit Break",
         "value": 0,
         "note": "0 of 17"
        },
        {
         "label": "Entrench",
         "value": 0,
         "note": "0 of 17"
        },
        {
         "label": "Sentinel",
         "value": 0,
         "note": "0 of 15"
        },
        {
         "label": "Dark Embrace",
         "value": 0,
         "note": "0 of 15"
        },
        {
         "label": "Dual Wield",
         "value": 0,
         "note": "0 of 14 (on screen 15 times, once not offered as an option)"
        },
        {
         "label": "Rupture",
         "value": 5,
         "note": "1 of 19"
        },
        {
         "label": "Burning Pact",
         "value": 6,
         "note": "1 of 16"
        },
        {
         "label": "Searing Blow",
         "value": 6,
         "note": "1 of 16"
        },
        {
         "label": "Barricade",
         "value": 7,
         "note": "1 of 14"
        },
        {
         "label": "Bloodletting",
         "value": 7,
         "note": "1 of 14"
        },
        {
         "label": "Body Slam",
         "value": 8,
         "note": "3 of 37"
        },
        {
         "label": "Second Wind",
         "value": 10,
         "note": "2 of 21"
        },
        {
         "label": "Warcry",
         "value": 10,
         "note": "6 of 60"
        },
        {
         "label": "Sword Boomerang",
         "value": 12,
         "note": "5 of 42"
        },
        {
         "label": "Headbutt",
         "value": 12,
         "note": "6 of 50"
        },
        {
         "label": "Infernal Blade",
         "value": 13,
         "note": "3 of 24"
        }
       ],
       "unit": "% picked when offered"
      }
     },
     {
      "id": "real-picks-a0-loves-and-snubs",
      "title": "A0: loved and never picked",
      "claim": "At Ascension 0 Fire Breathing (5 of 7) and Disarm (7 of 10) were its top picks. Body Slam was offered 23 times and never taken, and Dark Embrace (11 offers) and Sever Soul (10) were also never taken.",
      "tag": "real game · A0",
      "setting": "Real game, A0, runs 1-27, run rules 1. Top: cards offered at least 6 times; bottom: cards offered at least 9 times and never picked. · n: 319 card rewards, 27 runs; per-card offer counts in notes",
      "caveat": "The A0 counts are small (6-23 offers per card). Some A0 runs went into Act 2 (16 of the 27 runs had card rewards after floor 17), so the decks and the time horizon differ from A20. A few offered cards were never among the bot's options (Battle Trance 7 times, Juggernaut 6, Dual Wield 6), so for those cards a skip was forced. None of them is in these rows.",
      "checked": "confirmed",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Fire Breathing",
         "value": 71,
         "note": "5 of 7"
        },
        {
         "label": "Disarm",
         "value": 70,
         "note": "7 of 10"
        },
        {
         "label": "Demon Form",
         "value": 67,
         "note": "4 of 6"
        },
        {
         "label": "Shockwave",
         "value": 67,
         "note": "4 of 6"
        },
        {
         "label": "Metallicize",
         "value": 62,
         "note": "5 of 8"
        },
        {
         "label": "Rampage",
         "value": 58,
         "note": "7 of 12"
        },
        {
         "label": "Body Slam",
         "value": 0,
         "note": "0 of 23"
        },
        {
         "label": "Dark Embrace",
         "value": 0,
         "note": "0 of 11"
        },
        {
         "label": "Sever Soul",
         "value": 0,
         "note": "0 of 10"
        },
        {
         "label": "Sentinel",
         "value": 0,
         "note": "0 of 9"
        },
        {
         "label": "Searing Blow",
         "value": 0,
         "note": "0 of 9"
        }
       ],
       "unit": "% picked when offered"
      }
     },
     {
      "id": "real-picks-skip-rate",
      "title": "How often it skips the whole card reward",
      "claim": "About one card reward in five, the AI takes nothing: it rates 'skip' above every card offered. At Ascension 0 it got pickier late in the act (about a third skipped on floors 13-17); at Ascension 20 the skip rate barely moves with the floor.",
      "tag": "real game · A0 and A20, shown apart",
      "setting": "Real game, card-reward screens. A0: runs 1-27 (run rules 1). A20: runs 28-90, all run-rule versions and fight-guard settings pooled (picks are run-level, so treat the pooled A20 row as a mix of settings). · n: A0: 319 rewards in 27 runs; A20: 554 rewards in 63 runs",
      "caveat": "The AI always took the option it scored highest (873 of 873 rewards), so a skip means the net scored the deck without the card higher. A0 floors 18+ come from the 16 of 27 A0 runs that reached Act 2, with only 45 rewards in all; no A20 run got past floor 17. By setting within A20, the skip rate ranges from 10% to 33%, but the groups with the extreme rates are tiny (10-21 rewards each). The two large groups, rules 2 (148 rewards) and rules 5 with the fight guard (298 rewards), sit at 16% and 18%, so treat the spread as noise.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "A0, all floors",
         "value": 19,
         "note": "62 of 319"
        },
        {
         "label": "A0, floors 1-6",
         "value": 16,
         "note": "20 of 128"
        },
        {
         "label": "A0, floors 7-12",
         "value": 15,
         "note": "13 of 86"
        },
        {
         "label": "A0, floors 13-17",
         "value": 32,
         "note": "19 of 60"
        },
        {
         "label": "A0, floors 18+",
         "value": 22,
         "note": "10 of 45"
        },
        {
         "label": "A20, all floors",
         "value": 18,
         "note": "100 of 554"
        },
        {
         "label": "A20, floors 1-6",
         "value": 17,
         "note": "46 of 274"
        },
        {
         "label": "A20, floors 7-12",
         "value": 19,
         "note": "33 of 174"
        },
        {
         "label": "A20, floors 13-17",
         "value": 20,
         "note": "21 of 106"
        }
       ],
       "unit": "% of card rewards skipped"
      }
     },
     {
      "id": "real-picks-rarity",
      "title": "It doesn't chase rares",
      "claim": "Rare cards don't excite it: at Ascension 20 it took 29% of the rares it could pick, against 27% of commons and 27% of uncommons. At Ascension 0, uncommons were its favourite rarity (31%), and rares were no more popular than commons (26% against 25%).",
      "tag": "real game · A0 and A20, shown apart",
      "setting": "Real game, Ironclad card rewards from floor 1 on (Neow's floor-0 colorless choice left out). Counts only the cards the bot could take: 28 offered cards the engine doesn't model, such as Battle Trance and Reaper, are left out. Rarity comes from the game's own card data in states.jsonl. A0: runs 1-27 (run rules 1). A20: runs 28-90, all run-rule versions and both fight-guard settings pooled. · n: A0: 929 pickable cards in 314 rewards; A20: 1,641 pickable cards in 548 rewards",
      "caveat": "It can take at most one card per reward, so these rates are capped by its skip rate (about 18-20%) and by the other cards in the same reward. Rare samples are small (91 and 152 cards), and a few points' difference is within noise. The A0 uncommon lead is about 2 standard errors. Cards the engine doesn't model were never pickable and are left out. Counting them as offered would put A0 rares at 24% (24 of 100) and A0 uncommons at 30%. The A20 figures pool run-rule versions 1-5.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "A0 common",
         "value": 25,
         "note": "132 of 531"
        },
        {
         "label": "A0 uncommon",
         "value": 31,
         "note": "96 of 307"
        },
        {
         "label": "A0 rare",
         "value": 26,
         "note": "24 of 91"
        },
        {
         "label": "A20 common",
         "value": 27,
         "note": "245 of 896"
        },
        {
         "label": "A20 uncommon",
         "value": 27,
         "note": "160 of 593"
        },
        {
         "label": "A20 rare",
         "value": 29,
         "note": "44 of 152"
        }
       ],
       "unit": "% of offered cards picked"
      }
     },
     {
      "id": "real-picks-boss-deck",
      "title": "A20: the deck at the Act 1 boss, boss by boss",
      "claim": "Which boss a run met matters more than the cards. Hexaghost was beaten 4 times in 17 fights; Slime Boss and The Guardian together were beaten 26 times in 34. Most of the raw gap between cards comes from which boss each deck met. Wild Strike decks won only 3 of 9 boss fights, but 5 of those 9 were Hexaghost fights, all lost. Against Slime Boss or The Guardian, Wild Strike decks won 3 of 4, close to the 23 of 30 for the other decks. Fire Breathing stands out against both kinds of boss. Fire Breathing decks beat Hexaghost 2 times in 3, against 2 in 14 for the other decks. They also won all 5 of their fights against Slime Boss or The Guardian. Clash (10 of 11), Spot Weakness (8 of 9) and Pommel Strike (11 of 13) decks also beat Slime Boss and The Guardian more often than decks without those cards. Spot Weakness decks met Hexaghost only once, and Pommel Strike decks twice, so their good overall records partly reflect easier bosses.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20, runs 28-90. All run-rule versions and fight-guard settings are pooled. Only runs that reached the Act 1 boss (floor 16) are counted: 51 runs, one boss fight each. The deck is the run's deck during the boss fight, read from the floor-16 combat states, so a card from the boss's own reward isn't counted. Upgraded copies count as the base card. A card created during the fight, such as a random attack, doesn't count. 'Slime Boss/Guardian' pools the fights against Slime Boss (20) and The Guardian (14). · n: 51 A20 boss fights, 30 won: Hexaghost 17 (4 won), Slime Boss 20 (15 won), The Guardian 14 (11 won). Card groups are 3-13 fights.",
      "caveat": "This shows correlation, not cause, and the groups are tiny. Most of these rows rest on 3-13 fights, and the Hexaghost rows rest on 3-5 fights. These cards were picked as the high and low ends among about 30 cards found in 5 or more boss decks, so a few of them land high or low by chance. Some gaps that look big in the pooled numbers vanish once the bosses are split. Armaments decks beat Slime Boss and The Guardian 11 times in 14, against 15 in 20 without it. Shrug It Off decks did so 9 times in 12, against 17 in 22. A plausible reason Fire Breathing helps against Hexaghost is that it deals damage whenever a Status card is drawn, and Hexaghost shuffles Burns into the deck. These records don't prove that link. The pooled settings changed the route through the map over time (rules 1-5, with and without the fight guard), so the decks and HP that reached the boss differ between settings too. The deck reading from the combat piles gives the same 9 Wild Strike decks as the master deck. A count of 10 appears only if a Wild Strike created during the fight is counted.",
      "checked": "rewritten after the repeat audit, then confirmed",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Slime Boss/Guardian, any deck",
         "value": 76,
         "note": "26 of 34"
        },
        {
         "label": "Hexaghost, any deck",
         "value": 24,
         "note": "4 of 17"
        },
        {
         "label": "Fire Breathing vs Hexaghost",
         "value": 67,
         "note": "2 of 3 (other decks 2 of 14)"
        },
        {
         "label": "Fire Breathing vs Slime Boss/Guardian",
         "value": 100,
         "note": "5 of 5 (other decks 21 of 29)"
        },
        {
         "label": "Clash vs Slime Boss/Guardian",
         "value": 91,
         "note": "10 of 11 (other decks 16 of 23); vs Hexaghost 2 of 5"
        },
        {
         "label": "Spot Weakness vs Slime Boss/Guardian",
         "value": 89,
         "note": "8 of 9 (other decks 18 of 25); met Hexaghost once and lost"
        },
        {
         "label": "Pommel Strike vs Slime Boss/Guardian",
         "value": 85,
         "note": "11 of 13 (other decks 15 of 21); vs Hexaghost 0 of 2"
        },
        {
         "label": "Wild Strike vs Slime Boss/Guardian",
         "value": 75,
         "note": "3 of 4 (other decks 23 of 30): no real gap"
        },
        {
         "label": "Wild Strike vs Hexaghost",
         "value": 0,
         "note": "0 of 5 (other decks 4 of 12)"
        }
       ],
       "unit": "% of A20 boss fights won, by boss and by a card in the deck at the boss"
      }
     }
    ]
   },
   {
    "name": "What hurts",
    "items": [
     {
      "id": "trouble-killers-a20",
      "title": "What ended the A20 runs",
      "claim": "Of the 63 Ascension 20 runs, 33 died in Act 1. Hexaghost alone ended 13 of them: 13 of the 17 runs that reached it. Lagavulin was the deadliest elite: it ended 6 of the 17 runs that fought it (18 fights), against 2 deaths in 21 Gremlin Nob fights.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20 runs 28-90 (run rules 1-5, fight guard 0 and 1 pooled: rules 1-4 and rules 5 without guard = 30 runs, rules 5 with guard = 33 runs). Counted per run: the fight the run died in. · n: 63 runs, 33 deaths",
      "caveat": "This is run-level data pooled across all five run-rule versions and both fight-guard settings. The path rules change which fights a run takes and how much HP it brings to them. The three hallway deaths came from runs that started those fights with 10-12 HP, not from strong monsters. The counts per monster are small (one to 21 fights each), so the elite comparison is a hint, not a measured rate.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Hexaghost",
         "value": 13,
         "note": "reached by 17 runs"
        },
        {
         "label": "Lagavulin",
         "value": 6,
         "note": "fought 18 times in 17 runs"
        },
        {
         "label": "Slime Boss",
         "value": 5,
         "note": "met 20 times"
        },
        {
         "label": "The Guardian",
         "value": 3,
         "note": "met 14 times"
        },
        {
         "label": "Gremlin Nob",
         "value": 2,
         "note": "met 21 times"
        },
        {
         "label": "3 Sentries",
         "value": 1,
         "note": "met 15 times"
        },
        {
         "label": "Spike Slime (L)",
         "value": 1,
         "note": "met 22 times; the run arrived with 10 HP"
        },
        {
         "label": "Acid Slime (L)",
         "value": 1,
         "note": "met 14 times; the run arrived with 12 HP"
        },
        {
         "label": "Looter",
         "value": 1,
         "note": "met 38 times; the run arrived with 11 HP"
        }
       ],
       "unit": "runs ended"
      }
     },
     {
      "id": "trouble-encounters-a20",
      "title": "HP lost per encounter at A20",
      "claim": "In the A20 hallways, the Gremlin Gang cost about 18 HP a fight on average, twice a lone Jaw Worm's 8.8, though a few bad fights pull that average up (median 12). A Cultist cost only 3.4 HP: those fights end fast, before Ritual's Strength has stacked much.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20 runs 28-90, all run-rule versions pooled. HP lost = HP at fight start minus HP at fight end, before end-of-fight heals such as Burning Blood (heals during the fight count, so a few fights show a gain). Every encounter met at least 14 times; mixed groups of lice, gremlins and sentries are counted as one encounter. · n: 582 A20 fights in 63 runs. The n for each encounter is in its note.",
      "caveat": "A fight that ended in death counts only the HP that was left, so averages for deadly fights are capped by the HP the bot brought in. 13 of the 17 Hexaghost fights and 6 of the 18 Lagavulin fights were deaths. Decks differ from fight to fight. Pooling rule versions is fine for how a fight goes, but the mix of decks differs between versions (for example, Hexaghost averaged 49.5 under rules 1 and about 63 later). Heals during a fight (potions, relics) count, so a few hallway fights show a small gain.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Gremlin Gang",
         "value": 18.1,
         "note": "n=20, median 12"
        },
        {
         "label": "Acid Slime (L)",
         "value": 16.4,
         "note": "n=14"
        },
        {
         "label": "Acid Slime (M) + Spike Slime (S)",
         "value": 10.5,
         "note": "n=23"
        },
        {
         "label": "Red Slaver",
         "value": 10.3,
         "note": "n=25"
        },
        {
         "label": "Jaw Worm",
         "value": 8.8,
         "note": "n=49"
        },
        {
         "label": "Spike Slime (L)",
         "value": 8,
         "note": "n=22"
        },
        {
         "label": "Blue Slaver",
         "value": 8,
         "note": "n=34"
        },
        {
         "label": "3 lice",
         "value": 7.7,
         "note": "n=31"
        },
        {
         "label": "Acid Slime (S) + Spike Slime (M)",
         "value": 5.4,
         "note": "n=28"
        },
        {
         "label": "2 Fungi Beasts",
         "value": 5,
         "note": "n=34"
        },
        {
         "label": "Looter",
         "value": 4.6,
         "note": "n=38"
        },
        {
         "label": "2 lice",
         "value": 4.5,
         "note": "n=37"
        },
        {
         "label": "Cultist",
         "value": 3.4,
         "note": "n=52, median 1.5"
        }
       ],
       "unit": "mean HP lost per fight"
      }
     },
     {
      "id": "trouble-a0-vs-a20",
      "title": "Same monster, two Ascensions",
      "claim": "Every elite cost more HP at Ascension 20 than at A0. Gremlin Nob went from 11 to 32 HP, but its A0 figure rests on only 3 fights. Lagavulin went from 24.9 to 32.1 HP and won 9 of 9 at A0, but lost 6 of its 18 fights at A20.",
      "tag": "real game · A0 and A20, shown apart",
      "setting": "Real game, Act 1 elite and boss fights (Gremlin Gang left out: 1 fight). A0 = runs 1-27 (run rules 1). A20 = runs 28-90, all run-rule versions pooled. HP lost = HP at fight start minus HP at fight end, before end-of-fight heals; a lost fight counts all the HP the bot had left. · n: A0 / A20 fights: Hexaghost 3/17, The Guardian 14/14, Slime Boss 7/20, 3 Sentries 12/15, Lagavulin 9/18, Gremlin Nob 3/21. Fights lost A0 / A20: Hexaghost 0/13, The Guardian 2/3, Slime Boss 0/5, 3 Sentries 0/1, Lagavulin 0/6, Gremlin Nob 0/2",
      "caveat": "The two settings are not one experiment. They use different run rules and different net versions, and at A20 the bot starts with less HP and gets fewer heals. Read each pair as \"how much harder it got\", not as an exact Ascension effect. A lost fight counts all the HP the bot had left, so A20 cells with many losses (Hexaghost: 13 of 17) are capped by the starting HP and understate how hard the fight was. Gremlin Nob A0 and Hexaghost A0 hold only 3 fights each.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Gremlin Nob A0",
         "value": 11.3,
         "note": "n=3, 0 lost"
        },
        {
         "label": "Gremlin Nob A20",
         "value": 31.8,
         "note": "n=21, 2 lost"
        },
        {
         "label": "Lagavulin A0",
         "value": 24.9,
         "note": "n=9, 0 lost"
        },
        {
         "label": "Lagavulin A20",
         "value": 32.1,
         "note": "n=18, 6 lost"
        },
        {
         "label": "3 Sentries A0",
         "value": 30.3,
         "note": "n=12, 0 lost"
        },
        {
         "label": "3 Sentries A20",
         "value": 36.4,
         "note": "n=15, 1 lost"
        }
       ],
       "unit": "mean HP lost per fight"
      }
     }
    ]
   },
   {
    "name": "How it plays",
    "items": [
     {
      "id": "plays-most-played",
      "title": "Strike and Defend are six in ten of all cards played",
      "claim": "At Ascension 20 the bot played 7,792 cards, and 36% of them were plain Strikes and 25% plain Defends. The first card it picked up from a reward to make the top five is Anger. At Ascension 0 the picture is almost the same: Strike 35%, Defend 23%, then Anger at 5%.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20 (runs 28-90, all run-rule versions pooled), 582 fights, 2,922 turns. A0 (runs 1-27) is reported separately in the claim: 3,663 card plays. · n: 7,792 card plays at A20; 3,663 at A0",
      "caveat": "The record holds re-plans, not single clicks. Plays are rebuilt from each decision's planned line, cut where the next re-plan of the same turn starts. The last plan of a fight can list cards after the killing blow, so the counts can be a little high. Fights the fallback rule finished count only up to the hand-over. Upgraded cards are counted separately (Bash and Bash+ together would be 6.5% at A20 and 5.5% at A0, ahead of Anger).",
      "checked": "confirmed",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Strike",
         "value": 36.2,
         "note": "2,824 plays"
        },
        {
         "label": "Defend",
         "value": 24.8,
         "note": "1,936"
        },
        {
         "label": "Bash+",
         "value": 3.6,
         "note": "284"
        },
        {
         "label": "Bash",
         "value": 2.9,
         "note": "223"
        },
        {
         "label": "Anger",
         "value": 2.7,
         "note": "208"
        },
        {
         "label": "Armaments",
         "value": 1.6,
         "note": "121"
        },
        {
         "label": "Iron Wave",
         "value": 1.5,
         "note": "120"
        },
        {
         "label": "Shrug It Off",
         "value": 1.4,
         "note": "106"
        },
        {
         "label": "Pommel Strike",
         "value": 1.3,
         "note": "98"
        },
        {
         "label": "Defend+",
         "value": 1.2,
         "note": "95"
        },
        {
         "label": "Slimed",
         "value": 1,
         "note": "79 (it pays 1 energy to exhaust the status card)"
        }
       ],
       "unit": "% of all card plays (A20)"
      }
     },
     {
      "id": "plays-hand-rate",
      "title": "Whirlwind always gets played; Evolve rarely does",
      "claim": "When a card sits in the opening hand of a turn, how often does the bot play it that turn? Whirlwind gets played 92% of the time and Flex 88%. Evolve is played only 21% of the time, Fire Breathing about a third of the time, and even Bash only 44%. Strike (74%) gets played far more often than Defend (57%). At A0 the same pattern holds: Evolve 14%, Demon Form and Fire Breathing 26%.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20 (runs 28-90, all run-rule versions pooled), 2,922 turns. Only cards in the turn's opening hand at least 20 times are shown. · n: 2,922 turns; each row gives played/held",
      "caveat": "A turn counts as played if the card was played at least once. Copies drawn mid-turn are not counted. A power that was played leaves the deck, so its later turns never count against it. Plays are rebuilt from planned lines (see plays-most-played). Upgraded copies are separate rows (Bash+ is played 55% of the time).",
      "checked": "confirmed",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Whirlwind",
         "value": 92,
         "note": "35 of 38 turns"
        },
        {
         "label": "Flex",
         "value": 88,
         "note": "71/81"
        },
        {
         "label": "Iron Wave+",
         "value": 88,
         "note": "21/24"
        },
        {
         "label": "Anger",
         "value": 84,
         "note": "173/206"
        },
        {
         "label": "Ghostly Armor",
         "value": 82,
         "note": "45/55"
        },
        {
         "label": "Strike",
         "value": 74,
         "note": "1,921/2,593"
        },
        {
         "label": "Defend",
         "value": 57,
         "note": "1,335/2,360"
        },
        {
         "label": "Bash",
         "value": 44,
         "note": "223/504"
        },
        {
         "label": "Heavy Blade",
         "value": 42,
         "note": "46/110"
        },
        {
         "label": "Fire Breathing",
         "value": 32,
         "note": "20/63"
        },
        {
         "label": "Evolve",
         "value": 21,
         "note": "5/24"
        }
       ],
       "unit": "% of turns held in the opening hand that it was played that turn"
      }
     },
     {
      "id": "plays-bash-turn1",
      "title": "Bash on turn 1? It depends who is across the table",
      "claim": "With Bash in the opening hand at A20, the bot played it on turn 1 in 113 of 207 fights and played it as its first card 70 times. It Bashed every Cultist (18 of 18), every Gremlin Nob (7 of 7) and every Slime Boss (6 of 6). It mostly held Bash against lice (2 of 11 against a Green and Red Louse pair, 0 of 6 against a lone Red Louse), against Lagavulin (1 of 7) and against an Acid Slime (M) with a Spike Slime (S) (2 of 10). Lice curl up and Lagavulin starts asleep, which may be part of why, but the data doesn't show the reason.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20 (runs 28-90, all run-rule versions pooled): fights where Bash or Bash+ was in the turn-1 hand. Rows are all monster groups with at least 6 such fights (16 groups). A group is the set of monster names in the first turn-1 view. · n: 207 fights with Bash in the opening hand (A20, 62 runs)",
      "caveat": "Many groups have small counts (6 to 22 fights), so each row shows what happened in these runs, not a fixed rule. Holding Bash on turn 1 doesn't mean it was never played later. \"First card\" skips potions: counting a potion used first as the lead gives 66 instead of 70. At A0 (runs 1-27), Bash was played on turn 1 in 59 of 94 fights and was the first card in 33.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Cultist",
         "value": 100,
         "note": "18 of 18"
        },
        {
         "label": "Spike Slime (L)",
         "value": 100,
         "note": "8 of 8"
        },
        {
         "label": "Gremlin Nob",
         "value": 100,
         "note": "7 of 7"
        },
        {
         "label": "Slime Boss",
         "value": 100,
         "note": "6 of 6"
        },
        {
         "label": "Acid Slime (L)",
         "value": 83,
         "note": "5 of 6"
        },
        {
         "label": "Hexaghost",
         "value": 71,
         "note": "5 of 7"
        },
        {
         "label": "Looter",
         "value": 71,
         "note": "10 of 14"
        },
        {
         "label": "Blue Slaver",
         "value": 67,
         "note": "4 of 6"
        },
        {
         "label": "Jaw Worm",
         "value": 50,
         "note": "11 of 22"
        },
        {
         "label": "Acid Slime (S) + Spike Slime (M)",
         "value": 50,
         "note": "7 of 14"
        },
        {
         "label": "Red Slaver",
         "value": 38,
         "note": "3 of 8"
        },
        {
         "label": "Fungi Beast",
         "value": 31,
         "note": "4 of 13"
        },
        {
         "label": "Acid Slime (M) + Spike Slime (S)",
         "value": 20,
         "note": "2 of 10"
        },
        {
         "label": "Green + Red Louse",
         "value": 18,
         "note": "2 of 11"
        },
        {
         "label": "Lagavulin",
         "value": 14,
         "note": "1 of 7"
        },
        {
         "label": "Red Louse",
         "value": 0,
         "note": "0 of 6"
        }
       ],
       "unit": "% of fights where Bash was played on turn 1"
      }
     },
     {
      "id": "plays-nob-no-defend",
      "title": "It rarely Defends against Gremlin Nob",
      "claim": "Gremlin Nob's Enrage gives it Strength every time you play a Skill. The bot plays its Defends sparingly there: in 74 Nob turns with a Defend in hand it played one on only 17 (23%), against 154 of 216 (71%) at the other elites (Lagavulin and Sentries). Across all Nob turns it played 23 Defends to 101 Strikes, the lowest Defend-to-Strike ratio of any enemy group. It won 19 of its 21 Nob fights. The other end of the scale is Acid Slime (L) and The Guardian, where it blocked more than it struck.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20 (runs 28-90, all run-rule versions pooled). Rows are every single-enemy group (one monster name in view) with at least 40 Strike+Defend plays. Multi-enemy groups are left out of the rows; the \"lowest of any enemy group\" statement was checked against all 29 qualifying groups, mixed ones included. The Gremlin Gang (1.20) is left out because a single 84-turn fight dominates it (one 84-turn fight, run 83). · n: 21 Gremlin Nob fights (90 turns); 2,922 turns in all",
      "caveat": "Defend and Defend+ are counted together, and so are Strike and Strike+. A group is all monsters in view on that turn. The decision log has no line per card played. The plays were rebuilt from each search's planned line, up to where the next search of the same turn starts. Whether the bot held its Skills because of Enrage or for another reason (Nob fights are short races) can't be read from these numbers. At A0 there were only 3 Nob fights (2 Defends played in 8 turns with one in hand).",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Acid Slime (L)",
         "value": 1.43,
         "note": "50 Defends / 35 Strikes"
        },
        {
         "label": "The Guardian",
         "value": 1.1,
         "note": "117 / 106"
        },
        {
         "label": "Looter",
         "value": 0.98,
         "note": "95 / 97"
        },
        {
         "label": "Red Slaver",
         "value": 0.97,
         "note": "74 / 76"
        },
        {
         "label": "Sentry",
         "value": 0.96,
         "note": "106 / 110"
        },
        {
         "label": "Blue Slaver",
         "value": 0.93,
         "note": "98 / 105"
        },
        {
         "label": "Lagavulin",
         "value": 0.89,
         "note": "112 / 126"
        },
        {
         "label": "Acid Slime (M)",
         "value": 0.83,
         "note": "24 / 29"
        },
        {
         "label": "Hexaghost",
         "value": 0.82,
         "note": "88 / 107"
        },
        {
         "label": "Green Louse",
         "value": 0.72,
         "note": "31 / 43"
        },
        {
         "label": "Fungi Beast",
         "value": 0.61,
         "note": "91 / 148"
        },
        {
         "label": "Jaw Worm",
         "value": 0.61,
         "note": "148 / 242"
        },
        {
         "label": "Red Louse",
         "value": 0.53,
         "note": "35 / 66"
        },
        {
         "label": "Slime Boss",
         "value": 0.48,
         "note": "27 / 56"
        },
        {
         "label": "Spike Slime (M)",
         "value": 0.42,
         "note": "33 / 78"
        },
        {
         "label": "Cultist",
         "value": 0.36,
         "note": "89 / 248"
        },
        {
         "label": "Spike Slime (L)",
         "value": 0.29,
         "note": "17 / 58"
        },
        {
         "label": "Gremlin Nob",
         "value": 0.23,
         "note": "23 / 101"
        }
       ],
       "unit": "Defends played per Strike played"
      }
     },
     {
      "id": "plays-potions",
      "title": "Potions go down early, often on turn 1",
      "claim": "At A20 the bot drank 242 potions, and 176 of them (73%) on turn 1 of a fight. Its HP at the time was usually high: the median was 82% of max HP, and only 17 potions were drunk below half HP. It drank more potions per fight at bosses (25 in 51 fights) and elites (31 in 54) than in hallway fights (186 in 477). Energy, Weak and Fear Potions top the list. Fairy in a Bottle, which works on its own, sat in the belt for 120 turns.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20 (runs 28-90, all run-rule versions pooled), 582 fights. At A0 (runs 1-27, 332 fights), 109 potions were drunk, 78 of them on turn 1, at a median of 96% HP. · n: 242 potion uses at A20 (each a planned Potion action confirmed by that potion leaving the belt)",
      "caveat": "The potion's name is read from the slot in the bot's view of its belt. A use counts when a Potion action in a planned line matches a potion that is gone by the bot's next decision; 8 planned uses with no matching belt loss are left out. Turn of use at A20: 176 on turn 1, 50 on turn 2, 11 on turn 3, 5 later. A turn-1 potion isn't necessarily a waste: Weak, Fear and setup potions do the most when used early. The boss and elite numbers are small (51 and 54 fights), and the per-fight difference is an association: it doesn't show that the bot saves potions for those fights.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Energy Potion",
         "value": 15
        },
        {
         "label": "Weak Potion",
         "value": 14
        },
        {
         "label": "Fear Potion",
         "value": 14
        },
        {
         "label": "Power Potion",
         "value": 13
        },
        {
         "label": "Explosive Potion",
         "value": 12
        },
        {
         "label": "Flex Potion",
         "value": 11
        },
        {
         "label": "Skill Potion",
         "value": 11
        },
        {
         "label": "Dexterity Potion",
         "value": 11
        },
        {
         "label": "Block Potion",
         "value": 9
        },
        {
         "label": "Fire Potion",
         "value": 9
        },
        {
         "label": "Swift Potion",
         "value": 9
        },
        {
         "label": "Liquid Memories",
         "value": 8
        }
       ],
       "unit": "times drunk"
      }
     },
     {
      "id": "run-level-empty-belt",
      "title": "Never dies with a potion",
      "claim": "Whenever the engine played a losing fight to the end, its potion belt was empty when the run died: 33 of 33 deaths at Ascension 20 and 2 of 2 at Ascension 0 in Act 1. The third A0 Act 1 death (run 16, a boss fight handed to the fallback rule partway through) also had an empty belt. The Act 2 fights at A0 were played by a fallback rule that never drinks potions, and 13 of those 16 deaths still had potions unused.",
      "tag": "real game · A0 and A20, shown apart",
      "setting": "Real game. Potions held at the run's last state (the GAME_OVER screen for deaths, the Act 2 map for stops). Rows: A20 deaths (all run-rule versions, runs 28-90); A0 Act 1 deaths (runs 8, 16, 26; run 16's boss fight was finished by the fallback rule); A0 Act 2 deaths (runs 1-20, fallback rule); A20 runs that beat the boss and stopped at Act 2 (all run-rule versions). Runs 3, 5 and 21 (left early or restarted) and the A0 boss-beating stops (runs 22-27) are not in any row. · n: 33 + 3 + 16 deaths, and 30 boss-beating A20 runs",
      "caveat": "This shows the engine had used up its potions before dying, not that drinking them earlier would have saved the run. The A0 Act 1 row has only 3 deaths, and one of them (run 16) was finished by the fallback rule. A20 pools run-rule versions 1-5 and fight guard 0/1.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "A20 deaths (engine)",
         "value": 0,
         "note": "0 of 33"
        },
        {
         "label": "A0 Act 1 deaths",
         "value": 0,
         "note": "0 of 3 (run 16's boss fight was finished by the fallback rule)"
        },
        {
         "label": "A0 Act 2 deaths (fallback rule)",
         "value": 81,
         "note": "13 of 16, 25 potions left undrunk"
        },
        {
         "label": "A20 runs that beat the boss",
         "value": 47,
         "note": "14 of 30 still held a potion when they stopped"
        }
       ],
       "unit": "% of runs ending with at least one unused potion"
      }
     },
     {
      "id": "plays-energy-left",
      "title": "Ending the turn with energy and a playable card",
      "claim": "One 84-turn gremlin standoff (run 83, floor 5) is set aside here because it alone gave a quarter of the cases. Without it, the bot at A20 ended 8.9% of its turns with energy left over, and 5.3% with both energy and a card it could afford to play. The leftover card was usually a Strike. Without that fight Havoc almost never shows up (1 case). The rate depends a lot on the enemy. With The Guardian or a lone Acid Slime (L) on the board it was about 17%. With Jaw Worm, Cultist or Hexaghost it was close to 0. A0 is almost the same once its one long stall (run 18, floor 2, a lone Acid Slime (S)) is set aside: 8.8% and 5.2%. With that fight counted, both levels sit at 10.3% energy left and 6.8-6.9% energy plus an affordable card.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20 (runs 28-90, all run-rule versions pooled). Turn ends come from the game's own states: the last state of a turn before the next turn starts on the same floor. Fights the fallback rule finished are left out, and so is the run 83 floor 5 fight against Mad Gremlin + Shield Gremlin. Each row is the group of monsters still standing at that turn end. The A0 rates (runs 1-27, with and without the run 18 floor 2 fight) are given only in the text, never on the same chart. · n: A20: 2,254 turn ends in 568 fights, with 200 ending with energy left and 120 with energy and an affordable card. Counting run 83 floor 5 gives 2,337 turn ends, 241 and 161. A0: 982 turn ends in 265 fights, with 86 and 51. Counting run 18 floor 2 gives 1,009, 104 and 69.",
      "caveat": "Affordable means the game marked the card as playable and its cost was no more than the energy left. Status cards such as Slimed count (10 cases at A20). The last turn of each fight isn't counted. Holding a card can be the right play, for example to avoid triggering The Guardian's Mode Shift or to keep an Acid Slime (L) above its split threshold. These numbers don't say whether it was, and an enemy's high rate doesn't show that the enemy caused it. Most rows have only 5-27 cases, and the Slaver rate comes mostly from one fight. The A0 rate with run 18 counted is 6.8% or 6.9%, depending on how turn pairs split by a non-combat state are handled.",
      "checked": "rewritten after the repeat audit, then confirmed",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Acid Slime (L)",
         "value": 17.6,
         "note": "12 of 68 turn ends, 19 fights, at most 3 from one fight"
        },
        {
         "label": "The Guardian",
         "value": 17.4,
         "note": "27 of 155, 14 fights, at most 4 from one fight"
        },
        {
         "label": "Gremlin Nob",
         "value": 10.1,
         "note": "7 of 69, 21 fights"
        },
        {
         "label": "Lagavulin",
         "value": 8,
         "note": "10 of 125, 17 fights"
        },
        {
         "label": "Slime Boss",
         "value": 6.4,
         "note": "5 of 78, 20 fights"
        },
        {
         "label": "Acid Slime (M)",
         "value": 6.2,
         "note": "7 of 113, 43 fights"
        },
        {
         "label": "Sentry",
         "value": 5.3,
         "note": "7 of 131, 15 fights"
        },
        {
         "label": "Slaver",
         "value": 5.1,
         "note": "10 of 196, 66 fights; 8 of the 10 from one fight (run 56, floor 14)"
        },
        {
         "label": "Fungi Beast",
         "value": 4.7,
         "note": "6 of 127, 50 fights"
        },
        {
         "label": "Louse",
         "value": 2.7,
         "note": "5 of 182, 70 fights"
        },
        {
         "label": "Hexaghost",
         "value": 0.7,
         "note": "1 of 138, 17 fights"
        },
        {
         "label": "Jaw Worm",
         "value": 0,
         "note": "0 of 161, 54 fights"
        },
        {
         "label": "Cultist",
         "value": 0,
         "note": "0 of 130, 56 fights"
        },
        {
         "label": "All enemies (run 83 floor 5 set aside)",
         "value": 5.3,
         "note": "120 of 2,254; 6.9% (161 of 2,337) with that fight counted"
        }
       ],
       "unit": "% of A20 turn ends with energy left and an affordable playable card"
      }
     }
    ]
   },
   {
    "name": "Records",
    "items": [
     {
      "id": "records-longest-fight",
      "title": "The longest fights: an 84-turn gremlin standoff",
      "claim": "The longest real-game fight lasted 84 turns. In A20 run 83 (floor 5), a Shield Gremlin with 4 HP shielded the remaining Mad Gremlin, giving it 11 Block every turn, for about 69 turns (turns 14 to 82). On 67 of those turns the net struck the shielded Mad Gremlin rather than the 4-HP Shield Gremlin. The two strikes scored almost the same (1.51 vs 1.49). Its HP drained from 35 to 15 before it finally killed the Shield Gremlin, and it won on 8 HP. The A0 record has a different cause. In run 18, floor 2, a Small Acid Slime sat at 4 HP for about 23 turns while the net played Defend, Defend, End. Every option scored exactly the same (2.01), so to the search killing the slime looked no better than waiting.",
      "tag": "real game · A0 and A20, shown apart",
      "setting": "Real game, Act 1 fights (floors 1-16). A20: runs 28-90, run-rule and fight-guard versions pooled (fight-level stat), 582 fights. A0: runs 1-27, 272 Act 1 fights. Turns come from the game's turn counter in states.jsonl. · n: A20 582 fights, A0 272 fights; the median fight lasts 4 turns at both ascensions",
      "caveat": "These are single records, not trends. The two long stalls come from the search seeing no difference between options (A0: every option scored 2.01) or almost none (A20 run 83: 1.51 vs 1.49), not from the monsters. A0 and A20 rows are listed separately and never averaged together. Rows tied at 15 turns are all shown.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "A20 run 83 F5: 2 Mad Gremlins, Shield Gremlin, Sneaky Gremlin",
         "value": 84,
         "note": "won, HP 60 to 8"
        },
        {
         "label": "A20 run 56 F14: Med. Spike Slime + Blue Slaver",
         "value": 18,
         "note": "won, HP 75 to 5 (Blue Slaver at 6 HP for turns 7-18)"
        },
        {
         "label": "A20 run 50 F6: 3 Sentries",
         "value": 17,
         "note": "won, HP 67 to 19"
        },
        {
         "label": "A20 run 36 F5: Large Acid Slime",
         "value": 16,
         "note": "won, HP 70 to 41"
        },
        {
         "label": "A20 run 67 F16: The Guardian",
         "value": 16,
         "note": "won, HP 62 to 30"
        },
        {
         "label": "A20 run 28 F16: The Guardian",
         "value": 15,
         "note": "won, HP 87 to 16"
        },
        {
         "label": "A20 run 52 F5: 2 Fat Gremlins, Sneaky Gremlin, Gremlin Wizard",
         "value": 15,
         "note": "won, HP 79 to 22"
        },
        {
         "label": "A0 run 18 F2: Small Acid Slime + Med. Spike Slime",
         "value": 28,
         "note": "won, HP 79 to 79 (about 23 turns of Defend vs a 4-HP slime)"
        },
        {
         "label": "A0 run 23 F16: The Guardian",
         "value": 16,
         "note": "won, HP 68 to 40"
        },
        {
         "label": "A0 run 8 F16: The Guardian",
         "value": 15,
         "note": "lost from 51 HP"
        },
        {
         "label": "A0 run 13 F6: 3 Sentries",
         "value": 15,
         "note": "won, HP 80 to 13"
        }
       ],
       "unit": "turns"
      }
     },
     {
      "id": "records-closest-wins",
      "title": "Closest shaves: wins on 3 HP",
      "claim": "The net won two A20 fights with 3 HP left: three Fungi Beasts on floor 13 of run 34, and Slime Boss in run 44 after starting the fight on 66 HP. Some wins started from almost nothing. Run 34 entered a Red Slaver fight on 9 HP and left on 4, and run 33 beat a Blue Slaver from 12 HP. At A0 only one fight the net finished ended on 10 HP or less: Hexaghost on 7 HP.",
      "tag": "real game · A0 and A20, shown apart",
      "setting": "Real game, Act 1 (floors 1-16), won fights the net played to the end (fallback-rule finishes excluded). A20: runs 28-90, run-rule and fight-guard versions pooled. A0: runs 1-27. · n: A20: 546 won fights, 14 ended on 10 HP or less. A0: 264 won fights, 1 ended on 10 HP or less.",
      "caveat": "HP is measured before Burning Blood and other end-of-fight heals. A0 runs also reached Act 2, where the fallback rule finished many fights on 1 HP; those fights are left out because the net did not finish them.",
      "checked": "confirmed",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "A20 run 34 F13: 3 Fungi Beasts",
         "value": 3,
         "note": "of 80 max; came in at 36"
        },
        {
         "label": "A20 run 44 F16: Slime Boss",
         "value": 3,
         "note": "of 68 max; came in at 66"
        },
        {
         "label": "A20 run 33 F11: Blue Slaver",
         "value": 4,
         "note": "of 75 max; came in at 12"
        },
        {
         "label": "A20 run 34 F14: Red Slaver",
         "value": 4,
         "note": "of 80 max; came in at 9"
        },
        {
         "label": "A20 run 56 F14: Med. Spike Slime + Blue Slaver",
         "value": 5,
         "note": "of 92 max; came in at 75"
        },
        {
         "label": "A20 run 78 F12: 2 Red Lice + Green Louse",
         "value": 5,
         "note": "of 82 max; came in at 23"
        },
        {
         "label": "A20 run 33 F10: Jaw Worm + Red Louse",
         "value": 6,
         "note": "of 75 max; came in at 14"
        },
        {
         "label": "A20 run 37 F6: Gremlin Nob",
         "value": 6,
         "note": "of 75 max; came in at 57"
        },
        {
         "label": "A0 run 19 F16: Hexaghost",
         "value": 7,
         "note": "of 80 max; came in at 72"
        },
        {
         "label": "A0 run 13 F6: 3 Sentries",
         "value": 13,
         "note": "of 80 max; came in at 80"
        }
       ],
       "unit": "HP left at the end of a won fight (before end-of-fight heals)"
      }
     },
     {
      "id": "records-biggest-hit",
      "title": "The hardest single enemy turn",
      "claim": "The biggest single enemy turn took 38 HP: Slime Boss's Slam in A20 run 39, and the net still won that fight. Hexaghost fills much of the top of the list, with Divider (6 hits of 7 when the player is near full HP) and its 6x6 multi-hit. A hallway fight also made the top three: in run 52 on floor 5, a Gremlin Wizard's Ultimate Blast plus two Fat Gremlins took 37 HP in one turn.",
      "tag": "real game · A0 and A20, shown apart",
      "setting": "Real game, Act 1 (floors 1-16), all fights. A20: runs 28-90, run-rule and fight-guard versions pooled, 582 fights. A0: runs 1-27, 272 fights. Damage is the HP at the end of the player's turn minus the HP at the start of the next turn, so it is counted after Block. · n: A20 582 fights, A0 272 fights (every enemy turn in every fight was checked)",
      "caveat": "The HP drop also includes end-of-turn effects (Burn and the like). The attack named on each row is the monster's shown intent at the end of the player's turn; it was not checked against the game log line by line. Divider's hit size depends on the player's HP at that moment, not on the Ascension level. These are single record turns, not a measured rate.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "A20 run 39 F16: Slime Boss (Slam), turn 3",
         "value": 38,
         "note": "won"
        },
        {
         "label": "A20 run 52 F5: Gremlin Wizard + 2 Fat Gremlins, turn 3",
         "value": 37,
         "note": "won"
        },
        {
         "label": "A20 run 58 F16: Hexaghost (Divider 7x6), turn 2",
         "value": 37,
         "note": "lost"
        },
        {
         "label": "A20 run 54 F16: Hexaghost (6x6), turn 9",
         "value": 36,
         "note": "lost"
        },
        {
         "label": "A20 run 65 F16: Slime Boss (Slam), turn 3",
         "value": 36,
         "note": "lost"
        },
        {
         "label": "A20 run 29 F16: Hexaghost (6x6), turn 9",
         "value": 34,
         "note": "won"
        },
        {
         "label": "A20 run 31 F16: Hexaghost (Divider 7x6), turn 2",
         "value": 34,
         "note": "won"
        },
        {
         "label": "A20 run 51 F16: Hexaghost (Divider 7x6), turn 2",
         "value": 34,
         "note": "won"
        },
        {
         "label": "A0 run 11 F16: Slime Boss (Slam), turn 3",
         "value": 35,
         "note": "won"
        },
        {
         "label": "A0 run 19 F16: Hexaghost (Divider 7x6), turn 2",
         "value": 32,
         "note": "won"
        },
        {
         "label": "A0 run 16 F16: The Guardian (30 dmg), turn 6",
         "value": 30,
         "note": "lost"
        },
        {
         "label": "A0 run 22 F14: 2 Fungi Beasts (of 3), turn 6",
         "value": 21,
         "note": "won"
        }
       ],
       "unit": "HP lost in one enemy turn"
      }
     },
     {
      "id": "records-boss-speed",
      "title": "Fastest boss kills, and Hexaghost's wall",
      "claim": "Slime Boss gives the net its fastest boss wins: in 4 turns twice at A0, and in 6 turns at A20, where its median win took 9. The Guardian's wins run long, a median of 13 turns at A20 and 12.5 at A0. Hexaghost's few A20 wins were quick, 8 to 10 turns.",
      "tag": "real game · A0 and A20, shown apart",
      "setting": "Real game, Act 1 boss fights (floor 16). A20: runs 28-90, with all run-rule and fight-guard versions pooled, 51 boss fights. A0: runs 1-27, 24 boss fights. The game decided which boss each run met. Turns = the highest combat turn counter in that boss fight (states.jsonl). · n: A20 51 boss fights (30 won); A0 24 boss fights (22 won)",
      "caveat": "The samples per boss are small: A0 Hexaghost has 3 fights, and the A20 Hexaghost median comes from only 4 wins. The win counts pool every run-rule version and the fight guard (on from run 58). Those versions also change how much HP a run brings to the boss, so the win counts partly reflect the run before the boss, not only the fight.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "A20 Slime Boss: fastest win (runs 39, 47)",
         "value": 6,
         "note": "won 15 of 20; median win 9 turns"
        },
        {
         "label": "A20 The Guardian: fastest win (run 75)",
         "value": 7,
         "note": "won 11 of 14; median win 13 turns"
        },
        {
         "label": "A20 Hexaghost: fastest win (runs 31, 51, 73)",
         "value": 8,
         "note": "won 4 of 17; median win 8 turns (only 4 wins)"
        },
        {
         "label": "A0 Slime Boss: fastest win (runs 7, 11)",
         "value": 4,
         "note": "won 7 of 7; median win 7 turns"
        },
        {
         "label": "A0 The Guardian: fastest win (run 25)",
         "value": 7,
         "note": "won 12 of 14; median win 12.5 turns"
        },
        {
         "label": "A0 Hexaghost: fastest win (run 19)",
         "value": 9,
         "note": "won 3 of 3; median win 11 turns"
        }
       ],
       "unit": "turns in the fastest boss win"
      }
     },
     {
      "id": "records-heals",
      "title": "Meat on the Bone's big nights",
      "claim": "Burning Blood does steady work: +6 HP after nearly every win (507 of 549 A20 wins), 3,207 HP in all. The biggest single heals came from Burning Blood plus Meat on the Bone: +18 when a fight ends at half HP or lower. A20 run 77, the only A20 run that held Meat on the Bone, got that +18 in four of its five wins after picking it up, the last after The Guardian (23 to 41 HP). At A0, Black Blood (+12) shows up only in Act 2.",
      "tag": "real game · A0 and A20, shown apart",
      "setting": "Real game, won fights, all floors. A20: runs 28-90, settings pooled (only 1 A20 run held Meat on the Bone). A0: runs 1-27, including Act 2 floors 17-31. The heal is HP after end-of-fight relics minus HP at the fight's last state. · n: A20 549 won fights, 3,207 HP healed; A0 314 won fights, 1,629 HP healed. Meat on the Bone: A20 5 fights in 1 run (4 heals above 6); A0 13 fights in 2 runs (4 heals above 6). Black Blood: A0 4 fights in 2 runs (runs 13, 14), floors 18-21.",
      "caveat": "The heal is capped by max HP, so a fight that ends near full health shows a smaller heal. Relics are read from the game state at the fight's last turn. A few won fights (A20: 4, A0: 2) show a small negative heal because of recording glitches; they are kept in the means.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "A20 run 77 F16: The Guardian",
         "value": 18,
         "note": "23 to 41; Burning Blood + Meat on the Bone"
        },
        {
         "label": "A0 run 11 F16: Slime Boss",
         "value": 18,
         "note": "39 to 57; Burning Blood + Meat on the Bone"
        },
        {
         "label": "A0 run 23 F16: The Guardian",
         "value": 18,
         "note": "40 to 58; Burning Blood + Meat on the Bone"
        },
        {
         "label": "A0 run 11 F18: Shelled Parasite (Act 2)",
         "value": 18,
         "note": "31 to 49; Burning Blood + Meat on the Bone"
        },
        {
         "label": "A0 run 13 F18: Shelled Parasite (Act 2)",
         "value": 12,
         "note": "18 to 30; Black Blood"
        },
        {
         "label": "A20 mean heal per won fight",
         "value": 5.8,
         "note": "549 fights"
        },
        {
         "label": "A0 mean heal per won fight",
         "value": 5.2,
         "note": "314 fights, including Act 2"
        }
       ],
       "unit": "HP healed at the end of a fight"
      }
     },
     {
      "id": "records-flawless",
      "title": "Flawless fights: lice yes, Jaw Worm no",
      "claim": "At A20 the net finished about 1 in 7 hallway fights without losing HP: 68 of 471. Two Red Lice were the easiest at 4 of 12, and a Large Spike Slime was spotless 6 of 21 times. Jaw Worm almost always lands a hit (2 flawless of 48), and Medium Acid Slime + Small Spike Slime never went flawless in 23 fights. Elites and bosses at A20 had a single flawless win: Gremlin Nob in 3 turns (run 54, floor 14). At A0, Slime Boss fell without the net losing any HP 3 times out of 7.",
      "tag": "real game · A0 and A20, shown apart",
      "setting": "Real game, Act 1 (floors 1-16), won fights the net played to the end. Flawless means HP at the end is at least HP at the start. A20: runs 28-90, run-rule and fight-guard versions pooled; a selection of encounters with 12 or more fights. A0: runs 1-27, for the boss rows only. · n: A20: 471 hallway fights (68 flawless), 44 elite (1), 30 boss (0). A0: 219 hallway (39), 23 elite (0), 22 boss (3).",
      "caveat": "A Smoke Bomb escape from Lagavulin (A20 run 65, floor 13) is recorded as a 1-turn win and is left out here. It is the only Smoke Bomb use in the records. Slime fights can look easier because splits die fast. Small encounters (12 to 17 fights) can move by many points from one fight. A fight healed back to its starting HP during the fight also counts as flawless (for example run 87, floor 2).",
      "checked": "confirmed",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "A20 2 Red Lice",
         "value": 33,
         "note": "4 of 12"
        },
        {
         "label": "A20 Large Spike Slime",
         "value": 29,
         "note": "6 of 21"
        },
        {
         "label": "A20 2 Fungi Beasts",
         "value": 26,
         "note": "9 of 34"
        },
        {
         "label": "A20 Green Louse + Red Louse",
         "value": 24,
         "note": "4 of 17"
        },
        {
         "label": "A20 Cultist",
         "value": 17,
         "note": "9 of 52"
        },
        {
         "label": "A20 Looter",
         "value": 14,
         "note": "5 of 36"
        },
        {
         "label": "A20 Blue Slaver",
         "value": 9,
         "note": "3 of 34"
        },
        {
         "label": "A20 Gremlin Nob (elite)",
         "value": 5,
         "note": "1 of 19"
        },
        {
         "label": "A20 Jaw Worm",
         "value": 4,
         "note": "2 of 48"
        },
        {
         "label": "A20 Med. Acid Slime + Small Spike Slime",
         "value": 0,
         "note": "0 of 23"
        },
        {
         "label": "A20 3 Sentries (elite)",
         "value": 0,
         "note": "0 of 14"
        },
        {
         "label": "A0 Slime Boss (boss)",
         "value": 43,
         "note": "3 of 7 (runs 7, 10, 27)"
        }
       ],
       "unit": "% of won fights with no HP lost"
      }
     }
    ]
   },
   {
    "name": "What the net believes",
    "items": [
     {
      "id": "net-confidence-calibration",
      "title": "When the net says 'won', it wins",
      "claim": "At Ascension 20, the net scored 464 fights at 1.80 or higher at the start, and it won every one of them but one, a Lagavulin. Below 1.0 it expected to lose, and 21 of those 24 fights were lost. In the fights it won, it was a pessimist about HP: it expected to lose about 11 HP and actually lost about 7.6 (after Burning Blood's heal, which its score counts too).",
      "tag": "real game · A0 and A20, shown apart",
      "setting": "Real game, Act 1 fights that the net played to the end. A20: runs 28-90, all run-rule versions pooled, 579 fights. A0: runs 1-27, 266 fights. Fights handed to the fallback rule are left out (3 at A20, 6 at A0), and so is the one Act 2 fight the net played at A0. The score is the chosen first action's score at the fight's first decision on turn 1: the two-turn score, or the one-turn score where the record has no two-turn score (82 fights at A20, 68 at A0). · n: A20 579 fights (33 lost); A0 266 fights (2 lost)",
      "caveat": "The score mixes the chance of winning with the expected HP loss. A win scores 2 minus HP lost/100, where HP lost is counted after Burning Blood's heal and floored at 0. A loss scores 0. So a score of 1.6 can mean a near-certain win that costs 40 HP, or a likely win with some risk, and the buckets are not pure probabilities. Some fights' first decisions have no two-turn score, so the one-turn score is used for them. The 1.0-1.7 buckets at A20 have only 19-37 fights each, and A0 has only 2 losses. Before the heal, won A20 fights cost about 12 HP each.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "A20, start score < 1.0",
         "value": 12.5,
         "note": "3 of 24 won"
        },
        {
         "label": "A20, 1.0-1.5",
         "value": 73.7,
         "note": "14 of 19 won"
        },
        {
         "label": "A20, 1.5-1.7",
         "value": 83.8,
         "note": "31 of 37 won"
        },
        {
         "label": "A20, 1.7-1.8",
         "value": 100,
         "note": "35 of 35 won"
        },
        {
         "label": "A20, 1.8-1.9",
         "value": 99.2,
         "note": "118 of 119 won (the loss: run 79, Lagavulin)"
        },
        {
         "label": "A20, 1.9 and up",
         "value": 100,
         "note": "345 of 345 won"
        },
        {
         "label": "A0, start score < 1.5",
         "value": 77.8,
         "note": "7 of 9 won"
        },
        {
         "label": "A0, 1.5-1.8",
         "value": 100,
         "note": "24 of 24 won"
        },
        {
         "label": "A0, 1.8 and up",
         "value": 100,
         "note": "233 of 233 won"
        }
       ],
       "unit": "% of fights won"
      }
     },
     {
      "id": "net-confidence-misjudged-monsters",
      "title": "Hexaghost and Lagavulin fool it; The Guardian scares it more than it should",
      "claim": "At A20 the net's fight-start score was furthest above the real result against Hexaghost (13 of 17 fights lost) and Lagavulin (6 of 18 lost). Against The Guardian it was the other way round: in the 11 fights it won, its start score was worth about 70 HP lost, and it actually lost about 34 HP.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20, runs 28-90, all run-rule versions pooled. Act 1 fights the net played to the end. Shown: a selection of the encounters with at least 6 fights (all six that came out too hopeful, plus the most common hallway fights and The Guardian). The 12 other encounters with at least 6 fights, such as Looter, Louse and Blue Slaver, all lie between -0.4 and -4.8. · n: 282 fights across the shown encounters (524 across all 23 encounters with at least 6 fights; 579 fights at A20 in all)",
      "caveat": "A loss counts as score 0, so one loss moves an encounter's mean a lot. The boss and elite rows rest on 14-21 fights each. The score mixes the chance of winning with the HP lost, so \"worth about 70 HP\" is the score expressed in HP, not a pure HP forecast. At A0 (runs 1-27) the pattern is different: it was too gloomy about The Guardian (n=13), Slime Boss (n=7), Hexaghost (only 3 fights) and Lagavulin (8 fights, none lost). Only the Sentries came out slightly too hopeful (+4.0, n=12).",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Hexaghost (boss)",
         "value": 42.5,
         "note": "n=17, 13 lost"
        },
        {
         "label": "Lagavulin (elite)",
         "value": 34.1,
         "note": "n=18, 6 lost"
        },
        {
         "label": "Slime Boss",
         "value": 14.7,
         "note": "n=20, 5 lost"
        },
        {
         "label": "3 Sentries (elite)",
         "value": 11.6,
         "note": "n=15, 1 lost"
        },
        {
         "label": "Acid Slime (L)",
         "value": 11.6,
         "note": "n=14, 1 lost"
        },
        {
         "label": "Gremlin Nob (elite)",
         "value": 6.5,
         "note": "n=21, 2 lost"
        },
        {
         "label": "Cultist",
         "value": -1.5,
         "note": "n=52, 0 lost"
        },
        {
         "label": "Jaw Worm",
         "value": -4.5,
         "note": "n=48, 0 lost"
        },
        {
         "label": "Fungi Beast (2-3)",
         "value": -4.9,
         "note": "n=38, 0 lost"
        },
        {
         "label": "Red Slaver",
         "value": -6,
         "note": "n=25, 0 lost"
        },
        {
         "label": "The Guardian (boss)",
         "value": -17.3,
         "note": "n=14, 3 lost"
        }
       ],
       "unit": "mean (start score minus actual score) x 100; positive = too hopeful, roughly in HP"
      }
     },
     {
      "id": "net-confidence-second-turn-saves",
      "title": "When looking one more turn ahead changed the verdict",
      "claim": "In run 34 (A20), the Red Slaver fight on floor 14 started at 9 HP. One turn deep, the best option scored 0.15, which reads as an almost certain loss. Two turns deep, every attacking line scored about 1.52. The search played the Skill Potion, and the fight was won: 4 HP at the end, 10 after the end-of-fight heal. The reverse also happens: in run 78, against a Looter at 11 HP, one turn deep looked like a comfortable win at 1.58. Two turns deep it scored 0.43, and that fight was lost.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20, runs 28-90, all run-rule versions pooled. 3,175 decisions with at least two options where the two-turn search finished (cut decisions have no two-turn score). Value = two-turn score of the chosen option minus the best one-turn score. Each fight is shown once, at its most extreme decision. · n: 3,175 decisions; the 4 fights with the largest rises and the 4 with the largest drops are shown (one decision per fight)",
      "caveat": "These are hand-picked extremes from 3,175 decisions, not typical ones, and each fight is shown once. The scores are the net's beliefs, not outcomes: run 69's two-turn hope against The Guardian did not hold. In run 34 the second turn raised every attacking line (Strike and Cleave also scored about 1.52), so the potion was not the only saving line. At A0 (runs 1-27) the biggest rise was run 17's Hexaghost fight, turn 3: Defend went from 0.23 to 1.26, and the fight was won.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Run 34 fl 14 Red Slaver, 9 HP: Skill Potion (won)",
         "value": 1.365
        },
        {
         "label": "Run 69 fl 16 The Guardian, 44 HP: Bash+ (lost)",
         "value": 0.918
        },
        {
         "label": "Run 78 fl 13 Looter, 11 HP: Thunderclap (lost)",
         "value": -1.154
        },
        {
         "label": "Run 76 fl 8 Lagavulin, 40 HP, turn 10: Clothesline (lost)",
         "value": -1.053
        },
        {
         "label": "Run 79 fl 10 Lagavulin, 32 HP, turn 9: Strike (lost)",
         "value": -0.888
        },
        {
         "label": "Run 52 fl 10 Gremlin Nob, 44 HP: Defend (lost)",
         "value": -0.887
        }
       ],
       "unit": "two-turn minus one-turn score (score points; 1.0 = 100 HP-equivalents)"
      }
     },
     {
      "id": "net-confidence-overrules",
      "title": "Looking two turns ahead: start with Strike, not Defend",
      "claim": "About one decision in five, the two-turn search picked a first action that was not among the best-scoring ones one turn deep: 630 of 3,175 at A20 and 307 of 1,446 at A0. At A20 Strike was the two-turn pick in 351 of those 630 changes. Defend was a one-turn favourite overruled for Strike 138 times, and the reverse happened only 24 times.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20, runs 28-90, all run-rule versions pooled; 3,175 uncut decisions with at least two options. A0 is runs 1-27, 1,446 decisions. Rows are A20 changes counted from each card that tied for the best one-turn score to the two-turn pick. A decision with tied favourites counts once for each tied card, so the rows overlap. Changes that only switched a card's target are left out of the rows. · n: 630 changed picks at A20 (19.8%); 307 at A0 (21.2%)",
      "caveat": "An option here is the first action of a planned turn, so many changes only reorder the same turn. One-turn scores often tie: in 343 of the 630 A20 changes, two or more options shared the best one-turn score. The median one-turn cost of the overruled choice was small: 0.64 HP-equivalents at A20 and 0.40 at A0. Only 71 of the 630 A20 changes cost more than 5 HP-equivalents one turn deep. Changes where the fight guard picked the option are included.",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Defend -> Strike",
         "value": 138,
         "note": "Defend the sole one-turn favourite in 47"
        },
        {
         "label": "Bash -> Strike",
         "value": 37
        },
        {
         "label": "Strike -> Defend",
         "value": 24
        },
        {
         "label": "Bash+ -> Strike",
         "value": 17
        },
        {
         "label": "Shrug It Off -> Strike",
         "value": 15
        },
        {
         "label": "Armaments -> Strike",
         "value": 13
        },
        {
         "label": "Armaments -> Defend",
         "value": 13
        },
        {
         "label": "End turn -> Strike",
         "value": 11
        },
        {
         "label": "Strike -> Bash+",
         "value": 10
        }
       ],
       "unit": "decisions (A20)"
      }
     },
     {
      "id": "net-confidence-card-vs-end",
      "title": "Cards the net most wants to play rather than end the turn",
      "claim": "At A20, when Rampage or Ghostly Armor was playable, the net typically scored playing it about 22 points above ending the turn right there. Whirlwind came last of the cards shown, at about 10, from only 4 runs.",
      "tag": "real game · A20 · rule versions pooled",
      "setting": "Real game, A20, runs 28-90, all run-rule versions pooled. 3,266 uncut decisions where End was an option. Per card or potion: the best two-turn score among options that start by playing it (the same card aimed at several targets counts once), minus End's two-turn score in the same decision. Only cards and potions with at least 20 such decisions. · n: 57 cards and potions with n >= 20, each shown with its n (decisions); the number of runs behind each is in the notes",
      "caveat": "This measures each card in the hands where it showed up, not the card on its own. Ending a turn with unused energy is always costly, and a card held during desperate fights picks up that context. Many cards come from only a handful of runs (Havoc and Ghostly Armor from 5 each), so their values reflect a few decks. Turns close to lethal pull the averages far up, so medians are shown. At A0 (runs 1-27, 1,498 decisions) the top cards were Defend+ (+18.5, n=77) and Searing Blow (+17.9, n=20, 2 runs), and the bottom card was Demon Form (+3.5, n=28, 3 runs).",
      "checked": "corrected",
      "viz": {
       "kind": "bars",
       "rows": [
        {
         "label": "Rampage",
         "value": 22.5,
         "note": "n=27, 8 runs"
        },
        {
         "label": "Ghostly Armor",
         "value": 22.3,
         "note": "n=63, 5 runs"
        },
        {
         "label": "Perfected Strike+",
         "value": 21.6,
         "note": "n=25, 5 runs"
        },
        {
         "label": "Flex",
         "value": 19.7,
         "note": "n=84, 12 runs"
        },
        {
         "label": "Shockwave",
         "value": 19.1,
         "note": "n=35, 6 runs"
        },
        {
         "label": "Spot Weakness",
         "value": 17.9,
         "note": "n=81, 12 runs"
        },
        {
         "label": "Speed Potion",
         "value": 17.7,
         "note": "n=22, 8 runs"
        },
        {
         "label": "Carnage",
         "value": 17.5,
         "note": "n=61, 8 runs"
        },
        {
         "label": "Fire Breathing",
         "value": 12,
         "note": "n=70, 10 runs"
        },
        {
         "label": "Intimidate",
         "value": 11.2,
         "note": "n=32, 7 runs"
        },
        {
         "label": "Whirlwind",
         "value": 10.1,
         "note": "n=36, 4 runs"
        }
       ],
       "unit": "median score gain over ending the turn, x100 (roughly HP)"
      }
     }
    ]
   }
  ]
 }
];
