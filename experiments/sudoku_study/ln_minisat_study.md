# MiniSat 讀碼筆記與 GV `SATSolve DIMACS -ConfLimit`

本筆記對照 GV 內嵌 MiniSat（`satsolvers/minisat/`）與課程常見的 CDCL 概念，並記錄新增的衝突預算求解指令。

## 1. 讀碼對照（CDCL 骨架）

| 課程概念 | GV MiniSat 落點（檔案） | 備註 |
|----------|-------------------------|------|
| Trail / 決策層級 | `Solver.h`：`trail`、`trail_lim`、`level` | `trail` 為已賦值 literal 序列；`trail_lim` 切出各決策邊界。 |
| Implication / reason | `reason[]`、`propagate()` | 單元傳播時由 watcher 找衝突或推導新指派。 |
| Conflict analysis | `analyze()`、`analyzeFinal()` | 由衝突子句回溯、產生 learnt clause。 |
| 搜尋主迴圈 | `search(nof_conflicts, nof_learnts, params)` | 註解說明：`gv_l_True` 有模型、`gv_l_False` UNSAT、`gv_l_Undef` 達單輪衝突上限。 |
| 決策啟發式 | `VarOrder` / `Heap`、`SearchParams`（`var_decay`、`random_var_freq`） | 對應 VSIDS 類活動度與少量隨機決策。 |
| 有限資源求解 | `SolverV::solveLimited(assumps, nConflicts)` | `nConflicts >= 0` 時以 **`stats.conflicts` 累計值** 作為全域衝突預算；未判定則回傳 `gv_l_Undef`。每次呼叫 `search` 前會把單輪上限裁成「剩餘預算」，避免一輪內大幅超支。 |

`solve()` 路徑則在外層重啟迴圈中反覆呼叫 `search`，直到 SAT/UNSAT 或資源中止（與 `solveLimited` 的「單次有預算搜尋」不同）。

## 2. GV 如何接到 MiniSat

- 指令：`src/sat/satCmd.cpp` 的 `SATSolve DIMACS`，將 token 掃成 `-File`、可選 `-Model`、可選 `-ConfLimit`（**順序任意**）。
- 實作：`MinisatMgr::solve_dimacs_cnf()`（`src/sat/minisatMgr.cpp`）讀 DIMACS、建 `SolverV`，再依是否有預算呼叫 `solve()` 或 `solveLimited`。
- 抽象介面：`SatSolverMgr::solve_dimacs_cnf(..., int64_t conflict_limit = -1)`（`satMgr.h`）；`-1` 表示不設預算（完整 `solve()`）。

## 3. 新參數 `-ConfLimit <int64>` 語意

- **未指定**：行為與先前相同，呼叫 `solve()`，結果行為 **`SAT` / `UNSAT`**（二元）。
- **有指定且 ≥ 0**：呼叫 `solveLimited(empty_assumps, N)`，結果可為：
  - **`SAT`**：`gvlbool` 為 `gv_l_True`；若帶 `-Model` 則印出 DIMACS 變數整行指派。
  - **`UNSAT`**：`gv_l_False`（含空子句、根層矛盾、或 assumptions 矛盾等情況）。
  - **`UNKNOWN`**：`gv_l_Undef`，表示在 **累計 `stats.conflicts` 達到 N 前** 未能證明 SAT 亦未能證明 UNSAT。**此時不印 model**，避免誤導。
- **統計**：仍印 `GV_DIMACS_STATS`；若有 `-ConfLimit`，額外印 `conflict_limit=N` 與 `budget_exhausted=0|1`（`UNKNOWN` 時為 1）。

## 4. 實測（Sudoku DIMACS）

工作目錄假設為 GV 專案根目錄。結束互動：`Quit -Force`。

### 4.1 小預算 → UNKNOWN

```text
SATSolve DIMACS -File experiments/sudoku_study/bench_cnf/db_0000.cnf -ConfLimit 5
```

```text
UNKNOWN
GV_DIMACS_STATS conflicts=6 propagations=972 decisions=22 starts=1 conflict_limit=5 budget_exhausted=1
```

（此例完整求解約需 8 次衝突；預算 5 時在預算內無法定論。）

### 4.2 較大預算 → SAT

```text
SATSolve DIMACS -File experiments/sudoku_study/bench_cnf/db_0000.cnf -ConfLimit 20
```

```text
SAT
GV_DIMACS_STATS conflicts=8 propagations=1418 decisions=27 starts=1 conflict_limit=20 budget_exhausted=0
```

### 4.3 與 `-Model` 任意順序

```text
SATSolve DIMACS -File experiments/sudoku_study/bench_cnf/db_0000.cnf -Model -ConfLimit 20
```

行為：仍為 `SAT`，並印出整行 literal（略）。

```text
SATSolve DIMACS -ConfLimit 5 -Model -File experiments/sudoku_study/bench_cnf/db_0000.cnf
```

行為：`UNKNOWN` 時**不**印 model 行，僅統計（與「避免誤導性 SAT 輸出」一致）。

### 4.4 UNSAT 實例（預算僅影響搜尋深度；已 UNSAT 仍為 UNSAT）

```text
SATSolve DIMACS -File experiments/sudoku_study/bench_cnf_nondirect_unsat/N9_nondirect_unsat.cnf -ConfLimit 500
```

```text
UNSAT
GV_DIMACS_STATS conflicts=0 propagations=0 decisions=0 starts=0 conflict_limit=500 budget_exhausted=0
```

（此檔在傳播階段即矛盾，故統計為 0。）

## 5. 實作時修正的 MiniSat 細節

