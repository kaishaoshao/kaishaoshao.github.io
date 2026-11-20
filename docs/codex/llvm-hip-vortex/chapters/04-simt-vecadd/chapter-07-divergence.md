# 第 7 章 尾部判断、分歧与汇合

让同一 warp 内真、假 lane 分别执行。在 vecadd 尾部和分支后的公共路径检验活跃掩码。

> 本章提供实现提纲与验收目标。

## 本章目录

- [L04.3 引入混合 lane 的尾部判断](03-divergence.md)
- [L04.4 检查汇合与优化回归](04-reconvergence.md)

## 开始前

先能重复执行整块 vecadd。对照参考 Vortex LLVM 的分歧变换和 SimX 指令语义，定位汇合点。[分歧实现入口](../../plan.md#33-simt-的核心在-uniformity-与分歧控制流)

## 完成这一章

N=37 时有效索引正确、尾部哨兵完整，分支后的写回全员执行。O0/O2 均做回归，有需要再按 T05 扩展到 if/else、循环与嵌套控制流。

---

[上一章](README.md) · [全书目录](../../tutorial.md) · [下一章](../05-hip-runtime/README.md)
