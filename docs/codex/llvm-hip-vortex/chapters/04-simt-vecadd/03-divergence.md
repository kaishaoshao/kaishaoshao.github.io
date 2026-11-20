# L04.3 引入混合 lane 的尾部判断

只增加 `if (i < n)`，验证同一 warp 内各 lane 都遵守自己的谓词。

> 本节是实验提纲。通过标准用于实现后的验收。

- **操作** 取 N=37、block=8、grid=5。对照参考分歧 pass，从 `threadIdx` 追到比较条件，给实际需要分歧处理的分支接通 SPLIT/JOIN 和必要的控制指令。
- **测试与通过标准** 为 A/B/C 各分配 40 项并初始化，N 仍传 37。有效索引 `0..36` 得到 `3*i`，C 的 `37..39` 仍为 `-1234`。在默认 4-lane warp 中，最后一个 warp 包含索引 36～39，谓词应是一个真、三个假。汇编/必要的 trace 与结果一起检查。
- **实现注意** 保证真、假 lane 处于同一 warp，全部线程走同一路径测不出分歧。哨兵用于检测错误写入，若要验证假 lane 的加载也被抑制，再检查机器访存或 trace。按转换后的 CFG 选择重新汇合点。[分歧与流水线约束](../../architecture.md#73-simt-转换是必需语义不能只挂在优化流水线)

## 用于阅读的尾部条件

```cpp
__global__ void vecadd(float* a, float* b, float* c, int n) {
  int gid = blockIdx.x * blockDim.x + threadIdx.x;
  if (gid < n) {
    c[gid] = a[gid] + b[gid];
  }
}
```

SPLIT/JOIN 管理参与不同路径的活跃 lane 与重新汇合。先用该例识别确实发散的条件和实际汇合块，再验证生成的控制流与 mask。

---

[上一节 · L04.2](02-vecadd.md) · [本章目录](README.md) · [下一节 · L04.4](04-reconvergence.md)
