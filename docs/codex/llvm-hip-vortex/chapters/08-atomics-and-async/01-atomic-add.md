# 12.1 在匹配的 A 配置中实现 atomicAdd

先建立与设备 ISA 一致的 A-enabled 测试配置，再验收多个线程更新同一全局计数器的原子性。

> 本节为进阶实验提纲。

- **操作** 以独立构建目录配置 SimX、runtime 和设备库，核对 A 的默认启用状态。用 RISC-V atomic lowering 支持本阶段选择的 32 位整数 `atomicAdd`，写明顺序和作用域。
- **测试与通过标准** 比较 `-O0/-O2` 的高竞争计数与 histogram，记录实际的 AMO 和 CPU 对照。用默认无 A 配置和超出支持的类型作负例。
- **实现注意** 将原子性、内存顺序和作用域分别验收。只有计数结果正确时，结论限于此测试覆盖的原子操作。

[ISA 配置](../../architecture.md#isa-config) · [T10.2 原子支持](../../tasks.md#t102-支持-32-位整数-atomicadd)

---

[上一节 · 11.3](../07-shared-memory/03-cooperative-kernels.md) · [本章目录](README.md) · [下一节 · 12.2](02-stream-order.md)
