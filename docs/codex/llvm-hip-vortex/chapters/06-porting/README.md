# 第 10 章 移植一个已有 HIP 程序

用 Vortex SDK 的 HIP vecadd 找出实际缺口，补上所需接口并保留原程序的 CPU 对照。[固定版本的 vecadd](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/tests/hip/vecadd/main.cpp)

> 本章提供实现提纲与验收目标。

## 本章目录

- [L06.1 盘点已有源码依赖](01-inventory.md)
- [L06.2 尝试用原生链路编译](02-first-build.md)
- [L06.3 给一个真实缺口补测试和实现](03-close-a-gap.md)
- [L06.4 对照 CPU 运行原程序](04-cpu-reference.md)
- [L06.5 从干净产物复现并交付](05-reproduce.md)

## 开始前

已有 L05 自动编译和 SimX 正确性证据，并能看到实际 host/device jobs。将参考样例和你自己的构建产物放到不同目录，便于比对。

## 完成这一章

第一个已有 HIP 程序通过新链路在 SimX 跑通，交付可重现的 CPU 对照与必要补丁。

可在这里验收主线。后两章按目标程序需要继续阅读。

---

[上一章](../05-hip-runtime/chapter-09-offload.md) · [全书目录](../../tutorial.md) · [下一章](../07-shared-memory/README.md)