- `Solver.h` 中 `solveLimited(int64_t)` 原先誤呼叫自身遞迴，已改為 `solveLimited(tmp, nConflicts)`。
- `solveLimited` 內對預算的解讀改為與 **`stats.conflicts`** 對齊，並限制每輪 `search` 的衝突上限，使「總衝突預算」可被 `-ConfLimit` 直接對應。

## 6. 讀完 miniSat code 的心得（對照 Topic 6 / Topic 7）

這次把 `Solver.h/.cpp` 實際走過一輪後，我對課堂上「SAT 是搜尋問題」這件事有更具體的感受：  
`Topic 6: Introduction to SAT` 強調的 decision tree、backtrack、以及以 BCP 快速推進狀態，不只是概念圖，而是在 `search() -> propagate() -> analyze() -> cancelUntil()` 這條路徑中被非常直接地落實。  
換句話說，miniSat 的精髓不是把所有可能性列舉完，而是靠「傳播 + 衝突學習 + 回跳」去大幅剪枝，這也正對應講義裡「拿時間換空間、避免爆炸」的主軸。

`Topic 7: Advanced SAT Techniques` 則讓我更能理解為什麼 **decision order** 是一等公民。講義一開始就點出效率高度受 decision order 影響，miniSat 也確實把這件事放在核心：  
- 預設是動態啟發式（VSIDS 風格，活動度更新 + decay），會隨衝突學習持續調整。  
- 我新增的 `-DecisionOrder STATIC` 則對應講義的 static ordering 思維，讓順序更固定、便於觀察基線行為。  
- 實驗上同一個 CNF 在 `STATIC` 與 `VSIDS` 下會出現不同衝突數，正好印證「好的決策順序可能造成指數級差異」這個課堂重點。

另一個心得是：`-ConfLimit` 這種 budget solve 其實很適合教學。  
它把「proof/search effort」變成可控旋鈕，讓 `SAT/UNSAT/UNKNOWN` 的差異不再只是定義，而是可量測、可重現的行為：  
- 小 budget 看見 `UNKNOWN`，理解「目前證據不足」。  
- 大 budget 回到 `SAT/UNSAT`，理解「資源夠時可完成判定」。  
這也讓我更清楚課堂中「演算法正確性」與「工程上資源限制」其實是同一條線上的兩端。

整體來說，讀完 code 後最大的收穫是：  
1. 課堂的 CDCL 元件（決策、傳播、學習、回跳、重啟）在 miniSat 中是緊密耦合、彼此餵訊號的，而不是獨立模組。  
2. 啟發式（尤其 decision ordering）不是「微調」，而是決定求解曲線形狀的核心。  
3. 在 GV 加入可控參數（`-ConfLimit`、`-DecisionOrder`）後，理論可以直接轉成可觀測實驗，這對後續報告與比較研究很有幫助。

## 7. 表格版對照（課程章節 / code path / 一句心得）

| 課程投影片章節 | miniSat code path | 一句心得 |
|---|---|---|
| Topic 6：SAT 搜尋本質（decision tree + backtrack） | `satsolvers/minisat/Solver.cpp::search()` | `search()` 把「做決策 -> 發現錯誤就回退」變成可執行流程，課堂概念在程式裡非常具體。 |
| Topic 6：BCP（Boolean Constraint Propagation） | `satsolvers/minisat/Solver.cpp::propagate()` | 2-watched literals 是效率關鍵，避免每次都掃整條 clause。 |
| Topic 6：Conflict-driven learning | `satsolvers/minisat/Solver.cpp::analyze()`、`newClause(...)` | 衝突不是失敗，而是「提煉限制」後回灌資料庫，讓後續搜尋更快。 |
| Topic 6：Non-chronological backtrack | `satsolvers/minisat/Solver.cpp::cancelUntil(...)` | 回跳到「必要層級」而非單純退一步，這就是 CDCL 真正加速點。 |
| Topic 7：Decision order 影響效率 | `satsolvers/minisat/Solver.cpp::search()`（`order.select(...)`） | 決策順序直接決定探索樹形狀；同一 CNF 在不同順序下衝突數差異很明顯。 |
| Topic 7：VSIDS / 活動度啟發式 | `satsolvers/minisat/Solver.h::varBumpActivity()`、`varDecayActivity()`、`satsolvers/minisat/VarOrder.h::select()` | miniSat 透過 bump + decay 動態調整優先度，符合課堂「adaptive ordering」精神。 |
| Topic 7：Static vs Dynamic ordering | `src/sat/satCmd.cpp`（`-DecisionOrder`）與 `src/sat/minisatMgr.cpp`（設定 `default_params`） | 把 static/dynamic 做成可切換參數後，理論比較可以直接變成實驗數據。 |
| Topic 7：Database simplification | `satsolvers/minisat/Solver.cpp::simplifyDB()`、`reduceDB()` | 「學太多也會慢」，所以必須定期清理 learnt clauses，平衡品質與成本。 |
| Topic 7：Resource-bounded solving | `satsolvers/minisat/Solver.cpp::solveLimited(...)`、`search(...)` 回 `gv_l_Undef` | `UNKNOWN` 不是錯誤，而是預算下的合理狀態，能清楚呈現 proof effort 概念。 |
| 課堂到工具落地（GV 實作） | `src/sat/satCmd.cpp`、`src/sat/minisatMgr.cpp`、`src/sat/satMgr.h` | 透過 `-ConfLimit` / `-Model` / `-DecisionOrder`，把演算法觀念轉成可重現的 CLI workflow。 |
