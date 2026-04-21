# Vending 設計簡化報告（for BDD Assertion Checking）

## 目標

本次簡化的核心目標是讓 `vending` 設計更適合 BDD-based assertion checking，降低狀態空間與布林函數複雜度，減少 `ptrans/pimage` 卡住或記憶體爆炸的機率。

---

## 簡化重點總覽

- 幣種由多幣種縮減為兩種：僅保留 `COIN_HIGH(=5)` 與 `COIN_LOW(=1)`
- 商品由多商品縮減為單商品：僅保留 `ITEM_NONE` / `ITEM_A`
- 移除未使用欄位與對應邏輯（含 I/O 與內部 state）
- 主要金額暫存器位寬下修：`inputValue/serviceValue` 由 `8-bit` 降到 `6-bit`，再降到 `4-bit`
- 面額與價格縮放：高面額由 `10` 縮放為 `5`，`COST_A` 由 `8` 改為 `4`
- 找零/輸出計算同步改為較小位寬，降低算術電路複雜度

---

## 實際修改項目

### 1) 幣種與商品集合縮減

設計從原本較完整的販賣機行為，縮成驗證友善版本：

- 保留幣種：`COIN_HIGH`、`COIN_LOW`
- 移除幣種：`NTD_50`、`NTD_5`
- 保留商品：`ITEM_A`
- 移除其他商品與其對應分支邏輯

效益：

- 減少輸入組合（PI 空間縮小）
- 減少分支條件數，降低 transition relation 複雜度

### 2) 狀態變數與輸出欄位清理

已移除不再使用的欄位/邏輯：

- `coinInNTD_50`, `coinInNTD_5`
- `coinOutNTD_50`, `coinOutNTD_5`
- `countNTD_50`, `countNTD_5`

效益：

- 減少 FF 與組合邏輯依賴
- 降低 BDD 支援變數數量與節點成長速度

### 3) 位寬下修與數值縮放

分兩階段下修：

1. `8-bit -> 6-bit`
2. `6-bit -> 4-bit`

目前版本：

- `inputValue`: `4-bit`
- `serviceValue`: `4-bit`
- `outExchange`: `4-bit`（由輸出幣值計算）
- 幣值常數：`VALUE_COIN_HIGH = 4'd5`, `VALUE_COIN_LOW = 4'd1`
- 商品成本：`COST_A = 4'd4`

效益：

- 加法/比較/乘法網路變小
- BDD 對算術邏輯的展開成本下降

### 4) Property 介面擴充

除原本 `p` 外，補上 `p1`、`p2` 供 `pcheckp -o 1/-o 2` 使用，形成多 monitor 檢查流程。

注意：

- 在此流程中，`p* = 1` 代表「bad condition 可達」
- property 應定義成「違反條件」，不是「正常條件」

---

## 對 BDD 驗證的直接影響

簡化後，`cirread` 觀察到的 DC-valued FF 已下降（例如近期版本降到 22），反映設計狀態面向已被有效壓縮。  
這通常會改善：

- `PTRansrelation` 建構成功率與速度
- `PIMAGe` 可推進深度
- 記憶體使用峰值

但即使簡化後，販賣機仍可能在較深 image 時變慢；此時需再搭配：

- 更保守的 image 深度（例如 5/10/20 漸進）
- 嘗試不同 BDD ordering（`-dfs` / `-rdfs`）
- 把 property 聚焦在更小的安全性條件

---

## 後續可再簡化方向（若仍太慢）

1. 移除庫存限制（`count*`）改成無限找零假設
2. 移除逐步找零流程，改單拍計算
3. 避免一般乘法（以比較/查表替代）
4. 將 coin input 由多 bit 數量改成 1-bit 事件
5. 先驗核心 property，再逐步加回完整規格

---

## 結論

本次簡化的策略是「先保留最小行為語意，再最大幅度降低狀態與算術複雜度」。  
對 BDD assertion checking 而言，這類縮減通常比微調參數更有效，能明顯提升 `ptrans/pimage/pcheckp` 的可執行性與穩定性。
