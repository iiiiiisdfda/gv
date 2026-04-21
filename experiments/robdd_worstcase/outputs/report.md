# ROBDD Worst-case Experiment Report

## Highlights
- theta monotonic non-decreasing check: PASS
- layer-sum identity `sum_i min(r_i, R_i) + 2 = W(n)`: PASS
- average nodes (modeA complement-edge on): 125.639
- average nodes (modeB complement-edge off): 143.981
- off/on node ratio: 1.146

## Files
- `theory_theta.csv`: n, theta, W(n), ratio
- `layer_intersection.csv`: per-layer top/bottom/min and identity check
- `benchmark_results.csv`: 3 function families with modeA/modeB comparisons
- optional PNG plots if matplotlib is available
