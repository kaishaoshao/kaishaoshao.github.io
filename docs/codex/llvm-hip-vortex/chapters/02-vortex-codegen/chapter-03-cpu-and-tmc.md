# 第 3 章 配置 Vortex CPU 并定义 TMC

接通 `-mcpu=vortex`、`xvortex` 和 RV64 ABI，在 MC 层完成第一条专用指令的编解码。

## 本章目录

- [L02.3 接通 CPU、feature 和 ABI 选择](03-cpu-and-features.md)
- [L02.4 实现第一条专用指令 TMC](04-tmc-mc.md)
- [L02.5 生成第一个设备对象](05-device-object.md)

## 开始前

先用普通 RISC-V 函数核对目标参数，再读 `RISCVFeatures.td`、`RISCVProcessors.td` 和 TMC 定义。用户分支中的 CPU 改动为 `2cbb216a2`，TMC 改动为 `0d3d3fcd2`。记录源码 HEAD、二进制版本和实际参数。[目标配置](../../architecture.md#isa-config)

## 完成这一章

通过 CPU/feature 参数矩阵、TMC 编解码与禁用扩展的负例。保留 `store42.ll` 和 `store42.o` 作为后续链接的输入。对应 T01、T02.2/T02.3/T02.6 的相关验收。

---

[上一章](README.md) · [全书目录](../../tutorial.md) · [下一章](../03-store42/README.md)
