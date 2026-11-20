# 第 2 章 让 Clang 保留 kernel 身份

把 AST 的 `CUDAGlobalAttr` 传到设备 IR。用同一个输入区分 kernel、device helper 与 host stub。

## 本章目录

- [L02.1 设计逻辑 kernel 标记](01-kernel-marker-design.md)
- [L02.2 发射并核对标记](02-emit-kernel-marker.md)

## 开始前

已有 L01 的 AST 与设备 IR。完成 LLVM 23 构建，再看 Clang RISC-V CodeGen 的 `setTargetAttributes` hook。现有标记实现在 `d558c7fd0`，实验位于 LLVM 仓库的 `llvm/unittests/Vortex/102/`。[LLVM 构建步骤](../../build.md#llvm-build)

## 完成这一章

交付触发条件和消费者说明，以及 kernel、helper、host stub 和普通 RV64 的正负例。检查 O0/O2 的真实函数属性，对应 T03.5、T07.1 的相关部分。

---

[上一章](../01-hip-frontend/README.md) · [全书目录](../../tutorial.md) · [下一章](chapter-03-cpu-and-tmc.md)
