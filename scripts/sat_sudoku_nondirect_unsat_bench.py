#!/usr/bin/env python3
"""
非直接冲突 UNSAT 基准：
1) 先生成一个完整合法 Sudoku 解（9x9、16x16）。
2) 用完整解作为 givens 生成 SAT CNF（必 SAT）。
3) 在同一 CNF 末尾追加一个 blocking clause：
      (¬x_1 v ¬x_2 v ... v ¬x_{N*N})
   其中 x_i 是该完整解对应的每个格子赋值文字。
   由于完整 givens 已固定所有格子，此 blocking clause 与之全局矛盾 => UNSAT。

该 UNSAT 不是「同一行直接重复 givens」式构造，而是由全局附加约束导致。
"""

from __future__ import annotations

import csv
import math
import os
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sat_coloring_bench_gv import find_libyosys_dir, parse_gv_output


def digit_to_symbol(d: int) -> str:
    if 1 <= d <= 9:
        return str(d)
    return chr(ord("A") + (d - 10))


def var_id(n: int, r1: int, c1: int, d: int) -> int:
    return n * n * (r1 - 1) + n * (c1 - 1) + d


def gen_solution_nxn(n: int) -> List[List[int]]:
    k = int(math.isqrt(n))
    if k * k != n:
        raise ValueError("N must be perfect square")

    def base(r: int, c: int) -> int:
        return (r * k + r // k + c) % n + 1

    rng = random.Random(42 + n)
    rows = list(range(n))
    cols = list(range(n))
    nums = list(range(1, n + 1))

    def permute(arr: List[int]) -> List[int]:
        out: List[int] = []
        for b in range(k):
            chunk = arr[b * k : (b + 1) * k]
            rng.shuffle(chunk)
            out.extend(chunk)
        bands = [out[i * k : (i + 1) * k] for i in range(k)]
        rng.shuffle(bands)
        ret: List[int] = []
        for b in bands:
            ret.extend(b)
        return ret

    rows = permute(rows)
    cols = permute(cols)
    rng.shuffle(nums)

    sol = [[0 for _ in range(n)] for _ in range(n)]
    for r in range(n):
        for c in range(n):
            sol[r][c] = nums[base(rows[r], cols[c]) - 1]
    return sol


def solution_to_puzzle(sol: List[List[int]]) -> str:
    n = len(sol)
    chars: List[str] = []
    for r in range(n):
        for c in range(n):
            chars.append(digit_to_symbol(sol[r][c]))
    return "".join(chars)


def append_blocking_clause_for_solution(cnf_path: Path, sol: List[List[int]]) -> None:
    n = len(sol)
    block: List[int] = []
    for r in range(n):
        for c in range(n):
            lit = var_id(n, r + 1, c + 1, sol[r][c])
            block.append(-lit)

    text = cnf_path.read_text(encoding="ascii")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("p cnf"):
            parts = line.split()
            nvars = int(parts[2])
            ncls = int(parts[3])
            parts[3] = str(ncls + 1)
            lines[i] = " ".join(parts)
            break
    else:
        raise RuntimeError("DIMACS header not found")

    lines.append(" ".join(str(x) for x in block) + " 0")
    cnf_path.write_text("\n".join(lines) + "\n", encoding="ascii")


def parse_dimacs_header(cnf: Path) -> Tuple[int, int]:
    with cnf.open("r", encoding="ascii", errors="replace") as f:
        for line in f:
            if line.startswith("p cnf"):
                p = line.split()
                return int(p[2]), int(p[3])
    return 0, 0


def run_gv(gv_bin: Path, cnf: Path, work: Path, ld_path: Optional[str]) -> Tuple[bool, float, int, Optional[int], Optional[int], Optional[int], int, int]:
    dofile = work / "run.dofile"
    dofile.write_text(f"satsolve dimacs -file {cnf.resolve()}\nq -f\n", encoding="ascii")

    env = os.environ.copy()
    if ld_path:
        prev = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = ld_path + (os.pathsep + prev if prev else "")

    t0 = time.perf_counter()
    proc = subprocess.run([str(gv_bin), "-file", str(dofile)], cwd=str(work), capture_output=True, text=True, timeout=600, env=env)
    wall = time.perf_counter() - t0
    out = proc.stdout + "\n" + proc.stderr
    if proc.returncode != 0:
        raise RuntimeError(f"GV failed rc={proc.returncode}\n{out}")

    sat, cmax, prop, dec, starts = parse_gv_output(out)
    if sat is None:
        raise RuntimeError(f"Cannot parse SAT/UNSAT\n{out}")
    nvars, ncls = parse_dimacs_header(cnf)
    return sat, wall, cmax, prop, dec, starts, nvars, ncls


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    gv = (repo / "gv").resolve()
    if not gv.is_file():
        raise SystemExit(f"gv not found: {gv}")

    ld_path = find_libyosys_dir(repo)
    out_dir = (repo / "experiments" / "sudoku_study" / "bench_cnf_nondirect_unsat").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = (repo / "experiments" / "sudoku_study" / "sudoku_experiment_nondirect_unsat.csv").resolve()

    gen = repo / "scripts" / "sat_sudoku_dimacs.py"
    tmp = Path(tempfile.mkdtemp(prefix="gv_sudoku_nondirect_"))

    rows: List[Dict[str, object]] = []
    for n in (9, 16):
        sol = gen_solution_nxn(n)
        puzzle_full = solution_to_puzzle(sol)

        sat_cnf = out_dir / f"N{n}_full_sat.cnf"
        subprocess.check_call(
            [sys.executable, str(gen), "-o", str(sat_cnf), "--size", str(n), "--puzzle", puzzle_full],
            cwd=str(repo),
        )
        sat, wall, cmax, prop, dec, starts, nvars, ncls = run_gv(gv, sat_cnf, tmp, ld_path)
        rows.append(
            {
                "name": f"N{n}_full_sat",
                "size": n,
                "variant": "SAT_full_solution",
                "sat": sat,
                "wall_sec": f"{wall:.6f}",
                "nvars": nvars,
                "nclauses": ncls,
                "conflicts_progress_max": cmax,
                "propagations": prop if prop is not None else "",
                "decisions": dec if dec is not None else "",
                "starts": starts if starts is not None else "",
            }
        )

        unsat_cnf = out_dir / f"N{n}_nondirect_unsat.cnf"
        subprocess.check_call(
            [sys.executable, str(gen), "-o", str(unsat_cnf), "--size", str(n), "--puzzle", puzzle_full],
            cwd=str(repo),
        )
        append_blocking_clause_for_solution(unsat_cnf, sol)
        sat2, wall2, cmax2, prop2, dec2, starts2, nvars2, ncls2 = run_gv(gv, unsat_cnf, tmp, ld_path)
        rows.append(
            {
                "name": f"N{n}_nondirect_unsat",
                "size": n,
                "variant": "UNSAT_blocking_clause",
                "sat": sat2,
                "wall_sec": f"{wall2:.6f}",
                "nvars": nvars2,
                "nclauses": ncls2,
                "conflicts_progress_max": cmax2,
                "propagations": prop2 if prop2 is not None else "",
                "decisions": dec2 if dec2 is not None else "",
                "starts": starts2 if starts2 is not None else "",
            }
        )

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()

