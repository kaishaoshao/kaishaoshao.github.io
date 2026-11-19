"""Collect all stage cases and their standard-JIT mirrors."""

import argparse
import copy
import json

from stage_cases import (
    s0_frontend,
    s1_scalar,
    s2_block,
    s3_jit,
    s4_structured,
    s5_collectives,
    s6_grid,
    s7_storage,
    s8_dot,
    s9_extended,
)

STAGES = (
    s0_frontend,
    s1_scalar,
    s2_block,
    s3_jit,
    s4_structured,
    s5_collectives,
    s6_grid,
    s7_storage,
    s8_dot,
    s9_extended,
)


def cases():
    result = []

    def add(id, stage, steps, *, mode="aot", cores=1, features=(), error=None, **extra):
        result.append({"id": id, "stage": stage, "mode": mode, "core_mask": cores,
                       "features": list(features), "steps": steps, "error": error, **extra})

    for stage in STAGES:
        stage.add_cases(add)

    # Preserve original case IDs. JIT mirrors are explicit cases with their own mode and earliest stage.
    for original in list(result):
        if original["mode"] != "aot" or original["error"]:
            continue
        mirror = copy.deepcopy(original)
        mirror["id"] += ".jit"; mirror["mode"] = "jit"
        mirror["stage"] = "S" + str(max(3, int(original["stage"][1:])))
        if mirror.get("optional"):
            mirror["capability"] = mirror["capability"].removesuffix(".aot") + ".jit"
        result.append(mirror)
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
