"""S8 case definitions."""

import copy

from .inputs import SENTINEL, buffer, step


def add_cases(add):
    for m, n, k, cores in ((16, 16, 32, 1), (17, 19, 35, 1), (17, 19, 35, 15)):
        sa, sb, sc = k + 5, n + 5, n + 3
        a = [(r * 3 + c) % 17 - 8 for r in range(m) for c in range(sa)]
        b = [(r - 2 * c) % 13 - 6 for r in range(k) for c in range(sb)]
        out = [SENTINEL] * (m * sc)
        for r in range(m):
            for c in range(n): out[r * sc + c] = sum(a[r * sa + t] * b[t * sb + c] for t in range(k))
        matrix = step("matmul_i8",
            {"A": buffer("i8", a, "dram"), "B": buffer("i8", b, "dram"),
             "C": buffer("i32", [SENTINEL] * (m * sc), "dram")},
            {"M": m, "N": n, "K": k, "SA": sa, "SB": sb, "SC": sc},
            {"BM": 16, "BN": 16, "BK": 32}, [(m + 15) // 16, (n + 15) // 16, 1], {"C": out})
        add(f"S8.dot.{m}x{n}x{k}.mask{cores}", "S8", [matrix], cores=cores, features=("zvt", "schedule", "dma"), abi_version=3)
    add("S8.reject-v2", "S8", [copy.deepcopy(matrix)], abi_version=2,
        error="NC_ABI_CAPACITY")
