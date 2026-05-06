#!/usr/bin/env python3
"""
生成若干图着色 DIMACS 实例，调用 GV 的 `SATSolve DIMACS`，汇总运行时间与可从 stdout 解析的 MiniSat 统计。

依赖：仓库根目录可执行的 ./gv（或 --gv 指定）。若报缺少 libyosys.so，请将 Yosys 构建目录加入
`LD_LIBRARY_PATH`，或传 `--ld-library-path <含 libyosys.so 的目录>`（脚本会尝试在 `build/` 下自动搜索）。

说明：
  - MiniSat 进度表中 “Conflicts” 列在每轮 search 之前打印；本脚本取所有匹配行的最大值作为
    conflicts_progress_max（对极快结束的单次 search 可能低于最终内部计数，但可与耗时对照）。
  - 若你本地在 minisatMgr::solve_dimacs_cnf 末尾打印了 GV_DIMACS_STATS 行，本脚本会优先解析
    其中的 conflicts / propagations / decisions。
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


RE_MINISAT_ROW = re.compile(r"^\|\s*(\d+)\s*\|")
RE_GV_STATS = re.compile(
    r"^GV_DIMACS_STATS conflicts=(\d+) propagations=(\d+) decisions=(\d+) starts=(\d+)\s*$"
)


@dataclass
class BenchResult:
    name: str
    cnf_path: str
    wall_sec: float
    sat: Optional[bool]
    nvars: int
    nclauses: int
    conflicts_progress_max: int
    propagations: Optional[int]
    decisions: Optional[int]
    starts: Optional[int]
    raw_tail: str


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


def parse_gv_output(text: str) -> Tuple[Optional[bool], int, Optional[int], Optional[int], Optional[int]]:
    """返回 (is_sat, conflicts_progress_max, propagations, decisions, starts)"""
    lines = text.splitlines()
    sat: Optional[bool] = None
    if any(line.strip() == "SAT" for line in lines):
        sat = True
    elif any(line.strip().startswith("UNSAT") for line in lines):
        sat = False

    prog_max = 0
    prop = decc = starts = None
    for line in lines:
        m = RE_MINISAT_ROW.match(line)
        if m:
            prog_max = max(prog_max, int(m.group(1)))
        gs = RE_GV_STATS.match(line.strip())
        if gs:
            prog_max = max(prog_max, int(gs.group(1)))
            prop = int(gs.group(2))
            decc = int(gs.group(3))
            starts = int(gs.group(4))
    return sat, prog_max, prop, decc, starts


def find_libyosys_dir(repo: Path) -> Optional[str]:
    """在 build 目录下查找 libyosys.so，供 LD_LIBRARY_PATH 使用。"""
    root = repo / "build"
    if not root.is_dir():
        return None
    try:
        for dirpath, _, names in os.walk(root):
            if "libyosys.so" in names:
                return dirpath
    except OSError:
        return None
    return None


def run_gv(gv_bin: Path, cnf: Path, work: Path, extra_ld_path: Optional[str]) -> Tuple[str, float, int]:
    dofile = work / "run.dofile"
    # 与 tests 一致：命令对大小写不敏感时可写小写
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
    tail = "\n".join(text.splitlines()[-12:])
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
        raw_tail=tail,
    )


def default_suite(repo: Path, out_dir: Path, py: str) -> List[Tuple[str, Path, List[str]]]:
    """(名称, 输出 cnf 路径, 传给 sat_graph_coloring_dimacs.py 的 argv（含脚本路径）)"""
    gen = str(repo / "scripts" / "sat_graph_coloring_dimacs.py")
    o = out_dir

    def case(name: str, rel: str, extra: List[str]) -> Tuple[str, Path, List[str]]:
        cnf = o / rel
        return (name, cnf, [py, gen, "-o", str(cnf)] + extra)

    cases: List[Tuple[str, Path, List[str]]] = [
        # 稠密、UNSAT：完全图 K_m 用 m-1 色
        case("K8_k7_UNSAT", "k8_k7.cnf", ["--family", "complete", "-n", "8", "-k", "7"]),
        case("K10_k9_UNSAT", "k10_k9.cnf", ["--family", "complete", "-n", "10", "-k", "9"]),
        case("K8_k8_SAT", "k8_k8.cnf", ["--family", "complete", "-n", "8", "-k", "8"]),
        case("C11_k2_UNSAT", "c11_k2.cnf", ["--family", "cycle", "-n", "11", "-k", "2"]),
        case("C11_k3_SAT", "c11_k3.cnf", ["--family", "cycle", "-n", "11", "-k", "3"]),
        case("grid8x8_k2_SAT", "g88_k2.cnf", ["--family", "grid", "--rows", "8", "--cols", "8", "-k", "2"]),
        case("grid12x12_k3_SAT", "g1212_k3.cnf", ["--family", "grid", "--rows", "12", "--cols", "12", "-k", "3"]),
        case("gnp40_p05_k4", "gnp40.cnf", ["--family", "gnp", "-n", "40", "-k", "4", "--p", "0.5", "--seed", "42"]),
        case("gnp60_p02_k5", "gnp60.cnf", ["--family", "gnp", "-n", "60", "-k", "5", "--p", "0.2", "--seed", "7"]),
        case("gnp60_p5_k8", "gnp60d.cnf", ["--family", "gnp", "-n", "60", "-k", "8", "--p", "0.5", "--seed", "99"]),
        case("biclique20_20_k2", "bic20.cnf", ["--family", "biclique", "--a", "20", "--b", "20", "-k", "2"]),
    ]
    return cases


def main() -> None:
    ap = argparse.ArgumentParser(description="图着色 DIMACS + GV MiniSat 基准")
    ap.add_argument("--gv", default=None, help="gv 可执行文件路径（默认仓库根 ./gv）")
    ap.add_argument("--out-cnf-dir", default=None, help="生成 CNF 的目录（默认临时目录）")
    ap.add_argument("--csv", default=None, help="将结果写入 CSV")
    ap.add_argument("--list-only", action="store_true", help="只打印将要运行的实例说明")
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
    tmp = tempfile.mkdtemp(prefix="gv_sat_bench_")
    out_dir = Path(args.out_cnf_dir) if args.out_cnf_dir else Path(tmp)
    out_dir.mkdir(parents=True, exist_ok=True)

    ld_extra = args.ld_library_path or find_libyosys_dir(repo)

    suite = default_suite(repo, out_dir, py)
    if args.list_only:
        for name, cnf, cmd in suite:
            print(name, "->", cnf, "::", " ".join(cmd[2:]))
        shutil.rmtree(tmp, ignore_errors=True)
        return

    rows: List[Dict[str, object]] = []
    for name, cnf, cmd in suite:
        subprocess.check_call(cmd, cwd=str(repo))
        r = bench_one(gv, name, cnf, Path(tmp), ld_extra)
        rows.append(
            {
                "name": r.name,
                "sat": r.sat,
                "wall_sec": f"{r.wall_sec:.6f}",
                "nvars": r.nvars,
                "nclauses": r.nclauses,
                "conflicts_progress_max": r.conflicts_progress_max,
                "propagations": r.propagations if r.propagations is not None else "",
                "decisions": r.decisions if r.decisions is not None else "",
                "starts": r.starts if r.starts is not None else "",
            }
        )
        print(
            f"{r.name:22s} SAT={str(r.sat):5s}  {r.wall_sec:8.4f}s  "
            f"vars={r.nvars:6d} cls={r.nclauses:7d}  conflicts~={r.conflicts_progress_max}"
            + (f"  prop={r.propagations}" if r.propagations is not None else "")
        )

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
            w.writeheader()
            w.writerows(rows)

    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
