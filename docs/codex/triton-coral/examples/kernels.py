"""Small, cumulative Triton sources. No Coral execution adapter is implemented here."""

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


@triton.jit
def sum_scalars(X, Y, A, B, C, D, E, F):
    tl.store(Y, tl.load(X) + A + B + C + D + E + F)


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


@triton.jit
def grid_ids(Y):
    x = tl.program_id(0)
    y = tl.program_id(1)
    nx = tl.num_programs(0)
    ny = tl.num_programs(1)
    tl.store(Y + x + nx * y, x + 100 * y + 10000 * nx + 1000000 * ny)


@triton.jit
def grid_ids_3d(Y):
    x, y, z = tl.program_id(0), tl.program_id(1), tl.program_id(2)
    nx, ny, nz = tl.num_programs(0), tl.num_programs(1), tl.num_programs(2)
    tl.store(Y + x + nx * (y + ny * z), x + 10 * y + 100 * z + 1000 * nz)


@triton.jit
def matmul_i8(A, B, C, M, N, K, SA, SB, SC,
              BM: tl.constexpr, BN: tl.constexpr, BK: tl.constexpr):
    rows = tl.program_id(0) * BM + tl.arange(0, BM)
    cols = tl.program_id(1) * BN + tl.arange(0, BN)
    inner = tl.arange(0, BK)
    acc = tl.full((BM, BN), 0, tl.int32)
    for tile in range(tl.cdiv(K, BK)):
        k = tile * BK + inner
        a = tl.load(A + rows[:, None] * SA + k[None, :],
                    (rows[:, None] < M) & (k[None, :] < K), other=0)
        b = tl.load(B + k[:, None] * SB + cols[None, :],
                    (k[:, None] < K) & (cols[None, :] < N), other=0)
        acc = tl.dot(a, b, acc)
    tl.store(C + rows[:, None] * SC + cols[None, :], acc,
             (rows[:, None] < M) & (cols[None, :] < N))


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
