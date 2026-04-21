#!/usr/bin/env python3
from __future__ import annotations

import csv
import itertools
import math
import random
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Edge:
    node: int
    neg: int = 0

    def flip(self) -> "Edge":
        return Edge(self.node, self.neg ^ 1)


@dataclass(frozen=True)
class Node:
    level: int
    low: Edge
    high: Edge


class RobddBuilder:
    def __init__(self, n_vars: int, use_complement_edges: bool) -> None:
        self.n_vars = n_vars
        self.use_complement_edges = use_complement_edges
        self.unique: dict[tuple[int, Edge, Edge], int] = {}
        self.nodes: dict[int, Node] = {}
        # no complement-edge: terminals are 0(False), 1(True)
        # complement-edge: only one terminal object 0(False), True is ~0
        self._next_id = 1 if use_complement_edges else 2
        self.memo: dict[tuple[int, int, int], Edge] = {}

    @staticmethod
    def _bit_at(table: int, idx: int) -> int:
        return (table >> idx) & 1

    def _mk_node(self, level: int, low: Edge, high: Edge) -> Edge:
        if low == high:
            return low
        out = Edge(0, 0)
        if self.use_complement_edges and low.neg == 1:
            low = low.flip()
            high = high.flip()
            out = out.flip()
        key = (level, low, high)
        node_id = self.unique.get(key)
        if node_id is None:
            node_id = self._next_id
            self._next_id += 1
            self.unique[key] = node_id
            self.nodes[node_id] = Node(level=level, low=low, high=high)
        return Edge(node=node_id, neg=out.neg)

    def _build_recur(self, level: int, offset: int, stride: int, table: int) -> Edge:
        key = (level, offset, stride)
        if key in self.memo:
            return self.memo[key]
        if level == self.n_vars:
            if self.use_complement_edges:
                leaf = Edge(0, 1 if self._bit_at(table, offset) else 0)
            else:
                leaf = Edge(1 if self._bit_at(table, offset) else 0, 0)
            self.memo[key] = leaf
            return leaf

        low = self._build_recur(level + 1, offset, stride * 2, table)
        high = self._build_recur(level + 1, offset + stride, stride * 2, table)
        node = self._mk_node(level, low, high)
        self.memo[key] = node
        return node

    def build_from_truth_table_int(self, table: int) -> Edge:
        self.memo.clear()
        return self._build_recur(0, 0, 1, table)

    def count_nonterminal_nodes(self) -> int:
        return len(self.nodes)

    def count_edges(self) -> int:
        return 2 * len(self.nodes)


def find_theta(n: int) -> int:
    if n == 1:
        return 0
    chi = n + 1
    for i in range(1, n + 1):
        r = 1 << (i - 1)
        R = (1 << (1 << (n - i + 1))) - (1 << (1 << (n - i)))
        if r >= R:
            chi = i
            break
    theta = n - chi + 1
    return max(theta, 0)


def theory_worst_case_size(n: int) -> tuple[int, int]:
    theta = find_theta(n)
    w = (1 << (n - theta)) - 1 + (1 << (1 << theta))
    return theta, w


def layer_widths(n: int) -> list[dict[str, int]]:
    data: list[dict[str, int]] = []
    for i in range(1, n + 1):
        top = 1 << (i - 1)
        bot = (1 << (1 << (n - i + 1))) - (1 << (1 << (n - i)))
        width = min(top, bot)
        data.append({"n": n, "i": i, "top": top, "bottom": bot, "width": width})
    return data


def parity_table(n: int) -> int:
    v = 0
    for x in range(1 << n):
        if (bin(x).count("1") & 1) == 1:
            v |= 1 << x
    return v


def mux3_table(n: int) -> int:
    v = 0
    for x in range(1 << n):
        b0 = (x >> 0) & 1
        b1 = (x >> 1) & 1 if n > 1 else 0
        b2 = (x >> 2) & 1 if n > 2 else 0
        fx = b1 if b0 else b2
        if fx:
            v |= 1 << x
    return v


