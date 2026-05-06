# [LN] MiniSat 如何實作（CDCL 讀碼報告）

日期：2026-05-06  
範圍：`gv/satsolvers/minisat/`（以 `Solver.h`、`Solver.cpp`、`VarOrder.h` 為核心）

## 1. 報告目標

本報告聚焦在「MiniSat 如何把課程中的 SAT/CDCL 概念落成實作」，不再以 Sudoku 實驗為主。  
重點是回答三個問題：

1. MiniSat 的主流程如何運作？
2. 關鍵資料結構如何支援效率？
3. 啟發式、學習與預算控制如何在程式中被實現？

## 2. 核心資料結構（Solver 狀態）

在 `Solver.h` 可以看到 CDCL 狀態機所需的主要欄位：

- `trail`：目前已指派的 literal 序列。
- `trail_lim`：每個 decision level 在 `trail` 的切點。
- `reason[var]`：變數被推導的原因子句（若是決策則為空）。
- `level[var]`：該變數指派所在層級。
- `watches`：2-watched literals 結構，供快速 BCP。
- `activity` + `order`：變數活性與決策順序結構（heap）。

這些欄位對應課堂中的 implication graph 元件：節點是指派、邊由 reason clause 定義、decision level 由 `trail_lim` 管理。

## 3. 主迴圈（search）如何實作 CDCL

`Solver.cpp::search()` 是核心：

1. 先做 `propagate()`（BCP）。
2. 若衝突：
   - `analyze()` 產生 learned clause 與 backtrack level。
   - `cancelUntil(...)` 非時間序回跳。
   - `newClause(learnt_clause, true, ...)` 寫回 learnt DB。
3. 若無衝突：
   - 依條件執行 `simplifyDB()` 與 `reduceDB()`。
   - `order.select(...)` 選下一個決策變數。
   - 若已無可選變數則找到模型，回傳 `gv_l_True`。

對應語意：

- `gv_l_True`：SAT（找到完整一致指派）
- `gv_l_False`：UNSAT（根層衝突）
- `gv_l_Undef`：在給定衝突上限內未定（budget 模式）

## 4. BCP 與 2-Watched Literals

`propagate()` 的重點是「只處理受新指派影響的 watcher list」：

- 先確保 false literal 在 clause 的 watch 位置。
- 嘗試在 clause 內找新的可 watch literal。
- 若找不到：
  - 若第一個 literal 可推出，則 `enqueue(...)`（unit propagation）
  - 若連 enqueue 都失敗，代表衝突，回傳 conflict clause

這讓 propagation 避免每次掃整個 clause database，是 MiniSat 快速的核心之一。

## 5. 衝突分析與學習

當 `propagate()` 回傳衝突子句，`search()` 會呼叫 `analyze()`：

- 由目前衝突追溯 reason，計算 learned clause。
- 算出可回跳層級（非單步 backtrack）。
- 新增 learned clause 後回到較淺層繼續搜索。

這個流程把「失敗路徑」轉成「未來剪枝條件」，是 CDCL 相較 DPLL 的主要提升。

## 6. 決策順序（Decision Ordering）實作

MiniSat 的決策是 `order.select(random_var_freq)`：

- `VarOrder` 用 heap 維護未指派變數的活性排序。
- 預設有少量隨機挑選（`random_var_freq`）避免卡在局部形狀。
- 其餘時間採活動度導向（VSIDS 風格）。

活動度更新在 `varBumpActivity()` / `varDecayActivity()`：

- 衝突相關變數被 bump。
- 隨時間 decay，讓近期衝突資訊有更高權重。

在 GV 擴充後，`-DecisionOrder STATIC` 可把 `var_decay < 0`、`random_var_freq = 0`，近似固定順序決策，便於對照 dynamic ordering。

## 7. 資料庫管理（simplify / reduce）

`search()` 會週期性做兩種管理：

- `simplifyDB()`：在根層移除已滿足/冗餘資訊。
- `reduceDB()`：當 learnt 過多時刪除部分學習子句。

這對應課堂中的 database simplification：  
學習子句不是越多越好，必須在「推理能力」與「搜尋成本」間平衡。

## 8. 預算求解（solveLimited）與 UNKNOWN

`solveLimited(...)` 讓使用者限制求解 effort（以衝突數為預算）：

- 預算內得證 SAT/UNSAT：回傳 `gv_l_True` / `gv_l_False`
- 預算耗盡：回傳 `gv_l_Undef`（GV 顯示 `UNKNOWN`）

