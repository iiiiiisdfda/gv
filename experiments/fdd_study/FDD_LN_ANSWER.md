# [LN] Playing with different DDs — FDD Standalone 作答

本回答對應你原先 3 個問題，並基於本 repo 可重跑的實驗產物整理。

## 0. 我這次「FDD 做看看」的定義

為了先拿到可重跑結果、且不入侵 GV 核心，本次採 **standalone FDD 原型**：

- 固定變數順序（ordered）
- reduced DAG（共享子圖）
- 每層允許三種分解並取較小者：
  - Shannon
  - Positive Davio
  - Negative Davio

這是一個「可比較趨勢」的 FDD 近似原型，不是最終的 GV 內建 FDD engine。

---

## 1) 用 FDD 比較 DD node 數：怎麼做、結果是什麼

### 實驗設定

- 腳本：`experiments/fdd_study/run_fdd_vs_robdd.py`
- 函數族：`parity`, `mux`, `adder_lsb`, `majority`, `random`
- 規模：`n = 4..10`
- 排序：`File` 與 `RFile`
- 指標：
  - `robdd_nodes`, `fdd_nodes`（含 terminals）
  - `ratio_fdd_over_robdd`
  - runtime

### 重現方式

```bash
python3 experiments/fdd_study/run_fdd_vs_robdd.py
```

輸出：

- `experiments/fdd_study/outputs/fdd_vs_robdd.csv`
- `experiments/fdd_study/outputs/fdd_vs_robdd_plot.png`
- `experiments/fdd_study/outputs/summary.md`

### 結果摘要（File 平均）

`summary.md` 顯示：

- n=4: ratio ≈ 0.8317
- n=10: ratio ≈ 0.8363

代表在這個原型與函數集合下，**FDD 節點數平均約為 ROBDD 的 84% 左右**（有壓縮優勢）。

> 注意：這是 small-n 原型趨勢，不是理論最終定論。

---

## 2) 如何與你前面的 GV 實作（BSETOrder / Verilog input order）連結

你前面做的兩件事，剛好提供了「電路層」對照：

- BDD ordering：`experiments/bdd_report_study/REPORT.md`
- Worst-case 與 complement edge：`experiments/robdd_worstcase/outputs/report.md`

可在報告中明確分成兩層：

1. **GV 電路層（真網表）**
   - 比較 `-file/-rfile/-dfs/-rdfs` 對 BDD 大小影響
   - 驗證 Verilog `-InputOrder` 可控且可讀回
2. **FDD standalone 函數層**
   - 比較 FDD vs ROBDD 的節點比值

這樣敘事清楚，也能避免「把不同層級實驗混在一起」。

---

## 3) Any creative research idea?（可落地）

### Idea A: Hybrid ordering

- 先用 `DFS` 當初始排序
- 再做小範圍 swap（hill-climb）
- 目標函數：最小化 `BREPort` 節點總和或關鍵輸出節點數

### Idea B: Function-aware DD selection

- 先抽特徵（對稱性、影響度分布、算術結構）
- 規則式選擇 `ROBDD` 或 `FDD`，再選 `File/DFS/RFile/RDFS`
- 產出一個 policy table（類似 autotuner）

---

## 4) 對「good heuristics」的保守結論

1. **先做 ordering，再談 DD 類型**  
   在真實網表上，ordering 影響很大；先跑 `File/DFS/RFile/RDFS` baseline。

2. **算術/代數結構可優先嘗試 FDD 類分解**  
   本次原型在函數族平均上有 node 優勢（ratio < 1）。

3. **不要宣稱單一全勝**  
   變數排序最佳化本質困難（coNP-hard 背景），應採「先驗 + 實測」流程。

4. **報告寫法建議**  
   用「趨勢」與「適用條件」描述，不做過度外推。

---

## 5) 下一步（若要升級成課題）

- 把 standalone FDD 逐步搬進 GV（MVP）：
  - `FReset/FSetOrder/FConstruct/FReport`
  - 跟現有 `BSETOrder` 接口對齊
- 把 benchmark 從函數層擴到更多真實算術設計（adder tree, multiplier slice）
- 加上記憶體與構建時間的完整 profile

