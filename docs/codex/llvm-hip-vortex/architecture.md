# 架构方案：RISC-V 后端中的 Vortex CPU 与原生 HIP 支持

修订日期：2026-11-19（Asia/Shanghai）。设计基线为 LLVM 23.1.4。本方案用于指导你实现；此文档没有创建编译器功能。

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


<a id="hip-ir-bridge"></a>

### 1.1 从 HIP IR 到 Vortex 执行，桥梁具体是什么

先看四层，不把它们合成一个“后端有没有支持”的判断：

| 层次 | 现有观察/用途 | 本教程要补什么 |
|---|---|---|
| AST 语言信息 | __global__ 对应 CUDAGlobalAttr，__device__ 对应 CUDADeviceAttr | 复用现有语法与调用侧检查，不重写 Parser |
| 通用设备 IR | RISC-V triple/DataLayout、普通标量运算、函数属性 | 定义下游可稳定识别的逻辑 HIP kernel 标识及 helper 边界 |
| native 入口与启动 | SDK 从公共 startup 进入单参数区函数 | wrapper 解包、入口 alias/保留、镜像、两个 PC 与参数契约 |
| GPU 执行语义 | 普通标量指令在各个活跃线程的数据上执行 | CTA builtins、uniformity、分歧/汇合、同步；按输入需要引入 |

“IR 中没有 Vortex 专用入口契约”不等于“IR 中完全没有属性/元数据”。本机 Clang 23 的实验已有 target-cpu/features、convergent、optnone 等属性；uniform-work-group-size 也可能同时出现在 kernel 和 helper，不能作为唯一标记。AST 属性不必原样以同名节点出现在 LLVM IR 中，关键是后续消费者取得所需语义。

store42 只有普通 store，函数体不需要专用 SIMT 指令；generic-rv64 也是 L01 命令主动选择的 CPU。不能用这两个现象推导出前端没识别 HIP。L02 才增加 Vortex 编译连接，L03 建立执行入口，L04 让真正需要的线程/分歧语义正确工作。

