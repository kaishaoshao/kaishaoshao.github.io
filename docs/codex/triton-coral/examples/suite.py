"""Deterministic inputs and independent references, using only the standard library."""

import argparse
import json

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


def cases():
    result = []

    def add(id, stage, steps, *, mode="aot", cores=1, features=(), error=None, **extra):
        result.append({"id": id, "stage": stage, "mode": mode, "core_mask": cores,
                       "features": list(features), "steps": steps, "error": error, **extra})

    scalar = lambda k, x, d=1: step(k, {"X": buffer("i32", [x]), "Y": buffer("i32", [SENTINEL])},
                                    constants={} if k == "scalar_copy" else {"DELTA": d},
                                    expected={"Y": [x if k == "scalar_copy" else i32(x + d)]})
    add("S0.frontend", "S0", [scalar("scalar_copy", -3)], mode="frontend")
    add("S0.bad-target", "S0", [scalar("scalar_copy", -3)], mode="frontend",
        error="NC_UNSUPPORTED_TARGET", target_override="coral-invalid")
    add("S1.copy", "S1", [scalar("scalar_copy", -37)])
    add("S1.add", "S1", [scalar("scalar_add", 11, 7), scalar("scalar_add", -23, -5)])
    add("S1.wrap", "S1", [scalar("scalar_add", 2147483647)])
    add("S1.reload", "S1", [scalar("scalar_copy", 19), scalar("scalar_add", -29, 7), scalar("scalar_copy", 43)])
    add("S1.bad-abi", "S1", [scalar("scalar_copy", 1)], error="NC_ABI_VERSION", abi_version=-1)
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
    add("S2.bad-block", "S2", [vector(3, 3)], error="NC_UNSUPPORTED_SHAPE")
    changed = vector()
    changed["buffers"]["X"]["values"] = [i32(x + 19) for x in changed["buffers"]["X"]["values"]]
    changed["expected"]["Y"] = [i32(x + 1) for x in changed["buffers"]["X"]["values"]]
    add("S3.cache", "S3", [vector(), changed, vector(delta=7)], mode="jit",
        cache_pattern=[False, True, False], isolate_cache=True)
    zero = vector(); zero["grid"] = [0, 1, 1]; zero["expected"]["Y"] = [SENTINEL] * 37
    add("S3.zero-grid", "S3", [zero], mode="jit", zero_launch=True)
    add("S3.bad-buffer", "S3", [vector()], mode="jit", error="NC_INVALID_BUFFER", invalidate="X")
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
    for n in (1, 3, 37, 1000):
        data = [i % 31 - 15 for i in range(n)]; block = 1 << (n - 1).bit_length()
        for kernel, value in (("reduce_sum", i32(sum(data))), ("reduce_max", max(data))):
            add(f"S5.{kernel}.n{n}", "S5", [step(kernel, {"X": buffer("i32", data),
                "Y": buffer("i32", [SENTINEL])}, {"N": n}, {"BLOCK": max(16, block)},
                expected={"Y": [value]})], features=("rvv",))
    for cores in (1, 3, 15):
        for nx, ny in ((1, 1), (5, 13)):
            out = [x + 100 * y + 10000 * nx + 1000000 * ny for y in range(ny) for x in range(nx)]
            add(f"S6.grid.{nx}x{ny}.mask{cores}", "S6", [step("grid_ids",
                {"Y": buffer("i32", [SENTINEL] * (nx * ny))}, grid=[nx, ny, 1], expected={"Y": out})],
                cores=cores, features=("schedule",))
    for cores in (1, 15):
        add(f"S7.tiers.mask{cores}", "S7", [vector(257, 16, region="hbf")], cores=cores,
            features=("schedule", "dma"), storage_path=["hbf", "dram", "dtcm", "dram"], buffer_policy="single")
    for suffix, error in (("hbf-write", "NC_READ_ONLY"), ("owner", "NC_OWNER"), ("dma-mid", "NC_DMA_ERROR")):
        transfer = vector(37, 16, region="hbf")
        fault = None
        if suffix == "hbf-write":
            transfer["buffers"]["Y"]["region"] = "hbf"
        elif suffix == "owner":
            transfer["buffers"]["Y"].update(region="dtcm", owner=3)
        else:
            fault = {"engine": "dma", "after_bytes": 16}
        add("S7." + suffix, "S7", [transfer], error=error,
            fault=fault, features=("dma",), storage_path=["hbf", "dram", "dtcm", "dram"])
    for m, n, k, cores in ((16, 16, 32, 1), (17, 19, 35, 1), (17, 19, 35, 15)):
        sa, sb, sc = k + 5, n + 5, n + 3
        a = [(r * 3 + c) % 17 - 8 for r in range(m) for c in range(sa)]
        b = [(r - 2 * c) % 13 - 6 for r in range(k) for c in range(sb)]
        out = [SENTINEL] * (m * sc)
        for r in range(m):
            for c in range(n): out[r * sc + c] = sum(a[r * sa + t] * b[t * sb + c] for t in range(k))
        add(f"S8.dot.{m}x{n}x{k}.mask{cores}", "S8", [step("matmul_i8",
            {"A": buffer("i8", a, "dram"), "B": buffer("i8", b, "dram"),
             "C": buffer("i32", [SENTINEL] * (m * sc), "dram")},
            {"M": m, "N": n, "K": k, "SA": sa, "SB": sb, "SC": sc},
            {"BM": 16, "BN": 16, "BK": 32}, [(m + 15) // 16, (n + 15) // 16, 1], {"C": out})],
            cores=cores, features=("zvt", "schedule", "dma"))
    add("S9.overlap", "S9", [vector(257, 16, region="hbf")], cores=15,
        features=("schedule", "dma", "overlap"), storage_path=["hbf", "dram", "dtcm", "dram"],
        buffer_policy="double", compare_single_buffer=True)
    floats = [-2.0, -0.5, 0.0, 0.5, 2.0]
    for kernel, dtype, feature in (("fp32_add", "f32", "fp32"), ("bf16_widen", "bf16", "bf16")):
        constants = {"BLOCK": 16, **({"DELTA": 0.5} if kernel == "fp32_add" else {})}
        add("S9." + feature, "S9", [step(kernel, {"X": buffer(dtype, floats),
            "Y": buffer("f32", [float(SENTINEL)] * 5)}, {"N": 5}, constants,
            expected={"Y": [x + 0.5 for x in floats]})], features=(feature,), optional=True,
            tolerance={"rtol": 1e-6, "atol": 1e-6})
    return result


def inventory():
    all_cases = cases()
    return [{"stage": f"S{i}", "case_ids": [c["id"] for c in all_cases if c["stage"] == f"S{i}"],
             "kernels": sorted({s["kernel"] for c in all_cases if c["stage"] == f"S{i}" for s in c["steps"]})}
            for i in range(10)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", action="store_true")
    args = parser.parse_args()
    print(json.dumps(inventory() if args.inventory else cases(), ensure_ascii=False, indent=2))
