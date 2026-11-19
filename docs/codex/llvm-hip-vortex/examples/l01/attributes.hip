#define __global__ __attribute__((global))
#define __device__ __attribute__((device))
#define __host__ __attribute__((host))

__device__ int twice(int v) {
  return v * 2;
}

__global__ void store42(int* out) {
  *out = 42;
}
