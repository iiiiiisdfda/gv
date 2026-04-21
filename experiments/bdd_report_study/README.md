# BDD 排序實驗與書面報告產物

- **完整報告（實驗設計 + 指令實作說明）**：[REPORT.md](REPORT.md)

## 重新產生數據

```bash
# E1：四種 BSETOrder 與 BREPort 加總表
python3 experiments/bdd_report_study/run_four_modes.py

# E2：兩份 Verilog 與 input 行 diff
./experiments/bdd_report_study/run_e2_verilog_diff.sh
```

中間 dofile 會寫在 `experiments/bdd_report_study/tmp/`（可刪除，每次執行會重建）。
