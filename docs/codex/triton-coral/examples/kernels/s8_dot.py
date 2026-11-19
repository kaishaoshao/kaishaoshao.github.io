"""S8 tiled integer matrix multiplication."""

import triton
import triton.language as tl


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
