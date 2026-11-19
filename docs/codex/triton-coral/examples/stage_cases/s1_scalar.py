"""S1 case definitions."""

import copy

from .inputs import SENTINEL, buffer, scalar, step


def add_cases(add):
    empty = step("empty_kernel", {"X": buffer("i32", [0]), "Y": buffer("i32", [0])})
    add("S1.empty.frontend", "S1", [empty], mode="frontend")
    add("S1.empty.llvm", "S1", [copy.deepcopy(empty)], mode="ir", checkpoint="llvm-dialect")
    add("S1.copy", "S1", [scalar("scalar_copy", -37)])
    add("S1.add", "S1", [scalar("scalar_add", 11, 7), scalar("scalar_add", -23, -5)])
    add("S1.wrap", "S1", [scalar("scalar_add", 2147483647)])
    add("S1.reload", "S1", [scalar("scalar_copy", 19), scalar("scalar_add", -29, 7), scalar("scalar_copy", 43)])
    add("S1.bad-abi", "S1", [scalar("scalar_copy", 1)], error="NC_ABI_VERSION", abi_version=-1)
