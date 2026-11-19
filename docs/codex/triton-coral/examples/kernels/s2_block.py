"""S2 block and mask kernels, reused for JIT and storage tests."""

import triton
import triton.language as tl


@triton.jit
def block_add(X, Y, N, DELTA: tl.constexpr, BLOCK: tl.constexpr):
    offsets = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)
    value = tl.load(X + offsets, offsets < N, other=0)
    tl.store(Y + offsets, value + DELTA, offsets < N)


@triton.jit
def vector_add(X, Y, Z, N, BLOCK: tl.constexpr):
    offsets = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)
    mask = offsets < N
    x = tl.load(X + offsets, mask=mask, other=0)
    y = tl.load(Y + offsets, mask=mask, other=0)
    tl.store(Z + offsets, x + y, mask=mask)


@triton.jit
def block_select(X, Y, N, POSITIVE: tl.constexpr, BLOCK: tl.constexpr):
    offsets = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)
    value = tl.load(X + offsets, offsets < N, other=0)
    if POSITIVE:
        result = tl.where(value > 0, value * 2, value - 1)
    else:
        result = value + 3
    tl.store(Y + offsets, result, offsets < N)


@triton.jit
def masked_other(X, Y, N, BLOCK: tl.constexpr):
    offsets = tl.arange(0, BLOCK)
    value = tl.load(X + offsets, offsets < N, other=7)
    tl.store(Y + offsets, value)
