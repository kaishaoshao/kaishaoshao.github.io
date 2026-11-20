# L02.2 发射并核对标记

让 Clang 在选定的 Vortex HIP device 上下文发射标记，为下游识别逻辑 kernel 提供稳定依据。

- **操作** 用同一份 HIP 输入写定向 CodeGen 测试，再实现目标限定的发射逻辑。若用 `xvortex` 作为设备开关，可先完成 L02.3 的 feature 识别，CPU 默认选项和正式 HIP driver 接入按各自步骤验收。
- **测试与通过标准** `-O0/-O2` 下，保留发射的 `store42` 定义带标记，helper 不带标记。host stub、标准 RV64 C/C++ 和未选择 Vortex 的路径用各自的负例检查。在 `clang/test/CodeGenHIP` 以函数范围匹配输出，避免被其他函数的同名属性误匹配。
- **实现注意** 逻辑标记服务于 HIP body。SDK 启动时需要接收参数区指针的 wrapper，直接把多形参 body 导出为 `vortex.kernel` 会让设备读错参数。

## 当前分支的发射逻辑

提交 `d558c7fd0` 在 RISC-V 的 `setTargetAttributes` 中加入下列逻辑。

```cpp
if (CGM.getLangOpts().CUDAIsDevice && FD->hasAttr<CUDAGlobalAttr>()) {
  Fn->addFnAttr("vortex-hip-kernel");
  Fn->addFnAttr(llvm::Attribute::NoInline);
}
```

按这段条件，目前 RISC-V 设备模式的 `CUDAGlobalAttr` 定义都有可能被标记。用上面的负例检验普通 RV64 的 HIP device 模式，并据此补充 Vortex feature 门控。`noinline` 控制内联，链接保留与入口导出在 L03 单独检查。

---

[上一节 · L02.1](01-kernel-marker-design.md) · [本章目录](README.md) · [下一节 · L02.3](03-cpu-and-features.md)
