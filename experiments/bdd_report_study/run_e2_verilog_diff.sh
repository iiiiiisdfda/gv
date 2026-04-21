#!/usr/bin/env bash
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$REPO/experiments/bdd_report_study/outputs"
mkdir -p "$OUT"
DO="$OUT/e2_run.dofile"
cat >"$DO" <<'EOF'
cirread -v ./designs/SoCV/basic/a.v
cirwrite -verilog -output ./experiments/bdd_report_study/outputs/e2_inputorder_file.v -inputorder file
cirwrite -verilog -output ./experiments/bdd_report_study/outputs/e2_inputorder_rdfs.v -inputorder rdfs
q -f
EOF
"$REPO/gv" -file "$DO" >/dev/null
{
  echo '# E2: Verilog input 宣告順序差異（excerpt）'
  echo ""
  echo "## grep input（兩檔）"
  echo ""
  echo "### -inputorder file"
  grep -E '^\s*input\s' "$OUT/e2_inputorder_file.v" | head -40 || true
  echo ""
  echo "### -inputorder rdfs"
  grep -E '^\s*input\s' "$OUT/e2_inputorder_rdfs.v" | head -40 || true
  echo ""
  echo "## diff -u（input 行）"
  diff -u <(grep -E '^\s*input\s' "$OUT/e2_inputorder_file.v") <(grep -E '^\s*input\s' "$OUT/e2_inputorder_rdfs.v") || true
  echo ""
  echo "## 說明"
  echo ""
  echo "- \`basic/a.v\` 僅兩個 PI（reset, clk），且 Yosys 寫出時可能與內部 PI 順序一致，故兩種 \`-InputOrder\` 的 \`input\` 行常相同。"
  echo "- 多 PI、多行 \`input\` 宣告的設計較易觀察順序差異；讀回驗證可參考 \`tests/cir/dofile/cirwrite_verilog_inputorder.dofile\`。"
} >"$OUT/e2_verilog_diff.md"
