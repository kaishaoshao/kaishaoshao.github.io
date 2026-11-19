#define __device__ __attribute__((device))

__device__ int device_only() { return 7; }
int main() { return device_only(); }
