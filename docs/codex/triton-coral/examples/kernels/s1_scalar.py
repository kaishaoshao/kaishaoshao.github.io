"""S1 scalar lowering and device execution kernels."""

import triton
import triton.language as tl


@triton.jit
def empty_kernel(X, Y):
    pass


@triton.jit
def scalar_copy(X, Y):
    value = tl.load(X)
    tl.store(Y, value)


@triton.jit
def scalar_add(X, Y, DELTA: tl.constexpr):
    value = tl.load(X)
    tl.store(Y, value + DELTA)
