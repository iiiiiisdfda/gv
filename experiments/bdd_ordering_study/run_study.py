#!/usr/bin/env python3
from __future__ import annotations

import csv
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BddNode:
    var: int
    low: int
    high: int


class RobddNoComplement:
    def __init__(self, n: int, var_order: list[int]) -> None:
        self.n = n
        self.order = var_order
        self.unique: dict[BddNode, int] = {}
        self.nodes: dict[int, BddNode] = {}
        self.cache: dict[tuple[int, int, int], int] = {}
        self.next_id = 2  # 0:false, 1:true

    @staticmethod
    def _bit(table: int, idx: int) -> int:
        return (table >> idx) & 1

    def _mk(self, var: int, low: int, high: int) -> int:
        if low == high:
            return low
        key = BddNode(var, low, high)
        if key in self.unique:
            return self.unique[key]
        node_id = self.next_id
        self.next_id += 1
        self.unique[key] = node_id
        self.nodes[node_id] = key
        return node_id

    def _value_under_assignment(self, table: int, fixed_mask: int, fixed_val: int, rem_vars: list[int], rem_idx: int) -> int:
        # Build full assignment index from fixed part + remaining assignment bits.
        idx = fixed_val
        for b, v in enumerate(rem_vars):
            if (rem_idx >> b) & 1:
                idx |= (1 << v)
            else:
                idx &= ~(1 << v)
        return self._bit(table, idx)

    def _is_const_under(self, table: int, fixed_mask: int, fixed_val: int, rem_vars: list[int]) -> int | None:
        first = None
        total = 1 << len(rem_vars)
        for ridx in range(total):
            v = self._value_under_assignment(table, fixed_mask, fixed_val, rem_vars, ridx)
            if first is None:
                first = v
            elif v != first:
                return None
        return first

    def _build(self, table: int, level: int, fixed_mask: int, fixed_val: int) -> int:
        key = (level, fixed_mask, fixed_val)
        if key in self.cache:
            return self.cache[key]
        rem_vars = self.order[level:]
        c = self._is_const_under(table, fixed_mask, fixed_val, rem_vars)
        if c is not None:
            self.cache[key] = c
            return c
        var = self.order[level]
        low = self._build(table, level + 1, fixed_mask | (1 << var), fixed_val & ~(1 << var))
        high = self._build(table, level + 1, fixed_mask | (1 << var), fixed_val | (1 << var))
        res = self._mk(var, low, high)
        self.cache[key] = res
        return res

    def build(self, table: int) -> int:
        return self._build(table, 0, 0, 0)

    def node_count_including_terminals(self) -> int:
        return len(self.nodes) + 2


def parity_table(n: int) -> int:
    t = 0
    for x in range(1 << n):
        if bin(x).count("1") & 1:
            t |= 1 << x
    return t


def mux_table(n: int) -> int:
    t = 0
    for x in range(1 << n):
        s0 = (x >> 0) & 1
        s1 = (x >> 1) & 1
        d0 = (x >> 2) & 1
        d1 = (x >> 3) & 1
        d2 = (x >> 4) & 1 if n > 4 else 0
        d3 = (x >> 5) & 1 if n > 5 else 0
        data = [d0, d1, d2, d3]
        out = data[(s1 << 1) | s0]
        if out:
            t |= 1 << x
    return t


def adder_lsb_table(n: int) -> int:
    k = max(1, n // 3)
    t = 0
    for x in range(1 << n):
        a = x & ((1 << k) - 1)
        b = (x >> k) & ((1 << k) - 1)
        cin = (x >> (2 * k)) & 1 if (2 * k) < n else 0
        if (a + b + cin) & 1:
            t |= 1 << x
    return t


def majority_table(n: int) -> int:
    t = 0
    th = n // 2 + 1
    for x in range(1 << n):
        if bin(x).count("1") >= th:
            t |= 1 << x
    return t


def random_table(n: int, seed: int) -> int:
    rnd = random.Random(seed)
    t = 0
    for i in range(1 << n):
        if rnd.getrandbits(1):
            t |= 1 << i
    return t


def influence_order(table: int, n: int, reverse: bool = False) -> list[int]:
    # influence(v) = number of assignments where f(v=0) != f(v=1)
    infl = []
    for v in range(n):
        cnt = 0
        for x in range(1 << n):
            x0 = x & ~(1 << v)
            x1 = x | (1 << v)
            if ((table >> x0) & 1) != ((table >> x1) & 1):
                cnt += 1
        infl.append((cnt, v))
    infl.sort(reverse=not reverse)  # reverse=False => high influence first (DFS-like)
    return [v for _, v in infl]


def run() -> None:
    out_dir = Path(__file__).resolve().parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    n = 8
    funcs = {
        "parity": parity_table(n),
        "mux": mux_table(n),
        "adder_lsb": adder_lsb_table(n),
        "majority": majority_table(n),
        "random": random_table(n, 20260407),
    }

    rows = []
    for name, table in funcs.items():
        orders = {
            "File": list(range(n)),
            "RFile": list(range(n - 1, -1, -1)),
            "DFS": influence_order(table, n, reverse=False),
            "RDFS": influence_order(table, n, reverse=True),
        }
        for mode, order in orders.items():
            b = RobddNoComplement(n, order)
            b.build(table)
            rows.append(
                {
                    "function": name,
                    "mode": mode,
                    "order": " ".join(map(str, order)),
                    "nodes_including_terminals": b.node_count_including_terminals(),
                }
            )

    with (out_dir / "ordering_study.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["function", "mode", "order", "nodes_including_terminals"])
        w.writeheader()
        w.writerows(rows)

    by_func = defaultdict(list)
    for r in rows:
        by_func[r["function"]].append(r)

    lines = [
        "# BDD Variable Ordering Study",
        "",
        "Functions: parity, mux, adder_lsb, majority, random",
        "Modes compared: File / RFile / DFS(influence-desc) / RDFS(influence-asc)",
        "",
        "## Best mode by function",
    ]
    win_count = defaultdict(int)
    for fn, rs in by_func.items():
        rs = sorted(rs, key=lambda x: int(x["nodes_including_terminals"]))
        best = rs[0]
        win_count[best["mode"]] += 1
        lines.append(f"- {fn}: {best['mode']} ({best['nodes_including_terminals']} nodes)")

    lines += [
        "",
        "## Heuristic conclusion",
        f"- DFS wins: {win_count['DFS']} / {len(by_func)}",
        f"- RDFS wins: {win_count['RDFS']} / {len(by_func)}",
        f"- File wins: {win_count['File']} / {len(by_func)}",
        f"- RFile wins: {win_count['RFile']} / {len(by_func)}",
        "- Recommended default: start with DFS; fallback to RDFS when DFS is poor on symmetric/high-inversion functions.",
    ]
    (out_dir / "heuristics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
