#!/usr/bin/env python3
"""
将 SAT model（如: -1 -2 -3 ... 729）还原为 Sudoku 盘面。

支持 NxN（N 为完全平方数），例如：
  - N=9  -> 9x9
  - N=16 -> 16x16

输入可二选一：
  1) --model "<空格分隔整数列表>"
  2) --model-file <path>  (从文件读取，可包含其它文字；脚本会抓取所有整数 token)

规则：
  - 只读取正文字（正整数）作为 True literal
  - 变量编号映射：id = N*N*(r-1) + N*(c-1) + d
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import List, Optional, Set


def digit_to_symbol(d: int) -> str:
    if 1 <= d <= 9:
        return str(d)
    if 10 <= d <= 35:
        return chr(ord("A") + (d - 10))
    return "?"


def decode_var_id(var_id: int, n: int) -> tuple[int, int, int]:
    """返回 (r, c, d)，皆为 1-based。"""
    v = var_id - 1
    row_block = n * n
    r = v // row_block + 1
    rem = v % row_block
    c = rem // n + 1
    d = rem % n + 1
    return r, c, d


def parse_model_text(text: str) -> Set[int]:
    ints = [int(x) for x in re.findall(r"-?\d+", text)]
    return {x for x in ints if x > 0}


def build_grid_from_true_vars(true_vars: Set[int], n: int) -> List[List[Optional[int]]]:
    grid: List[List[Optional[int]]] = [[None for _ in range(n)] for _ in range(n)]
    for v in sorted(true_vars):
        if v > n * n * n:
            continue
        r, c, d = decode_var_id(v, n)
        rr = r - 1
        cc = c - 1
        if grid[rr][cc] is None:
            grid[rr][cc] = d
        elif grid[rr][cc] != d:
            # 模型异常：同一格多个数字为真
            raise ValueError(f"模型不一致：cell ({r},{c}) 同时出现 {grid[rr][cc]} 与 {d}")
    return grid


def grid_to_compact_line(grid: List[List[Optional[int]]]) -> str:
    out: List[str] = []
    for row in grid:
        for d in row:
            out.append(digit_to_symbol(d) if d is not None else "0")
    return "".join(out)


def print_pretty_grid(grid: List[List[Optional[int]]]) -> None:
    n = len(grid)
    k = int(math.isqrt(n))
    hline_parts = []
    for _ in range(k):
        hline_parts.append("-" * (2 * k + 1))
    hline = "+".join(hline_parts)

    for r in range(n):
        if r % k == 0:
            print(hline)
        row_cells: List[str] = []
        for c in range(n):
            d = grid[r][c]
            sym = digit_to_symbol(d) if d is not None else "."
            row_cells.append(sym)
        chunks = [" ".join(row_cells[i : i + k]) for i in range(0, n, k)]
        print("|".join(chunks))
    print(hline)


def main() -> None:
    ap = argparse.ArgumentParser(description="Decode SAT model to Sudoku grid")
    ap.add_argument("--size", type=int, default=9, help="Sudoku size N (e.g. 9, 16)")
    ap.add_argument("--model", default=None, help="Model literals string")
    ap.add_argument("--model-file", default=None, help="Read model text from file")
    args = ap.parse_args()

    n = args.size
    k = int(math.isqrt(n))
    if k * k != n:
        raise SystemExit("N 必须是完全平方数")
    if bool(args.model) == bool(args.model_file):
        raise SystemExit("必须且只能提供 --model 或 --model-file 其中之一")

    text = args.model if args.model is not None else Path(args.model_file).read_text(encoding="utf-8", errors="replace")
    true_vars = parse_model_text(text)
    grid = build_grid_from_true_vars(true_vars, n)

    print("Compact:")
    print(grid_to_compact_line(grid))
    print("\nGrid:")
    print_pretty_grid(grid)


if __name__ == "__main__":
    main()

