# 第 4 章 多线程 vecadd 与分支分歧（L04）

沿用 L03 的启动链，先让线程算对各自的索引和加法，再让同一 warp 内只有部分线程写结果。完成后，整块 vecadd、尾部边界和分支后的汇合都有独立测试。

> 本章各节为实施提纲，列出实现顺序、测试输入和通过标准。

## 本章目录

- [L04.1 读取 CTA 坐标并写回索引](01-thread-coordinates.md)
- [L04.2 做无尾部判断的 vecadd](02-vecadd.md)
- [L04.3 引入混合 lane 的尾部判断](03-divergence.md)
- [L04.4 检查汇合与优化回归](04-reconvergence.md)

## 开始前

L03 的镜像能重复执行，参数区与输出能检查。先查实际 warp 宽度和 block 容量。下面的配置取本教程默认每 warp 4 个线程、每 core 4 个 warp。[CTA CSR 对照](../../architecture.md#65-csr-与-hip-builtins)

[参考 Vortex LLVM 分歧实现](../../plan.md#33-simt-的核心在-uniformity-与分歧控制流)

## 完成这一章

N=32/37 的结果、尾部哨兵和汇合测试均有新设备代码的执行证据。更复杂的 if/else、嵌套和循环按 T05 子任务补充，当前支持范围写明已覆盖的控制流。

---

[上一章](../03-store42/README.md) · [全书目录](../../tutorial.md) · [下一章](../05-hip-runtime/README.md)
