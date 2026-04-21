#!/usr/bin/env python3
from __future__ import annotations

import csv
import random
import time
from dataclasses import dataclass
from pathlib import Path


def parity_table(n: int) -> int:
    t = 0
    for x in range(1 << n):
        if (bin(x).count("1") & 1) == 1:
            t |= (1 << x)
    return t


def mux_table(n: int) -> int:
    t = 0
    for x in range(1 << n):
        s0 = (x >> 0) & 1
        s1 = (x >> 1) & 1 if n > 1 else 0
        d0 = (x >> 2) & 1 if n > 2 else 0
        d1 = (x >> 3) & 1 if n > 3 else 0
        d2 = (x >> 4) & 1 if n > 4 else 0
        d3 = (x >> 5) & 1 if n > 5 else 0
        y = [d0, d1, d2, d3][(s1 << 1) | s0]
        if y:
            t |= (1 << x)
    return t


def adder_lsb_table(n: int) -> int:
    k = max(1, n // 3)
    t = 0
    for x in range(1 << n):
        a = x & ((1 << k) - 1)
        b = (x >> k) & ((1 << k) - 1)
        cin = (x >> (2 * k)) & 1 if (2 * k) < n else 0
        if ((a + b + cin) & 1) == 1:
            t |= (1 << x)
    return t


def majority_table(n: int) -> int:
    t = 0
    th = n // 2 + 1
    for x in range(1 << n):
        if bin(x).count("1") >= th:
            t |= (1 << x)
    return t


def random_table(n: int, seed: int) -> int:
    rnd = random.Random(seed)
    t = 0
    for i in range(1 << n):
        if rnd.getrandbits(1):
            t |= (1 << i)
    return t


def reorder_table(table: int, n: int, order: list[int]) -> int:
    out = 0
    for y in range(1 << n):
        x = 0
        for i in range(n):
            bit = (y >> i) & 1
            x |= (bit << order[i])
        if ((table >> x) & 1) == 1:
            out |= (1 << y)
    return out


def cofactor_lsb(table: int, m: int) -> tuple[int, int]:
    t0 = 0
    t1 = 0
    out_idx = 0
    for i in range(0, 1 << m, 2):
        b0 = (table >> i) & 1
        b1 = (table >> (i + 1)) & 1
        if b0:
            t0 |= (1 << out_idx)
        if b1:
            t1 |= (1 << out_idx)
        out_idx += 1
    return t0, t1


def is_const(table: int, m: int) -> int | None:
    if m == 0:
        return table & 1
    bits = 1 << m
    if table == 0:
        return 0
    if table == ((1 << bits) - 1):
        return 1
    return None


@dataclass(frozen=True)
class NodeKey:
    level: int
    kind: str
    a: int
    b: int


class RobddBuilder:
    def __init__(self) -> None:
        self.unique: dict[NodeKey, int] = {}
        self.next_id = 2

    def _mk(self, level: int, low: int, high: int) -> int:
        if low == high:
            return low
        k = NodeKey(level, "sh", low, high)
        if k in self.unique:
            return self.unique[k]
        nid = self.next_id
        self.next_id += 1
        self.unique[k] = nid
        return nid

    def _build(self, table: int, m: int, level: int, memo: dict[tuple[int, int, int], int]) -> int:
        key = (table, m, level)
        if key in memo:
            return memo[key]
        c = is_const(table, m)
        if c is not None:
            memo[key] = c
            return c
        t0, t1 = cofactor_lsb(table, m)
        low = self._build(t0, m - 1, level + 1, memo)
        high = self._build(t1, m - 1, level + 1, memo)
        out = self._mk(level, low, high)
        memo[key] = out
        return out

    def build(self, table: int, n: int) -> int:
        return self._build(table, n, 0, {})

    def node_count_including_terminals(self, root: int) -> int:
        if root <= 1:
            return 2
        id_to_key = {v: k for k, v in self.unique.items()}
        seen = set()
        stack = [root]
        while stack:
            cur = stack.pop()
            if cur <= 1 or cur in seen:
                continue
            seen.add(cur)
            key = id_to_key[cur]
            stack.append(key.a)
            stack.append(key.b)
        return len(seen) + 2


class FddBuilder:
    """
    FDD prototype used here: for each variable level, choose the best among:
    - Shannon: f = f0 + x*(f1 xor f0)
    - Positive Davio: f = f0 xor x*(f0 xor f1)
    - Negative Davio: f = f1 xor (~x)*(f0 xor f1)
    with reduced shared DAG and fixed variable order.
    """

    def __init__(self) -> None:
        self.unique: dict[NodeKey, int] = {}
        self.next_id = 2

    def _mk(self, level: int, kind: str, a: int, b: int) -> int:
        if kind == "sh" and a == b:
            return a
        if kind in ("pd", "nd") and b == 0:
            return a
        k = NodeKey(level, kind, a, b)
        if k in self.unique:
            return self.unique[k]
        nid = self.next_id
        self.next_id += 1
        self.unique[k] = nid
        return nid

    def _build(self, table: int, m: int, level: int, memo: dict[tuple[int, int, int], int]) -> int:
        key = (table, m, level)
        if key in memo:
            return memo[key]
        c = is_const(table, m)
        if c is not None:
            memo[key] = c
            return c

        t0, t1 = cofactor_lsb(table, m)
        d = t0 ^ t1

        # Shannon candidate
        sh_a = self._build(t0, m - 1, level + 1, memo)
        sh_b = self._build(t1, m - 1, level + 1, memo)
        sh_root = self._mk(level, "sh", sh_a, sh_b)
        sh_nodes = self._subgraph_nodes(sh_root)

        # Positive Davio candidate
        pd_a = self._build(t0, m - 1, level + 1, memo)
        pd_b = self._build(d, m - 1, level + 1, memo)
        pd_root = self._mk(level, "pd", pd_a, pd_b)
        pd_nodes = self._subgraph_nodes(pd_root)

        # Negative Davio candidate
        nd_a = self._build(t1, m - 1, level + 1, memo)
        nd_b = self._build(d, m - 1, level + 1, memo)
        nd_root = self._mk(level, "nd", nd_a, nd_b)
        nd_nodes = self._subgraph_nodes(nd_root)

        best_root = sh_root
        best_nodes = sh_nodes
        if pd_nodes < best_nodes:
            best_nodes = pd_nodes
            best_root = pd_root
        if nd_nodes < best_nodes:
            best_root = nd_root
        memo[key] = best_root
        return best_root

    def _subgraph_nodes(self, root: int) -> int:
        if root <= 1:
            return 2
        id_to_key = {v: k for k, v in self.unique.items()}
        seen = set()
        stack = [root]
        while stack:
            cur = stack.pop()
            if cur <= 1 or cur in seen:
                continue
            seen.add(cur)
            key = id_to_key[cur]
            stack.append(key.a)
            stack.append(key.b)
        return len(seen) + 2

    def build(self, table: int, n: int) -> int:
        return self._build(table, n, 0, {})

    def node_count_including_terminals(self, root: int) -> int:
        return self._subgraph_nodes(root)


def run_once(table: int, n: int, order_name: str, order: list[int]) -> dict[str, object]:
    rt = reorder_table(table, n, order)

    rb = RobddBuilder()
    t0 = time.perf_counter()
    r_root = rb.build(rt, n)
    r_ms = (time.perf_counter() - t0) * 1000.0
    r_nodes = rb.node_count_including_terminals(r_root)

    fb = FddBuilder()
    t1 = time.perf_counter()
    f_root = fb.build(rt, n)
    f_ms = (time.perf_counter() - t1) * 1000.0
    f_nodes = fb.node_count_including_terminals(f_root)

    return {
        "order": order_name,
        "robdd_nodes": r_nodes,
        "fdd_nodes": f_nodes,
        "ratio_fdd_over_robdd": (f_nodes / r_nodes) if r_nodes else 0.0,
        "robdd_runtime_ms": round(r_ms, 6),
        "fdd_runtime_ms": round(f_ms, 6),
    }


def main() -> None:
    out_dir = Path(__file__).resolve().parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    families = ["parity", "mux", "adder_lsb", "majority", "random"]
    for n in range(4, 11):
        funcs = {
            "parity": parity_table(n),
            "mux": mux_table(n),
            "adder_lsb": adder_lsb_table(n),
            "majority": majority_table(n),
            "random": random_table(n, 20260407 + n),
        }
        for fam in families:
            t = funcs[fam]
            for order_name, order in [("File", list(range(n))), ("RFile", list(range(n - 1, -1, -1)))]:
                data = run_once(t, n, order_name, order)
                rows.append(
                    {
                        "n": n,
                        "function": fam,
                        **data,
                    }
                )

    csv_path = out_dir / "fdd_vs_robdd.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "n",
                "function",
                "order",
                "robdd_nodes",
                "fdd_nodes",
                "ratio_fdd_over_robdd",
                "robdd_runtime_ms",
                "fdd_runtime_ms",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    # Optional plot
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        plt = None
    if plt is not None:
        file_rows = [r for r in rows if r["order"] == "File"]
        xs = list(range(4, 11))
        avg_ratio = []
        for n in xs:
            vals = [float(r["ratio_fdd_over_robdd"]) for r in file_rows if int(r["n"]) == n]
            avg_ratio.append(sum(vals) / len(vals))
        plt.figure(figsize=(7, 4.5))
        plt.plot(xs, avg_ratio, marker="o")
        plt.axhline(1.0, linestyle="--")
        plt.xlabel("n")
        plt.ylabel("avg(FDD nodes / ROBDD nodes), File order")
        plt.title("FDD vs ROBDD size ratio")
        plt.tight_layout()
        plt.savefig(out_dir / "fdd_vs_robdd_plot.png", dpi=170)
        plt.close()

    # Summary markdown
    md_lines = [
        "# FDD vs ROBDD Summary",
        "",
        "- FDD definition in this prototype: ordered reduced DAG with per-level best choice among Shannon / positive-Davio / negative-Davio.",
        "- This is a standalone exploratory model for small n; it is not yet GV-integrated FDD.",
        "",
        "| n | avg ratio (File) |",
        "|---|------------------|",
    ]
    for n in range(4, 11):
        vals = [float(r["ratio_fdd_over_robdd"]) for r in rows if int(r["n"]) == n and r["order"] == "File"]
        md_lines.append(f"| {n} | {sum(vals)/len(vals):.4f} |")
    (out_dir / "summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
