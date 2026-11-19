"""S6 logical grid coordinates and grid sizes."""

import triton
import triton.language as tl


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
