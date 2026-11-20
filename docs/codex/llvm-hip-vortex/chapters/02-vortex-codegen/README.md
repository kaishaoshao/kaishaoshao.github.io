# 第 2 章 接通 Vortex 编译入口（L02）

让新 LLVM 识别逻辑 HIP kernel、选择 RV64 Vortex 配置，并认识第一条专用指令 TMC。完成后，同一份 `store42` 可以生成可检查的设备对象，供 L03 链接。

## 本章目录

- [L02.1 设计逻辑 kernel 标记](01-kernel-marker-design.md)
- [L02.2 发射并核对标记](02-emit-kernel-marker.md)
- [L02.3 接通 CPU、feature 和 ABI 选择](03-cpu-and-features.md)
- [L02.4 实现第一条专用指令 TMC](04-tmc-mc.md)
- [L02.5 生成第一个设备对象](05-device-object.md)

## 开始前

已有 L01 观察和 LLVM 23 构建。记录当前源码 HEAD 与二进制版本。L02.1～L02.2 学习 kernel 信息传递，L02.3 是独立的 CPU/feature 工作，L02.4 等到 feature 可用后开始。[LLVM 构建步骤](../../build.md#llvm-build)

用户分支的 CPU、TMC 和 kernel 标记改动分别在 `2cbb216a2`、`0d3d3fcd2`、`d558c7fd0`。实验位于 LLVM 仓库的 `llvm/unittests/Vortex/102/`，各节列出的回归条件用于逐项验收。

## 完成这一章

提交标记、CPU/feature、TMC 三个可分别复查的修改。交付 IR、设备对象和目标/MC 测试记录，接着做 L03 的参数与链接。工程验收对应 T01、T02.2/T02.3/T02.6、T03.5、T07.1 的相关部分。

---

[上一章](../01-hip-frontend/README.md) · [全书目录](../../tutorial.md) · [下一章](../03-store42/README.md)
