# BSETOrder（DFS / RDFS）與 Verilog 輸入順序

本文件說明 GV 中 **BDD 變數排序** 與 **Verilog 輸出時 input 宣告順序** 的用法，以及如何驗證。

## 前置條件

- 已編譯 `gv`（專案根目錄執行 `make`）。
- 使用 **setup 模式**（讀入電路後）才能執行 `BSETOrder`、`CIRWrite` 等指令。

## 一、`BSETOrder`：四種變數順序

### 語法

```text
BSETOrder < -File | -RFile | -DFS | -RDFS >
```

- 每個指令**只能選一個**選項；同一 session 內**只能成功** `BSETOrder` 一次（若已設定會警告）。
- 執行 `BSETOrder` 前通常要先 `BRESET`（依設計規模調整 support / hash / cache 大小），並在讀入電路之後。

### 各模式意義

| 選項 | 說明 |
|------|------|
| `-File` | 依 **PI 在檔案／內部列表中的正序** 對應到 BDD support。 |
| `-RFile` | 依 **PI 反序**（與 `-File` 相反）。 |
| `-DFS` | 依 **DFS 後序列表 `_dfsList`** 中 PI 首次出現的順序（從 PO、RI 開始 DFS 後收集到的 PI 順序）。 |
| `-RDFS` | 與 `-DFS` **相反順序**（仍從 `_dfsList` 擷取 PI，去重後再反向）。 |

若序時電路含 latch，FF 的 **CS / NS** 對應與舊行為一致：`-File`/`-DFS` 為同向；`-RFile`/`-RDFS` 為反向（與 `RFile` 時對 RO/RI 的處理一致）。

### 使用範例（互動）

```text
cirread -v ./designs/SoCV/basic/a.v
breset 50000 60013 70001
bsetorder -dfs
bconstruct -all
```

將 `-dfs` 換成 `-rdfs`、`-file`、`-rfile` 即可比較不同排序。

### 常見錯誤

- `BDD Support Size is Smaller Than Current Design Required`：`BRESET` 的第一個參數（support 數量）需大於 `PI + 2×Latch` 所需。

---

## 二、`CIRWrite`：輸出 Verilog 並重排 `input` 宣告

### 語法

```text
CIRWrite -Verilog -Output <檔名> [-InputOrder File|RFile|DFS|RDFS]
```

- 必須先讀入電路（`CIRRead`）。
- `-Output` 指定輸出檔路徑。
- `-InputOrder`（可選）：輸出後對 **top module 的 `input` 單行宣告** 依指定順序重排；**只改宣告順序，不改邏輯**。
- 若省略 `-InputOrder`，預設為 `File`（即沿用 `collectPiOrder` 的 `File` 語意）。

### 使用範例

```text
cirread -v ./designs/SoCV/basic/a.v
cirwrite -verilog -output /tmp/out.v -inputorder rdfs
```

再以 `CIRRead -Replace` 讀回驗證：

```text
cirread -v /tmp/out.v -replace
cirprint -pi
```

---

## 三、如何驗證

### 1. 自動回歸（建議）

在專案根目錄執行 `scripts/RUN_TEST`，並指定下列 dofile（會與 `ref_linux` / `ref_macos` 下的 golden log 比對）：

```bash
scripts/RUN_TEST \
  tests/bdd/dofile/bsetorder_dfs.dofile \
  tests/bdd/dofile/bsetorder_rdfs.dofile \
  tests/cir/dofile/cirwrite_verilog_inputorder.dofile
```

全部通過表示：

- `BSETOrder -dfs` / `-rdfs` 可正常完成設定。
- `CIRWrite -Verilog` 搭配 `-InputOrder` 可產檔，且讀回後 `CIRPrint -PI` 與預期一致。

更新 golden（若刻意改輸出）：

```bash
scripts/RUN_TEST -u tests/bdd/dofile/bsetorder_dfs.dofile
```

### 2. 手動驗證 BDD 排序差異

- 同一設計、同一 `BRESET` 參數下，依次執行 `bsetorder -file`、`-dfs` 等（需重開 session 或重置 BDD 狀態；實務上可寫多個 dofile 分別跑）。
- 對同一輸出節點用 `BREPort <bddName>` 比較 **節點數** 是否不同（排序會影響 BDD 大小）。

### 3. 手動驗證 Verilog 輸入順序

- 用 `CIRWrite -Verilog` 產生兩個檔案，分別使用 `-InputOrder file` 與 `-InputOrder rdfs`。
- 用 `diff` 比對兩檔中 `input` 宣告區塊順序是否不同。
- 邏輯等價可依團隊流程用模擬或其它工具交叉檢查。

---

## 四、排序實驗腳本（選用）

專案內含獨立 Python 實驗（非 GV 內建指令），用於比較不同排序對小型布林函數的 ROBDD 節點數：

```bash
python3 experiments/bdd_ordering_study/run_study.py
```

輸出會寫在 `experiments/bdd_ordering_study/outputs/`（含 CSV 與簡短結論）。

---

## 五、相關程式位置（方便維護）

| 項目 | 檔案 |
|------|------|
| `BSETOrder` 解析 | `src/bdd/bddCmd.cpp` |
| `setBddOrder` / PI 順序 | `src/cir/cirBdd.cpp`、`src/cir/cirMgr.h`（`BddOrderMode`、`collectPiOrder`） |
| DFS 列表來源 | `src/cir/cirMgr.cpp`（`genDfsList`） |
| `CIRWrite -Verilog` | `src/cir/cirCmd.cpp` |
| Yosys `write_verilog` | `src/yosys/yosysMgr.cpp`（`writeVerilog`） |

## 六、書面報告（實驗數據與實作敘述）

可一併參考 [`experiments/bdd_report_study/REPORT.md`](../experiments/bdd_report_study/REPORT.md)（含 E1/E2 重現方式與「指令如何完成」條列）。
