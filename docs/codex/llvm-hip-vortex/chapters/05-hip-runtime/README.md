# 第 8 章 实现 HIP runtime 的基本接口

先把分配、拷贝和默认队列跑通，再用已有设备镜像验证显式模块启动与资源持有。

> 本章提供实现提纲与验收目标。

## 本章目录

- [L05.1 验证最小内存 API](01-memory-api.md)
- [L05.2 验证显式模块启动和资源持有](02-module-launch.md)

## 开始前

已有 L03 的 SDK 镜像与参数约定就可开始。固定 HIP 声明版本，读 SDK buffer、module、kernel、queue 入口。[运行时源码导航](../../tasks.md#源码导航)

## 完成这一章

同步内存 API 能正确处理偏移、范围与错误。显式模块启动能用同一个 staging 区向两份不同的设备缓冲提交任务并读回结果。

---

[上一章](../04-simt-vecadd/chapter-07-divergence.md) · [全书目录](../../tutorial.md) · [下一章](chapter-09-offload.md)
