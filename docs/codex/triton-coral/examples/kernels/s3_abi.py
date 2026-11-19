"""S3 kernel with six runtime scalar arguments."""

import triton
import triton.language as tl


@triton.jit
def sum_scalars(X, Y, A, B, C, D, E, F):
    tl.store(Y, tl.load(X) + A + B + C + D + E + F)
