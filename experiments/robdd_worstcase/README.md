# ROBDD Worst-case and Complement-edge Experiments

This experiment package implements the attached plan items:

- `FindTheta` and `W(n) = (2^(n-theta)-1) + 2^(2^theta)` theoretical curve.
- Layer-width intersection check using `min(2^(i-1), 2^(2^(n-i+1)) - 2^(2^(n-i)))`.
- A ROBDD builder with switchable complement-edge mode for A/B comparison.
- Benchmarks on:
  - `worstcase_search` (exhaustive for small `n`, sampled for larger `n`)
  - random truth tables
  - structured functions (`parity`, `mux3`, `adder_lsb`)

## Run

From repo root:

```bash
python3 experiments/robdd_worstcase/run_experiments.py
```

## Outputs

Generated in `experiments/robdd_worstcase/outputs/`:

- `theory_theta.csv`
- `layer_intersection.csv`
- `benchmark_results.csv`
- `report.md`
- optional plots (`*.png`) if `matplotlib` is available

## Notes

- The script is dependency-free except optional plotting.
- The reported node count includes 2 terminal nodes for alignment with the paper.
