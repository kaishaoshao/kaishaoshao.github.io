#define __global__ __attribute__((global))
#define __host__ __attribute__((host))

__host__ int host_only() { return 7; }
__global__ void bad_kernel(int* out) { *out = host_only(); }
