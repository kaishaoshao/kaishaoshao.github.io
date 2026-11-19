"""S5 case definitions."""

from .inputs import SENTINEL, buffer, i32, step


def add_cases(add):
    for n in (1, 3, 37, 1000):
        data = [i % 31 - 15 for i in range(n)]; block = 1 << (n - 1).bit_length()
        for kernel, value in (("reduce_sum", i32(sum(data))), ("reduce_max", max(data))):
            add(f"S5.{kernel}.n{n}", "S5", [step(kernel, {"X": buffer("i32", data),
                "Y": buffer("i32", [SENTINEL])}, {"N": n}, {"BLOCK": max(16, block)},
                expected={"Y": [value]})], features=("rvv",))
    for data in ([-5, -2, -2, -7, -3], [-2147483648]):
        add(f"S5.argmax.n{len(data)}", "S5", [step("argmax_i32", {"X": buffer("i32", data),
            "Y": buffer("i32", [SENTINEL])}, {"N": len(data)}, {"BLOCK": 16},
            expected={"Y": [data.index(max(data))]})])
    data = [i % 7 - 2 for i in range(37)]
    add("S5.scan", "S5", [step("prefix_sum", {"X": buffer("i32", data),
        "Y": buffer("i32", [SENTINEL] * 37)}, {"N": 37}, {"BLOCK": 64},
        expected={"Y": [sum(data[:i + 1]) for i in range(37)]})])
