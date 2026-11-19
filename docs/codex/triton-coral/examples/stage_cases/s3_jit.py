"""S3 case definitions."""

import copy

from .inputs import SENTINEL, buffer, i32, step, vector


def add_cases(add):
    changed = vector()
    changed["buffers"]["X"]["values"] = [i32(x + 19) for x in changed["buffers"]["X"]["values"]]
    changed["expected"]["Y"] = [i32(x + 1) for x in changed["buffers"]["X"]["values"]]
    add("S3.cache", "S3", [vector(), changed, vector(delta=7)], mode="jit",
        cache_pattern=[False, True, False], isolate_cache=True)
    zero = vector(); zero["grid"] = [0, 1, 1]; zero["expected"]["Y"] = [SENTINEL] * 37
    add("S3.zero-grid", "S3", [zero], mode="jit", zero_launch=True)
    add("S3.bad-buffer", "S3", [vector()], mode="jit", error="NC_INVALID_BUFFER", invalidate="X")
    six = step("sum_scalars", {"X": buffer("i32", [-10]), "Y": buffer("i32", [SENTINEL])},
               {name: i + 1 for i, name in enumerate("ABCDEF")}, expected={"Y": [11]})
    add("S3.abi-v3", "S3", [six], abi_version=3)
    add("S3.abi-v2-capacity", "S3", [copy.deepcopy(six)], abi_version=2, error="NC_ABI_CAPACITY")
