"""Mandatory standard-JIT host entry for adapters; no direct AOT compilation here."""

import hashlib
import importlib


def launch(step, device_buffers, *, request_sha256, step_index):
    from triton.runtime import driver

    if driver.active.get_current_target().backend != "coral":
        raise ValueError("standard JIT did not select the Coral driver")
    kernel = getattr(importlib.import_module("kernels"), step["kernel"])
    return call_kernel(kernel, step, device_buffers, request_sha256=request_sha256, step_index=step_index)


def call_kernel(kernel, step, device_buffers, *, request_sha256, step_index):
    """Separate helper also permits host-only route tests with a recording kernel."""
    arguments = []
    for name in kernel.arg_names:
        if name in step["constants"]:
            continue
        arguments.append(device_buffers[name] if name in step["buffers"] else step["scalars"][name])
    compiled = kernel[tuple(step["grid"])](*arguments, **step["constants"])
    zero = any(n == 0 for n in step["grid"])
    if not zero and (compiled is None or not hasattr(compiled, "asm")):
        raise ValueError("standard JIT did not return a compiled kernel")
    assembly = getattr(compiled, "asm", {}) if compiled is not None else {}
    elf = assembly.get("elf")
    if not zero and not isinstance(elf, bytes):
        raise ValueError("standard JIT did not return Coral ELF bytes")
    record = {"protocol": 2, "api": "kernel[grid](...)", "backend": "coral",
              "kernel": step["kernel"], "grid": step["grid"], "step": step_index,
              "request_sha256": request_sha256, "zero_grid": zero,
              "compiled_elf_sha256": hashlib.sha256(elf).hexdigest() if isinstance(elf, bytes) else None}
    # The adapter must still wait for real device completion and collect raw execution/cache logs.
    return compiled, record
