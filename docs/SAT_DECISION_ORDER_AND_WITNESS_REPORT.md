# SAT Decision Order 與 Witness 實作報告

## 1) 實作目標

本次我在 GV 的 `SATSolve DIMACS` 指令上完成兩個 SAT 功能：

- `-DecisionOrder <VSIDS|STATIC>`：可切換決策變數順序策略。
- `-Witness <literal>`：在 SAT 時回報指定 DIMACS literal 的真值。


## 2) DecisionOrder 功能實作（我完成）

### (a) 指令解析層

我在 `src/sat/satCmd.cpp` 的 `SATSolve DIMACS` 選項解析加入 `-DecisionOrder`：

- 接受 `VSIDS` 或 `STATIC`
- 轉成布林旗標 `static_decision_order`
- 針對重複參數、缺少參數、非法字串做錯誤處理

### (b) 介面傳遞層

我擴充 `solve_dimacs_cnf()` 介面，讓 decision order 設定可由 command 傳到 solver：

- `src/sat/satMgr.h`
- `src/sat/minisatMgr.h`
- `src/sat/minisatMgr.cpp`

### (c) Solver 設定層

我在 `src/sat/minisatMgr.cpp` 中，DIMACS 載入完成後、求解前加入：

- `default_params.var_decay = -1.0`
- `default_params.random_var_freq = 0.0`

當使用 `STATIC` 時，以上設定會讓流程接近固定變數順序，不走一般 VSIDS 動態活性更新。

### (d) 輸出可驗證性

我在統計列增加模式標記，`STATIC` 會印出：

- `decision_order=STATIC`

可直接從 log 驗證是否啟用正確策略。

## 3) Witness 功能實作（我完成）

### (a) 功能定義

我新增 `-Witness <non-zero-int-literal>`，用途是：

- 若結果為 `SAT`，回報指定 DIMACS literal 在 model 下的值
- 支援正、負 literal（例如 `6`、`-6`）
- 若 literal 超出範圍，輸出錯誤訊息但不影響求解流程

### (b) 主要修改檔案

- `src/sat/satCmd.cpp`：加入 `-Witness` 參數解析與 usage 說明
- `src/sat/satMgr.h`：擴充 `solve_dimacs_cnf(...)` 介面參數
- `src/sat/minisatMgr.h`：同步函式宣告
- `src/sat/minisatMgr.cpp`：SAT 結果下輸出 witness 資訊

### (c) 輸出格式

SAT 且 `-Witness` 啟用時，會輸出：

- `GV_DIMACS_WITNESS literal=<L> variable=<abs(L)> variable_value=<0|1> literal_value=<0|1>`

## 4) 使用方式

### DecisionOrder

```bash
satsolve dimacs -file ./testbench/dimacs_sat.txt -decisionorder VSIDS
satsolve dimacs -file ./testbench/dimacs_sat.txt -decisionorder STATIC
```

### Witness

```bash
satsolve dimacs -file ./testbench/dimacs_sat.txt -witness 6
satsolve dimacs -file ./testbench/dimacs_sat.txt -witness -6
```

### 組合使用

```bash
satsolve dimacs -file ./testbench/dimacs_sat.txt -conflimit 2000 -decisionorder STATIC -witness 6
```

## 5) 實測結果

測試環境：本機編譯後以 `./gv` 執行。

### (a) DecisionOrder 驗證

- `VSIDS`：結果為 `SAT`
- `STATIC`：結果為 `SAT`，且統計列包含 `decision_order=STATIC`

因此可確認我加入的 decision order 切換有生效。

### (b) Witness 驗證

- `-witness 6` 輸出：`literal_value=1`
- `-witness -6` 輸出：`literal_value=0`
- 在 UNSAT case（`dimacs_unsat.txt`）下不輸出 witness（因無 SAT model）

因此可確認 witness 功能在 SAT/UNSAT 兩種情況的行為都符合預期。

## 6) 結論

- 我完成了 `-DecisionOrder <VSIDS|STATIC>` 與 `-Witness <literal>` 兩個功能。
- `DecisionOrder` 不是註解功能，而是可實際使用並可從輸出驗證的完整實作。
- `Witness` 能提供單一 literal 的 model 見證，提升 DIMACS 問題除錯與分析效率。
