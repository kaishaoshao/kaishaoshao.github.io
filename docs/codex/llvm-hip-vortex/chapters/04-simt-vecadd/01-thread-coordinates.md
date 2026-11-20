# L04.1 读取 CTA 坐标并写回索引

先只写每个线程的编号，从输出确认 builtin 读的是对应 CTA 坐标。

> 本节是实验提纲。通过标准用于实现后的验收。

- **操作** 从 SDK 的 `vx_spawn2.h` 和 `VX_types.toml` 核对 `threadIdx/blockIdx/blockDim/gridDim` 的 CSR。先实现 1D 索引，再添加 2D 坐标写回小用例。
- **测试与通过标准** 1D 用 grid=2、block=8，期望读回 `0..15`。2D 用 grid=(2,3,1)、block=(2,4,1)，用 CPU 枚举每项 X/Y 坐标，逐项比较写回的坐标、维度和值所在位置。IR/汇编还要检查 X/Y 用到各自的 CSR。
- **实现注意** warp 内 lane ID 会在下一个 warp 重新从 0 开始。用超过一个 warp 的 block 才能暴露把 lane ID 当作整个 `threadIdx` 的错误。CSR 读取沿用标准编码，坐标值只在对应 CTA 上下文中有效。

对于 1D 网格，先在纸上列出 `gid = blockIdx.x * blockDim.x + threadIdx.x` 的 16 个结果，再核对 `VX_CSR_CTA_THREAD_ID_X` 等 CSR 在每个 block 和 warp 中的值。

---

[上一节 · L03.5](../03-store42/05-rebuild-and-check.md) · [本章目录](README.md) · [下一节 · L04.2](02-vecadd.md)