逻辑 kernel 标记可以是 IR 函数属性、annotation 或其他约定的 metadata；形式需要在实现时冻结，并有明确消费者/保留测试。它和现有 SDK 的 vortex.kernel 原生单参数区入口标记不能直接等同。源码阅读入口与最小练习见 [L02](plan.md#l02)。

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

下表是工程能力与完整出口，授课顺序见 [plan.md 的六阶段主线](plan.md#tutorial-route)。教学从现有 HIP 语法/AST/Sema/IR 的隔离实验开始，按程序需要引入表中的连接点；mcpu=vortex 仍是目标配置，但不作为理解第一段 HIP 源码之前的实现前置。

后端源码修改从 L02 开始，首条 MC 指令建议为 TMC；L03 核对启动所需 TMC/WSYNC，L04 接通 CTA CSR 与必要 SPLIT/JOIN/SIMT lowering，L05 接通普通 HIP 流程。L06 开始移植已有程序，需要 block 协作时再实现 BAR；原子/异步能力同样按需增加。完整说明见 [接入时点表](plan.md#backend-timing)，不能把“语法优先”理解为把后端一直推迟到完整 HIP runtime 之后。

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

每个工程分组保留 6 项，共 66 项。详细验收见 [任务账本](tasks.md)，已有 ID/状态不因授课重排而改变。课程可先实现局部连接，只有相关执行依赖补齐后才能声称某个完整出口通过。

## 5. 最终产物与用户体验

完成 T08 后，用户编写受支持的 HIP 程序，使用一体编译入口构建 host 可执行文件，在配置好的 SimX 环境运行；无需手写 native kernel 参数结构或打包命令。编译驱动自动向设备任务传递 `-mcpu=vortex`，host 继续使用 x86 配置。开发者仍可通过 -### 和保留中间产物检查整个流程。

完成 T10 后交付：LLVM 23 分支、独立原生 HIP runtime、安装/编译/运行入口、示例与分层测试、版本和支持矩阵。可演示范围为 vecadd/SAXPY、分歧/循环、shared reduction、tiled SGEMM，以及匹配配置下的整数 atomicAdd/histogram 和 stream/event 依赖。

这是原生 HIP 子集的可扩展原型；完整设备库、跨文件设备链接、RV32、真实硬件与大型应用另设专题。已重编对象与仍复用的参考库必须在报告里逐项区分。完整目标例子见 [教程末尾](plan.md#6-最后可以做成什么样子)。

<a id="vortex-isa"></a>

## 6. Vortex 指令集与 SIMT 执行模型

本节核对日期为 2026-11-18（Asia/Shanghai）。设备源码基线为 Vortex `26d2bc4b5409a35a111e8316ac3a87d07b15fc80`，编译器对照为 Vortex LLVM `f44a6bb2af4c62847585305bbdc760fbe0e3645f`（参考 Clang 20.1.8）。下面区分设备指令、SDK 接口与编译器覆盖范围，不将它们当作同一份完整 ISA 规范。

### 6.1 三部分构成

Vortex 采用标准 RISC-V 指令处理每个线程的普通计算，通过自定义指令管理 SIMT 线程执行，并使用扩展 CSR 暴露设备与 CTA 上下文。

| 部分 | 内容 | 编译器中的主要落点 |
|---|---|---|
| 标准 RISC-V | 整数/浮点运算、访存、跳转及所选标准扩展 | 复用 RISCV 后端与已有指令定义 |
| Vortex 自定义指令 | active mask、分歧/汇合、warp 控制、同步、投票与 shuffle 等 | xvortex 指令、intrinsic、指令选择与 SIMT pass |
| Vortex CSR | 线程/warp/core 标识、活跃 mask、CTA 坐标与维度等 | CSR 访问、builtins 和 uniformity 分类 |

`-mcpu=vortex` 是本项目待实现的处理器选择入口，`xvortex` 是能力选择。HIP 的 `__global__` 和 `<<<>>>` 是语言与启动机制，不是新增两条机器指令。

<a id="isa-config"></a>

### 6.2 当前 RV64 基线使用哪些标准扩展

固定 SDK 的 [VX_config.toml](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/VX_config.toml) 与 [原生测试 common.mk](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/tests/regression/common.mk) 是配置依据。

| 能力 | 示例/用途 | 当前默认基线 |
|---|---|---|
| RV64I | add、sub、位运算、分支、load/store | RV64 原生路径的基础 |
| M | 整数乘除 | 开启 |
| F | 单精度浮点，例如 fadd.s | 开启 |
| D | 双精度浮点，例如 fadd.d | RV64 默认开启；RV32 默认不同 |
| Zicond | 条件置零等整数条件操作 | 开启，并由测试编译选项启用 |
| A | 标准原子操作 | 默认关闭，需要匹配配置后单独验收 |
| C | 16 位压缩指令 | 默认关闭 |
| Zacas、Zfhmin | 原子比较交换、最小半精度支持 | 默认关闭，各自有前置条件 |

注意实际存在的差异：参考 common.mk 写的是 `-march=rv64imafd -mabi=lp64d`，**其中含 A**；当前 VX_config.toml 默认却关闭 A/C。普通 demo 通过只能证明已执行路径，不能据此宣称原子或完整 ISA 匹配已验证。保留这个参考事实，不把它悄悄改写成没有 A 的命令。

新 CPU 的默认能力应匹配所选 SimX；不使用 A/C 的标准标量实验可以显式采用 `-march=rv64imfd -mabi=lp64d`。Zicsr/Zicond 和 xvortex 的最终版本化 ISA 字符串在 T01 冻结。复用旧对象/静态库时还要检查 ELF attributes 和实际机器码；只修改新 Clang 的选项，不能清除旧库已有的 A 声明或证明其全部路径安全。严格配置对齐仍是 T01/T04 的验收项。

官方 README 所说的 RV32IMAFC/RV64IMAFDC 是项目可支持的标准组合，不代表所有构建都全部开启。按规范顺序，I 是基础整数，M 是整数乘除，A 是原子，F/D 是单/双精度，C 是 16 位压缩编码；见 [RISC-V 命名规范](https://docs.riscv.org/reference/isa/unpriv/naming.html)。Vortex 专用指令和 CSR 在这串字母之外描述。

RV32/RV64 控制基础整数位宽，不决定 GPU 是否可并行，也不等同浮点精度；两种配置要分别构建并匹配参数/地址/库 ABI。x86_64 host 可以管理 RV32 device，但转换规则需要单独实现。本教程初版 -mcpu=vortex 只接 RV64 是项目范围选择，不表示上游 Vortex 不支持 RV32。

RV64 描述基础整数寄存器/运算宽度；本节介绍的自定义 R 型编码仍是 32 位。标准 RVV 与 Vortex SIMT 是不同机制，本教程不要求先把 HIP 线程计算转换成 RVV；也不能仅凭配置中的 VLEN 字段推断标准 V 扩展已启用。

### 6.3 普通 RISC-V 指令如何在线程上执行

Core 管理多个 warp，同一 warp 内的活跃线程共享指令执行流程，各自持有数据状态。以 `add a0, a1, a2` 为例，每个活跃线程使用自己的 a1/a2 计算自己的 a0，参与者由 active mask 决定。通常可以先为一个逻辑线程生成标量 LLVM IR，再由 Vortex 的 SIMT 机制组织执行。

当线程条件不同，编译器需要为分歧与重新汇合生成正确控制流。warp 的线程数、Core 可驻留的 warp 数和执行单元的物理 lane 数应分别核对配置，不能仅凭一个数推断同周期执行宽度。调度与 mask 的硬件入口见 [VX_scheduler.sv](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/hw/rtl/core/VX_scheduler.sv)。

### 6.4 主要自定义操作

下表的 `vx_*` 为 SDK 中的 C/C++ 封装接口，不能据此假定参考 LLVM 已为每个操作提供同名汇编助记符。语义入口见 [vx_intrinsics.h](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/sw/kernel/include/vx_intrinsics.h)。

| 操作 | SDK 接口示例 | 主要作用 |
|---|---|---|
| TMC | vx_tmc(mask) | 设置当前 warp 的活跃线程 mask |
| WSPAWN | vx_wspawn(count, entry) | 启动 warp 执行指定入口 |
| SPLIT / SPLIT.N | vx_split(predicate)、vx_split_n(predicate) | 建立分歧执行状态，返回汇合使用的 token |
| JOIN | vx_join(token) | 使用 token 进行重新汇合处理 |
| PRED / PRED.N | vx_pred(condition, mask) 等 | 按条件进行线程 mask 控制 |
| BAR | vx_barrier(id, num_warps) | 按 barrier 标识和参与 warp 数同步 |
| BAR ARRIVE / WAIT | vx_barrier_arrive、vx_barrier_wait | 分离到达与等待 |
| WSYNC | vx_wsync() | warp 级同步/流水线等待操作 |
| VOTE | vx_vote_all/any/uni/ballot | 对活跃 lane 的谓词进行归约或形成 bitmask |
| SHFL | vx_shfl_up/down/bfly/idx | 在线程 lane 间交换数据 |

SPLIT/JOIN 要与普通分支、跳转及 CFG 变换配合，不能仅在任意 if 前后插入一对就认为正确。BAR 的参与数按 warp 计；`__syncthreads()` 的完整实现还要保证约定的内存可见性和编译器重排约束。WSYNC 的作用范围也不能直接当作整个 block 的 barrier。相关控制和解码应对照 [SimX decode.cpp](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/sim/simx/decode.cpp) 与 RTL。

WSPAWN 是 ISA/runtime 可用的机制；当前 kernel launch 的 CTA/warp 分配还涉及 KMU 和 CTA dispatcher，不能把每次 HIP launch 简化为插入一条 WSPAWN。

### 6.5 CSR 与 HIP builtins

CSR 的读取沿用 RISC-V CSR 指令编码，Vortex 定义相应地址和内容。`csrr` 是常见汇编伪指令写法，不是另一个 Vortex 专用 opcode。固定地址来自 [VX_types.toml](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/VX_types.toml)，CTA builtin 包装见 [vx_spawn2.h](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/sw/kernel/include/vx_spawn2.h)。

| CSR/范围 | 固定基线地址 | 含义或语言映射 |
|---|---|---|
| VX_CSR_THREAD_ID | 0xCC0 | warp 内线程/lane 标识 |
| VX_CSR_WARP_ID | 0xCC1 | warp 标识 |
| VX_CSR_CORE_ID | 0xCC2 | Core 标识 |
| VX_CSR_ACTIVE_THREADS | 0xCC4 | 当前活跃线程 mask |
| VX_CSR_CTA_THREAD_ID_X/Y/Z | 0xCD3～0xCD5 | threadIdx.x/y/z |
| VX_CSR_CTA_BLOCK_ID_X/Y/Z | 0xCD6～0xCD8 | blockIdx.x/y/z |
| VX_CSR_CTA_BLOCK_DIM_X/Y/Z | 0xCD9～0xCDB | blockDim.x/y/z |
| VX_CSR_CTA_GRID_DIM_X/Y/Z | 0xCDC～0xCDE | gridDim.x/y/z |

warp 内 lane 标识与 CTA 中的 threadIdx 坐标是不同概念。block 可能包含多个 warp；二维/三维 block 还需要正确的坐标分解，不能直接用 vx_thread_id() 代替全部 threadIdx。

CTA 身份/维度与活跃 mask 的变化规律不同。优化时要按真实生命周期选择可合并/可提升的读取，并将 threadIdx 等分歧来源传给分析；不能把所有 CSR 读取统一标成纯函数或 uniform。

CTA 坐标/维度在一次 CTA 执行内稳定，warp slot 复用或不同 launch 后可改变；不能跨这些边界把读取值缓存为全局常量。

### 6.6 编码长什么样

核心 warp 控制操作使用 CUSTOM0，opcode 为 `0x0b`。以下只列 `funct7=0` 的一组操作；其他 funct7 或其他 CUSTOM 编码空间还承载其他扩展。

```text
位段    31..25   24..20   19..15   14..12   11..7   6..0
字段    funct7   rs2      rs1      funct3   rd      opcode
宽度    7        5        5        3        5       7
```

| funct3 | 操作 | 重要字段约束/模式 |
|---|---|---|
| 0 | TMC | rd=0，rs2=0，rs1 提供 mask |
| 1 | WSPAWN | rd=0，rs1/rs2 提供数量和入口 |
| 2 | SPLIT / SPLIT.N | rd 返回 token；参考定义中 rs2 字段为 0/1 选择模式 |
| 3 | JOIN | rd=0、rs2=0，rs1 提供 token |
| 4 | BAR | rd=0，rs1/rs2 提供 barrier 参数 |
| 5 | PRED / PRED.N | rd 字段 0/1 选择模式 |
| 6 | BAR ARRIVE / WAIT | 在设备解码中按 rd 等字段区分 |
| 7 | WSYNC | SDK 包装将寄存器字段置零 |

SPLIT.N 的固定 rs2 字段和 PRED.N 的 rd 模式位不能简单理解成对 x1 的读取/写回。以实际操作数定义为准。前六类的 LLVM 定义见 [RISCVInstrInfoVX.td](https://github.com/vortexgpgpu/llvm/blob/f44a6bb2af4c62847585305bbdc760fbe0e3645f/llvm/lib/Target/RISCV/RISCVInstrInfoVX.td)，扩展操作同时核对设备解码和 SDK 的 `.insn`。

2026-11-18 已使用现有参考 LLVM 的 llvm-mc 实际检查以下四条编码：

| 汇编 | 32 位指令字 | 文件中的小端字节 |
|---|---|---|
| vx_tmc a0 | 0x0005000b | 0b 00 05 00 |
| vx_split a1, a0 | 0x0005258b | 8b 25 05 00 |
| vx_join a1 | 0x0005b00b | 0b b0 05 00 |
| vx_bar a0, a1 | 0x00b5400b | 0b 40 b5 00 |

复核命令在 WSL Bash 中执行：

```bash
printf 'vx_tmc a0\nvx_split a1,a0\nvx_join a1\nvx_bar a0,a1\n' |
  /home/kaikai/vortex-word/tools/llvm-vortex/bin/llvm-mc \
    -triple=riscv64 -mattr=+xvortex -show-encoding
```

这项记录覆盖参考 llvm-mc 对四条输入的编码。2026-11-19 又核对了 TMC 的两个寄存器和反汇编，发现参考工具在 `-mattr=-xvortex` 下仍接受 `vx_tmc`。在新 LLVM 上单独检查编码、feature 诊断和执行。[TMC 小阶段](plan.md#l02-4)

### 6.7 可选扩展与工具链覆盖

当前基线还提供按配置选择的 TCU/矩阵操作、DXA 异步数据搬运、纹理/图形相关操作，以及半精度和更宽/矩阵访存等方向。它们有各自的依赖，且本节基线默认关闭相应开关；不能将“源码存在”当作当前模拟器配置已经启用。具体可用操作以 VX_config.toml、SDK、SimX 与 RTL 一致为准。

参考 LLVM 的单个 td 文件并不覆盖 SDK/设备源码中的全部操作。SDK 可以用 `.insn` 直接发出合法编码，因此“设备能执行”“SDK 有包装”“llvm-mc 认识助记符”“Clang 能从 builtin/IR 生成”要分别验收。LLVM 23 的 xvortex 支持范围必须明确列出，未实现能力应诊断或记录为限制。

`.insn` 本身是原始编码出口。其接受输入不能证明该指令适合当前设备，也不能替代具名助记符/IR 路径的 feature 负例测试。

### 6.8 对本教程任务的影响

- T01：用标准扩展与 xvortex 定义 CPU 的默认能力，固定 ABI/ISA 选择规则。
- T02：先完成 TMC/SPLIT/JOIN/BAR 四条 MC 切片；本节编码表用于核对，其他控制操作按后续实际需要补全。
- T03：补 intrinsic、CSR、builtins、annotation 与优化属性，让 IR 正确表达指令语义。
- T04/T05：在真实 kernel ABI 和 SIMT 控制流中验证执行，不能以 MC 通过代替。
- T09/T10：单独验证 block 同步与原子等能力；vote/shuffle、矩阵等未纳入主线子集的能力按专题扩展，不因本节介绍而自动扩大 66 项的完成承诺。

阅读顺序为配置→SDK 包装→SimX 解码→RTL 解码/执行→LLVM 定义与 pass。某层只识别编码，另一层负责分析与生成，迁移时要保持两端契约一致。

<a id="implementation-contracts"></a>

## 7. 实现前要固定的边界与契约

2026-11-18 建立、2026-11-19 复核。本节按用到的能力查阅，不是第一课必须全部掌握的内容；细化现有 66 项任务的设计与验收，不表示这些功能已实现，也不重置任务状态。具体参数例子和两个启动 PC 见 [编译器与 SimX 契约](compiler-sim-contract.md)。

### 7.1 固定 host/device 平台与第一版子集

第一版 host 明确为 **WSL 中的 x86_64 Linux**，设备为 **RV64、little-endian、lp64d 的裸机目标**。LLVM 构建目标 X86 不能代替具体 host triple/ABI 记录；Windows 原生 host、RV32 与跨平台 ABI 兼容另行验证。

| 项目 | T08 最小闭环的约定 | 后续范围 |
|---|---|---|
| 设备与编译单元 | 单设备、一个 HIP 翻译单元、多个 kernel、重复启动 | 多设备与跨文件 device linking 另设专题 |
| 参数 | 设备指针、int32/uint32/int64/uint64、float，按设备布局打包 | bool、long double、任意按值结构/类、非平凡对象不自动纳入 |
| 设备函数 | 普通算术与已验证控制流，初期优先内联 helper | 非内联调用在 T05.5 单独验收；递归、虚调用、间接调用未承诺 |
| 设备 C++ 运行时 | 不以异常、RTTI、设备 malloc/printf、动态构造对象为前置 | 每类能力增加设备库与生命周期测试后再开放 |
| 存储 | 显式分配的设备 buffer；明确的私有栈 | shared 在 T09，managed memory、复杂全局对象另行实现 |
| stream | 初版只支持约定的 legacy 默认 stream | per-thread default stream 先拒绝；显式 stream 与默认流交互在 T10 定义 |
| 优化 | 正确性验收覆盖 O0/O2，先使用 SelectionDAG 路径 | GlobalISel、LTO、fast-math 与性能调优另行验证 |

不支持的行为应尽早诊断；尚未实现诊断的限制必须写入支持矩阵，不能宣称任意 HIP/C++ 输入都可用。设备 printf、全局构造函数等不能仅因参考 libc/startup 中有代码就算已兼容。

### 7.2 HIP 头文件和设备库需要独立处理

“Clang 已能解析 HIP”不等于所有默认 HIP 头文件都适用于 RISC-V。LLVM 23 的 [__clang_hip_runtime_wrapper.h](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.4/clang/lib/Headers/__clang_hip_runtime_wrapper.h) 会引入 libdevice、数学和标准库支持，还包含与 OCKL 等外部符号相关的分支；迁移时需要审查它和相关包装头。

初版建议维护精简的 Vortex HIP 支持头/声明，在 T06.1 开始实现公开 runtime API 前固定所参考的 HIP 公共接口版本，保留 Clang 的真实 host/device/global 属性语义。T07.2 再交付设备头文件/宏/隐式 include/设备库清单；未使用的 AMD/NV/SPIR-V 依赖不能意外泄漏到 Vortex 设备 IR 和链接中。

精简支持范围不等于任意改变公开枚举、错误码或结构体 ABI。公共结构体应采用固定版本的完整声明，或初期只提供明确的标量能力查询；不能缩短 hipDeviceProp_t 等布局后宣称可与任意现有 HIP 客户端二进制互换。

host 的 C++ 系统头、设备 sysroot 和 baremetal 库分别配置。先允许复用固定参考版本的设备 ELF 静态库，但每个库都记录来源、ISA/ABI 和实际链接路径。不能把 LLVM 20 的设备 bitcode、AMDGPU device library 或宿主 libstdc++ 二进制当作天然兼容 LLVM 23/RISC-V；需要 bitcode 时按新编译器重新构建并检查。

### 7.3 SIMT 转换是必需语义，不能只挂在优化流水线

T03/T05 应写出 pipeline 不变量：在分歧分析前，线程标识与 private load 等语义可见；转换后，mask/token 和汇合结构仍成立。LLVM 23 的 IR 分析/转换与机器 pass 按实际接口接入，不能只换旧版注册宏。

O0 的 optnone/优化跳过规则不能跳过必要的 SIMT lowering；O2 后续 CFG 变换也不能破坏已经生成的结构。测试 pass 是否会漏跑、重复运行是否安全，并保存关键阶段 IR。遇到不支持或超过复杂度限制的 CFG，不能仅跳过 lowering 后继续生成可能错误的程序。

内联、非内联调用、每线程栈/alloca、PHI、不同循环退出路径分别验证。convergent、side effects 和 memory effects 各自有含义，不能靠统一添加一个属性替代正确的流水线与内存语义。

现有 SDK common.mk 默认使用 O3；已有 validate-compiler.sh 复用该配置，不能自动算作 O0/O2 验收。任务测试需提供明确模式，并记录实际 clang 命令中最终生效的 -O 选项。

### 7.4 内存、地址空间和参数不能混为一种布局

设备指针在参数区中是 64 位设备地址；host 的 void** args 是每个参数值的 host 地址列表。参数描述需要区分 pointer/scalar，不能按值是否落在地址范围内猜类型。偏移与对齐由设备 DataLayout/所定序列化契约决定，不能直接沿用宿主 sizeof 一个任意结构体。

global/private/shared 的语义、LLVM 地址空间数值、指针宽度、允许的转换与 alias 规则应形成表格，T07.3/T09.1 分别冻结并验证。不要直接照搬 AMDGPU 地址空间编号或 kernel calling convention；初版优先复用已验证的 RISC-V 普通函数调用约定，加 Vortex kernel wrapper。

shared memory 总量为静态资源与动态请求按约定布局后的大小；检查对齐、加法和 grid/block 乘法溢出。warpSize、maxThreadsPerBlock 等来自能力查询或明确的编译假设，不硬编码为常见 GPU 的 32/64 或 256。若设备库把某个配置编成常量，镜像需记录该假设并在加载/启动时检查。

### 7.5 公开 HIP API 与隐式编译器 ABI 分开验收

| 接口层 | 最小需要固定的行为 | 对应任务 |
|---|---|---|
| 设备与错误 | 单设备查询/选择子集、能力、错误码与 hipGetErrorString | T06.1 |
| 内存 | hipMalloc/hipFree、同步 H2D/D2H/D2D，范围与生命周期 | T06.2～T06.3 |
| 同步与 launch 错误 | hipDeviceSynchronize、hipGetLastError/hipPeekAtLastError 的选定契约 | T06.6、T08.4 |
| 隐式 ABI | 镜像注册/注销、函数注册、配置压栈/出栈、host stub 调用签名 | T08.1～T08.4 |

`<<<>>>` 语法本身不返回一个可直接检查的 hipError_t。运行时必须区分可立即发现的启动参数错误和需要同步才能报告的执行错误；错误状态不能用一个无条件共享的全局变量代替所选 host 线程语义。正式样例检查公开 API 和启动后的错误，避免失败后继续读取未定义输出。

参考 [HIP 错误处理说明](https://rocm.docs.amd.com/projects/HIP/en/latest/how-to/hip_runtime_api/error_handling.html)：GetLastError 读取并清除，PeekAtLastError 读取而不清除；哪些 API 结果写入 last-error 状态还需固定参考版本，因为该行为存在版本差异。实现时记录具体版本，而不是只写“兼容最新 HIP”。

注册构造函数可能在 main 之前执行。初版可先登记镜像与 kernel 描述，按需要延迟初始化设备/加载模块；明确构造、首次使用、在途任务与退出注销的所有权，不依赖不同全局构造函数的偶然顺序。

### 7.6 同步、原子和异步的完成标准

T09 的 barrier 测试同时覆盖 shared 和 block 内 global 数据的写入→同步→互读，以及循环中多轮同步。按 [HIP 同步语义](https://rocm.docs.amd.com/projects/HIP/en/latest/how-to/hip_cpp_language_extensions.html#synchronization-functions) 验证执行汇合、可见性和编译器重排约束；非法分歧 barrier 程序不作为要求得到确定结果的用例。

T10 原子先限定实际支持的类型、作用域和顺序，不把一次 AMO 生成等同于全部 HIP/C++ 原子语义。原子性和更强的内存顺序分别测试；不从竞争计数正确推出所有数据发布顺序都正确。修改 A 等配置后，还要核对缓存/内存路径及编译对象要求。

异步接口要写明 host 内存条件、阻塞回退、参数快照时机、buffer/module 保活和销毁等待。正确的 event 依赖可以在串行模拟器中验证；同时运行与性能提升属于另一个结论。

### 7.7 尚需在任务中冻结的设计项

| 设计项 | 最晚冻结任务 | 所需产物 |
|---|---|---|
| xvortex 版本、CPU 默认 ISA、ABI 与配置要求 | T01.6 | 选项/能力矩阵 |
| native 启动 PC、kernel PC、参数指针与库边界 | T04.1～T04.4 | ELF/启动/镜像契约与实物检查 |
| HIP 公共 API 参考版本、设备包装头和库策略 | 公共声明在 T06.1，设备部分在 T07.2 | 版本/依赖/声明清单 |
| 地址空间与参数格式、入口 wrapper | T07.3～T07.4 | 逐字段布局与 host/device 对照 |
| Clang 23 隐式 host ABI、镜像容器与错误行为 | T08.1～T08.4 | host IR、注册表和运行记录 |
| shared/barrier 与 atomic/stream/event 的支持子集 | T09.1、T10.2～T10.5 | 语义表和有区分力的执行测试 |

这些待冻结项是任务交付要求，不是当前已经确定所有格式或实现细节。验收时应回填实际选择与证据，继续在本文件和现有任务卡原地更新。

### 7.8 审查指令选择之后新增的分歧

IR 中的 select 可能在后端展开成机器级分支。LLVM 23 的 [RISCVISelLowering.cpp](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.4/llvm/lib/Target/RISCV/RISCVISelLowering.cpp) 中，本地基线的 `emitSelectPseudo` 路径会创建 MachineBasicBlock、条件分支和 PHI。因此 IR 阶段的 SIMT 转换完成后，还要检查 SelectionDAG、custom inserter、伪指令展开及后续 CFG 处理是否引入了需要 mask/汇合管理的新分支。

这是一项迁移风险，不是已经证实官方 Vortex 编译器存在错误。需要追踪原实现如何处理这些情况，再选择目标约束、无分支 lowering 或机器级处理；不能先假定所有普通 RISC-V lowering 都适合 SIMT。

T03.6/T05.5 至少检查整数/浮点条件选择、嵌套 select，以及实际会触发展开或 helper 的支持内运算；同时检查 Zicond 能解决哪些类型、哪些情况仍会走其他路径。保存 MIR/最终汇编，并用同一 warp 内不同条件的 lane 执行比较。机器验证器通过只证明相应结构约束，不证明 SIMT 语义正确。

### 7.9 执行推进、故障和恢复能力分别定义

普通 kernel 不能依赖所有 block 同时驻留，单个 warp 也不能默认具有其他 GPU 的独立线程推进语义。初版不承诺跨 block 自旋构造的全局 barrier、依赖同 warp 不同分支独立推进的锁算法或 cooperative grid 同步。合法的 block 内 barrier 和普通循环仍需正确完成；不能把所有超时都归因于用户算法。

故障通道同样要按实际后端区分。固定 SDK 的 [SimX core.cpp](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/sim/simx/core.cpp) 部分 issue-timeout 路径打印 PC、warp、mask 和等待信息后调用 abort；这类故障未必能返回到 HIP API。[queue.cpp](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/sw/runtime/common/queue.cpp) 中的队列错误/等待超时则有自己的返回路径，二者不能混同。

初版逐项列出：可由 API 返回的参数/队列错误、同步才能观察的错误，以及会终止进程的后端故障。测试用子进程和有界 watchdog 保存退出码/信号、超时与日志；超时只是未完成的证据，仍需定位原因。进程隔离、设备/context 恢复另行设计，不能声称已经具备完整 HIP 故障恢复能力，也不自动重试可能已经修改数据的 kernel。

### 7.10 将版本兼容与产物身份分开记录

| 版本/身份 | 描述什么 | 需要匹配的两端 |
|---|---|---|
| xvortex ISA 版本与所需 features | 指令编码和执行能力 | 编译器与 SDK/SimX/硬件 |
| native kernel ABI 与固定 SDK 提交 | startup、两个 PC、参数指针和基础调用规则 | 设备镜像与 loader/调度端 |
| HIP 参数描述/容器版本 | 参数布局、资源要求、镜像封装 | 编译器生成器与 host runtime |
| Clang 隐式 host ABI / HIP 公共声明版本 | 注册、stub、公开函数和结构声明 | host 编译、头文件与 runtime |
| 具体构建指纹 | 编译选项、头/库来源和配置假设 | 本次测试及其输入产物 |

不能只用一个 xvortex 版本号代表上述全部兼容性。第一版可继续使用固定 SDK 的原生 vxbin 格式，把 HIP 版本信息放在外层描述/容器，避免同时更改设备 loader。

调试闭环优先使用新生成的设备镜像。以后若增加设备产物缓存，缓存键要覆盖编译器修订、有效选项、相关头/库、ISA/ABI 和元数据版本；源文件名或时间戳不足以标识可执行结果。T10.6 报告应能从 host 程序追到嵌入镜像和生成命令，防止运行旧产物后误判新后端通过。
