"""S5 reductions and prefix scan."""

import triton
import triton.language as tl


@triton.jit
def reduce_sum(X, Y, N, BLOCK: tl.constexpr):
    offsets = tl.arange(0, BLOCK)
    value = tl.load(X + offsets, offsets < N, other=0)
    tl.store(Y, tl.sum(value, axis=0))


@triton.jit
def reduce_max(X, Y, N, BLOCK: tl.constexpr):
    offsets = tl.arange(0, BLOCK)
    value = tl.load(X + offsets, offsets < N, other=-2147483648)
    tl.store(Y, tl.max(value, axis=0))


@triton.jit
def argmax_i32(X, Y, N, BLOCK: tl.constexpr):
    offsets = tl.arange(0, BLOCK)
    value = tl.load(X + offsets, offsets < N, other=-2147483648)
    tl.store(Y, tl.argmax(value, axis=0, tie_break_left=True))


@triton.jit
def prefix_sum(X, Y, N, BLOCK: tl.constexpr):
    offsets = tl.arange(0, BLOCK)
    value = tl.load(X + offsets, offsets < N, other=0)
    tl.store(Y + offsets, tl.cumsum(value, axis=0), offsets < N)
