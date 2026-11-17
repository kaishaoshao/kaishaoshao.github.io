# 架构方案：RISC-V 后端中的 Vortex CPU 与原生 HIP 支持

修订日期：2026-11-18（Asia/Shanghai）。设计基线为 LLVM 23.1.4。本方案用于指导你实现；此文档没有创建编译器功能。

## 1. 已确定的结构

在 LLVM 的 RISCV Target 内增加 `vortex` CPU/subtarget，初版固定 RV64；`-mcpu=vortex` 选择处理器及默认配置，`xvortex` 描述 ISA 能力。复用 RISC-V 基础代码生成，新增 Vortex 的 SIMT、kernel ABI，以及 Clang HIP 设备编译支持。独立 HIP runtime 直接对接固定版本的 Vortex SDK，以 SimX 为执行验收端。

```text
HIP 输入
  ├─ Host jobs：x86 → HIP API 调用 / 注册 / launch stub
  └─ Device jobs：riscv64 + -mcpu=vortex
       → HIP device 语义 / builtins / kernel 标记
       → RISC-V IR + 参数 ABI + Vortex SIMT 转换
       → RISC-V 通用代码生成 + xvortex 指令
       → ELF → vxbin + kernel/参数元数据
  → 镜像嵌入与 host 链接
  → libhip_vortex → Vortex SDK → SimX
```

开发分工的核心是下面这张表。CPU 选择、ISA 能力和语言入口分别表达自己的含义，避免 CPU 名承担全部语义。

| 层 | 设计责任 | 复用/新增 |
|---|---|---|
| Target | RISC-V 基础架构与 ELF 支持 | 复用 RISCV，不另建 LLVM Target |
| CPU/subtarget | 处理器名称、默认 ISA、调度策略 | 新增 `vortex` |
| ISA feature | 扩展版本、指令可用性、必要的目标能力 | 新增 `xvortex`，复用所需标准扩展 |
| 通用后端 | 标准指令、寄存器分配、栈与基础调用约定 | 尽量复用 RISC-V；GPU 不变量需要检查 |
| SIMT | uniformity、mask、分歧/汇合、循环与优化约束 | 参考官方实现，迁移/适配到 LLVM 23 |
| Kernel ABI | kernel 标记、入口、wrapper、参数布局和保留规则 | 兼容固定 SDK 的启动契约 |
| HIP frontend/CodeGen | HIP 属性/语义、builtins、设备类型/地址空间 | 复用 Clang HIP，增加 Vortex 适配 |
| HIP driver | host/device jobs、设备链接、镜像封装、host 链接 | 增加拟定 HIPVortex toolchain |
| Runtime | 镜像注册、内存、启动、同步及资源生命周期 | 独立 hip-vortex 项目 |

## 2. -mcpu、-march、feature、ABI 的契约

以下是要实现和测试的接口约定，当前 LLVM 23 尚未具备 `vortex` CPU。

- `--target=riscv64-unknown-elf`：设备的基础目标。host 仍为 x86，不接受设备 CPU 配置。
- `-mcpu=vortex`：选择初版 RV64 Vortex 处理器，取得与参考 SimX 一致的默认 ISA。初版不把 A/C 等未开启能力加入默认配置。
- `xvortex`：以 vendor extension/feature 表达特殊指令支持，版本与命名在 T01 中确定；CPU 默认包含它。指令谓词与相关 pass 查询实际 subtarget 能力，不在各处硬编码 CPU 名字符串。
- `-march=...`：沿用上游 ISA 选择优先级。显式 ISA 覆盖默认 ISA 后，必须检查最终 feature 集，不能假定 CPU 名强行保留 xvortex。
- `-mabi=lp64d`：初版约定的基础参数 ABI，与 ISA/库匹配；HIP kernel 另有 wrapper/参数区约定，不能只靠这个选项完成。
- kernel/device 上下文：普通函数不会因为 CPU 名就自动成为 kernel。kernel 入口用 annotation/attribute/元数据表示；SIMT 处理覆盖需要的设备 helper，并按 feature 与编译上下文接入。

LLVM 23 的 [RISCVProcessors.td](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.4/llvm/lib/Target/RISCV/RISCVProcessors.td) 提供 ProcessorModel 与 DefaultMarch；[RISC-V driver](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.4/clang/lib/Driver/ToolChains/Arch/RISCV.cpp) 实现 CPU 校验和 ISA 选择。上述项目约定需基于这些机制实现，不新增一套互相冲突的选项解析。

### 需要固定的选项组合

| 输入组合 | 项目期望 |
|---|---|
| RV64 + mcpu=vortex，无显式 march | 使用匹配参考配置的默认 ISA，包含 xvortex |
| RV64 + mcpu=vortex + 兼容的显式 march | ISA 取显式值，CPU 模型保持 vortex，按最终能力生成代码 |
| mcpu=vortex + 显式 march 去掉 xvortex | 普通 RISC-V 编译遵循上游选择规则；Vortex kernel/HIP device 编译要求必需能力，给出明确冲突诊断 |
| RV32 + 初版 mcpu=vortex | 报告 CPU/目标位宽不匹配，RV32 放到后续专题 |
| 普通 RISC-V CPU/ISA | 保持原行为，不误启用 Vortex 指令或 pass |
| HIP host x86 job | 不携带 mcpu=vortex，设备选项只进入 device job |
| 要求 A/C 等可选能力 | 仅在匹配 SDK/SimX 配置时执行验收，默认配置不承诺支持 |