這個介面非常適合實驗：

- 可以觀察不同 budget 下，解題狀態如何從 `UNKNOWN` 轉為可判定。
- 可量化 heuristics 與 decision order 對「單位預算效益」的影響。

## 9. 與 GV 指令的接線關係

目前 GV 端主要透過 `SATSolve DIMACS` 接到 MiniSat：

- `src/sat/satCmd.cpp`：解析 `-File`、`-Model`、`-ConfLimit`、`-DecisionOrder`
- `src/sat/minisatMgr.cpp`：讀 DIMACS、建 solver、選擇 `solve()` 或 `solveLimited()`
- `GV_DIMACS_STATS`：輸出 conflicts/propagations/decisions/starts 等統計

因此課程概念已可直接透過 CLI 操作並觀測結果。

## 10. 結論

MiniSat 的實作呈現一個非常乾淨的 CDCL 架構：

1. **Propagation 驅動**：大部分時間花在 BCP。
2. **Conflict 反饋**：每次衝突都轉成 learned clause。
3. **Heuristic 自適應**：用 activity/decay 持續調整決策順序。
4. **Resource-aware**：可透過 conflict budget 在 SAT/UNSAT/UNKNOWN 間做可控折衷。

對我而言，讀完程式後最大的收穫是：  
課堂上的每個名詞（BCP、learning、backjump、VSIDS、DB simplification）都能在 MiniSat 找到精確落點，且能透過 GV 的參數化介面做可重現驗證。

- 一般化：`id(r,c,d) = N*N*(r-1) + N*(c-1) + d`
- 9x9：`id(r,c,d) = 81*(r-1) + 9*(c-1) + d`

### 3.2 子句約束
1. 每格至少一個數字：`OR_{d=1..9} x[r,c,d]`  
   例：格子 `(r=1,c=1)` 至少要填一個數字：  
   `x[1,1,1] OR x[1,1,2] OR ... OR x[1,1,9]`  
   依 `id(r,c,d)=81*(r-1)+9*(c-1)+d`，對應 DIMACS：`1 2 3 4 5 6 7 8 9 0`
2. 每格至多一個數字：`(!x[r,c,d1] OR !x[r,c,d2])`  
   例：格子 `(1,1)` 不可同時是 1 和 2：  
   `!x[1,1,1] OR !x[1,1,2]`，DIMACS：`-1 -2 0`
3. 每列每個數字恰一次  
   例：第 1 列的數字 5 至少出現一次：  
   `x[1,1,5] OR x[1,2,5] OR ... OR x[1,9,5]`  
   同時需加「至多一次」，例如 `(c=1)` 與 `(c=2)` 不能同時是 5：  
   `!x[1,1,5] OR !x[1,2,5]`
4. 每行每個數字恰一次  
   例：第 1 行的數字 5 至少出現一次：  
   `x[1,1,5] OR x[2,1,5] OR ... OR x[9,1,5]`  
   同時需加「至多一次」，例如 `(r=1)` 與 `(r=2)` 不能同時是 5：  
   `!x[1,1,5] OR !x[2,1,5]`
5. 每個 3x3 宮每個數字恰一次  
   例：左上角宮（`r=1..3,c=1..3`）的數字 9 至少出現一次：  
   `x[1,1,9] OR x[1,2,9] OR ... OR x[3,3,9]`  
   並加「至多一次」，例如 `(1,1)` 與 `(2,2)` 不能同時是 9：  
   `!x[1,1,9] OR !x[2,2,9]`
6. givens 直接轉為單一子句（unit clause）  
   例：若題目給定 `(r=1,c=1)=5`，加入：`x[1,1,5]`，DIMACS：`5 0`

## 4. 實驗設計
本實驗從兩個維度比較 miniSat 的行為：

第一個維度是盤面大小。基準是 9x9，再擴充到更大盤面（例如 16x16、25x25；分別對應子宮 4x4、5x5）。  
盤面變大時，`N^3` 個變數與大量 pairwise 子句會快速增加，預期 `propagations`、`decisions` 與 `conflicts` 都會上升。

第二個維度是初始 clue 多寡。對同一個盤面大小，分成 clue 多（easy）、clue 中等（medium）、clue 少（hard）與故意矛盾（UNSAT）四類。  
clue 越少，搜尋空間越大，通常會造成更多 implication（propagation）與 backtracking；  
UNSAT 個案則常在衝突學習階段累積較高 conflict 次數。

