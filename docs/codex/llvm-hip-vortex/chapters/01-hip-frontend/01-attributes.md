# L01.1 宏展开与属性 AST

确认 `__global__` 和 `__device__` 经过宏展开后怎样进入 AST。

准备好 `HIP_TUTORIAL_CLANG` 与 `L01_OUT` 再继续。[实验环境](README.md#准备实验)

输入是 [attributes.hip](../../examples/l01/attributes.hip)：

```cpp
#define __global__ __attribute__((global))
#define __device__ __attribute__((device))
#define __host__ __attribute__((host))

__device__ int twice(int v) {
  return v * 2;
}

__global__ void store42(int* out) {
  *out = 42;
}
```

先看预处理，再看 AST：

```bash
"$HIP_TUTORIAL_CLANG" -x hip --offload-host-only -nogpuinc -nogpulib \
  -E -P "$L01_OUT/attributes.hip" > "$L01_OUT/attributes.ii"
cat "$L01_OUT/attributes.ii"

"$HIP_TUTORIAL_CLANG" -x hip --offload-host-only -nogpuinc -nogpulib \
  -fsyntax-only -Xclang -ast-dump "$L01_OUT/attributes.hip" \
  > "$L01_OUT/attributes.ast.txt"
rg 'FunctionDecl|CUDADeviceAttr|CUDAGlobalAttr' "$L01_OUT/attributes.ast.txt"
```

预期：预处理后限定符成为属性；twice 的 AST 带 CUDADeviceAttr，store42 带 CUDAGlobalAttr。CUDA 前缀来自 Clang 的共享实现，不表示选择了 NVIDIA 设备。地址和源码位置可变化，不比较固定 AST 十六进制地址。

这里用宏写出真实属性，方便观察；把 __global__ 定义为空会丢掉语义。-x hip 选择语言；host-only 只走本次观察所需的 host 路径；nogpuinc/nogpulib 排除默认 GPU 支持头/库。你尚未生成设备镜像，也尚未检查全部设备侧语义。

自己做：增加显式 __host__ 函数和未标记函数，解释各自的调用侧；默认 host 语义不一定对应一个显式 CUDAHostAttr。交付输入改动、AST 摘要和“宏→属性→AST”的解释。

---

[全书目录](../../tutorial.md) · [本章目录](README.md) · [下一节 · L01.2](02-sema-launch.md)
