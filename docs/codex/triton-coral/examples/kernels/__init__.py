"""Look up sample kernels without importing Triton until a kernel is requested."""

import hashlib
from importlib import import_module
import json
from pathlib import Path


MODULE_KERNELS = {
    "s1_scalar": ("empty_kernel", "scalar_copy", "scalar_add"),
    "s2_block": ("block_add", "vector_add", "block_select", "masked_other"),
    "s3_abi": ("sum_scalars",),
    "s4_structured": ("strided_bias", "loop_sum", "transpose_tile", "scalar_while"),
    "s5_collectives": ("reduce_sum", "reduce_max", "argmax_i32", "prefix_sum"),
    "s6_grid": ("grid_ids", "grid_ids_3d"),
    "s8_dot": ("matmul_i8",),
    "s9_extended": ("fp32_add", "bf16_widen", "indexed_copy", "sort_i32", "atomic_add_i32"),
}
_KERNEL_MODULES = {name: module for module, names in MODULE_KERNELS.items() for name in names}


def __getattr__(name):
    if name not in _KERNEL_MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(f".{_KERNEL_MODULES[name]}", __name__), name)


def source_sha256():
    """Bind requests to the kernel package, with portable text line endings."""
    sources = {path.name: path.read_text(encoding="utf-8")
               for path in Path(__file__).parent.glob("*.py")}
    return hashlib.sha256(json.dumps(sources, sort_keys=True).encode("utf-8")).hexdigest()
