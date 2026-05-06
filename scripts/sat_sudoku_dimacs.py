#!/usr/bin/env python3
"""
将 Sudoku 编码为 CNF（DIMACS）。

支持 NxN（N 必须是完全平方数），例如：
  - N=9  -> 9x9 Sudoku
  - N=16 -> 16x16 Sudoku

布林变量 x[r,c,d]：格子 (r,c) 是否填入数字 d，其中：
  - r, c, d 皆为 1..N
  - DIMACS 变量编号：id = N*N*(r-1) + N*(c-1) + d

输入格式（两种其一）：
  1) --puzzle "<N*N字符>"
  2) --puzzle-file <path>（读取文件中的首个有效 puzzle）

谜题字符约定：
  - 空白：`0` 或 `.`
  - 数字：1..9 用字符 `1`..`9`
  - >=10 用大写字母：A=10, B=11, ...（最大支持到 N=36 以内的字符范围）

输出：
  - DIMACS CNF 文件，可直接给 GV:
      SATSolve DIMACS -File <your.cnf>
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


def var_id(n: int, r: int, c: int, d: int) -> int:
    """r, c, d 为 1-based。"""
    return n * n * (r - 1) + n * (c - 1) + d


def digit_to_symbol(d: int) -> str:
    if 1 <= d <= 9:
        return str(d)
    if 10 <= d <= 35:
        return chr(ord("A") + (d - 10))
    raise ValueError(f"Unsupported digit for symbol mapping: d={d}")


def symbol_to_digit(ch: str) -> Optional[int]:
    if ch in ("0", "."):
        return None
    if "1" <= ch <= "9":
        return int(ch)
    up = ch.upper()
    if "A" <= up <= "Z":
        return 10 + (ord(up) - ord("A"))
    return None


def normalize_puzzle(text: str, n: int) -> str:
    allowed = set("0123456789.") | set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    chars = [ch for ch in text if ch in allowed]
    expected = n * n
    if len(chars) != expected:
        raise ValueError(f"谜题长度错误：过滤后得到 {len(chars)} 个字符，预期 {expected}（N={n}）")
    return "".join(chars)


def read_puzzle_from_file(path: Path, n: int) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return normalize_puzzle(raw, n)


def parse_givens(puzzle: str, n: int) -> List[Tuple[int, int, int]]:
    givens: List[Tuple[int, int, int]] = []
    for idx, ch in enumerate(puzzle):
        d = symbol_to_digit(ch)
        if d is None:
            continue
        if d < 1 or d > n:
            raise ValueError(f"谜题中存在超出范围的数字：ch={ch} -> d={d}, but N={n}")
        r = idx // n + 1
        c = idx % n + 1
        givens.append((r, c, d))
    return givens


def encode_sudoku_cnf(n: int, givens: Sequence[Tuple[int, int, int]]) -> Tuple[int, List[List[int]]]:
    box = int(math.isqrt(n))
    if box * box != n:
        raise ValueError(f"N={n} 不是完全平方数，无法得到标准子宫大小")

    digits = range(1, n + 1)
    clauses: List[List[int]] = []

    # 1) 每格至少一个数字
    for r in digits:
        for c in digits:
            clauses.append([var_id(n, r, c, d) for d in digits])

    # 2) 每格至多一个数字
    for r in digits:
        for c in digits:
            for d1 in digits:
                for d2 in range(d1 + 1, n + 1):
                    clauses.append([-var_id(n, r, c, d1), -var_id(n, r, c, d2)])

    # 3) 每列每个数字恰一次（至少一次 + 至多一次）
    for r in digits:
        for d in digits:
            clauses.append([var_id(n, r, c, d) for c in digits])
            for c1 in digits:
                for c2 in range(c1 + 1, n + 1):
                    clauses.append([-var_id(n, r, c1, d), -var_id(n, r, c2, d)])

    # 4) 每行每个数字恰一次（至少一次 + 至多一次）
    for c in digits:
        for d in digits:
            clauses.append([var_id(n, r, c, d) for r in digits])
            for r1 in digits:
                for r2 in range(r1 + 1, n + 1):
                    clauses.append([-var_id(n, r1, c, d), -var_id(n, r2, c, d)])

    # 5) 每个 3x3 宫每个数字恰一次（至少一次 + 至多一次）
    for br in range(1, n + 1, box):
        for bc in range(1, n + 1, box):
            cells = [(r, c) for r in range(br, br + box) for c in range(bc, bc + box)]
            for d in digits:
                clauses.append([var_id(n, r, c, d) for (r, c) in cells])
                for i in range(len(cells)):
                    for j in range(i + 1, len(cells)):
                        r1, c1 = cells[i]
                        r2, c2 = cells[j]
                        clauses.append([-var_id(n, r1, c1, d), -var_id(n, r2, c2, d)])

    # 6) givens：固定格子取值
    for r, c, d in givens:
        clauses.append([var_id(n, r, c, d)])

    nvars = n * n * n
    return nvars, clauses


def write_dimacs(path: Path, nvars: int, clauses: Sequence[Sequence[int]], comments: Sequence[str]) -> None:
    lines: List[str] = []
    for c in comments:
        lines.append("c " + c.replace("\n", " "))
    lines.append(f"p cnf {nvars} {len(clauses)}")
    for cl in clauses:
        lines.append(" ".join(str(lit) for lit in cl) + " 0")
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def main() -> None:
    ap = argparse.ArgumentParser(description="Sudoku -> DIMACS CNF")
    ap.add_argument("-o", "--output", required=True, help="输出 .cnf 路径")
    ap.add_argument(
        "--size",
        type=int,
        default=9,
        help="Sudoku 尺寸 N（例如 9->9x9, 16->16x16）。N 必须为完全平方数。",
    )
    ap.add_argument("--puzzle", default=None, help="N*N 字符谜题（0/. 为空，数字/字母为值）")
    ap.add_argument("--puzzle-file", default=None, help="包含谜题的文本文件")
    args = ap.parse_args()

    n = args.size

    if bool(args.puzzle) == bool(args.puzzle_file):
        raise SystemExit("必须且只能提供 --puzzle 或 --puzzle-file 其中之一")

    if args.puzzle:
        puzzle = normalize_puzzle(args.puzzle, n)
    else:
        puzzle = read_puzzle_from_file(Path(args.puzzle_file), n)

    givens = parse_givens(puzzle, n)
    nvars, clauses = encode_sudoku_cnf(n, givens)

    comments = [
        f"sudoku_{n}x{n}",
        f"givens={len(givens)}",
        f"nvars={nvars}",
        f"nclauses={len(clauses)}",
        f"var_id={n}*{n}*(r-1)+{n}*(c-1)+d, r/c/d in 1..{n}",
    ]
    write_dimacs(Path(args.output), nvars, clauses, comments)
    print(f"Wrote {args.output} (vars={nvars}, clauses={len(clauses)}, givens={len(givens)})")


if __name__ == "__main__":
    main()
