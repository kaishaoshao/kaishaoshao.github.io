"""Shared input builders and independent numerical helpers."""

SENTINEL = 1515870810


def i32(value):
    return (value + (1 << 31)) % (1 << 32) - (1 << 31)


def buffer(dtype, values, region="shared", **extra):
    return {"dtype": dtype, "values": values, "region": region, **extra}


def step(kernel, buffers, scalars=None, constants=None, grid=None, expected=None, **extra):
    return {"kernel": kernel, "buffers": buffers, "scalars": scalars or {},
            "constants": constants or {}, "grid": grid or [1, 1, 1],
            "expected": expected or {}, **extra}


def vector(n=37, block=16, delta=1, *, region="shared", inplace=False):
    data = [i32(17 * i - 211) for i in range(n)]
    return step("block_add", {"X": buffer("i32", data, region),
                             "Y": buffer("i32", [SENTINEL] * n, "dram" if region == "hbf" else region,
                                         **({"alias_of": "X"} if inplace else {}))},
                {"N": n}, {"DELTA": delta, "BLOCK": block},
                [max(1, (n + block - 1) // block), 1, 1],
                {"Y": [i32(x + delta) for x in data]})


def scalar(kernel, value, delta=1):
    return step(
        kernel,
        {"X": buffer("i32", [value]), "Y": buffer("i32", [SENTINEL])},
        constants={} if kernel == "scalar_copy" else {"DELTA": delta},
        expected={"Y": [value if kernel == "scalar_copy" else i32(value + delta)]},
    )
