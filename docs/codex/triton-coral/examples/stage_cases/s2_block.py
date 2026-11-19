"""S2 case definitions."""

from .inputs import SENTINEL, buffer, i32, step, vector


def add_cases(add):
    for n in (0, 1, 3, 37, 128, 1000):
        for block in (16, 64):
            add(f"S2.mask.n{n}.b{block}", "S2", [vector(n, block)])
    add("S2.inplace", "S2", [vector(inplace=True)])
    for positive in (True, False):
        data = [-9, 0, 11]
        expected = [i32((x * 2 if x > 0 else x - 1) if positive else x + 3) for x in data]
        add(f"S2.constexpr.{int(positive)}", "S2", [step("block_select",
            {"X": buffer("i32", data), "Y": buffer("i32", [SENTINEL] * 3)}, {"N": 3},
            {"POSITIVE": positive, "BLOCK": 16}, expected={"Y": expected})])
    add("S2.other", "S2", [step("masked_other", {"X": buffer("i32", [3, 4, 5]),
        "Y": buffer("i32", [SENTINEL] * 16)}, {"N": 3}, {"BLOCK": 16},
        expected={"Y": [3, 4, 5] + [7] * 13})])
    x = [i - 20 for i in range(37)]
    y = [31 - 2 * i for i in range(37)]
    add("S2.vector-add", "S2", [step("vector_add", {"X": buffer("i32", x),
        "Y": buffer("i32", y), "Z": buffer("i32", [SENTINEL] * 37)},
        {"N": 37}, {"BLOCK": 16}, [3, 1, 1], {"Z": [a + b for a, b in zip(x, y)]})])
    add("S2.bad-block", "S2", [vector(3, 3)], error="NC_UNSUPPORTED_SHAPE")