本實驗統計 miniSat 的 `propagations`（通常可視為 implication 次數）、`conflicts`、`decisions` 與 `wall_sec`。

9x9 的主要結果（均含 `clues` 欄位）：
- `experiments/sudoku_study/sudoku_experiment_full.csv`：混合題庫（預設三題 + `puzzles_9x9_all.txt`）
- `experiments/sudoku_study/sudoku_experiment_heavy.csv`：大型/困難題（Norvig top95 子集，`puzzles_9x9_heavy_benchmark.txt`）

16x16 的結果：
- `experiments/sudoku_study/sudoku_experiment_16x16.csv`：以 `N=16` 生成 SAT/UNSAT，並比較不同初始 clues 數的行為。

## 5. 執行流程
1. 準備 Sudoku 題目檔。9x9 可用 81 字元字串（`0` 表示空格）；更大盤面使用對應長度格式。
2. 轉為 DIMACS CNF（相同編碼規則推廣到 `N x N`）。
3. 在 GV 中執行：
   - `SATSolve DIMACS -File <sudoku.cnf>`
4. 蒐集輸出中的 SAT 結果與統計值（`propagations`、`conflicts`、`decisions`、runtime）。
5. 依「盤面大小」與「clue 多寡」兩軸做文字比較，描述指標如何變化。

## 6. 預期觀察（文字分析重點）
在 9x9 的情況下，clue 多寡是主要難度來源：當 clue 從多變少時，通常先看到 `decisions` 上升，再帶動 `propagations` 與 `conflicts` 上升，runtime 也隨之增加。  
當題目被刻意改成 UNSAT，solver 需要證明「不存在解」，常比一般 SAT 題目累積更多衝突學習步驟。

從 9x9 擴充到 16x16、25x25 時，因為變數與子句成長很快，指標會整體抬升；在大盤面且 clue 偏少時，implication（propagation）次數通常成長最明顯。  
因此，盤面大小與 clue 多寡會共同影響求解成本：大盤面 + 少 clue 往往是最吃資源的組合。

## 7. 實驗結果與限制
### 7.1 9x9 混合題庫（`sudoku_experiment_full.csv`）
以 `clues`（初始已給定數量）分段觀察到明顯趨勢：`clues` 越少，平均 `propagations` 與 `conflicts` 通常越高，平均 `wall_sec` 也略有上升。

（144 筆中的 `db_*` 題目，分 bins 取平均與最大值；數字皆由 CSV 計算而來）

