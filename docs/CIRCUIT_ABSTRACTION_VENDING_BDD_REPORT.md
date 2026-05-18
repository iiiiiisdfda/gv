# 比較視角：Vending 設計上的三種過近似抽象與 BDD 再證明

> **主題**：形式驗證 — 電路過近似抽象（over-approximation）  
> **對象**：`vending-mini` 自動販賣機  
> **引擎**：GV（BDD 為主的 assertion checking）  
> **日期**：2026-05-18

---

## 前言：為何要做「橫向比較」？

在同一組安全性性質（以 bad condition 表示，值為 1 代表違反）下，我們將**具體設計**與**三種過近似抽象變體**並列：各自重新建立轉移影像、跑 `pcheckp`，再比對**牆鐘時間**、**不動點步數**與**性質判定**。過近似下 **SAFE ⇒ 原設計 SAFE**（結論可靠）；**VIOLATED** 則可能是偽反例，須與具體模型對照解讀——這正是本文比較軸心。

---

## 一、四個「選手」：基準與三種抽象

| 角色 | 檔案 | 過近似手法（摘要） |
|------|------|-------------------|
| **基準（具體）** | `vending-mini.v` | 無抽象 |
| **抽象 A：count** | `vending-mini-abs-count.v` | `countHigh` / `countLow` 改由自由輸入 `countHigh_nxt`、`countLow_nxt` 驅動；庫存不再遵守真實增減，可出現物理上不可能的庫存組合 |
| **抽象 B：change** | `vending-mini-abs-change.v` | `serviceValue`、`serviceCoinType`、`exchangeReady` 改由自由輸入驅動；`SERVICE_BUSY` 僅保留粗粒度 FSM；多步找零被抹平，內部金額關係大幅鬆弛 |
| **抽象 C：output** | `vending-mini-abs-output.v` | `coinOutHigh`、`coinOutLow`、`itemTypeOut` 改由自由輸入驅動；輸出可任意跳變，最易在金額相關性質上「誤報」違反 |

**性質對照**（均為 bad condition）：

- **p**：服務結束且無商品時，找零總額應等於投入  
- **p1**：非法 service 編碼  
- **p2**：輸出金額大於投入  

---

## 二、實驗設定：確保「可比性」

| 項目 | 內容 |
|------|------|
| 工具 | `./gv` |
| 流程 | `cirread` → `breset` → `bsetorder -dfs` → `bconstruct -all` → `pinit` → `ptrans` → `pimage` → `pcheckp` |
| Dofile | 基準：`prove_vending_mini.dofile`；count / change / output 分別對應 `prove_vending_abs_count.dofile`、`prove_vending_abs_change.dofile`、`prove_vending_abs_output.dofile` |
| 參數 | 統一：`breset 2000 100003 200003`；先 `pimage -n 10` 後 `pcheckp -o 0/1/2`，再 `pimage -n 30` 後再次 `pcheckp` |

---

## 三、結果對照：時間、深度與判定

### 3.1 總表（橫向比較）

| 設計 | 牆鐘時間 | 不動點步數 | p | p1 | p2 |
|------|----------|------------|---|----|----|
| **vending-mini（具體）** | **149.5 s** | 27 | ✅ safe | ✅ safe | ✅ safe |
| abs-count | 152.8 s | 12 | 淺影像 ✅ → 深影像 ❌ | ✅ safe | ✅ safe |
| abs-change | **74.8 s** | 7 | ✅ safe | ✅ safe | ✅ safe |
| abs-output | **28.3 s** | 7 | ❌ violated | ✅ safe | ❌ violated |

註：GV 訊息中 `Monitor "p[0]" is safe` 表示該 bad condition 不可達；`violated` 表示可達。

### 3.2 速度與深度的視覺對照

```
具體設計     ████████████████████████████████  149.5 s
abs-count    ████████████████████████████████  152.8 s  （幾乎無加速）
abs-change   ████████████████                   74.8 s  （約 2.0×）
abs-output   ██████                             28.3 s  （約 5.3×）
```

### 3.3 比較式解讀（誰快、誰準？）

| 比較維度 | abs-count | abs-change | abs-output |
|----------|-----------|------------|------------|
| **相對具體設計的加速** | 無（總時間相近） | 約 **2×** | 約 **5.3×** |
| **不動點深度** | 12 步（較淺） | 7 步 | 7 步 |
| **與具體結論是否一致** | 深影像後 **p** 與具體不同（具體為 safe） | 三性質皆 safe，**可推斷具體亦 safe** | **p、p2** violated，與具體矛盾 |
| **務實評語** | 影像較快但新增 PI 可能放大 `ptrans` BDD；淺 safe、深 violated 顯示偽壞狀態可能需更深才進入 Reach | **速度與可靠性較平衡** | **最快但最易偽反例**（輸出自由賦值易構造金額不合理軌跡） |

---

## 四、小結：三種抽象怎麼選？

若目標是**在過近似下仍得到可遷移到具體設計的 SAFE 結論**，三者中以 **abs-change** 最符合：約兩倍加速且 p、p1、p2 全數 safe。**abs-output** 適合當「效能上限」對照組，但 violated 應視為精化或反例重放的對象，不宜直接當作設計錯誤。**abs-count** 則凸顯「影像深度」與偽反例的交互：總時間未必下降，且可能出現深影像才顯現的 violated。

---

## 附錄：路徑與性質（供重現）

**設計檔**

```
designs/SoCV/vending/
├── vending-mini.v
├── vending-mini-abs-count.v
├── vending-mini-abs-change.v
└── vending-mini-abs-output.v

tests/full/prove/dofile/
├── prove_vending_mini.dofile
├── prove_vending_abs_count.dofile
├── prove_vending_abs_change.dofile
└── prove_vending_abs_output.dofile
```

**性質（摘錄）**

```verilog
assign p = initialized && (serviceTypeOut == SERVICE_OFF) &&
           (itemTypeOut == ITEM_NONE) && (outExchange != inputValue);

assign p1 = initialized && !((serviceTypeOut == SERVICE_OFF) ||
           (serviceTypeOut == SERVICE_BUSY) || (serviceTypeOut == SERVICE_ON));

assign p2 = initialized && ((serviceTypeOut == SERVICE_OFF) ||
           (serviceTypeOut == SERVICE_BUSY)) && (outExchange > inputValue);
```

---

*本報告僅整理（3） vending 上三種過近似與 BDD 再證明之對照數據與解讀。*
