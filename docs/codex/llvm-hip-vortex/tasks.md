# LLVM 23 HIP/Vortex：66 个主线任务卡

更新日期：2026-11-18（Asia/Shanghai）。配套总览：[教程与最终成果](plan.md)。本文件是任务设计，不是已完成清单；任务进度以实际证据为准，文档修订不重置既有状态。

本修订按 [CPU/subtarget 架构方案](architecture.md) 重排：新增 T01 专门实现 `-mcpu=vortex`，原 T01～T09 顺延为 T02～T10。共 11 个阶段、66 个任务，旧的 T00 基线编号保持不变。

## 使用方式与共同交付要求

每阶段 6 个任务，共 66 个；按编号推进。每阶段列出共同前置知识、源码入口与排查方法，每个小任务再指定阅读范围、实施练习和验收。这里的练习规定行为和边界，不提供后端实现答案。一个任务可以包含多个小提交，遇到新语义问题也可以继续拆分。

每个任务都提交：① 用自己的话解释设计；② 实际修改或分析产物；③ 输入、命令、预期/实际结果；④ 涉及哪些参考组件；⑤ 一个失败/错误行为的解释。使用 [证据模板](evidence-template.md)。源码任务应有检验语义的测试；纯阅读任务用分析表/执行证据验收，不为凑数量编写测试。

验收分层：MC 编码测试不能替代 SIMT 执行测试，IR 检查不能替代参数 ABI 验证，SimX 执行成功不能替代 host 注册与资源生命周期检查。暂不支持的输入应有明确诊断或限制，避免静默误编译。

