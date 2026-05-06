#!/usr/bin/env python3
"""
生成若干 Sudoku DIMACS 实例，调用 GV 的 `SATSolve DIMACS`，汇总运行时间与 MiniSat 统计。

依赖：
  - 仓库根目录可执行 ./gv（或 --gv 指定）
  - scripts/sat_sudoku_dimacs.py
  - 若报缺少 libyosys.so，请设置 LD_LIBRARY_PATH 或传 --ld-library-path
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from sat_coloring_bench_gv import find_libyosys_dir, parse_gv_output


@dataclass
class BenchResult:
    name: str
    cnf_path: str
    wall_sec: float
    sat: bool
    nvars: int
    nclauses: int
    conflicts_progress_max: int
    propagations: Optional[int]
    decisions: Optional[int]
    starts: Optional[int]


def parse_dimacs_header(cnf: Path) -> Tuple[int, int]:
    nvars = 0
    nclauses = 0
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
        raise RuntimeError(
            f"GV 执行失败（case={name}, rc={rc}）\n"
            "请确认 libyosys.so 可被加载（LD_LIBRARY_PATH 或 --ld-library-path）。\n"
            f"输出尾部:\n{chr(10).join(text.splitlines()[-20:])}"
        )
    sat, cmax, prop, decn, starts = parse_gv_output(text)
    if sat is None:
        raise RuntimeError(
            f"未能从 GV 输出解析 SAT/UNSAT（case={name}）。\n"
            "这通常表示 SATSolve 没有成功执行，请检查命令与输入 CNF。\n"
            f"输出尾部:\n{chr(10).join(text.splitlines()[-20:])}"
        )
    return BenchResult(
        name=name,
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


def make_unsat_puzzle(puzzle: str) -> str:
    """
    把一个 SAT Sudoku 谜题改成明显 UNSAT：
    令第 1 行前两格都固定为 5（同行冲突）。
    """
    if len(puzzle) != 81:
        raise ValueError("puzzle 长度必须为 81")
    arr = list(puzzle)
    arr[0] = "5"
    arr[1] = "5"
    return "".join(arr)


def load_puzzle_lines(path: Path) -> List[str]:
    puzzles: List[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = "".join(ch for ch in line.strip() if ch in "1234567890.")
        if not s:
            continue
        s = s.replace(".", "0")
        if len(s) != 81 or any(ch not in "0123456789" for ch in s):
            raise ValueError(f"无效谜题行（需 81 个 0-9）: {line[:40]}...")
        puzzles.append(s)
    return puzzles


def clue_count(puzzle: str) -> int:
    return sum(1 for ch in puzzle if ch != "0")


def default_suite(repo: Path, out_dir: Path, py: str) -> List[Tuple[str, Path, Sequence[str], int]]:
    gen = str(repo / "scripts" / "sat_sudoku_dimacs.py")

    # 经典 SAT 题：同一题目的完整/较少 givens 版本 + UNSAT 版本
    easy = "534678912672195348198342567859761423426853791713924856961537284287419635345286179"
    hard = "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
    unsat = make_unsat_puzzle(hard)

    def case(name: str, rel: str, puzzle: str) -> Tuple[str, Path, Sequence[str], int]:
        cnf = out_dir / rel
        cmd: Sequence[str] = [py, gen, "-o", str(cnf), "--puzzle", puzzle]
        return name, cnf, cmd, clue_count(puzzle)

    return [
        case("sudoku_easy_sat", "sudoku_easy.cnf", easy),
        case("sudoku_hard_sat", "sudoku_hard.cnf", hard),
        case("sudoku_unsat_conflict", "sudoku_unsat.cnf", unsat),
    ]


def database_suite(
    repo: Path,
    out_dir: Path,
    py: str,
    puzzle_file: Path,
    limit: int,
) -> List[Tuple[str, Path, Sequence[str], int]]:
    """返回 (name, cnf, cmd, clues) 列表。"""
    gen = str(repo / "scripts" / "sat_sudoku_dimacs.py")
    lines = load_puzzle_lines(puzzle_file)
    if limit > 0:
        lines = lines[:limit]
    out: List[Tuple[str, Path, Sequence[str], int]] = []
    for i, puzzle in enumerate(lines):
        clues = clue_count(puzzle)
        name = f"db_{i:04d}_clues{clues}"
        cnf = out_dir / f"db_{i:04d}.cnf"
        cmd: Sequence[str] = [py, gen, "-o", str(cnf), "--puzzle", puzzle]
        out.append((name, cnf, cmd, clues))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Sudoku DIMACS + GV MiniSat 基准")
    ap.add_argument("--gv", default=None, help="gv 可执行文件路径（默认仓库根 ./gv）")
    ap.add_argument("--out-cnf-dir", default=None, help="生成 CNF 的目录（默认临时目录）")
    ap.add_argument("--csv", default=None, help="将结果写入 CSV")
    ap.add_argument("--list-only", action="store_true", help="只打印将要运行的实例说明")
    ap.add_argument(
        "--puzzle-list",
        default=None,
        help="每行一个 81 字符谜题（0 空格），与此默认三题一并运行（除非 --database-only）",
    )
    ap.add_argument(
        "--database-only",
        action="store_true",
        help="仅运行 --puzzle-list 指定文件中的题目（不跑默认 easy/hard/unsat）",
    )
    ap.add_argument("--limit", type=int, default=0, help="题库最多跑前 N 题（0 表示全部）")
    ap.add_argument(
        "--ld-library-path",
        default=None,
        help="包含 libyosys.so 的目录；默认自动在 build/ 下搜索，也可用环境变量 LD_LIBRARY_PATH",
    )
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    gv = Path(args.gv or (repo / "gv")).resolve()
    if not gv.is_file():
        print(f"找不到 gv: {gv}", file=sys.stderr)
        sys.exit(1)

    py = sys.executable
    tmp = tempfile.mkdtemp(prefix="gv_sudoku_bench_")
    out_dir = Path(args.out_cnf_dir) if args.out_cnf_dir else Path(tmp)
    out_dir.mkdir(parents=True, exist_ok=True)
    ld_extra = args.ld_library_path or find_libyosys_dir(repo)

    suite: List[Tuple[str, Path, Sequence[str], int]] = []
    if not args.database_only:
        suite.extend(default_suite(repo, out_dir, py))
    if args.puzzle_list:
        pf = Path(args.puzzle_list)
        if not pf.is_file():
            print(f"找不到题库: {pf}", file=sys.stderr)
            sys.exit(1)
        for name, cnf, cmd, clues in database_suite(repo, out_dir, py, pf, args.limit):
            suite.append((name, cnf, cmd, clues))
    elif args.database_only:
        print("需要同时提供 --puzzle-list", file=sys.stderr)
        sys.exit(1)

    if args.list_only:
        for name, cnf, cmd, clues in suite:
            print(name, "->", cnf, "::", " ".join(cmd[2:]), f"clues={clues}")
        return

    rows: List[Dict[str, object]] = []
    for name, cnf, cmd, clues in suite:
        subprocess.check_call(cmd, cwd=str(repo))
        r = bench_one(gv, name, cnf, Path(tmp), ld_extra)
        row: Dict[str, object] = {
            "name": r.name,
            "clues": clues,
            "sat": r.sat,
            "wall_sec": f"{r.wall_sec:.6f}",
            "nvars": r.nvars,
            "nclauses": r.nclauses,
            "conflicts_progress_max": r.conflicts_progress_max,
            "propagations": r.propagations if r.propagations is not None else "",
            "decisions": r.decisions if r.decisions is not None else "",
            "starts": r.starts if r.starts is not None else "",
        }
        rows.append(row)
        print(
            f"{r.name:24s} SAT={str(r.sat):5s}  {r.wall_sec:8.4f}s  "
            f"vars={r.nvars:6d} cls={r.nclauses:7d}  conflicts~={r.conflicts_progress_max}"
            + (f"  prop={r.propagations}" if r.propagations is not None else "")
            + f"  clues={clues}"
        )

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
