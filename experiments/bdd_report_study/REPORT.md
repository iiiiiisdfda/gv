# 書面作答：實驗設計與「指令如何完成」說明

本文整合三個子題的**可重現實驗**與**實作路徑**，供報告或簡報直接引用。

---

## 子題 1：`BSETOrder -DFS | -RDFS` 與 `_dfsList`

### 機制（報告用一段話）

- `CirMgr::genDfsList` 從 **PO、RI** 出發做 DFS，列表為 **post-order**（fanin 先、節點後）。
- `-DFS`：依 `_dfsList` 中 **PI 首次出現順序**（去重）對應到 BDD support。
- `-RDFS`：將上述 PI 順序**反向**。
- 與 `-File/-RFile` 差異：**File/RFile** 依宣告／內部 PI 索引；**DFS/RDFS** 依網表錐狀 traversal。

### 實驗 E1：同一設計、四種排序、量測 BREPort

下列數據由 [`run_four_modes.py`](run_four_modes.py) 自動產生（輸出另存 [`outputs/e1_four_modes_table.md`](outputs/e1_four_modes_table.md)）。

| 模式 | 選項 | brep 筆數 | 節點數加總 | 單 gate 最大節點數 |
|------|------|-----------|------------|-------------------|
| File | `-file` | 224 | 14380 | 890 |
| RFile | `-rfile` | 224 | 8511 | 511 |
| DFS | `-dfs` | 224 | 14380 | 890 |
| RDFS | `-rdfs` | 224 | 8511 | 511 |

**解讀（本 benchmark `designs/SoCV/basic/a.v`）：**

- 僅 **兩個 PI**，DFS 掃到的 PI 順序與 File 順序一致，故 **File 與 DFS**、**RFile 與 RDFS** 數據兩兩相同。
- 節點加總為各 gate 之 `Total #BddNodeVs` 相加（**非**全域去重後的單一圖節點數），用於四種模式**橫向比較**。

**重現指令：**

```bash
python3 experiments/bdd_report_study/run_four_modes.py
```

---

## 子題 2：修改 Verilog「輸入宣告順序」

### 機制

- `CIRWrite -Verilog -Output <檔> [-InputOrder File|RFile|DFS|RDFS]`：Yosys `write_verilog` 後，僅重排 **top module** 的 `input` 單行宣告，**語意不變**。

### 實驗 E2：兩種 `-InputOrder` 產檔與 diff

- 產物：[`outputs/e2_verilog_diff.md`](outputs/e2_verilog_diff.md)、[`outputs/e2_inputorder_file.v`](outputs/e2_inputorder_file.v)、[`outputs/e2_inputorder_rdfs.v`](outputs/e2_inputorder_rdfs.v)
- 自動化：[`run_e2_verilog_diff.sh`](run_e2_verilog_diff.sh)

**重現指令：**

```bash
./experiments/bdd_report_study/run_e2_verilog_diff.sh
```

- 讀回 smoke 與 golden 測試：[`tests/cir/dofile/cirwrite_verilog_inputorder.dofile`](../../tests/cir/dofile/cirwrite_verilog_inputorder.dofile)

---

## 子題 3：不同布林函數與「好」的排序啟發式

### 抽象層實驗（truth-table 函數族）

- 腳本：[`experiments/bdd_ordering_study/run_study.py`](../bdd_ordering_study/run_study.py)
- 產出：[`experiments/bdd_ordering_study/outputs/ordering_study.csv`](../bdd_ordering_study/outputs/ordering_study.csv)、[`heuristics.md`](../bdd_ordering_study/outputs/heuristics.md)

該腳本以「變數影響度」近似 DFS 啟發式；在 **n=8** 的實驗設定下，**File 順序** 對所列函數族節點數較佳。報告應強調：**最佳變數排序為 coNP-hard**，小實驗結論不可推廣為全域規則；宜寫成「依函數型態（對稱、多路選擇、加法進位等）敏感度不同，需實測或動態重排」。

### 電路層（GV）

- 以 **E1** 表為例：真實網表上 **File/DFS** 與 **RFile/RDFS** 可分組對照；多 PI 設計更可能出現 **File ≠ DFS**。

### 與 worst-case 理論（選述）

- [`experiments/robdd_worstcase`](../robdd_worstcase)：理論 `W(n)`、complement edge 對節點數的對照，用於說明「排序與表示法影響實務大小，與最壞情況公式分開討論」。

### 可寫入報告的保守結論

1. **錐狀結構**：從輸出往輸入掃 PI（`-DFS`）有助讓「同一錐內」變數在順序上較連貫，但不保證最小 BDD。
2. **對稱／奇偶類**：對變數排列極敏感，應以實測或已知好順序（如變數分組）為準。
3. **實務流程**：先 `-file` 與 `-dfs` 對照；再試 `-rfile`/`-rdfs`；大型案例可規劃 dynamic reordering 作未來工作。

---

## 「指令如何完成」— 實作路徑（四段）

1. **命令列（`BSETOrder`）**  
   - 檔案：[`src/bdd/bddCmd.cpp`](../../src/bdd/bddCmd.cpp)  
   - 在 `BSetOrderCmd::exec` 解析 `-File|-RFile|-DFS|-RDFS`，呼叫 `cirMgr->setBddOrder(orderMode)`；更新 `usage`/`help`；`help` 測試 golden 見 `tests/common/ref_*/help.log`。

2. **排序語意（PI / FF support）**  
   - 檔案：[`src/cir/cirMgr.h`](../../src/cir/cirMgr.h)（`BddOrderMode`、`collectPiOrder`）、[`src/cir/cirBdd.cpp`](../../src/cir/cirBdd.cpp)（`setBddOrder` 依模式綁定 `bddMgrV` support；`DFS/RDFS` 自 `_dfsList` 擷取 PI；latch 在 `RFile/RDFS` 時與既有反向策略一致）。

3. **Verilog 寫出與 input 重排**  
   - 檔案：[`src/yosys/yosysMgr.cpp`](../../src/yosys/yosysMgr.cpp)（`writeVerilog`）、[`src/cir/cirCmd.cpp`](../../src/cir/cirCmd.cpp)（`CIRWrite -Verilog`、`-InputOrder`、宣告 rewriter）。

4. **驗證與文件**  
   - `scripts/RUN_TEST`：`tests/bdd/dofile/bsetorder_*.dofile`、`tests/cir/dofile/cirwrite_verilog_inputorder.dofile`  
   - 使用者說明：[`docs/BSET_ORDER_AND_VERILOG.md`](../../docs/BSET_ORDER_AND_VERILOG.md)

---

## 附錄：檔案索引

| 用途 | 路徑 |
|------|------|
| E1 表格（自動） | `experiments/bdd_report_study/outputs/e1_four_modes_table.md` |
| E2 diff 說明 | `experiments/bdd_report_study/outputs/e2_verilog_diff.md` |
| 函數族排序研究 | `experiments/bdd_ordering_study/outputs/` |
| 使用說明 | `docs/BSET_ORDER_AND_VERILOG.md` |