CPU 的默认 feature 列表与 DefaultMarch 必须一致。初期选用可通过正确性测试的保守调度配置；精确延迟/吞吐模型属于后续性能工作，不虚构调度参数。是否支持普通 RISC-V 标量代码的 CPU/ISA 覆盖，与是否可把其当作 Vortex kernel 执行是不同的验收问题。

## 3. 源码落点

以下路径以 `/home/kaikai/vortex-word/llvm-project` 为根。新文件名为建议，实际实现可调整，但各层职责保持稳定。

| 文件/区域 | 工作 |
|---|---|
| `llvm/lib/Target/RISCV/RISCVProcessors.td` | 注册 vortex、默认 ISA、CPU features 和调度选择 |
| `llvm/lib/Target/RISCV/RISCVFeatures.td` | xvortex extension 与谓词 |
| `llvm/lib/TargetParser/RISCVTargetParser.cpp`、`RISCVISAInfo.cpp` 及生成表 | CPU/ISA 识别与校验；先检查 TableGen 生成机制，避免重复维护 CPU 清单 |
| `clang/lib/Driver/ToolChains/Arch/RISCV.cpp` | mcpu/march/ABI 选择、传递与诊断 |
| `clang/lib/Basic/Targets/RISCV.*` | CPU 校验、feature、宏和前端 target 接口 |
| `llvm/lib/Target/RISCV/` 内的 Vortex 指令定义 | 编码、汇编、反汇编与 feature gating |
| `llvm/include/llvm/IR/IntrinsicsRISCV.td` 与 RISCV lowering/TTI | intrinsic、CSR 与分歧来源 |
| RISCV 的 Vortex pass 与 pipeline 接入 | SIMT 转换、入口生成和目标约束 |
| Clang HIP Sema/CodeGen/target ABI | 设备语义、wrapper、参数元数据和 host ABI |
| 拟新增 `clang/lib/Driver/ToolChains/HIPVortex.*` | 编译/链接/打包 jobs |
| `/home/kaikai/vortex-word/hip-vortex`（拟建） | 独立 runtime、支持头/库、编译入口、示例和测试 |

## 4. 分阶段实施

| 阶段 | 核心问题 | 退出条件 |
|---|---|---|
| T00 | 环境和 ABI 基线是否清楚 | 新 LLVM 基础构建、参考执行与 ABI 分析 |
| T01 | 编译器是否能正确选择 Vortex CPU | mcpu/default ISA/ABI、选项组合和目标隔离测试 |
| T02 | 工具是否认识 Vortex 特殊指令 | 四条 MC 指令、往返和负例 |
| T03 | IR 是否表达了正确设备语义 | intrinsic、CSR、uniformity、annotation 与优化测试 |
| T04 | 新编译器产物是否能启动 | native ABI/镜像经 SimX 执行正确 |
| T05 | SIMT 控制流是否正确 | 混合 lane 的分支、循环、尾部边界在 O0/O2 通过 |
| T06 | 设备资源和 launch 是否可靠 | 显式 module runtime 与内存/同步/生命周期 |
| T07 | HIP device 源码是否可编译执行 | wrapper/元数据正确，手写 host 启动 HIP kernel |
| T08 | 普通 HIP 源码是否一体编译运行 | 自动注册/传参，<<<>>> vecadd/SAXPY 正确 |
| T09 | 是否支持 block 协作 | shared memory、barrier、reduction、SGEMM |
| T10 | 是否可扩展和复现 | 匹配配置的原子、stream/event 与交付验证 |

每阶段 6 项，共 66 个主线任务。详细练习与验收见 [任务卡](tasks.md)。旧稿已包含“复用 RISC-V、增加 Vortex 语义与 HIP”的主线；本修订补上明确的 CPU/subtarget 设计及单独验收阶段。

## 5. 最终产物与用户体验

完成 T08 后，用户编写受支持的 HIP 程序，使用一体编译入口构建 host 可执行文件，在配置好的 SimX 环境运行；无需手写 native kernel 参数结构或打包命令。编译驱动自动向设备任务传递 `-mcpu=vortex`，host 继续使用 x86 配置。开发者仍可通过 -### 和保留中间产物检查整个流程。

完成 T10 后交付：LLVM 23 分支、独立原生 HIP runtime、安装/编译/运行入口、示例与分层测试、版本和支持矩阵。可演示范围为 vecadd/SAXPY、分歧/循环、shared reduction、tiled SGEMM，以及匹配配置下的整数 atomicAdd/histogram 和 stream/event 依赖。

这是原生 HIP 子集的可扩展原型；完整设备库、跨文件设备链接、RV32、真实硬件与大型应用另设专题。已重编对象与仍复用的参考库必须在报告里逐项区分。完整目标例子见 [教程末尾](plan.md#6-最后可以做成什么样子)。
