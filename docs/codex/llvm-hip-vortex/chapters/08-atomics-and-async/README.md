# 第 12 章 原子、异步执行与交付

用高竞争计数和跨流依赖分别验证设备原子与 runtime 顺序。从新构建目录复现已实现的范围。

> 本章提供实现提纲与验收目标。

## 本章目录

- [12.1 在匹配的 A 配置中实现 atomicAdd](01-atomic-add.md)
- [12.2 接通 stream 和队列内顺序](02-stream-order.md)
- [12.3 用事件连接两个 stream](03-event-lifetime.md)
- [12.4 发布可复现的原型](04-release-reproduction.md)

## 开始前

准备可用的 HIP 编译和 runtime。原子实验使用单独的 A-enabled 配置；stream/event 实验可沿用默认配置。[T10 工程任务](../../tasks.md#阶段-t10原子streamevent-与可复现交付)

## 完成这一章

交付支持子集的汇编、运行和错误用例。记录防止资源提前释放的规则，并附可复现构建说明和实例矩阵。

---

[上一章](../07-shared-memory/README.md) · [全书目录](../../tutorial.md) · [附录与后续专题](../../tutorial.md#附录与后续专题)
