# L02.1 设计逻辑 kernel 标记

画出 `CUDAGlobalAttr` 到 IR 的传递路径，写清后续 wrapper 生成器怎样识别 kernel。

- **操作** 从下面三个入口追踪声明、目标 hook 和通用函数属性。为你选择的函数属性、annotation 或 metadata 写下触发条件、消费者和保留规则。

  ```bash
  cd /home/kaikai/vortex-word/llvm-project
  rg -n 'setTargetAttributes|SetLLVMFunctionAttributesForDefinition' clang/lib/CodeGen/CodeGenModule.cpp
  rg -n 'setTargetAttributes|RISCVInterruptAttr' clang/lib/CodeGen/Targets/RISCV.cpp
  rg -n 'OffloadUniformBlock|uniform-work-group-size' clang/lib/CodeGen/CGCall.cpp
  ```

- **测试与通过标准** 拿 L01 的 `store42` 和 `twice` 对照 AST、IR，列出应当标记和应当保持原样的函数。设计表至少覆盖 Vortex 设备 kernel、device helper、host stub、普通 RV64 函数。
- **实现注意** 查清 hook 在创建声明和发射定义时的调用位置。RISC-V 的 `setTargetAttributes` 当前含有 interrupt 分支和早退，先确认新增逻辑的落点。

---

[上一节 · L01.3](../01-hip-frontend/03-device-ir.md) · [本章目录](README.md) · [下一节 · L02.2](02-emit-kernel-marker.md)