| clues 範圍 | 案例數 n | propagations 平均 | propagations 最大 | conflicts 平均 | conflicts 最大 | decisions 平均 | wall_sec 平均(s) | wall_sec 最大(s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 17-20 | 40 | 1405.10 | 2993 | 9.38 | 30 | 28.88 | 0.0249 | 0.0746 |
| 21-24 | 53 | 1315.26 | 2716 | 8.32 | 22 | 18.08 | 0.0236 | 0.0288 |
| 25+ | 51 | 899.10 | 3428 | 2.47 | 33 | 5.24 | 0.0237 | 0.0309 |

整體（`db_*`）`clues` 與 `propagations` 呈中度負相關（約 `r ≈ -0.42`）。

### 7.2 9x9 困難題（`sudoku_experiment_heavy.csv`）
在 Norvig top95 的少提示子集中（95 筆）：

| clues 範圍 | 案例數 n | propagations 平均 | propagations 最大 | conflicts 平均 | conflicts 最大 | decisions 平均 | wall_sec 平均(s) | wall_sec 最大(s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 17-20 | 40 | 1405.10 | 2993 | 9.38 | 30 | 28.88 | 0.0237 | 0.0345 |
| 21-24 | 47 | 1381.00 | 2716 | 9.21 | 22 | 20.00 | 0.0235 | 0.0280 |
| 25+ | 8 | 1776.25 | 3428 | 15.12 | 33 | 26.13 | 0.0235 | 0.0256 |

此批題目 runtime 仍多數落在數十毫秒等級，顯示在此 CNF 編碼與 GV 設定下主要難點更偏向「需要更多推論步驟」。

### 7.3 16x16 大盤面（`sudoku_experiment_16x16.csv`）
在 `N=16` 的結果中，SAT 題目呈現「clues 越少，搜尋/推論成本越高」的方向性。

（每個 clues 跑 5 組 trial，以下為 SAT 平均值）

| clues | sat | wall_sec 平均(s) | propagations 平均 | conflicts 平均 | decisions 平均 |
|---:|---|---:|---:|---:|---:|
| 32 | True | 0.0527 | 4757.0 | 11.2 | 396.6 |
| 64 | True | 0.0495 | 4877.8 | 7.6 | 180.2 |
| 96 | True | 0.0498 | 5251.4 | 9.6 | 71.6 |
| 128 | True | 0.0491 | 4096.0 | 0.0 | 9.0 |

### 7.4 9x9 與 16x16 直接比較（SAT）
下面用 CSV 的實測數字做對照。  
9x9 使用分段平均（`sudoku_experiment_full.csv` 的 `db_* SAT`）；16x16 使用各 clues 的 **5 次 SAT 平均量測**（`sudoku_experiment_16x16.csv`）。

| 尺寸 | clues（設定） | clues 比例 | nvars | 代表 nclauses | propagations | conflicts | decisions | wall_sec(s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 9x9（平均） | 17-20 | 約 21%-25% | 729 | 約 12005~12008 | 1405.10 | 9.38 | 28.88 | 0.0249 |
| 9x9（平均） | 21-24 | 約 26%-30% | 729 | 約 12009~12012 | 1315.26 | 8.32 | 18.08 | 0.0236 |
| 9x9（平均） | 25+ | 約 31%+ | 729 | 約 12013+ | 899.10 | 2.47 | 5.24 | 0.0237 |
| 16x16（平均） | 32 | 12.5% | 4096 | 123936 | 4757.00 | 11.20 | 396.60 | 0.0527 |
| 16x16（平均） | 64 | 25.0% | 4096 | 123968 | 4877.80 | 7.60 | 180.20 | 0.0495 |
| 16x16（平均） | 96 | 37.5% | 4096 | 124000 | 5251.40 | 9.60 | 71.60 | 0.0498 |
| 16x16（平均） | 128 | 50.0% | 4096 | 124032 | 4096.00 | 0.00 | 9.00 | 0.0491 |

比較重點：
- 規模由 9x9 升到 16x16 時，`nvars` 從 729 增到 4096，`nclauses` 從約 1.2 萬級增到約 12.4 萬級。
- 在近似 clues 比例（約 25%）下，16x16 的 `propagations/decisions` 明顯高於 9x9（例如 16x16 clues=64 的平均 `prop=4877.8, dec=180.2`，而 9x9 clues=17-20 平均約 `prop=1405.1, dec=28.9`）。
- `wall_sec` 也呈現一致放大：9x9 約 0.024 秒級，16x16 約 0.05 秒級（約 2 倍量級）。

### 7.5 建議與可改進方向
本次已補上一版「非直接衝突 UNSAT」實驗（`experiments/sudoku_study/sudoku_experiment_nondirect_unsat.csv`）。  
方法是：先用完整合法解生成 SAT，再追加一條 **blocking clause**（要求至少有一格不同於該完整解），形成全域矛盾。  
這不是同列重複 givens 的直接衝突，而是「完整解 + 額外全域限制」造成的不可滿足。

| case | size | variant | sat | wall_sec(s) | nvars | nclauses | propagations | conflicts | decisions |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| N9_full_sat | 9 | SAT_full_solution | True | 0.0387 | 729 | 12069 | 729 | 0 | 1 |
| N9_nondirect_unsat | 9 | UNSAT_blocking_clause | False | 0.0218 | 729 | 12070 | 0 | 0 | 0 |
| N16_full_sat | 16 | SAT_full_solution | True | 0.0538 | 4096 | 124160 | 4096 | 0 | 1 |
| N16_nondirect_unsat | 16 | UNSAT_blocking_clause | False | 0.0464 | 4096 | 124161 | 0 | 0 | 0 |

後續若要更「難」的 UNSAT，可再改成不依賴完整 givens 的全域限制（例如在部分 clues 下加入互斥結構約束），讓 solver 需要較多衝突學習才證明 UNSAT。

## 8. 新功能實作說明（SAT 時輸出一組解）
為了讓 `SATSolve DIMACS` 在 `SAT` 時能輸出一組 model，本次新增可選參數 `-Model`。

### 8.1 怎麼做
1. 在 `SATSolve DIMACS` 指令解析中加入 `-Model` 選項。  
2. 將 `print_model` 布林值一路傳到 `solve_dimacs_cnf()`。  
3. 在 `solve_dimacs_cnf()` 中，若求解結果為 `SAT` 且 `print_model=true`，就輸出每個變數的指派：  
   - `+i` 表示第 `i` 個變數為 True  
   - `-i` 表示第 `i` 個變數為 False  
4. 若不帶 `-Model`，維持原本行為（只印 `SAT/UNSAT` 與 `GV_DIMACS_STATS`）。

### 8.2 使用方式
```cpp
gv> SATSolve DIMACS -File <your.cnf>
gv> SATSolve DIMACS -File <your.cnf> -Model
```

### 8.3 輸出實例
不帶 `-Model`（只看結果）：
```text
SAT
GV_DIMACS_STATS conflicts=0 propagations=729 decisions=1 starts=1
```

帶 `-Model`（輸出一組解）：
```text
SAT
-1 -2 -3 -4 5 -6 ... -728 729
GV_DIMACS_STATS conflicts=0 propagations=729 decisions=1 starts=1
```

其中第二行就是 SAT solver 回傳的一組可滿足指派，可用來還原 Sudoku 解盤。
還原後會得到兩種輸出：

- `Compact`（單行 81 字元答案，例如）  
  `534678912672195348198342567859761423426853791713924856961537284287419635345286179`
- `Grid`（9x9 可讀棋盤，例如）  
  ```
  -------+-------+-------
  5 3 4|6 7 8|9 1 2
  6 7 2|1 9 5|3 4 8
  1 9 8|3 4 2|5 6 7
  -------+-------+-------
  8 5 9|7 6 1|4 2 3
  4 2 6|8 5 3|7 9 1
  7 1 3|9 2 4|8 5 6
  -------+-------+-------
  9 6 1|5 3 7|2 8 4
  2 8 7|4 1 9|6 3 5
  3 4 5|2 8 6|1 7 9
  -------+-------+-------
  ```

### 8.4 Model 還原 Sudoku（新增工具）
除了在 GV 輸出 model，本次也新增還原工具：`scripts/sat_model_to_sudoku.py`。  
它可以把 `-1 -2 ...` 的變數指派轉回 Sudoku 盤面（支援 9x9 / 16x16）。

還原方法（建議流程）：

1. 先在 GV 用 `-Model` 求解，取得 SAT 指派輸出。  
   例如：
   ```cpp
   gv> SATSolve DIMACS -File experiments/sudoku_study/sudoku_test.cnf -Model
   ```
2. 把該次終端輸出存成文字檔（例如 `gv_output.txt`）。  
   檔案中至少要包含那行 SAT model（像 `-1 -2 ... 729`）。
3. 用還原工具解析：
   - 9x9：
     ```bash
     python3 scripts/sat_model_to_sudoku.py --size 9 --model-file gv_output.txt
     ```
   - 16x16：
     ```bash
     python3 scripts/sat_model_to_sudoku.py --size 16 --model-file gv_output.txt
     ```
4. 工具會輸出兩種結果：
   - `Compact`：單行答案字串（9x9 為 81 字元；16x16 為 256 字元）
   - `Grid`：可讀棋盤格式（可直接貼到報告）

補充：
- 若你已經把 model 行複製成字串，也可直接用 `--model "<model_literals>"`，不一定要檔案。
- 目前符號規則為：`1-9` 直接用數字；`10` 以上用字母（`A=10, B=11, ...`）。

#### 還原方式
```bash
python3 scripts/sat_model_to_sudoku.py --size 9 --model-file <gv_output.txt>
```

#### 實例（9x9）
```bash
# 1) 先讓 GV 輸出 SAT model
./gv -file run.do

# run.do 內容示意：
# satsolve dimacs -file experiments/sudoku_study/sudoku_test.cnf -model
# q -f

# 2) 再把 model 還原成 Sudoku 盤面
python3 scripts/sat_model_to_sudoku.py --size 9 --model-file gv_output.txt
```

輸出會包含：
- `Compact`：81 字元單行答案
- `Grid`：可讀棋盤格式（可直接貼到報告）

## 9. 結論
本實驗以 Sudoku 建立完整流程：`Sudoku -> DIMACS -> SATSolve DIMACS -> 統計分析`。  
即使在變數數量固定的前提下，題目難度與可滿足性仍會顯著影響 miniSat 的衝突數、推論量與執行時間，適合作為 SAT solver 行為分析的實驗題材。
