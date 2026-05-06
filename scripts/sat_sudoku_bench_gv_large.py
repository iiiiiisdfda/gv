#!/usr/bin/env python3
"""
16x16 Sudoku（N=16）较大案例基准：生成不同初始 clues 数的 SAT/UNSAT，再调用 GV 的 SATSolve DIMACS。

策略：
  - 使用一个构造式生成完整 16x16 解（确保题目一定 SAT）
  - 从该解中抽取给定（givens）得到 SAT
  - 对 UNSAT：在同一行选择两格 givens，并把其中一格覆盖成与另一格相同的数字（行约束强制冲突 => UNSAT）

输出 CSV 字段：
  name,size,clues,variant,trial,wall_sec,nvars,nclauses,conflicts_progress_max,propagations,decisions,starts,sat
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from sat_coloring_bench_gv import find_libyosys_dir, parse_gv_output


def digit_to_symbol(d: int) -> str:
    if 1 <= d <= 9:
        return str(d)
    if 10 <= d <= 35:
        return chr(ord("A") + (d - 10))
    raise ValueError(f"digit_to_symbol unsupported d={d}")


def gen_solution_nxn(n: int, k: int) -> List[List[int]]:
    """构造标准 Sudoku 解：val = (r*k + r//k + c) % n + 1，并做随机置换。"""

    def base(r: int, c: int) -> int:
        return (r * k + r // k + c) % n + 1

    # band-wise row/col permutations + symbol permutation
    rng = random.Random(0)
    rows = list(range(n))
    cols = list(range(n))
    nums = list(range(1, n + 1))

    # permute within each band/stack
    def permute_bands(arr: List[int]) -> List[int]:
        out: List[int] = []
        for b in range(k):
            band = arr[b * k : (b + 1) * k]
            rng.shuffle(band)
            out.extend(band)
        # shuffle bands themselves
        bands = [out[i * k : (i + 1) * k] for i in range(k)]
        rng.shuffle(bands)
        out2: List[int] = []
        for band in bands:
            out2.extend(band)
        return out2

    rows = permute_bands(rows)
    cols = permute_bands(cols)
    rng.shuffle(nums)

    sol: List[List[int]] = [[0 for _ in range(n)] for _ in range(n)]
    for r in range(n):
        for c in range(n):
            sol[r][c] = nums[base(rows[r], cols[c]) - 1]
    return sol


def make_puzzle_from_solution(
    sol: List[List[int]],
    givens: Sequence[Tuple[int, int]],
    n: int,
) -> str:
    """givens: list of (r0,c0) 0-based positions to keep from sol."""
    grid = [["0" for _ in range(n)] for _ in range(n)]
    for r0, c0 in givens:
        d = sol[r0][c0]
        grid[r0][c0] = digit_to_symbol(d)
    # row-major string
    return "".join("".join(row) for row in grid)


def choose_givens_sat(rng: random.Random, n: int, clues: int) -> List[Tuple[int, int]]:
    positions = [(r, c) for r in range(n) for c in range(n)]
    chosen = rng.sample(positions, clues)
    return chosen


def make_unsat_from_sat(
    rng: random.Random,
    sol: List[List[int]],
    sat_givens: Sequence[Tuple[int, int]],
    n: int,
    clues: int,
) -> str:
    """在同一行选择两格 givens，并让其中一格覆盖成另一格的数字 => 行重复 => UNSAT。"""
    if clues < 2:
        raise ValueError("clues too small for UNSAT construction")

    # build givens set for fast membership and row grouping
    row_to_cols: Dict[int, List[int]] = {}
    for r0, c0 in sat_givens:
        row_to_cols.setdefault(r0, []).append(c0)

    # pick a row with >=2 givens
    for _ in range(200):
        r0 = rng.randrange(n)
        cols = row_to_cols.get(r0, [])
        if len(cols) >= 2:
            break
    else:
        # fallback: pick row deterministically
        candidates = [r for r, cols in row_to_cols.items() if len(cols) >= 2]
        if not candidates:
            raise RuntimeError("cannot build UNSAT: no row has >=2 givens")
        r0 = rng.choice(candidates)
        cols = row_to_cols[r0]

    c1, c2 = rng.sample(cols, 2)
    d = sol[r0][c1]

    # keep same givens positions; overwrite digit at (r0,c2) to d
    # This changes puzzle symbol but keeps clues count.
    sat_givens_set = set(sat_givens)
    # Create givens list with overwritten symbol
    # We'll build puzzle string directly from sol, but with a per-position override.
    override: Dict[Tuple[int, int], int] = {(r0, c2): d}
    grid = [["0" for _ in range(n)] for _ in range(n)]
    for r0_, c0_ in sat_givens_set:
        val = override.get((r0_, c0_), sol[r0_][c0_])
        grid[r0_][c0_] = digit_to_symbol(val)
    return "".join("".join(row) for row in grid)


@dataclass
class BenchResult:
    name: str
    size: int
    clues: int
    variant: str
    trial: int
    cnf_path: str
    wall_sec: float
    sat: Optional[bool]
    nvars: int
    nclauses: int
    conflicts_progress_max: int
    propagations: Optional[int]
    decisions: Optional[int]
    starts: Optional[int]


def parse_dimacs_header(cnf: Path) -> Tuple[int, int]:
    nvars = nclauses = 0
    with cnf.open("r", encoding="ascii", errors="replace") as f:
        for line in f:
            if line.startswith("p cnf"):
                parts = line.split()
                nvars = int(parts[2])
                nclauses = int(parts[3])
                break
    return nvars, nclauses


def run_gv(gv_bin: Path, cnf: Path, work: Path, extra_ld_path: Optional[str]) -> Tuple[str, float, int]:
    dofile = work / "run.dofile"
    dofile.write_text(f"satsolve dimacs -file {cnf.resolve()}\nq -f\n", encoding="ascii")
    env = os.environ.copy()
    if extra_ld_path:
        prev = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = extra_ld_path + (os.pathsep + prev if prev else "")
    t0 = time.perf_counter()
    proc = subprocess.run(
        [str(gv_bin), "-file", str(dofile)],
        cwd=str(work),
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )
    elapsed = time.perf_counter() - t0
    out = proc.stdout + "\n" + proc.stderr
    if proc.returncode != 0:
        out += f"\n[exit {proc.returncode}]"
    return out, elapsed, proc.returncode


def bench_one(
    gv_bin: Path,
    name: str,
    cnf: Path,
    work_root: Path,
    ld_path: Optional[str],
) -> BenchResult:
    work = work_root / name.replace("/", "_")
    work.mkdir(parents=True, exist_ok=True)
    nvars, ncls = parse_dimacs_header(cnf)
    text, wall, rc = run_gv(gv_bin, cnf, work, ld_path)
    if rc != 0:
        raise RuntimeError(f"GV 执行失败（case={name}, rc={rc}）\n{chr(10).join(text.splitlines()[-20:])}")
    sat, cmax, prop, decn, starts = parse_gv_output(text)
    if sat is None:
        raise RuntimeError(f"未能解析 SAT/UNSAT（case={name}）\n{chr(10).join(text.splitlines()[-20:])}")
    return BenchResult(
        name=name,
        size=0,  # filled by caller
        clues=0,  # filled by caller
        variant="",
        trial=0,
        cnf_path=str(cnf),
        wall_sec=wall,
        sat=sat,
        nvars=nvars,
        nclauses=ncls,
        conflicts_progress_max=cmax,
        propagations=prop,
        decisions=decn,
        starts=starts,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate and bench larger Sudoku (e.g., 16x16).")
    ap.add_argument("--gv", default=None, help="gv 可执行文件路径（默认仓库根 ./gv）")
    ap.add_argument("--size", type=int, default=16, help="Sudoku 大小 N（例如 16）")
    ap.add_argument("--clues", default="64,96,128", help="逗号分隔的初始 clues 数列表（例如 32,64,96,128）")
    ap.add_argument("--trials", type=int, default=1, help="每个 clues 跑多少组 SAT/UNSAT")
    ap.add_argument("--seed", type=int, default=1, help="随机种子")
    ap.add_argument("--out-csv", default="experiments/sudoku_study/sudoku_experiment_16x16.csv")
    ap.add_argument("--out-cnf-dir", default="experiments/sudoku_study/bench_cnf_16x16")
    ap.add_argument(
        "--ld-library-path",
        default=None,
        help="包含 libyosys.so 的目录；默认自动在 build/ 下搜索",
    )
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    gv = Path(args.gv or (repo / "gv")).resolve()
    if not gv.is_file():
        print(f"找不到 gv: {gv}", file=sys.stderr)
        sys.exit(1)

    n = args.size
    k = int(n ** 0.5)
    if k * k != n:
        raise SystemExit(f"N={n} 不是完全平方数（必须是 k^2）")

    clues_list = [int(x) for x in args.clues.split(",") if x.strip()]
    if any(c < 0 or c > n * n for c in clues_list):
        raise SystemExit("clues 超出范围")

    out_csv = Path(args.out_csv).resolve()
    out_cnf_dir = Path(args.out_cnf_dir).resolve()
    out_cnf_dir.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    ld_extra = args.ld_library_path or find_libyosys_dir(repo)

    # generate fixed solution (deterministic construction; randomness used only for permutation)
    sol = gen_solution_nxn(n, k)

    gen_dimacs = str(repo / "scripts" / "sat_sudoku_dimacs.py")
    rng = random.Random(args.seed)

    tmp_work = Path(tempfile.mkdtemp(prefix="gv_sudoku_large_"))
    rows: List[Dict[str, object]] = []

    trial_idx = 0
    for clues in clues_list:
        for t in range(args.trials):
            # SAT puzzle
            sat_rng = random.Random(rng.randint(0, 10**9))
            sat_givens = choose_givens_sat(sat_rng, n, clues)
            sat_puzzle = make_puzzle_from_solution(sol, sat_givens, n)

            sat_name = f"N{n}_sat_clues{clues}_t{t}"
            sat_cnf = out_cnf_dir / f"{sat_name}.cnf"
            subprocess.check_call(
                [sys.executable, gen_dimacs, "-o", str(sat_cnf), "--size", str(n), "--puzzle", sat_puzzle],
                cwd=str(repo),
            )
            r1 = bench_one(gv, sat_name, sat_cnf, tmp_work, ld_extra)
            r1.size, r1.clues, r1.variant, r1.trial = n, clues, "SAT", t

            rows.append(
                {
                    "name": r1.name,
                    "size": r1.size,
                    "clues": r1.clues,
                    "variant": r1.variant,
                    "trial": r1.trial,
                    "wall_sec": f"{r1.wall_sec:.6f}",
                    "nvars": r1.nvars,
                    "nclauses": r1.nclauses,
                    "conflicts_progress_max": r1.conflicts_progress_max,
                    "propagations": r1.propagations if r1.propagations is not None else "",
                    "decisions": r1.decisions if r1.decisions is not None else "",
                    "starts": r1.starts if r1.starts is not None else "",
                    "sat": r1.sat,
                }
            )
            print(
                f"{r1.name:28s} SAT={r1.sat}  wall={r1.wall_sec:.4f}s  conflicts={r1.conflicts_progress_max}  prop={r1.propagations}"
            )

            # UNSAT puzzle
            unsat_rng = random.Random(rng.randint(0, 10**9))
            unsat_puzzle = make_unsat_from_sat(unsat_rng, sol, sat_givens, n, clues)
            unsat_name = f"N{n}_unsat_clues{clues}_t{t}"
            unsat_cnf = out_cnf_dir / f"{unsat_name}.cnf"
            subprocess.check_call(
                [sys.executable, gen_dimacs, "-o", str(unsat_cnf), "--size", str(n), "--puzzle", unsat_puzzle],
                cwd=str(repo),
            )
            r2 = bench_one(gv, unsat_name, unsat_cnf, tmp_work, ld_extra)
            r2.size, r2.clues, r2.variant, r2.trial = n, clues, "UNSAT", t
            rows.append(
                {
                    "name": r2.name,
                    "size": r2.size,
                    "clues": r2.clues,
                    "variant": r2.variant,
                    "trial": r2.trial,
                    "wall_sec": f"{r2.wall_sec:.6f}",
                    "nvars": r2.nvars,
                    "nclauses": r2.nclauses,
                    "conflicts_progress_max": r2.conflicts_progress_max,
                    "propagations": r2.propagations if r2.propagations is not None else "",
                    "decisions": r2.decisions if r2.decisions is not None else "",
                    "starts": r2.starts if r2.starts is not None else "",
                    "sat": r2.sat,
                }
            )
            print(
                f"{r2.name:28s} SAT={r2.sat}  wall={r2.wall_sec:.4f}s  conflicts={r2.conflicts_progress_max}  prop={r2.propagations}"
            )

    fieldnames = list(rows[0].keys()) if rows else []
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote CSV: {out_csv}  (rows={len(rows)})")


if __name__ == "__main__":
    main()

