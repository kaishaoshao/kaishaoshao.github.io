# 第 11 章 共享内存与块内同步

为需要块内协作的程序支持 `__shared__` 和 `__syncthreads()`，用跨 warp reduction 和分块矩阵乘验收。

> 本章提供实现提纲与验收目标。

## 本章目录

- [11.1 为每个 block 布置共享内存](01-local-memory-layout.md)
- [11.2 从 BAR 指令接到块内屏障](02-block-barrier.md)
- [11.3 用 reduction 和 tiled SGEMM 验收](03-cooperative-kernels.md)

## 开始前

先核对目标配置的 LMEM、warp/block 容量和屏障语义。已有 native ABI 可做设备侧实验，普通 HIP 源码执行沿用第 9 章的编译链。[T09 工程任务](../../tasks.md#阶段-t09shared-memory-与-block-同步)

## 完成这一章

共享区布局、块间隔离、屏障的执行与可见性均有单独记录。跨 warp reduction 和 tiled SGEMM 与 CPU 对照正确，并验证超容量诊断。

---

[上一章](../06-porting/README.md) · [全书目录](../../tutorial.md) · [下一章](../08-atomics-and-async/README.md)