本轮审阅补充的契约见 [架构方案第 7 节](architecture.md#implementation-contracts) 与 [启动/参数契约](compiler-sim-contract.md)。下面新增的验收细节保留全部 66 个任务 ID；已经有执行证据的任务只需复核新增条件，不重新标成待做。优先补齐两个 PC、O0 必需转换、HIP 包装头/设备库和参数布局，再扩展功能。

## 源码导航

指令集入门先读 [架构方案第 6 节](architecture.md#vortex-isa)，其中包含当前标准扩展、自定义操作、CSR 与编码示例。它提供阅读材料，不改变现有任务 ID、状态或验收范围。

本地路径前缀：LLVM=`/home/kaikai/vortex-word/llvm-project`，SDK=`/home/kaikai/vortex-word/vortex`，工作区=`/home/kaikai/vortex-word`。下表使用相对路径定位文件；链接指向固定参考代码。LLVM 23 目标源码与 Vortex 20 参考源码要对照阅读，不能混成一个版本。

| 编号 | 阅读入口 | 关注内容 |
|---|---|---|
| R1 | LLVM `llvm/lib/Target/RISCV/RISCVFeatures.td`、`RISCVInstrInfo.td`；[参考 VX 指令定义](https://github.com/vortexgpgpu/llvm/blob/f44a6bb2af4c62847585305bbdc760fbe0e3645f/llvm/lib/Target/RISCV/RISCVInstrInfoVX.td) | feature、指令字段、谓词、输入输出 |
| R2 | [参考 IntrinsicsRISCV.td](https://github.com/vortexgpgpu/llvm/blob/f44a6bb2af4c62847585305bbdc760fbe0e3645f/llvm/include/llvm/IR/IntrinsicsRISCV.td)；LLVM `RISCVISelLowering.cpp` | IR 类型/属性与目标指令选择 |
| R3 | [参考 TTI](https://github.com/vortexgpgpu/llvm/blob/f44a6bb2af4c62847585305bbdc760fbe0e3645f/llvm/lib/Target/RISCV/RISCVTargetTransformInfo.h)、[分歧 pass](https://github.com/vortexgpgpu/llvm/blob/f44a6bb2af4c62847585305bbdc760fbe0e3645f/llvm/lib/Target/RISCV/VortexBranchDivergence.cpp) | 分歧来源、分析与控制流变换 |
| R4 | [参考 TargetMachine](https://github.com/vortexgpgpu/llvm/blob/f44a6bb2af4c62847585305bbdc760fbe0e3645f/llvm/lib/Target/RISCV/RISCVTargetMachine.cpp)；LLVM 同名文件及 `llvm/lib/Passes` | pass 顺序与 LLVM 23 接入方式 |
| R5 | [参考入口 pass](https://github.com/vortexgpgpu/llvm/blob/f44a6bb2af4c62847585305bbdc760fbe0e3645f/llvm/lib/Target/RISCV/RISCVVortexKEntry.cpp) | annotation 到入口 alias |
| R6 | LLVM `llvm/lib/TargetParser/RISCVISAInfo.cpp`、`clang/lib/Basic/Targets/RISCV.*` | ISA 扩展识别、Clang feature 和诊断 |
| R7 | LLVM [Driver.cpp](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.4/clang/lib/Driver/Driver.cpp)、`clang/lib/Driver/ToolChains/HIPSPV.*`、`AMDGPU.*` | host/device jobs 与工具链选择；路径/类名以本地源码为准 |
| R8 | LLVM [CGCUDANV.cpp](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.4/clang/lib/CodeGen/CGCUDANV.cpp)、`clang/lib/Sema/SemaCUDA.cpp` | HIP 调用限制、host stub、注册与启动 |
| R9 | LLVM [RISCVProcessors.td](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.4/llvm/lib/Target/RISCV/RISCVProcessors.td)、`llvm/lib/TargetParser/RISCVTargetParser.cpp`、[RISC-V driver](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.4/clang/lib/Driver/ToolChains/Arch/RISCV.cpp) | CPU 模型、DefaultMarch、CPU 校验与 mcpu/march 优先级 |
| V1 | SDK `sim/simx/decode.cpp`、`hw/rtl/core/VX_decode.sv` | 编译器输出位字段与执行端一致 |
| V2 | SDK [vx_spawn2.h](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/sw/kernel/include/vx_spawn2.h)、`sw/kernel/include/vx_intrinsics.h` | CTA builtins、uniform/kernel annotation、同步原语 |
| V3 | SDK `tests/regression/demo/{main.cpp,kernel.cpp,common.h}`、`tests/regression/common.mk` | native 最小编译/执行样例与 ABI |
| V4 | SDK `sw/kernel/src/vx_start.S`、`sw/kernel/scripts/link64.ld` | 启动、栈、CSR 参数与链接布局 |
| V5 | SDK `sw/kernel/scripts/vxbin.py` | 镜像格式与入口表 |
| V6 | SDK [vortex2.h](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/sw/runtime/include/vortex2.h)、`sw/runtime/common` 对应实现 | buffer、module、queue、event 与生命周期 |
| V7 | SDK `tests/hip/common.mk`、`tests/hip/vecadd`、`tests/hip/sgemm`；[现有 HIP 设计](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/docs/designs/hip_on_vortex_chipstar.md) | 对照现有 chipStar 路径与测试行为 |
| W1 | 工作区 `scripts/{run-smoke.sh,validate-compiler.sh,run-kernel.sh,inspect-kernel.py}` | 基线、编译器替换范围与产物检查 |

SDK 当前使用 sparse checkout；尚未出现在本地的参考文件先通过固定提交链接阅读。不要因文件未检出就判定官方没有实现。编译器参考 fork 也不是本地 LLVM 23 的一部分。

## 阶段 T00：构建与 ABI 基线

前置：能在 Bash 使用 Git、CMake、编译器。按 [TASK-000 操作命令](getting-started.md)完成本阶段；每个小任务单独留证据。退出条件：知道哪些结果来自参考工具链，哪些来自新 LLVM。

### T00.1 固定版本和能力

- 目标/阅读：阅读总览基线、W1/env.sh，识别 LLVM、SDK、参考工具链和 SimX 的版本关系。
- 练习：记录 Git commit/diff、编译器路径、RV64/ABI、模拟器扩展开关与 block 限制。
- 验收：任何一条测试命令都能指出所用 compiler 与配置；没有把目录名字当版本证据。
- 交付/排查：版本与能力表。失败先核对 PATH 和实际文件；现有 build.sh/.gitignore 修改应记录保留。

### T00.2 构建四目标 LLVM

- 目标/阅读：阅读工作区 `docs/llvm-build.md` 和 LLVM 根目录 build.sh，理解源码/构建/安装目录。
- 练习：完成构建，取得 clang、llc、opt、llvm-mc、llvm-objdump、FileCheck；记录 targets-built。
- 验收：LLVM 23 版本正确，AMDGPU/RISCV/NVPTX/X86 均在构建目标中，构建退出码为 0。
- 交付/排查：构建日志与工具清单。tee 使用 pipefail；内存不足降低并行度，不改后端规避构建错误。

### T00.3 认识标准 RV64 编译链

- 目标/阅读：阅读 RISC-V 目标输出和 TASK-000 的 add.c，区分源码、IR、汇编、对象与可执行镜像。
- 练习：用新 Clang 生成 add.ll/add.s，标出 triple、DataLayout、参数和返回值。
- 验收：不依赖 Vortex feature 或设备 libc，能解释为什么当前产物还不能直接作为完整 kernel 执行。
- 交付/排查：两个产物与短注释；若出现 host 汇编，先核对 --target 和实际 compiler 路径。

### T00.4 复跑参考 SimX 测试

- 目标/阅读：阅读 W1/run-smoke.sh 和 V7，区分 native/OpenCL/chipStar HIP 三条路径。
- 练习：复跑五项 smoke，保留配置、完整命令和逐项结果。
- 验收：五项均通过，记录清楚它们使用参考编译器；现有 HIP 通过不计为原生 HIPVortex 实现。
- 交付/排查：基线报告；执行端失败先检查参考环境，不把尚未修改的新 LLVM 当作故障来源。

### T00.5 画出 kernel ABI 调用链

- 目标/阅读：依次阅读 V3、V2、V6、V4、V5、R5。
- 练习：手算 demo 的参数偏移和 40 字节总大小，画 buffer→地址→参数区→CSR→a0→kernel→读回链路。
- 验收：说明 startup、kernel body、入口 alias 的区别，以及 annotation 与 retain 的不同责任。
- 交付/排查：ABI 图与源码定位表。把 host 指针当设备地址、把 body 入口当 startup 都应能解释为何错误。

### T00.6 建立分层验收方法

- 目标/阅读：阅读 W1/validate-compiler.sh，列出它替换与复用的组件。
- 练习：整理 MC、IR、镜像、runtime、执行各层测试；可选尝试未扩展 LLVM 的验证并记录第一处实际错误。
- 验收：提交 TASK-000 中七个问题的回答；能解释“参考系统可跑”和“新编译器已可跑”的区别。
- 交付/排查：evidence.md 和下一阶段测试计划。这里不要求未扩展 LLVM 通过 native 验证。

## 阶段 T01：Vortex CPU/subtarget 与选项契约

前置：T00 通过；理解 Target、CPU、ISA extension、ABI 的区别。公共入口 R9/R6/R1。本阶段让工具正确选择 Vortex 配置，尚不实现四条特殊指令。首版固定 RV64，默认配置对齐现有 SimX。

### T01.1 写下 CPU、ISA、ABI 和设备边界

- 目标/阅读：阅读 R9 的 ProcessorModel/DefaultMarch、架构方案第 6.2 节的标准扩展配置和 T00 能力表。
- 练习：定义名称 vortex、位宽、标准扩展、xvortex、基础 ABI、保守调度选择；列出 CPU 默认能力与可选配置。
- 验收：明确 -mcpu 不表示源文件自动变成 HIP 或所有函数都变成 kernel；host x86 与设备 RV64 配置分开。
- 交付/排查：CPU 契约与选项组合表。默认 ISA 不夹带当前 SimX 未启用的 A/C，不虚构精确性能参数。

### T01.2 建立 xvortex feature 与 ISA 解析

- 目标/阅读：阅读 R1 的 RISCVExtension 模式和 R6 的 ISA 识别/版本规则。
- 练习：定义 xvortex extension、版本、Subtarget 查询和谓词基础；打通默认 ISA 字符串的解析，暂不新增指令编码。
- 验收：显式 ISA 能识别约定的 xvortex，拼错名称/版本有诊断，+/- feature 可解释；标准 RV64 行为不变。
- 交付/排查：feature/parser diff 与测试。优先利用 LLVM 23 的生成机制，不手工维护多份相同扩展清单。

### T01.3 注册 vortex ProcessorModel

- 目标/阅读：阅读 R9 的 RISCVProcessors.td、TargetParser 和 CPU 信息生成路径。
- 练习：注册 vortex CPU，设置一致的位宽、features、DefaultMarch 和保守调度配置，检查 Clang CPU 列表与后端查询。
- 验收：工具识别 vortex，RV64 默认 ISA 与契约一致，错误 CPU 名和 RV32/vortex 组合有正确错误。
- 交付/排查：CPU 注册 diff 与识别测试。生成的 .inc 文件不是主要编辑对象；追踪它来自哪个 TableGen 源。

### T01.4 验证 Clang 的 mcpu/march/ABI 传递

- 目标/阅读：阅读 R9 的 getRISCVArch、CPU 校验与 R6 的 setCPU/feature 初始化。
- 练习：编译不含特殊指令的 add.c，通过 -### 和 IR 检查 CPU、features、ABI；覆盖无 march、兼容 march、移除 xvortex 的 march。
- 验收：显式 ISA 遵循上游优先级，CPU 默认配置与实际传递一致，错误 ABI/目标组合可解释。Vortex kernel/HIP 的额外约束先写成后续集成验收要求。
- 交付/排查：driver/前端定向测试与参数追踪图；不能只验证 mcpu 参数被接受，就假定 feature 已生效。

### T01.5 验证 LLVM 工具与函数属性

- 目标/阅读：阅读 R9 的 CPU 数据与 R4/R6 的 subtarget 创建、IR target 属性通路。
- 练习：用 llc/llvm-mc 的 CPU 选择编译标准指令，比较显式 feature 选择；检查 IR target-cpu/target-features 如何保持或覆盖配置。
- 验收：Clang 与独立工具取得一致的有效能力；无 Vortex feature 的函数不误启用扩展；能解释 per-function 配置来源。
- 交付/排查：工具级测试和最终配置表。尚无特殊指令时只证明选择通路，真正指令 gating 在 T02 验证。

### T01.6 固定 CPU 选择矩阵

- 目标/阅读：对照架构方案中的组合表与本阶段所有配置测试。
- 练习：整理默认 CPU、兼容/冲突 march、错误位宽、普通 RISCV、显式禁用 feature、ABI 的回归；记录后续 kernel/HIP 必须追加的诊断。
- 验收：当前 CPU/ISA 选择矩阵通过，标准标量函数输出正确；明确初版 vortex 仅 RV64、未实现特殊指令和 HIP。T04/T07 需回填设备上下文冲突测试。
- 交付/排查：CPU/subtarget 阶段报告与测试清单；不通过硬编码 CPU 名强制覆盖用户的显式 ISA。

## 阶段 T02：MC 指令切片

前置：T01 通过；理解寄存器、R 型编码、TableGen 基本语法。公共入口 R1/V1。所有指令按当前执行端核对位字段；本阶段验证 CPU 默认路径和显式 -mattr 路径共同约束特殊指令。

### T02.1 建立编码对照表

- 目标/阅读：先读架构方案第 6.6 节的位段与编码，再对照 R1 与 V1 的 TMC/SPLIT/JOIN/BAR 定义与解码。
- 练习：列出 opcode/funct3/funct7、固定字段、可变寄存器；任选寄存器手算一条指令的 32 位编码。
- 验收：TableGen、手算和执行端对字段的解释一致，明确输入/输出与隐含状态变化。
- 交付/排查：编码表和手算过程；小端字节序与位字段书写顺序分别核对。

### T02.2 接入扩展指令文件与 feature 谓词

- 目标/阅读：阅读 R1 的 feature/Predicate 模式与 T01 已创建的 xvortex 定义。
- 练习：接入扩展指令文件，统一汇编/反汇编与指令选择所用谓词；不要重新定义第二份 CPU/feature。
- 验收：+xvortex 与 mcpu=vortex 的默认能力可启用定义，最终 feature 被关闭时不会误用指令；已有 RISCV 指令保持可用。
- 交付/排查：接入 diff 和谓词设计；实际指令编码在随后三项实现，禁用行为在 T02.6 统一验收。

### T02.3 实现 TMC

- 目标/阅读：阅读 R1 的 VX_TMC 和 V1 对 thread mask 的解释。
- 练习：定义汇编助记符、单寄存器操作数及固定字段，增加 show-encoding 测试。
- 验收：至少两个不同寄存器编码正确；多余/错误操作数拒绝，关闭 feature 拒绝。
- 交付/排查：指令定义和 MC 测试；不能把改变 mask 的指令误描述成无副作用普通运算。

### T02.4 实现 SPLIT/JOIN

- 目标/阅读：对照 R1 的结果 token、谓词输入与 JOIN 输入。
- 练习：实现两条指令，解释 token 与普通条件分支的关系，不在本任务实现 CFG pass。
- 验收：各寄存器字段与固定 rs2/rd 正确；输入输出寄存器变换有独立编码用例。
- 交付/排查：diff、编码测试与语义说明；不要把 SPLIT 当作自身已完成所有分支跳转。

### T02.5 实现 BAR

- 目标/阅读：阅读 R1 的 BAR 标志及 V2 barrier 包装调用。
- 练习：实现双寄存器操作数，解释描述符里的 barrier/side-effect 标志负责什么。
- 验收：两参数位置、编码和非法输入测试正确；说明完整内存同步留待 T09 验证。
- 交付/排查：MC 测试与同步问题列表；isBarrier 标志本身不证明 HIP 内存模型已满足。

### T02.6 补齐反汇编与负例

- 目标/阅读：阅读 LLVM `llvm/test/MC/RISCV` 同类测试的运行方式。
- 练习：生成对象再反汇编，覆盖四条指令、CPU 默认与显式 feature 通路、feature 关闭、非法操作数和普通 RISC-V 回归。
- 验收：编码/反汇编往返一致；测试断言关键字段和诊断，不依赖无关格式。
- 交付/排查：完整 MC 切片证据与评审 diff。反汇编器未开 feature 时可能显示未知编码，和汇编拒绝分别验收。
- 补充验收：区分具名指令/IR 的 feature 负例与 `.insn` 原始编码出口；原始字节能被汇编器写出不表示其在目标设备上合法。

## 阶段 T03：IR、CSR、uniformity 与 Clang feature

前置：T02 通过；理解 SSA、intrinsic 属性和优化重排。公共入口 R2/R3/R4/R6/V2。重点是语义，不是“让 llc 不报错”。

### T03.1 设计最小 intrinsic 契约

- 目标/阅读：阅读 R2 中 Vortex intrinsic 定义并对照 LLVM 23 属性规则。
- 练习：为最小控制/标识 intrinsic 列类型、宽度、副作用、memory effects、convergent 与可优化条件。
- 验收：可解释哪些操作可公共子表达式消除、哪些不能删除/跨控制流移动；参考属性也需审查。
- 交付/排查：语义表与属性设计，不机械把全部 CSR 读取标成相同纯度。
- 补充验收：写出 pointer/整数宽度、convergent 与访存约束各自的理由；检查 O0/optnone 下必需语义仍保留，不只依赖优化运行。

### T03.2 实现 intrinsic 到指令的选择

- 目标/阅读：阅读 R2 与 R1 的 Pat/目标 lowering 对应关系。
- 练习：先支持 TMC/SPLIT/JOIN/BAR 必需 IR 路径，加入 RV64 类型合法化和禁用 feature 诊断。
- 验收：小型 IR 经 llc 产生期望指令；错误签名不能静默截断；优化后关键副作用仍保留。
- 交付/排查：CodeGen 测试、优化前后 IR 与汇编；区分 intrinsic 名字匹配失败和选择失败。

### T03.3 接通 CSR 与线程 builtins

- 目标/阅读：阅读 V2 的 CTA thread/block/dimension CSR 包装和 V1 的相关执行路径。
- 练习：接通 threadIdx/blockIdx/blockDim/gridDim 所需最小能力，审查 X/Y/Z 与返回值宽度。
- 验收：IR/汇编访问正确 CSR，不把 warp 内 lane ID 直接当完整 CTA threadIdx；执行坐标验证在 T04 完成。
- 交付/排查：builtin/CSR 对照表和 CodeGen 测试；不要混用旧运行模型的编号。
- 补充验收：同模块使用不同 grid/block 维度重复启动时，CTA 坐标/维度按当前执行上下文读取，不跨 CTA/launch 缓存为全局常量。

### T03.4 识别分歧来源

- 目标/阅读：阅读 R3 的 TTI 查询与 UniformityAnalysis 相关接口。
- 练习：建立 threadIdx、block 维度、普通参数/加载值的保守分类，测试依赖传播。
- 验收：同一 warp 不同线程的条件可判为 divergent；未知加载不因地址一致就被错误判为 uniform。
- 交付/排查：分析测试和分类依据；每线程栈、参数值与地址空间要分别检查。

### T03.5 消费 annotation 并选择 pass 接入点

- 目标/阅读：阅读 V2 的 vortex.uniform/kernel、R3/R4，以及相关 Clang annotation 发射代码。
- 练习：追踪 annotation 到 IR，再设计分析/转换中的消费方式；文档写明当前保留或尚未使用的标记。
- 验收：测试 O0/O2 下信息的存续及实际用途；普通 RISC-V 不进入 Vortex 专用逻辑。
- 交付/排查：pipeline 图与 IR 测试。这里处理信息传递，完整 kernel alias 在 T04，CFG 变换在 T05。

### T03.6 验证 CPU 选择贯穿 IR 与代码生成

- 目标/阅读：阅读 R6、T01 的选择契约与 T03 intrinsic/annotation 路径。
- 练习：用 mcpu=vortex 驱动 Clang→IR→llc，核对版本/feature/必要宏与优化后设备语义；显式 ISA 覆盖也要走完整路径。
- 验收：CPU/feature 选择与实际指令一致；关闭扩展、错误扩展、普通 RV64 有回归，Vortex pass 不影响其他目标。
- 交付/排查：跨层测试与完整命令；T01 已定义规则，本任务验证新语义接入后没有破坏这些规则。

## 阶段 T04：native kernel 可运行

前置：T03 通过；理解 ELF、链接、栈与参数 ABI。公共入口 R5/V3/V4/V5/W1。先复用固定参考设备库和链接工具，明确每个对象的编译来源。

### T04.1 写下 native kernel ABI 契约

- 目标/阅读：复读 V3/V4，区分启动入口、被调 kernel 与参数结构。
- 练习：定义 RV64/lp64d、参数指针位置、对齐、callee 约定、入口命名和保留规则。
- 设备配置检查：回填 T01.6 的 kernel 上下文用例，缺少必需 xvortex 能力时明确诊断，不因 CPU 名仍为 vortex 就继续生成不兼容 kernel。
- 验收：host 写入布局与 device 读取布局逐字段一致，设备地址不等于 host 指针。
- 交付/排查：带版本的 ABI 说明；后续 HIP wrapper 以此为设备入口契约。
- 补充交付：记录程序启动 PC、kernel 函数 PC 与参数地址三项，及 x86_64 Linux host / RV64 lp64d device、code model、库来源和地址空间约定。

### T04.2 迁移 kernel entry alias 生成

- 目标/阅读：阅读 R5 的 annotation 扫描、GlobalAlias 创建与链接保留逻辑。
- 练习：按 LLVM 23 API 实现入口生成，处理重复执行、无 annotation、多个 kernel。
- 验收：只对标记函数生成稳定 alias；重复运行不重复创建，未标记函数不被误注册。
- 交付/排查：IR pass 测试；alias 生成成功后仍需在链接产物验证未被删除。
- 补充核对：固定 SDK 实际采用公共 startup 与 CTA_ENTRY 的分离路径；不能依据旧注释把函数 alias 当作每 kernel 启动 stub。

### T04.3 接入 startup 与链接布局

- 目标/阅读：阅读 V4 与 V3/common.mk，核对当前 KMU 启动方式。
- 练习：使用新 compiler 处理启动/设备对象，复用已固定库与链接脚本，记录每项来源。
- 验收：ELF 为正确 RV64 可执行文件；入口、段地址、栈、a0 和间接调用约定匹配执行端。
- 交付/排查：ELF/map/反汇编；先查链接地址与缺失符号，再归因到设备执行。
- 补充验收：公共入口与镜像基址/runtime program_pc 一致，kernel_pc 独立指向选中函数；检查 CTA slot 复用依赖的 dispatch window，不任意改变其长度。

### T04.4 检查 vxbin 与 kernel 表

- 目标/阅读：阅读 V5 的入口枚举、地址范围与 footer，结合 W1/inspect-kernel.py。
- 练习：对链接 ELF 打包，核对 kernel_main→main 映射、入口地址和镜像内存范围。
- 验收：镜像通过结构检查，模块可找到指定 kernel；错误文件和缺失 kernel 有可解释失败。
- 交付/排查：格式检查记录；不要把 .o 重命名为 .vxbin，或只验证文件存在。
- 补充验收：镜像 payload 与含 BSS 的运行时范围分别检查；现有 VXSYMTAB 只有名称/PC，HIP 参数描述另有版本契约，不假定 footer 已携带它。

### T04.5 在 SimX 执行首个 kernel

- 目标/阅读：阅读 V3 host 和 W1/run-kernel.sh 的 ABI 限制。
- 练习：用新 compiler 编译兼容 demo 的 kernel，选择整除 block 的规模，运行并验证 1D/2D 坐标。
- 验收：多 block、不同 X/Y 坐标的整数结果与 CPU 一致；记录新镜像路径和生成日志。
- 交付/排查：首次执行证据；此时避免 lane 分歧，uniform 循环也应检查生成代码，不默认后端都正确。

### T04.6 固定第一个可运行里程碑

- 目标/阅读：阅读 W1 的编译器替换流程与缓存/临时目录策略。
- 练习：重新生成产物复跑 demo，尝试适用的 native sgemm 接入，保存支持范围与失败分层方法。
- 验收：能从命令证明 kernel 来自 LLVM 23；符合本阶段约束的用例稳定通过，非目标能力明确记录。
- 交付/排查：M1 报告。复用参考 runtime 要明示；不能把旧 kernel 或参考 compiler 的产物当新后端结果。
- 补充验收：用不同结果的两个 kernel 交替启动，并覆盖多轮 CTA slot 复用；区分默认 O3 接入脚本与另行控制的 O0/O2 测试。

## 阶段 T05：SIMT 分歧与重新汇合

前置：T04 通过；理解 dominator/postdominator、SSA/PHI、循环与 active mask。公共入口 R3/R4/R2/V1。本阶段只给已有硬件语义生成正确程序，不通过改变 SimX 指令语义来适配错误 lowering。

### T05.1 拆解官方分歧流水线

- 目标/阅读：阅读 R3/R4，追踪分析、CFG 结构化、控制 intrinsic 和机器指令各在哪一步出现。
- 练习：画出参考 pass 的输入/输出与依赖；对照 LLVM 23 说明 IR pass 和后端 pipeline 如何接入。
- 验收：能指出 pass 前后必须成立的不变量，解释为何不能随便换顺序；普通 RISC-V 有关闭保护。
- 交付/排查：迁移设计与阶段 IR 样例；legacy/new pass manager 的适配按实际流水线处理，不机械替换类名。
- 补充验收：必需转换在 O0/optnone 下仍运行；pass 重跑与后续 CFG 优化有不变量检查，复杂度退出不能静默留下错误 SIMT 程序。

### T05.2 处理最简单的分歧 if

- 目标/阅读：阅读 R3 的分歧分支处理与 R1/R2 的 split/join 语义。
- 练习：用同一 warp 内奇偶 threadIdx 构造单臂 if，标出执行 mask、token 和汇合点；补全实际需要的控制指令。
- 验收：条件为真/假 lane 都存在，分支后共同写回正确，未参与 lane 的哨兵值保留；O0/O2 均通过。
- 交付/排查：CFG 图、变换后 IR、汇编与 SimX 对照。只看见 split/join 名字不算语义验收。

### T05.3 扩展到 if/else 与嵌套分支

- 目标/阅读：阅读 R3 的 mask/token 保存恢复、汇合与 PHI 处理。
- 练习：实现双臂分支、两层嵌套和分支结果在汇合后使用的用例；核对每条边的值与活跃线程。
- 验收：混合 lane 下两臂均执行正确，PHI/共同后续代码无重复或漏执行，O0/O2 输出一致。
- 交付/排查：嵌套 CFG 与状态变化表；token 活跃期、寄存器分配和错误汇合点分别排查。

### T05.4 支持循环与循环退出

- 目标/阅读：阅读 R3 的 LoopInfo、回边、退出处理及相关 SSA 更新。
- 练习：依次加入不同 lane 不同迭代次数、break、continue、循环后写回；一次仅增加一种退出结构。
- 验收：包含零次、一轮、多轮迭代及混合退出 lane，循环后 mask 恢复正确；不会超时挂死。
- 交付/排查：每个子用例的 IR/执行记录。复杂不可规约 CFG 若暂不支持，必须定义诊断/限制而非静默跳过后误编译。

### T05.5 验证优化、内存与函数调用边界

- 目标/阅读：对照 R2/R3 的 convergent、side effect、uniformity 传播及调用处理。
- 练习：构造带普通 load/store、PHI、内联 helper 的分歧用例，比较 O0/O2；测试非内联调用是否在支持范围。
- 验收：优化未错误移动/合并 lane 控制和访存；受支持调用保留语义，未实现的分歧跨函数调用明确拒绝或列入限制。
- 交付/排查：优化差异与最小回归用例；不能通过永久关闭所有优化来宣告 O2 支持。
- 补充用例：private 栈/alloca 的地址与值分类、内联与不内联 helper、分歧路径上的提前退出；未支持的递归/间接调用需列明限制。

### T05.6 通过尾部边界与控制流套件

- 目标/阅读：重看 V3/V7 的索引方式和本阶段所有失败用例。
- 练习：增加 N=1/37/64 等 vecadd，输出尾部哨兵，多 block 与不同合法 block 规模；汇总分歧测试套件。
- 验收：包含同一 warp 内部分 lane 越界的情形，整数严格比对、浮点按预先定义容差，O0/O2 均正确。
- 交付/排查：M2 报告与支持 CFG 清单，说明已实现/尚未支持的调用和退出结构，不只报告一个 vecadd PASS。

## 阶段 T06：原生 runtime 底座

前置：T05 通过；理解 host/device 地址、对象所有权与同步。公共入口 V6/V3/W1。建议单独建立 hip-vortex 项目；此时显式 module launch，不依赖自动 host stub。

### T06.1 设计设备上下文和错误模型

- 目标/阅读：阅读 V6 的 device/query 接口及 V3 中的错误处理方式。
- 练习：建立独立 runtime 的最小构建，封装单设备初始化/关闭、能力查询、公开错误码与错误字符串。
- 验收：初始化成功与不可用设备失败均可解释；查询结果用于检查 block/内存/ISA 限制，避免硬编码所有设备相同。
- 交付/排查：接口边界、构建说明与初始化测试；HIP 子集头文件需保证约定签名与 ABI。
- 补充交付：先固定 HIP 公共 API 参考版本，再列明 hipGetDeviceCount/GetDevice/SetDevice/能力查询及 hipGetErrorString 子集；公开枚举/结构布局保持该版本约定，单设备以外请求不静默接受，不硬编码 warpSize=32/64。

### T06.2 实现分配、释放与设备地址映射

- 目标/阅读：阅读 V6 的 buffer create/address/release 与底层所有权。
- 练习：建立设备地址区间→buffer/偏移映射，实现最小 hipMalloc/hipFree 行为，写明零长度及无效释放策略。
- 验收：多个分配不混淆；支持合法指针加偏移查找；越界、重复释放等按约定返回错误，无 host 解引用设备指针。
- 交付/排查：地址表设计与边界测试；检查长度加法溢出、地址转换和对象保活。

### T06.3 实现同步内存拷贝

- 目标/阅读：阅读 V6 的队列读写/拷贝与完成事件语义。
- 练习：先实现 H2D/D2H，再实现范围内 D2D；定义支持的拷贝方向和零字节行为。
- 验收：数据往返一致，带偏移拷贝不覆盖哨兵；同步 API 返回时相应缓冲区已可安全使用。
- 交付/排查：数据与非法范围用例；异步 SDK 调用后不能未经等待就报告同步拷贝完成。

### T06.4 加载 module 与定位 kernel

- 目标/阅读：阅读 V6 module load/get-kernel 与 V5 符号表约定。
- 练习：加载 T04/T05 镜像，按名字取得 kernel handle，约定 module 与 kernel handle 生命周期。
- 验收：合法名字可启动；文件损坏、名字缺失、已卸载句柄有明确处理，引用中的镜像不被过早释放。
- 交付/排查：加载测试与生命周期图；kernel 名与 ELF 符号/打包导出名分开核查。

### T06.5 显式参数打包与默认队列启动

- 目标/阅读：阅读 V6 的 launch_info、args_host/args_size 和 V3 的 launch。
- 练习：先用已知 native ABI 构造参数区，检查 grid/block、共享内存请求和参数生命周期，默认队列启动并同步。
- 验收：不同数据、不同 grid、重复启动结果正确；非法维度/超设备限制在可行位置检查并返回错误。
- 交付/排查：最小 module host 例子；先核对参数布局与设备地址，再查 kernel 算法。

### T06.6 固定 runtime 底座与清理规则

- 目标/阅读：审查 V6 对队列、event、buffer、module 的 retain/release 与等待要求。
- 练习：组合完整分配→拷贝→启动→等待→读回→释放，覆盖中途失败和多次重复；补 hipDeviceSynchronize 的约定。
- 验收：成功/失败路径不遗漏自己创建的资源；在途任务所需对象保持有效；默认 stream 范围写明。
- 交付/排查：runtime smoke 与资源所有权表。多设备/多 stream 不在此阶段的实现承诺中。
- 补充契约：定义 hipGetLastError/hipPeekAtLastError 的记录/读取/清除及 host 线程行为，区分立即参数错误和同步报告的执行错误；在途 free/unload 不破坏引用。

## 阶段 T07：HIP device-only 编译

前置：T06 通过；理解 HIP host/device 函数、Clang target/ABI、类型布局。公共入口 R6/R7/R8/V2。最终产物必须直接走 RISC-V/Vortex，现有 SPIR-V 路径只作对照。

### T07.1 接入已确定的 Vortex CPU 到 HIP device jobs

- 目标/阅读：阅读 R7 的工具链选择和 HIPSPV/AMDGPU jobs，结合 R6 的 RISC-V target。
- 练习：区分 x86 host 与 RV64 device，将 -mcpu=vortex、默认 ISA/ABI、设备库位置接入 HIP toolchain；继承 T01 契约。
- 验收：设备 jobs 的 CPU/feature 正确，x86 host 不收到 vortex CPU；普通 RV64 不误选 HIP，HIP 设备缺少必需能力时诊断。
- 交付/排查：toolchain 设计与 -### 测试，回填 T01.6 的 HIP 上下文检查；命令拼写在实现确定后固化，不重新引入独立架构。

### T07.2 建立最小 HIP 设备头文件与语义边界

- 目标/阅读：阅读 R8 的 HIP 语义检查、V7 的 vecadd 输入及参考 HIP 头文件使用方式。
- 练习：提供所需的 dim3、函数属性和设备声明，验证 __global__/__device__/__host__、host/device 调用限制。
- 验收：合法 kernel 与 helper 可分析，非法 host/device 调用有诊断；不依赖 AMD 特定头文件假设生成目标代码。
- 交付/排查：Sema/头文件测试；仅用宏把 __global__ 擦掉不算完成 HIP frontend。
- 补充交付：沿用 T06.1 固定的 HIP 公共声明版本，审计 Clang 隐式 runtime wrapper、数学/stdlib 头和设备库；禁止未说明/未实现的 AMD/NV 设备调用、宿主库或不匹配的旧 bitcode 依赖。

### T07.3 映射 HIP builtins 与设备地址语义

- 目标/阅读：对照 V2、R2/R3 和本地 Clang CodeGen target/ABI 逻辑。
- 练习：接通 HIP thread/block/dimension，明确 global/private 指针和 DataLayout 的选择，检查分歧分析能看见来源。
- 验收：X/Y/Z 对应正确，设备指针运算与 RV64 地址宽度一致；生成 IR 不残留错误 AMD/NV 特定依赖。
- 交付/排查：HIP→IR/汇编测试及地址空间表；语言地址空间编号与实际硬件存储语义不可混淆。
- 补充交付：global/private/shared 的语义、LLVM 数值映射、宽度/对齐、转换和 alias 规则；kernel wrapper 与普通 helper 的调用约定分开说明。

### T07.4 设计参数元数据与 kernel wrapper

- 目标/阅读：结合 R8 的 kernel 函数表示、R5/V4 的 native 入口 ABI。
- 练习：限定指针/int32/uint32/int64/uint64/float 参数，定义版本化偏移/大小/对齐元数据，生成单参数区入口 wrapper。
- 验收：wrapper 按相同布局解包并调用 HIP 实现；混合参数顺序、padding、两个签名和零参数 kernel 有用例。
- 交付/排查：ABI 文档和 IR/布局测试；void** 只提供值的位置，不能替代类型布局元数据。
- 补充验收：逐字节验证 [vecadd 的建议 32 字节参数区](compiler-sim-contract.md) 及不同签名；检查 pointer/scalar kind、尾部 padding、元数据版本与错误布局。示例数值需由真实目标 DataLayout/生成器再次确认。

### T07.5 构建设备链接与打包 jobs

- 目标/阅读：阅读 R7 的 device linker/bundling 编排，与 V4/V5 的 Vortex 镜像要求对照。
- 练习：为 device-only 路径连接编译、startup/库链接与 vxbin 打包；限定单翻译单元，保留可检查中间产物。
- 验收：-### 与实际执行一致，device ELF/镜像可检查；缺失链接器/设备库能报告准确错误。
- 交付/排查：driver 测试与完整产物链；不要只改 IR triple 而沿用错误设备 ABI/库。
- 补充验收：保留参数元数据并与设备镜像/入口匹配；记录 sysroot、libc、compiler-rt、LLD 的实际来源，检查最终 ELF 未引入 host crt/动态装载器。

### T07.6 执行 HIP device-only kernel

- 目标/阅读：阅读 T06 的显式 module host，核对 T07 参数元数据。
- 练习：手写 host 按元数据打包，运行 HIP device vecadd/SAXPY，覆盖不同参数值、浮点标量和尾部判断。
- 验收：新 Clang 从 HIP 输入直接生成 RISC-V 镜像，SimX 与 CPU 结果一致；无 PoCL/SPIR-V JIT 参与该路径。
- 交付/排查：设备侧 HIP 里程碑报告；此时手写 host 仍允许，不能提前宣称自动 <<<>>> 全链路已完成。

## 阶段 T08：HIP host/device 全链路

前置：T07 通过；理解 host ABI、全局构造/析构、二进制容器和符号关联。公共入口 R7/R8/V6。先完成一个翻译单元，暂不引入跨文件 device linking。

### T08.1 从 host IR 提取真实 HIP ABI

- 目标/阅读：阅读 R8 的 host stub、注册、launch 与配置压栈/出栈逻辑。
- 练习：以最小 HIP 输入检查 host IR，列出所有隐式外部符号、函数签名、dim3 传递与调用次序。
- 验收：清单与实际 IR 一致，区分公开 API 与编译器 ABI；头文件、CodeGen 与 runtime 原型相同。
- 交付/排查：host ABI 表与 IR 测试，特别核对默认 stream 选项，不能只凭函数名实现。
- 补充验收：dim3/size_t/stream 与函数原型来自同一套声明；明确只支持约定的默认流模式，per-thread 默认流不能被静默忽略。

### T08.2 封装并嵌入设备镜像

- 目标/阅读：阅读 R7/R8 的 fatbin wrapper/嵌入逻辑，与 T07 镜像和参数元数据格式对照。
- 练习：设计版本化容器，封装 vxbin、kernel 标识与参数表，保留对 host 注册 ABI 所需 wrapper 的适配。
- 验收：host 对象/程序包含可提取的正确镜像和元数据；错误版本、长度或缺失记录可诊断。
- 交付/排查：容器规格与提取检查；自定义容器不能与 Clang 期望的注册 wrapper 布局混用。

### T08.3 实现镜像与 kernel 注册/注销

- 目标/阅读：阅读 R8 的模块构造/析构、RegisterFatBinary/RegisterFunction 调用和 V6 module 生命周期。
- 练习：实现 host function/stub 标识→设备入口/参数表的映射，处理 C++ 名字、同模块多个 kernel 和注销。
- 验收：两个不同签名 kernel 不混淆，重复注册策略明确，未注册 kernel 有错误，卸载不会破坏在途执行。
- 交付/排查：注册表测试与全局生命周期图；host 函数地址不是可直接交给设备执行的地址。
- 补充用例：命名空间中同 basename 的不同 kernel 不碰撞；注册发生在 main 前、首次使用和退出注销时，不依赖其他全局构造顺序。

### T08.4 接通启动配置与参数打包

- 目标/阅读：阅读 R8 的 launch stub 与配置操作，结合 T06 默认队列和 T07 元数据。
- 练习：由实际 host ABI 取得 grid/block/sharedMem/stream 与 void** args，按元数据复制值并提交 kernel。
- 验收：指针、32/64 位标量、float、零参数及多次启动正确；参数区在异步提交后仍有效，非法启动返回明确错误。
- 交付/排查：参数布局与启动测试；host 局部变量生命周期和 SDK staging 行为必须查清。
- 补充验收：SDK 在 enqueue_launch 复制 blob 不等于 HIP 参数里的所有 buffer 已保活；超限/溢出的 grid/block/shared 请求和 launch 错误能被公开错误 API 观察。

### T08.5 实现一体编译入口

- 目标/阅读：阅读 R7 的 HIP action builder、toolchain 选择和 host 链接流程。
- 练习：连接 host/device 编译、设备链接打包、镜像嵌入、runtime 链接；设计可复现入口并检查 device-only CPU 选项隔离。
- 验收：一个 HIP 输入生成 host 可执行程序，-### 可显示真实 jobs；缺失依赖有正确诊断，普通 host 编译不受影响。
- 交付/排查：driver 集成测试与完整命令。拟定 hipcc-vortex 是用户入口设计，不应掩盖 Clang 缺失的 offload 编排。

### T08.6 验收原生 HIP 最小闭环

- 目标/阅读：对照总览的最终 vecadd 示例和 V7 的 API/计算行为。
- 练习：运行整除/非整除 vecadd、SAXPY、两个不同签名 kernel 连续启动，覆盖反复分配释放与错误返回。
- 验收：用户不手工写 native 参数区/打包命令；LLVM 23 生成设备代码，经原生 runtime 在 SimX 正确执行，O0/O2 结果合格。
- 交付/排查：M3 报告、支持 API/参数/控制流矩阵和复现命令。仍复用的设备库单独列出，现有 chipStar 测试不冒充此结果。
- 补充验收：正式样例检查每次 API、launch 后的错误及同步错误；检查 host/device 目标、元数据/镜像对应和所用优化模式。

## 阶段 T09：shared memory 与 block 同步

前置：T08 通过；理解地址空间、存储作用域、执行屏障与内存顺序。公共入口 V2/V6、Clang CodeGen、R2/R3。当前配置下使用合法且能覆盖多个 warp 的 block。

### T09.1 定义 shared memory ABI

- 目标/阅读：阅读 V2 的 local memory 地址、V6 的 launch local memory 字段与当前硬件容量。
- 练习：定义每 block 的静态/动态区域、对齐、容量、初始化与复用规则，说明 LLVM 地址空间和实际地址的关系。
- 验收：一个 block 内共享、不同 block 间隔离，超过容量有明确处理；不将每线程栈当成 shared memory。
- 交付/排查：存储布局图和 ABI 说明，先用能力查询核对物理限制。

### T09.2 支持静态 __shared__ 对象

- 目标/阅读：阅读 Clang 的 shared 对象发射与 T09.1 布局设计。
- 练习：lower 固定大小的整数/浮点共享数组，统计每 kernel 静态资源，并保留元数据。
- 验收：同 block 线程可访问同一对象，不同 block 的值不串扰；不同对象的偏移/对齐正确。
- 交付/排查：IR/布局/执行测试。跨线程读取的正确性用已实现同步或独立测试协议保证，不依赖偶然调度。

### T09.3 支持动态共享内存

- 目标/阅读：阅读 R8 的 sharedMem 启动参数与 V6 的 local memory 配置。
- 练习：接通 extern __shared__、静态区域后的动态起点和 launch 字节数，支持合法 typed view/对齐。
- 验收：不同动态大小和静态/动态组合正确；总容量检查与每次 launch 参数匹配。
- 交付/排查：参数路径图与边界测试；同名动态共享声明的区域别名规则要写清楚。

### T09.4 实现 __syncthreads 的完整语义

- 目标/阅读：阅读 V2 barrier 包装、R2 的 intrinsic 属性与执行端 barrier 行为。
- 练习：接通 block barrier，审查 compiler memory effects、调度约束与所需 fence/等待机制，明确本阶段保证的可见性范围。
- 验收：多个 warp 写共享数据→同步→互读正确，O2 也不越过 barrier 错误重排；循环中多轮 barrier 正确。
- 交付/排查：同步契约与执行/优化回归。所有参与线程必须满足约定的收敛条件，不要求保证非法分歧 barrier 程序有确定结果。
- 补充用例：除 shared 外，验证 block 内 global 数据写入→barrier→互读；分别审查硬件等待、cache/fence 路径和编译器重排。

### T09.5 运行跨 warp reduction

- 目标/阅读：阅读已经实现的 shared/barrier 路径，并自行画 reduction 各轮读写关系。
- 练习：先整数再浮点，选择合法的多 warp block，覆盖多 block、重复启动和非整除输入规模。
- 验收：结果与 CPU 参考一致，浮点容差预先约定；共享区域没有跨 block/轮次污染。
- 交付/排查：算法依赖图和运行记录，错误时区分算法缺少 barrier 与后端 barrier 语义错误。

### T09.6 运行 tiled SGEMM 并固定资源回归

- 目标/阅读：对照 V7/sgemm 的数学结果与 tiled 算法，检查每个 tile 的加载/同步/计算顺序。
- 练习：例如使用当前可容纳的 4×4 block，覆盖完整 tile 和边缘 tile，加入 shared 容量/布局回归。
- 验收：多种矩阵尺寸在 O0/O2 正确，边缘线程仍按要求参与 block barrier，超限启动有诊断。
- 交付/排查：T09 支持矩阵与样例；以正确性为主，不据 SimX 运行时间宣称硬件加速。

## 阶段 T10：原子、stream/event 与可复现交付

前置：T09 通过；理解 atomicity/memory order、队列顺序与异步对象生命周期。公共入口 V6/V7/R2。原子配置与原默认配置分开构建和记录，避免宿主/设备/模拟器宏不一致。

### T10.1 建立 A 扩展配置

- 目标/阅读：阅读 V7 原子测试的扩展条件及 SDK configure/configuration 流程。
- 练习：建立单独 A-enabled SimX/runtime/device 配置，核对编译 ISA 与设备能力，保留原无 A 基线。
- 验收：能力查询和编译选项一致；默认无 A 的配置不会误宣称支持原子路径。
- 交付/排查：配置差异与重建命令。变更硬件配置后按 SDK 流程重新配置相关组件，不只给 Clang 加一个选项。

### T10.2 支持 32 位整数 atomicAdd

- 目标/阅读：阅读 R2/本地 RISC-V atomic lowering、V7 histogram/atomicreduce 源码或固定版本参考。
- 练习：先定义目标 HIP atomicAdd 的作用域/顺序契约，实现需要的设备 builtin/lowering，检查 AMO 及必要顺序机制。
- 验收：高竞争计数和 histogram 与 CPU 参考一致，O0/O2 重复通过；不支持的宽度/类型有明确限制。
- 交付/排查：原子契约、汇编和执行测试；普通 load+store 在单次测试正确也不能作为原子实现。
- 补充验收：把原子性、内存顺序和作用域分开；只对所承诺的顺序增加可区分用例，不把 atomicAdd 等同于全设备同步。

### T10.3 支持 stream 与队列内顺序

- 目标/阅读：阅读 V6 queue 接口和此前默认 stream 行为。
- 练习：添加显式 stream 创建/销毁/同步与队列内 FIFO，定义本阶段支持的默认 stream 交互规则及不支持的 flag。
- 验收：单 stream 拷贝→kernel→拷贝有序，不同 stream 资源不混淆；销毁/同步满足规定生命周期。
- 交付/排查：stream 语义表与顺序测试。SDK queue 能力不自动覆盖 HIP legacy/per-thread default stream 的所有规则。

### T10.4 支持 event 与跨 stream 依赖

- 目标/阅读：阅读 V6 event、队列 signal/wait 与完成状态查询。
- 练习：实现 event 创建、record、query、synchronize、stream wait 与销毁的选定子集，定义未记录 event 的行为。
- 验收：两个 stream 通过 event 构成依赖后结果正确；未完成/已完成状态和重复记录按约定处理。
- 交付/排查：依赖图、API 矩阵与测试；event 句柄、一次记录状态和底层计数值不能混为一个概念。

### T10.5 审查异步拷贝和资源生命周期

- 目标/阅读：审查 V6 对异步 host buffer、event、module、参数 staging 的要求。
- 练习：明确 memcpyAsync 对普通/固定页 host 内存的支持子集；审查在途任务中的参数、buffer、module、stream 销毁行为。
- 验收：受支持路径在依赖完成前对象有效，阻塞回退如实记录；成功、失败与退出路径无明显资源遗漏。
- 交付/排查：生命周期测试与限制清单。正确顺序不要求模拟器真正并发，不能把串行模拟结果当并发性能证据。

### T10.6 发布可复现的教学原型

- 目标/阅读：逐项对照总览“最后可以做成什么样子”和全部任务证据。
- 练习：整理 LLVM patch、独立 runtime、编译入口、样例、配置清单、支持矩阵和安装/复现说明；从新构建目录重跑必要验证。
- 验收：他人能按文档构建并运行 native/HIP vecadd、SAXPY、分歧/循环、reduction、SGEMM、A-enabled histogram 与 event 依赖例子；每例明确配置、预期和编译来源。
- 交付/排查：最终报告与发布候选目录；不能把尚未执行的测试列为通过。仍复用的参考设备库逐项列出，重编迁移可另开专题。

## 进度登记与阶段评审

每一阶段建立一个 evidence 目录，按任务 ID 保存记录，例如 `/home/kaikai/vortex-word/artifacts/tutorial/t02/T02.3.md`。代码保存在相应源码仓库，日志/临时对象不混入源码提交。任务 ID 表示学习和验收范围，不强制对应固定数量的 commits。

阶段出口只在前面六项都达到约定条件后标记通过。若缩小实现范围，先修改支持矩阵与验收，保留原因；不能靠删掉失败用例直接把阶段标为通过。新增失败先变成最小回归用例，修复后只重跑相关层和必要回归。

主线最终产物与目标 HIP 示例见 [总览第 6 节](plan.md#6-最后可以做成什么样子)。完成 66 项代表本教程规定的子集与验收完成；完整 HIP、真实硬件验证、性能优化和大型应用迁移是后续独立工作。
