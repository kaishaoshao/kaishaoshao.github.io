#define __global__ __attribute__((global))

struct dim3 {
  unsigned x, y, z;
  constexpr dim3(unsigned x=1, unsigned y=1, unsigned z=1)
      : x(x), y(y), z(z) {}
};
using hipStream_t = void*;
extern "C" int __hipPushCallConfiguration(
    dim3, dim3, __SIZE_TYPE__=0, hipStream_t=nullptr);

__global__ void store42(int* out) { *out = 42; }
void launch(int* out) { store42<<<1,1>>>(out); }
