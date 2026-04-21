# [LN] Implement BDD-Based Assertion Checking in GV

## 1. 目標

本 Learning Note 的目標是完成 GV 的 BDD-based assertion checker，讓以下指令可真正工作：

- `PINITialstate`
- `PTRansrelation`
- `PIMAGe`
- `PCHECKProperty`

核心概念是以 BDD 表示「狀態集合」與「轉移關係」，透過 image 計算可達狀態，再檢查 monitor 是否可達。

---

## 2. 程式實作重點

## 2.1 啟用 prove 指令

在 `main.cpp`：

- 開啟 `extern bool initProveCmd();`
- 在初始化鏈加入 `&& initProveCmd()`

使 `prove/proveCmd.cpp` 中的 prove commands 被系統註冊。

## 2.2 補齊 prove 演算法（原空函式）

實作檔案：`src/prove/proveBdd.cpp`

已補函式：

- `buildPInitialState()`
- `buildPTransRelation()`
- `buildPImage(int level)`
- `runPCheckProperty(const string&, BddNodeV monitor)`
- `find_ns(BddNodeV cs)`
- `ns_to_cs(BddNodeV ns)`

並在 `src/bdd/bddMgrV.cpp` 的 `reset()` 補 proof 狀態清理：

- `_isFixed`
- `_initState`
- `_tr`
- `_tri`
- `_reachStates`

---

## 3. BDD assertion checker 原理

## 3.1 Initial state

將所有 current-state FF 初始化為 0：

$$
Init(CS)=\bigwedge_i \neg CS_i
$$

對應 `PINITialstate`。

## 3.2 Transition relation

對每個 latch i 建立：

$$
TR_i = (NS_i \leftrightarrow F_i(CS,PI))
$$

整體：

$$
TR = \bigwedge_i TR_i
$$

對應 `PTRansrelation`。

## 3.3 Image 計算

下一步可達狀態：

$$
Image_{NS}(R)=\exists_{CS,PI}(R(CS)\wedge TR(CS,PI,NS))
$$

再把 NS 變數映回 CS 變數空間，得到下一輪 reachable states。  
若 reachable 不再成長，達到 fixed point。  
對應 `PIMAGe`。

## 3.4 Property check

令 `Reach` 為目前可達集合，`Monitor` 為輸出 property BDD：

$$
Bad = Reach \wedge Monitor
$$

- `Bad == 0`：safe
- `Bad != 0`：violated

對應 `PCHECKProperty`。

---

## 4. 使用流程（dofile）

```bash
cirread -v <design.v>
breset <nSupports> <hashSize> <cacheSize>
bsetorder -file
bconstruct -all
set system vrf
pinit init
ptrans tri tr
pimage -n <k> reachK
pcheckp -o <idx>
```

注意：

- `nSupports` 要滿足 `#PI + 2*#FF`
- `cirread` 失敗時不可繼續 prove 命令
- 大設計可能出現 BDD memory explosion

---

## 5. 實驗與結果

## 5.1 basic 設計（回歸）

`tests/full/prove/dofile/prove_bdd.dofile` 可通過，代表 prove pipeline 可運作。

## 5.2 traffic 設計（`designs/V3/traffic/traffic.v`）

使用 `tests/full/prove/dofile/prove_traffic.dofile`：

- 在 `pimage -n 30` 後：
  - `p1` safe
  - `p2` safe
  - `p3` safe
- 再做 `pimage -n 50`（更深）後：
  - `p1` safe
  - `p2` safe
  - `p3` violated

結論：小深度 safe 不代表全域 safe；更深可達集合會暴露反例。

## 5.3 vending 設計

vending 類設計在 `PTRansrelation` / image 計算較容易爆，符合 BDD memory explosion 特性。  
已進行簡化（如 `vending-mini.v`）以降低複雜度。

---

## 6. Debug 心得

- 先用小設計（basic / traffic）確認 checker 正確，再跑大型設計。
- 若 violation 發生，要區分是 design bug 或 assertion 定義錯誤。
- `bsetorder` 對 BDD 大小影響大，可比較 `-file/-dfs/-rdfs`。

---

## 7. 限制與未來工作

- 目前只報 safe/violated，未輸出 counterexample trace。
- 尚未做 dynamic variable reordering。
- 可擴充：
  - 反例路徑回溯
  - 分割式 TR（partitioned transition relation）
  - 自動排序策略選擇

---

## 8. 總結

本次完成了 GV 內 BDD assertion checker 的核心演算法與命令整合。  
`PINITialstate/PTRansrelation/PIMAGe/PCHECKProperty` 可在真實設計上運作，並能檢出深層可達反例。  
同時驗證了 BDD 在中大型設計上的記憶體與時間瓶頸，後續需搭配抽象化與更進階優化方法。

