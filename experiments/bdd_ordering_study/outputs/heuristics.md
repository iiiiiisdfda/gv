# BDD Variable Ordering Study

Functions: parity, mux, adder_lsb, majority, random
Modes compared: File / RFile / DFS(influence-desc) / RDFS(influence-asc)

## Best mode by function
- parity: File (17 nodes)
- mux: File (9 nodes)
- adder_lsb: File (7 nodes)
- majority: File (22 nodes)
- random: File (72 nodes)

## Heuristic conclusion
- DFS wins: 0 / 5
- RDFS wins: 0 / 5
- File wins: 5 / 5
- RFile wins: 0 / 5
- Recommended default: start with DFS; fallback to RDFS when DFS is poor on symmetric/high-inversion functions.
