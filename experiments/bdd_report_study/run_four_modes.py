#!/usr/bin/env python3
"""Run GV four BSETOrder modes on the same design and aggregate BREPort node counts."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GV = REPO / "gv"
DESIGN = REPO / "designs" / "SoCV" / "basic" / "a.v"
# Match breport_basic_a.dofile gate range
GATE_MAX = 240


def dofile_for_mode(flag: str) -> str:
    lines = [
        f"cirread -v {DESIGN}",
        "breset 50000 60013 70001",
        f"bsetorder {flag}",
        "bcons -all",
    ]
    lines.extend(f"brep {i}" for i in range(GATE_MAX + 1))
    lines.append("q -f")
    return "\n".join(lines) + "\n"


def run_gv(dofile_path: Path) -> str:
    p = subprocess.run(
        [str(GV), "-file", str(dofile_path)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if p.returncode != 0:
        print(p.stderr, file=sys.stderr)
        sys.exit(p.returncode)
    return p.stdout + p.stderr


def parse_node_totals(out: str) -> list[int]:
    pat = re.compile(r"==>\s*Total #BddNodeVs\s*:\s*(\d+)")
    return [int(m.group(1)) for m in pat.finditer(out)]


def main() -> None:
    modes = [
        ("-file", "File"),
        ("-rfile", "RFile"),
        ("-dfs", "DFS"),
        ("-rdfs", "RDFS"),
    ]
    base = Path(__file__).resolve().parent
    out_dir = base / "outputs"
    tmp_dir = base / "tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for flag, name in modes:
        p = tmp_dir / f"e1_{name.lower()}.dofile"
        p.write_text(dofile_for_mode(flag), encoding="utf-8")
        text = run_gv(p)
        totals = parse_node_totals(text)
        if len(totals) != GATE_MAX + 1:
            print(
                f"note: expected up to {GATE_MAX + 1} brep totals, got {len(totals)} for {flag} (some gates may omit BDD)",
                file=sys.stderr,
            )
        s = sum(totals)
        mx = max(totals) if totals else 0
        rows.append((name, flag, len(totals), s, mx))

    lines = [
        "# E1: 四種 BSETOrder 下 BREPort 節點數彙總",
        "",
        f"- 設計: `{DESIGN.relative_to(REPO)}`",
        f"- 流程: `cirread` → `breset` → `bsetorder` → `bcons -all` → `brep 0..{GATE_MAX}`",
        "- 指標: 各 gate BDD 的 `Total #BddNodeVs` **加總**（每個 gate 獨立計，非全域去重共享節點）。",
        "",
        "| 模式 | 選項 | brep 筆數 | 節點數加總 | 單 gate 最大節點數 |",
        "|------|------|-----------|------------|-------------------|",
    ]
    for name, flag, n, s, mx in rows:
        lines.append(f"| {name} | `{flag}` | {n} | {s} | {mx} |")
    lines.append("")
    lines.append(
        "說明: 加總用於比較不同排序對「各輸出錐 BDD 大小」的相對影響；數值會因共享子圖在不同 gate 重複計入而偏大，但四種模式在相同流程下可橫向比較。"
    )
    (out_dir / "e1_four_modes_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print((out_dir / "e1_four_modes_table.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
