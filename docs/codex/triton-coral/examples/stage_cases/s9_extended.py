"""S9 case definitions."""

from .inputs import SENTINEL, buffer, step, vector


def add_cases(add):
    add("S9.overlap", "S9", [vector(257, 16, region="hbf")], cores=15,
        features=("schedule", "dma", "overlap"), storage_path=["hbf", "dram", "dtcm", "dram"],
        buffer_policy="double", compare_single_buffer=True)
    floats = [-2.0, -0.5, 0.0, 0.5, 2.0]
    for kernel, dtype, feature in (("fp32_add", "f32", "fp32"), ("bf16_widen", "bf16", "bf16")):
        constants = {"BLOCK": 16, **({"DELTA": 0.5} if kernel == "fp32_add" else {})}
        add("S9." + feature, "S9", [step(kernel, {"X": buffer(dtype, floats),
            "Y": buffer("f32", [float(SENTINEL)] * 5)}, {"N": 5}, constants,
            expected={"Y": [x + 0.5 for x in floats]})], features=(feature,), optional=True,
            tolerance={"rtol": 1e-6, "atol": 1e-6}, capability=feature + ".basic.aot", requires_stage="S5")
    data = [17, -8, 5, 11, -2, 42]
    indices = [4, 0, 5, 3, 1, 2]
    for scatter in (False, True):
        operation = "scatter" if scatter else "gather"
        expected = [data[indices.index(i)] if scatter else data[indices[i]] for i in range(len(data))]
        add("S9." + operation, "S9", [step("indexed_copy", {"X": buffer("i32", data),
            "Index": buffer("i32", indices), "Y": buffer("i32", [SENTINEL] * len(data))},
            {"N": len(data)}, {"SCATTER": scatter, "BLOCK": 8}, expected={"Y": expected})],
            optional=True, capability=f"{operation}.basic.aot", requires_stage="S5")
    data = [3, -2, 7, 3, 0, -9, 7, 1]
    add("S9.sort", "S9", [step("sort_i32", {"X": buffer("i32", data),
        "Y": buffer("i32", [SENTINEL] * 8)}, constants={"BLOCK": 8},
        expected={"Y": sorted(data, reverse=True)})],
        optional=True, capability="sort.basic.aot", requires_stage="S5")
    add("S9.atomic-add", "S9", [step("atomic_add_i32", {"Counter": buffer("i32", [41]),
        "Old": buffer("i32", [SENTINEL])}, {"DELTA": 2}, expected={"Counter": [43], "Old": [41]})],
        optional=True, capability="atomic_add.single_program.aot", requires_stage="S6")
