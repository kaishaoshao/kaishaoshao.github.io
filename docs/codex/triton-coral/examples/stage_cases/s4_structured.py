"""S4 case definitions."""

from .inputs import SENTINEL, buffer, step


def add_cases(add):
    m, n, sx, sy = 5, 7, 11, 9
    data = [SENTINEL] * (m * sx); expected = [SENTINEL] * (m * sy)
    for r in range(m):
        for c in range(n):
            data[r * sx + c] = 10 * r - c
            expected[r * sy + c] = 10 * r + c
    add("S4.stride-broadcast", "S4", [step("strided_bias", {"X": buffer("i32", data),
        "Bias": buffer("i32", [2 * c for c in range(n)]), "Y": buffer("i32", [SENTINEL] * (m * sy))},
        {"M": m, "N": n, "SX": sx, "SY": sy}, {"BM": 4, "BN": 8}, [2, 1, 1], {"Y": expected})],
        features=("structured",))
    for rounds in (0, 1, 3):
        data = [r * 11 - c for r in range(rounds) for c in range(8)]
        add(f"S4.loop.r{rounds}", "S4", [step("loop_sum", {"X": buffer("i32", data),
            "Y": buffer("i32", [SENTINEL] * 5)}, {"N": 5, "R": rounds, "STRIDE": 8}, {"BLOCK": 8},
            expected={"Y": [sum(r * 11 - c for r in range(rounds)) for c in range(5)]})], features=("structured",))
    for flag in (0, 1):
        add(f"S4.while.{flag}", "S4", [step("scalar_while", {"X": buffer("i32", [9]),
            "Y": buffer("i32", [SENTINEL])}, {"R": 3, "FLAG": flag},
            expected={"Y": [9 + 3 * (2 if flag else -1)]})], features=("structured",))
    tile = [i * 3 - 7 for i in range(8)]
    add("S4.transpose", "S4", [step("transpose_tile", {"X": buffer("i32", tile),
        "Y": buffer("i32", [SENTINEL] * 8)}, expected={"Y": tile[::4] + tile[1::4] + tile[2::4] + tile[3::4]})],
        features=("structured",))
