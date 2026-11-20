# 第 4 章 链接并直接运行设备 ELF

让 SimX 直接加载一个能独立启动的 `store42`，理解 ELF 入口、装载段、参数寄存器和设备退出状态。

## 本章目录

- [L03.0 直接用 SimX 运行 ELF](00-direct-elf.md)
- [4.2 从设备对象链接独立 ELF](00-link-standalone.md)
- [4.3 用入口地址和退出码排查故障](00-diagnose-standalone.md)

## 开始前

先准备第 3 章的设备对象和 SimX 命令行程序。独立 `_start` 准备输出地址、直接调用设备函数、在设备端比较结果。第 5 章会使用 SDK 传参，由 host 读回输出。[SimX 构建](../../build.md#simx-build)

## 完成这一章

交付两个 ELF 的入口和装载段检查、实际启动命令与退出码。期望值 42 的镜像退出 0，故意期望 43 的镜像退出 1。

---

[上一章](../02-vortex-codegen/chapter-03-cpu-and-tmc.md) · [全书目录](../../tutorial.md) · [下一章](chapter-05-sdk-launch.md)
