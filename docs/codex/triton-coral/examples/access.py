"""Logical element access oracle; physical DMA padding is checked separately."""

import itertools

DTYPE_BYTES = {"i8": 1, "bf16": 2, "i32": 4, "f32": 4}


def program_accesses(step, program):
    """Map (binding, direction) to active element indices for one logical program."""
    name, a, k = step["kernel"], step["scalars"], step["constants"]
    result = {}

    def add(binding, mode, indices):
        result.setdefault((binding, mode), set()).update(indices)

    if name == "empty_kernel":
        return result
    if name in ("scalar_copy", "scalar_add", "sum_scalars", "scalar_while"):
        add("X", "read", [0]); add("Y", "write", [0])
    elif name in ("block_add", "block_select", "fp32_add"):
        indices = range(program[0] * k["BLOCK"], min((program[0] + 1) * k["BLOCK"], a["N"]))
        indices = list(indices); add("X", "read", indices); add("Y", "write", indices)
    elif name in ("masked_other", "bf16_widen"):
        add("X", "read", range(a["N"]))
        add("Y", "write", range(k["BLOCK"] if name == "masked_other" else a["N"]))
    elif name == "strided_bias":
        rows = range(program[0] * k["BM"], min((program[0] + 1) * k["BM"], a["M"]))
        rows = list(rows)
        add("X", "read", [r * a["SX"] + c for r in rows for c in range(a["N"])])
        add("Bias", "read", range(a["N"]))
        add("Y", "write", [r * a["SY"] + c for r in rows for c in range(a["N"])])
    elif name == "loop_sum":
        add("X", "read", [r * a["STRIDE"] + c for r in range(a["R"]) for c in range(a["N"])])
        add("Y", "write", range(a["N"]))
    elif name in ("reduce_sum", "reduce_max"):
        add("X", "read", range(a["N"])); add("Y", "write", [0])
    elif name == "grid_ids":
        add("Y", "write", [program[0] + step["grid"][0] * program[1]])
    elif name == "matmul_i8":
        rows = range(program[0] * k["BM"], min((program[0] + 1) * k["BM"], a["M"]))
        cols = range(program[1] * k["BN"], min((program[1] + 1) * k["BN"], a["N"]))
        rows, cols = list(rows), list(cols)
        add("A", "read", [r * a["SA"] + t for r in rows for t in range(a["K"])])
        add("B", "read", [t * a["SB"] + c for t in range(a["K"]) for c in cols])
        add("C", "write", [r * a["SC"] + c for r in rows for c in cols])
    else:
        raise ValueError("no access contract for kernel: " + name)
    return {key: indices for key, indices in result.items() if indices}


def all_programs(step):
    return list(itertools.product(*(range(n) for n in step["grid"])))


def select_cases(all_cases, stage, *, cumulative=False, ids=(), include_optional=False, validated=()):
    """Validated optional capabilities become mandatory regressions, including the G5 side track."""
    known = {c.get("capability") for c in all_cases if c.get("optional")}
    if not set(validated) <= known:
        raise ValueError("unknown validated capability")
    selected = []
    for case in all_cases:
        normal_stage = int(case["stage"][1:]) <= int(stage[1:]) if cumulative else case["stage"] == stage
        side_track = (cumulative and case.get("capability") in validated and
                      int(case.get("requires_stage", case["stage"])[1:]) <= int(stage[1:]))
        if not (normal_stage or side_track) or (ids and case["id"] not in ids):
            continue
        if case.get("optional") and not (include_optional or ids or case.get("capability") in validated):
            continue
        selected.append(case)
    if not selected or not set(ids) <= {c["id"] for c in selected}:
        raise ValueError("no cases selected, unknown case ID, or case outside the selected stages")
    return selected
