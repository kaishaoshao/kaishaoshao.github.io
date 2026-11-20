# L02.3 接通 CPU、feature 和 ABI 选择

让 Clang 与 LLVM 工具对 `vortex` 的默认能力得出同一个结果。

- **操作** 从 `RISCVFeatures.td` 的 extension 定义接到 `RISCVProcessors.td` 的 CPU/DefaultMarch，随后追踪 Clang RISC-V driver 与每个函数的 target 属性。先以简单 `add.c` 试通标准代码生成。
- **测试与通过标准** 比较四组输入。RV64 默认 `-mcpu=vortex` 应启用约定的 `xvortex`、匹配的标准 ISA 和 `lp64d`。显式 `-march` 以最终解析结果为准。RV32 选择初版 CPU 应报告位宽冲突。普通 RV64 保持原有行为。用 `-###` 核对参数传递，再用 IR 的 `target-cpu/target-features` 和独立 `llc/llvm-mc` 核对实际处理结果。
- **实现注意** 当前 SimX 默认关闭 A/C，参考 SDK 参数里的 `rv64imafd` 含 A。测试普通标量的显式覆盖与 Vortex kernel 的必需 feature 诊断时，要分别走各自上下文。后者在设备 jobs 接通后复测。[选项矩阵](../../architecture.md#2--mcpu-marchfeatureabi-的契约) · [ISA 配置](../../architecture.md#isa-config)

## 当前分支的 CPU 定义

提交 `2cbb216a2` 从 `llvm/lib/Target/RISCV/RISCVFeatures.td` 注册版本为 1.0 的 `xvortex`，生成供 subtarget 查询和汇编检查使用的 feature。

```tablegen
def FeatureVendorXVortex
    : RISCVExtension<1, 0, "Vortex SIMT extension">;
def HasVendorXVortex
    : Predicate<"Subtarget->hasVendorXVortex()">,
      AssemblerPredicate<(all_of FeatureVendorXVortex), "'XVortex' (Vortex SIMT extensions)">;
```

`llvm/lib/Target/RISCV/RISCVProcessors.td` 使用 `RocketModel` 作为初期调度模型。看清默认特性的选择，再验证 driver 与设备镜像实际使用的 ISA。

```tablegen
def VORTEX : RISCVProcessorModel<"vortex",
                                RocketModel,
                                [Feature64Bit,
                                 FeatureStdExtI,
                                 FeatureStdExtM,
                                 FeatureStdExtF,
                                 FeatureStdExtD,
                                 FeatureStdExtZicsr,
                                 FeatureStdExtZifencei,
                                 FeatureStdExtZicond,
                                 FeatureVendorXVortex]>;
```

这个 CPU 定义的默认 ISA 为 RV64IMFD、Zicsr、Zifencei、Zicond 和 `xvortex`。A、C 按目标配置另行启用和测试。

---

[上一节 · L02.2](02-emit-kernel-marker.md) · [本章目录](chapter-03-cpu-and-tmc.md) · [下一节 · L02.4](04-tmc-mc.md)
