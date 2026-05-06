#!/usr/bin/env python3
"""
将图 k-着色问题编码为 CNF（DIMACS）。

变量 x[v,c]：顶点 v 是否使用颜色 c（one-hot）。
  - DIMACS 变量编号：v * k + c + 1  （1-based）

子句：
  1) 每个顶点至少一种颜色：OR_c x[v,c]
  2) 每个顶点至多一种颜色：对所有 c1 < c2，(!x[v,c1] OR !x[v,c2])
  3) 每条边 (u,v) 不能同色：对所有 c，(!x[u,c] OR !x[v,c])
"""

from __future__ import annotations

import argparse
import random
from collections import defaultdict
from typing import Iterable, List, Set, Tuple

Edge = Tuple[int, int]


def lit(v: int, c: int, k: int) -> int:
    return v * k + c + 1


def encode_coloring(n: int, k: int, edges: Iterable[Edge]) -> Tuple[int, List[List[int]]]:
    """返回 (变量数, 子句列表)，每个子句为文字列表（可含正负）。"""
    clauses: List[List[int]] = []
    # 1) at least one color per vertex
    for v in range(n):
        clauses.append([lit(v, c, k) for c in range(k)])
    # 2) at most one color per vertex
    for v in range(n):
        for c1 in range(k):
            for c2 in range(c1 + 1, k):
                clauses.append([-lit(v, c1, k), -lit(v, c2, k)])
    # 3) edge constraints
    for u, v in edges:
        if u > v:
            u, v = v, u
        for c in range(k):
            clauses.append([-lit(u, c, k), -lit(v, c, k)])
    nvars = n * k
    return nvars, clauses


def write_dimacs(path: str, nvars: int, clauses: List[List[int]], comments: List[str] | None = None) -> None:
    lines: List[str] = []
    if comments:
        for c in comments:
            lines.append("c " + c.replace("\n", " "))
    lines.append(f"p cnf {nvars} {len(clauses)}")
    for cl in clauses:
        lines.append(" ".join(str(x) for x in cl) + " 0")
    with open(path, "w", encoding="ascii") as f:
        f.write("\n".join(lines) + "\n")


def graph_complete(n: int) -> List[Edge]:
    e: List[Edge] = []
    for u in range(n):
        for v in range(u + 1, n):
            e.append((u, v))
    return e


def graph_cycle(n: int) -> List[Edge]:
    return [(i, (i + 1) % n) for i in range(n)]


def graph_path(n: int) -> List[Edge]:
    return [(i, i + 1) for i in range(n - 1)]


def graph_grid(rows: int, cols: int) -> List[Edge]:
    def vid(r: int, c: int) -> int:
        return r * cols + c

    e: Set[Edge] = set()
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                u, v = vid(r, c), vid(r, c + 1)
                if u > v:
                    u, v = v, u
                e.add((u, v))
            if r + 1 < rows:
                u, v = vid(r, c), vid(r + 1, c)
                if u > v:
                    u, v = v, u
                e.add((u, v))
    return sorted(e)


def graph_random_gnp(n: int, p: float, rng: random.Random) -> List[Edge]:
    e: List[Edge] = []
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                e.append((u, v))
    return e


def graph_bipartite_complete(a: int, b: int) -> List[Edge]:
    """两部分大小为 a、b，顶点 0..a-1 与 a..a+b-1 之间的完全二部图。"""
    e: List[Edge] = []
    for u in range(a):
        for v in range(a, a + b):
            e.append((u, v))
    return e


def main() -> None:
    ap = argparse.ArgumentParser(description="图着色 -> DIMACS CNF")
    ap.add_argument("-o", "--output", required=True, help="输出 .cnf 路径")
    ap.add_argument("-k", "--colors", type=int, required=True, help="颜色数 k")
    ap.add_argument(
        "--family",
        choices=("complete", "cycle", "path", "grid", "gnp", "biclique"),
        required=True,
    )
    ap.add_argument("-n", "--n", type=int, default=0, help="complete/cycle/path/gnp: 顶点数")
    ap.add_argument("--rows", type=int, default=0, help="grid: 行数")
    ap.add_argument("--cols", type=int, default=0, help="grid: 列数")
    ap.add_argument("--p", type=float, default=0.1, help="gnp: 边概率")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--a", type=int, default=0, help="biclique: 左侧大小")
    ap.add_argument("--b", type=int, default=0, help="biclique: 右侧大小")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    edges: List[Edge]
    n: int
    comments: List[str] = []

    if args.family == "complete":
        n = args.n
        if n < 2:
            raise SystemExit("complete 需要 --n >= 2")
        edges = graph_complete(n)
        comments.append(f"family=K_{n} chromatic={n}")
    elif args.family == "cycle":
        n = args.n
        if n < 3:
            raise SystemExit("cycle 需要 --n >= 3")
        edges = graph_cycle(n)
        chi = 2 if n % 2 == 0 else 3
        comments.append(f"family=C_{n} chromatic={chi}")
    elif args.family == "path":
        n = args.n
        if n < 2:
            raise SystemExit("path 需要 --n >= 2")
        edges = graph_path(n)
        comments.append("family=path tree bipartite chi<=2")
    elif args.family == "grid":
        if args.rows < 1 or args.cols < 1:
            raise SystemExit("grid 需要 --rows --cols >= 1")
        n = args.rows * args.cols
        edges = graph_grid(args.rows, args.cols)
        comments.append(f"family=grid {args.rows}x{args.cols} bipartite")
    elif args.family == "gnp":
        n = args.n
        if n < 2:
            raise SystemExit("gnp 需要 --n >= 2")
        edges = graph_random_gnp(n, args.p, rng)
        comments.append(f"family=G({n},{args.p}) seed={args.seed}")
    else:  # biclique
        a, b = args.a, args.b
        if a < 1 or b < 1:
            raise SystemExit("biclique 需要 --a --b >= 1")
        n = a + b
        edges = graph_bipartite_complete(a, b)
        comments.append(f"family=K_{{{a},{b}}} bipartite")

    nvars, clauses = encode_coloring(n, args.colors, edges)
    comments.insert(0, f"graph_coloring n={n} k={args.colors} m_edges={len(edges)} nvars={nvars} nclauses={len(clauses)}")
    write_dimacs(args.output, nvars, clauses, comments)


if __name__ == "__main__":
    main()
