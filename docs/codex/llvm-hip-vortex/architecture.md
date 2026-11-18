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

在当前未启用可选扩展的 RV64 原生测试中，基础选项为 `-march=rv64imafd -mabi=lp64d`，另外通过 target feature 启用 `+xvortex` 和 `+zicond`。这描述当前参考构建方式；LLVM 23 的最终默认 ISA 字符串与扩展版本由 T01 实现并验证。

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

这项记录只证明参考 llvm-mc 对四条输入的编码结果；没有证明 LLVM 23 已迁移这些指令，也没有新增 SimX 执行通过记录。

### 6.7 可选扩展与工具链覆盖

当前基线还提供按配置选择的 TCU/矩阵操作、DXA 异步数据搬运、纹理/图形相关操作，以及半精度和更宽/矩阵访存等方向。它们有各自的依赖，且本节基线默认关闭相应开关；不能将“源码存在”当作当前模拟器配置已经启用。具体可用操作以 VX_config.toml、SDK、SimX 与 RTL 一致为准。

参考 LLVM 的单个 td 文件并不覆盖 SDK/设备源码中的全部操作。SDK 可以用 `.insn` 直接发出合法编码，因此“设备能执行”“SDK 有包装”“llvm-mc 认识助记符”“Clang 能从 builtin/IR 生成”要分别验收。LLVM 23 的 xvortex 支持范围必须明确列出，未实现能力应诊断或记录为限制。

### 6.8 对本教程任务的影响

- T01：用标准扩展与 xvortex 定义 CPU 的默认能力，固定 ABI/ISA 选择规则。
- T02：先完成 TMC/SPLIT/JOIN/BAR 四条 MC 切片；本节编码表用于核对，其他控制操作按后续实际需要补全。
- T03：补 intrinsic、CSR、builtins、annotation 与优化属性，让 IR 正确表达指令语义。
- T04/T05：在真实 kernel ABI 和 SIMT 控制流中验证执行，不能以 MC 通过代替。
- T09/T10：单独验证 block 同步与原子等能力；vote/shuffle、矩阵等未纳入主线子集的能力按专题扩展，不因本节介绍而自动扩大 66 项的完成承诺。

阅读顺序为配置→SDK 包装→SimX 解码→RTL 解码/执行→LLVM 定义与 pass。某层只识别编码，另一层负责分析与生成，迁移时要保持两端契约一致。
