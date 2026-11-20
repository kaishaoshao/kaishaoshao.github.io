# L01.3 设备 IR 与后续接口

观察 HIP kernel 在通用 RV64 上生成的标量 IR，列出 Vortex 下游还需要哪些信息。

准备好 `HIP_TUTORIAL_CLANG` 与 `L01_OUT` 再继续。[实验环境](README.md#准备实验)

```bash
"$HIP_TUTORIAL_CLANG" -cc1 -triple riscv64-unknown-elf \
  -target-cpu generic-rv64 -target-feature +m -target-feature +f -target-feature +d \
  -target-abi lp64d -x hip -fcuda-is-device \
  -emit-llvm -O0 -o "$L01_OUT/device.ll" "$L01_OUT/attributes.hip"
rg 'target |define |store i32 42|attributes #' "$L01_OUT/device.ll"
```

这里故意通过内部 cc1 接口选择 generic-rv64，绕过公共 HIP offload driver；因此 CPU 属性是 generic-rv64 很正常。+d 与 lp64d 配套，不能把它误抄成重复的 +f。IR 通常把 triple 规范化为 riscv64-unknown-unknown-elf，DataLayout 描述目标布局。

2026-11-19 对本机 Clang 23 的观察包括 `store i32 42`、target-cpu/target-features、convergent、optnone 和 uniform-work-group-size 等属性；两个函数都可带 uniform-work-group-size，不能据此唯一识别 kernel。参考 Clang 20 的属性形式略有不同，均以实际版本产物为准。

**正确结论是：Clang 已识别 HIP 函数并生成普通 RISC-V IR；尚未建立供 Vortex 下游稳定消费的逻辑 kernel 标识、native 参数入口和启动链。** 不能说“IR 完全没有属性/信息”，也不能说“没有 SIMT 指令就说明编译失败”。

store42 的函数体只做一次普通 store，本来不必出现 SPLIT/JOIN。后续特殊指令主要来自启动环境和真正需要分歧控制/同步的程序。CPU 选择、逻辑 kernel 标记、native wrapper、SIMT 转换是四件不同的工作，详见 [桥接关系](../../architecture.md#hip-ir-bridge)。

自己做：指出两个函数的真实符号、调用约定、目标属性和 store；解释为什么既不能用函数名，也不能只用 uniform-work-group-size 判定可启动入口。不要为了“IR 看起来像 GPU”给每个函数硬插一条 TMC。

---

[上一节 · L01.2](02-sema-launch.md) · [本章目录](README.md) · [下一节 · L02.1](../02-vortex-codegen/01-kernel-marker-design.md)
