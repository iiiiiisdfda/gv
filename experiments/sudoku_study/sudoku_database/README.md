# Sudoku Database（9x9）

## 來源

- `top95.txt`：Peter Norvig 的 **Top 95** hard benchmark（`.` 表空格）
- `projecteuler_0096.txt`：Project Euler 第 96 題附檔（50 個 9x9 盤面，含 `Grid xx` 標頭）

## 檔案說明

| 檔案 | 說明 |
|------|------|
| `top95.txt` | 原始 Norvig 題庫 |
| `projecteuler_0096.txt` | 原始 Euler 題庫 |
| `puzzles_9x9_all.txt` | 合併清洗後清單（每行 81 字元，`0` 表空格），**去重後 144 題** |
| `puzzles_9x9_heavy_benchmark.txt` | **僅 Norvig top95**（95 題），少提示／高難度為主的壓力測試子集 |
| `puzzles_9x9_project_euler50.txt` | **僅 Project Euler 50 題**（與 top95 不重複來源），補足「另一批大套題」 |

## 批次實驗範例

混合題庫（預設三題 + `puzzles_9x9_all.txt`）：

```bash
python3 scripts/sat_sudoku_bench_gv.py \
  --puzzle-list experiments/sudoku_study/sudoku_database/puzzles_9x9_all.txt \
  --out-cnf-dir experiments/sudoku_study/bench_cnf \
  --csv experiments/sudoku_study/sudoku_experiment_full.csv
```

僅跑 heavy（Norvig top95）：

```bash
python3 scripts/sat_sudoku_bench_gv.py \
  --database-only \
  --puzzle-list experiments/sudoku_study/sudoku_database/puzzles_9x9_heavy_benchmark.txt \
  --out-cnf-dir experiments/sudoku_study/bench_cnf_heavy \
  --csv experiments/sudoku_study/sudoku_experiment_heavy.csv
```

僅跑 Euler 50 題：

```bash
python3 scripts/sat_sudoku_bench_gv.py \
  --database-only \
  --puzzle-list experiments/sudoku_study/sudoku_database/puzzles_9x9_project_euler50.txt \
  --out-cnf-dir experiments/sudoku_study/bench_cnf_euler \
  --csv experiments/sudoku_study/sudoku_experiment_euler50.csv
```