def adder_lsb_table(n: int) -> int:
    k = max(1, n // 2)
    v = 0
    for x in range(1 << n):
        a = x & ((1 << k) - 1)
        b = (x >> k) & ((1 << k) - 1)
        cin = (x >> (2 * k)) & 1 if (2 * k) < n else 0
        fx = (a + b + cin) & 1
        if fx:
            v |= 1 << x
    return v


def random_table(n: int, rnd: random.Random) -> int:
    table = 0
    for bit in range(1 << n):
        if rnd.getrandbits(1):
            table |= 1 << bit
    return table


def exhaustive_or_sampled_worst_case(
    n: int, samples: int, rnd: random.Random, use_complement_edges: bool
) -> tuple[int, int]:
    if n <= 4:
        iterator = range(1 << (1 << n))
    else:
        iterator = (random_table(n, rnd) for _ in range(samples))
    best_nodes = -1
    best_table = 0
    for table in iterator:
        b = RobddBuilder(n, use_complement_edges=use_complement_edges)
        b.build_from_truth_table_int(table)
        nodes = b.count_nonterminal_nodes()
        if nodes > best_nodes:
            best_nodes = nodes
            best_table = table
    return best_table, best_nodes


def bench_one_function(
    n: int, family: str, table: int, mode: str, use_complement_edges: bool
) -> dict[str, object]:
    t0 = time.perf_counter()
    b = RobddBuilder(n, use_complement_edges=use_complement_edges)
    root = b.build_from_truth_table_int(table)
    dt_ms = (time.perf_counter() - t0) * 1000.0
    theta, theory = theory_worst_case_size(n)
    return {
        "n": n,
        "family": family,
        "mode": mode,
        "use_complement_edges": int(use_complement_edges),
        "theta": theta,
        "theory_worst_nodes_including_terminals": theory,
        "measured_nonterminal_nodes": b.count_nonterminal_nodes(),
        "measured_nodes_including_terminals": b.count_nonterminal_nodes() + 2,
        "measured_edges": b.count_edges(),
        "root_neg": root.neg,
        "runtime_ms": round(dt_ms, 6),
    }


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def maybe_plot(out_dir: Path, theory_rows: list[dict[str, object]], bench_rows: list[dict[str, object]]) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return

    ns = [int(r["n"]) for r in theory_rows]
    ws = [float(r["W_n"]) for r in theory_rows]
    ratio = [float(r["W_over_2n"]) for r in theory_rows]

    plt.figure(figsize=(8, 5))
    plt.plot(ns, ws, marker="o")
    plt.yscale("log")
    plt.xlabel("n")
    plt.ylabel("W(n) (log scale)")
    plt.title("Theoretical worst-case ROBDD size")
    plt.tight_layout()
    plt.savefig(out_dir / "plot_theory_w.png", dpi=180)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.plot(ns, ratio, marker="o")
    plt.xlabel("n")
    plt.ylabel("W(n)/2^n")
    plt.title("Residual ratio proxy")
    plt.tight_layout()
    plt.savefig(out_dir / "plot_ratio.png", dpi=180)
    plt.close()

    rows = [r for r in bench_rows if r["family"] == "worstcase_search"]
    if rows:
        n_sorted = sorted({int(r["n"]) for r in rows})
        on = []
        off = []
        theory = []
        for n in n_sorted:
            rr_on = [r for r in rows if int(r["n"]) == n and r["mode"] == "modeA_on"]
            rr_off = [r for r in rows if int(r["n"]) == n and r["mode"] == "modeB_off"]
            on.append(float(statistics.mean(float(x["measured_nodes_including_terminals"]) for x in rr_on)))
            off.append(float(statistics.mean(float(x["measured_nodes_including_terminals"]) for x in rr_off)))
            theory.append(float(rr_on[0]["theory_worst_nodes_including_terminals"]) if rr_on else 0.0)
        plt.figure(figsize=(8, 5))
        plt.plot(n_sorted, on, marker="o", label="complement on")
        plt.plot(n_sorted, off, marker="o", label="complement off")
        plt.xlabel("n")
        plt.ylabel("Nodes (incl terminals)")
        plt.title("Worstcase-search nodes by mode")
        plt.legend()
        plt.tight_layout()
        plt.savefig(out_dir / "plot_mode_compare.png", dpi=180)
        plt.close()

        # Requested overlay: theory and measured worst-case in one plot
        plt.figure(figsize=(8, 5))
        plt.plot(n_sorted, theory, marker="o", linewidth=2.2, label="theory W(n)")
        plt.plot(n_sorted, off, marker="s", label="measured worstcase (modeB off)")
        plt.plot(n_sorted, on, marker="^", label="measured worstcase (modeA on)")
        plt.xlabel("n")
        plt.ylabel("Nodes (incl terminals)")
        plt.title("Theory vs measured worst-case ROBDD size")
        plt.legend()
        plt.tight_layout()
        plt.savefig(out_dir / "plot_theory_vs_measured_worstcase.png", dpi=180)
        plt.close()


def generate_report(out_dir: Path, theory_rows: list[dict[str, object]], layer_rows: list[dict[str, object]], bench_rows: list[dict[str, object]]) -> None:
    by_mode = {"modeA_on": [], "modeB_off": []}
    for r in bench_rows:
        by_mode[str(r["mode"])].append(float(r["measured_nodes_including_terminals"]))
    avg_on = statistics.mean(by_mode["modeA_on"]) if by_mode["modeA_on"] else 0.0
    avg_off = statistics.mean(by_mode["modeB_off"]) if by_mode["modeB_off"] else 0.0
    ratio = (avg_off / avg_on) if avg_on else 0.0

    bad_layer = [
        r for r in layer_rows
        if int(r["sum_width_plus_2"]) != int(r["theory_W_n"])
    ]
    monotonic_ok = all(
        int(theory_rows[i]["theta"]) <= int(theory_rows[i + 1]["theta"])
        for i in range(len(theory_rows) - 1)
    )
    lines = [
        "# ROBDD Worst-case Experiment Report",
        "",
        "## Highlights",
        f"- theta monotonic non-decreasing check: {'PASS' if monotonic_ok else 'FAIL'}",
        f"- layer-sum identity `sum_i min(r_i, R_i) + 2 = W(n)`: {'PASS' if not bad_layer else 'FAIL'}",
        f"- average nodes (modeA complement-edge on): {avg_on:.3f}",
        f"- average nodes (modeB complement-edge off): {avg_off:.3f}",
        f"- off/on node ratio: {ratio:.3f}",
        "",
        "## Files",
        "- `theory_theta.csv`: n, theta, W(n), ratio",
        "- `layer_intersection.csv`: per-layer top/bottom/min and identity check",
        "- `benchmark_results.csv`: 3 function families with modeA/modeB comparisons",
        "- optional PNG plots if matplotlib is available",
    ]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    out_dir = Path(__file__).resolve().parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    n_theory_max = 20
    theory_rows: list[dict[str, object]] = []
    for n in range(1, n_theory_max + 1):
        theta, w = theory_worst_case_size(n)
        theory_rows.append(
            {
                "n": n,
                "theta": theta,
                "W_n": w,
                "log2_n_floor": int(math.log2(n)),
                "theta_leq_log2_n": int(theta <= int(math.log2(n))),
                "W_over_2n": w / float(1 << n),
            }
        )
    write_csv(
        out_dir / "theory_theta.csv",
        theory_rows,
        ["n", "theta", "W_n", "log2_n_floor", "theta_leq_log2_n", "W_over_2n"],
    )

    layer_rows: list[dict[str, object]] = []
    for n in range(1, 21):
        rows = layer_widths(n)
        w = sum(r["width"] for r in rows) + 2
        theta, theory = theory_worst_case_size(n)
        for r in rows:
            layer_rows.append(
                {
                    "n": n,
                    "theta": theta,
                    "i": r["i"],
                    "top": r["top"],
                    "bottom": r["bottom"],
                    "width": r["width"],
                    "sum_width_plus_2": w,
                    "theory_W_n": theory,
                }
            )
    write_csv(
        out_dir / "layer_intersection.csv",
        layer_rows,
        ["n", "theta", "i", "top", "bottom", "width", "sum_width_plus_2", "theory_W_n"],
    )

    rnd = random.Random(20260407)
    bench_rows: list[dict[str, object]] = []
    families: list[tuple[str, Callable[[int], int]]] = [
        ("parity", parity_table),
        ("mux3", mux3_table),
        ("adder_lsb", adder_lsb_table),
    ]
    for n in range(4, 13):
        worst_table_on, _ = exhaustive_or_sampled_worst_case(n, samples=2000, rnd=rnd, use_complement_edges=True)
        worst_table_off, _ = exhaustive_or_sampled_worst_case(n, samples=2000, rnd=rnd, use_complement_edges=False)
        for mode, use_ce, t in [
            ("modeA_on", True, worst_table_on),
            ("modeB_off", False, worst_table_off),
        ]:
            bench_rows.append(bench_one_function(n, "worstcase_search", t, mode, use_ce))

        for _ in range(8):
            table = random_table(n, rnd)
            bench_rows.append(bench_one_function(n, "random_truth_table", table, "modeA_on", True))
            bench_rows.append(bench_one_function(n, "random_truth_table", table, "modeB_off", False))

        for fam_name, fam_builder in families:
            table = fam_builder(n)
            bench_rows.append(bench_one_function(n, fam_name, table, "modeA_on", True))
            bench_rows.append(bench_one_function(n, fam_name, table, "modeB_off", False))

    write_csv(
        out_dir / "benchmark_results.csv",
        bench_rows,
        [
            "n",
            "family",
            "mode",
            "use_complement_edges",
            "theta",
            "theory_worst_nodes_including_terminals",
            "measured_nonterminal_nodes",
            "measured_nodes_including_terminals",
            "measured_edges",
            "root_neg",
            "runtime_ms",
        ],
    )

    maybe_plot(out_dir, theory_rows, bench_rows)
    generate_report(out_dir, theory_rows, layer_rows, bench_rows)


if __name__ == "__main__":
    main()
