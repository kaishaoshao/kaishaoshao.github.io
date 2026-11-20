# 第 6 章 线程坐标与整块 vecadd

沿用 SDK 启动，先让每个线程写回自己的索引，再用刚好填满网格的输入验证多线程向量加法。

> 本章提供实现提纲与验收目标。

## 本章目录

- [L04.1 读取 CTA 坐标并写回索引](01-thread-coordinates.md)
- [L04.2 做无尾部判断的 vecadd](02-vecadd.md)

## 开始前

基于已能执行的 L03 SDK 镜像练习。核对实际 warp 和 block 配置。下方练习以默认每 warp 4 个线程、每 core 4 个 warp 为基线。[CTA CSR 对照](../../architecture.md#65-csr-与-hip-builtins)

## 完成这一章

1D/2D 的坐标与 CPU 枚举一致，N=32 的所有结果正确。留下索引写回、CSR 指令和设备计算的证据。

---

[上一章](../03-store42/chapter-05-sdk-launch.md) · [全书目录](../../tutorial.md) · [下一章](chapter-07-divergence.md)
