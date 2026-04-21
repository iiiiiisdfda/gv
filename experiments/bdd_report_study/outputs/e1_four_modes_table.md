# E1: 四種 BSETOrder 下 BREPort 節點數彙總

- 設計: `designs/SoCV/basic/a.v`
- 流程: `cirread` → `breset` → `bsetorder` → `bcons -all` → `brep 0..240`
- 指標: 各 gate BDD 的 `Total #BddNodeVs` **加總**（每個 gate 獨立計，非全域去重共享節點）。

| 模式 | 選項 | brep 筆數 | 節點數加總 | 單 gate 最大節點數 |
|------|------|-----------|------------|-------------------|
| File | `-file` | 224 | 14380 | 890 |
| RFile | `-rfile` | 224 | 8511 | 511 |
| DFS | `-dfs` | 224 | 14380 | 890 |
| RDFS | `-rdfs` | 224 | 8511 | 511 |

說明: 加總用於比較不同排序對「各輸出錐 BDD 大小」的相對影響；數值會因共享子圖在不同 gate 重複計入而偏大，但四種模式在相同流程下可橫向比較。
