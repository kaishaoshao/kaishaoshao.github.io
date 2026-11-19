"""S4 structured addressing, layout changes and control flow."""

import triton
import triton.language as tl


@triton.jit
def strided_bias(X, Bias, Y, M, N, SX, SY, BM: tl.constexpr, BN: tl.constexpr):
    rows = tl.program_id(0) * BM + tl.arange(0, BM)
    cols = tl.arange(0, BN)
    valid = (rows[:, None] < M) & (cols[None, :] < N)
    value = tl.load(X + rows[:, None] * SX + cols[None, :], valid, other=0)
    bias = tl.load(Bias + cols, cols < N, other=0)
    tl.store(Y + rows[:, None] * SY + cols[None, :], value + bias[None, :], valid)


@triton.jit
def loop_sum(X, Y, N, R, STRIDE, BLOCK: tl.constexpr):
    cols = tl.arange(0, BLOCK)
    acc = tl.full((BLOCK,), 0, tl.int32)
    pointer = X + cols
    for _ in range(R):
        acc += tl.load(pointer, cols < N, other=0)
        pointer += STRIDE
    tl.store(Y + cols, acc, cols < N)


@triton.jit
def transpose_tile(X, Y):
    offsets = tl.arange(0, 8)
    tile = tl.reshape(tl.load(X + offsets), (2, 4))
    tl.store(Y + offsets, tl.reshape(tl.trans(tile), (8,)))


@triton.jit
def scalar_while(X, Y, R, FLAG):
    value = tl.load(X)
    index = 0
    while index < R:
        if FLAG:
            value += 2
        else:
            value -= 1
        index += 1
    tl.store(Y, value)
