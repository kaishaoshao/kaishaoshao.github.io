"""S9 optional dtype, irregular memory and operation coverage."""

import triton
import triton.language as tl


@triton.jit
def fp32_add(X, Y, N, DELTA: tl.constexpr, BLOCK: tl.constexpr):
    offsets = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)
    value = tl.load(X + offsets, offsets < N, other=0)
    tl.store(Y + offsets, value + DELTA, offsets < N)


@triton.jit
def bf16_widen(X, Y, N, BLOCK: tl.constexpr):
    offsets = tl.arange(0, BLOCK)
    value = tl.load(X + offsets, offsets < N, other=0).to(tl.float32)
    tl.store(Y + offsets, value + 0.5, offsets < N)


@triton.jit
def indexed_copy(X, Index, Y, N, SCATTER: tl.constexpr, BLOCK: tl.constexpr):
    offsets = tl.arange(0, BLOCK)
    mask = offsets < N
    index = tl.load(Index + offsets, mask=mask, other=0)
    if SCATTER:
        value = tl.load(X + offsets, mask=mask, other=0)
        tl.store(Y + index, value, mask=mask)
    else:
        value = tl.load(X + index, mask=mask, other=0)
        tl.store(Y + offsets, value, mask=mask)


@triton.jit
def sort_i32(X, Y, BLOCK: tl.constexpr):
    offsets = tl.arange(0, BLOCK)
    values = tl.load(X + offsets)
    tl.store(Y + offsets, tl.sort(values, descending=True))


@triton.jit
def atomic_add_i32(Counter, Old, DELTA):
    old = tl.atomic_add(Counter, DELTA, sem="relaxed", scope="gpu")
    tl.store(Old, old)
