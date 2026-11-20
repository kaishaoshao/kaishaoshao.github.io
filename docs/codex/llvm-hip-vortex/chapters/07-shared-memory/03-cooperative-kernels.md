# 11.3 用 reduction 和 tiled SGEMM 验收

先用跨 warp reduction 测试多轮协作，再用分块矩阵乘验证 shared 布局与重复同步。

> 本节为进阶实验提纲。

- **操作** 画出 reduction 各轮的读写与 barrier，先做整数用例。再按 tile 的装载、同步、计算顺序完成 SGEMM，选定与当前 core 容量匹配的 block。
- **测试与通过标准** 覆盖多 block、重复启动、完整 tile 和边缘 tile，使用 CPU 参考与约定容差验证 `-O0/-O2` 的输出。记录 shared 用量和超限诊断。
- **实现注意** 边界判断保护数据访问。参与块内 barrier 的线程仍需按约定汇合。用一个小的跨 warp 样例区分算法错误和 barrier 回归。

[T09.5 reduction](../../tasks.md#t095-运行跨-warp-reduction) · [T09.6 tiled SGEMM](../../tasks.md#t096-运行-tiled-sgemm-并固定资源回归)

---

[上一节 · 11.2](02-block-barrier.md) · [本章目录](README.md) · [下一节 · 12.1](../08-atomics-and-async/01-atomic-add.md)
