# LLVM 23 原生 HIP/Vortex 教程与任务路线

设计基线：2026-11-17；更新日期：2026-11-18（Asia/Shanghai）。本文是供你逐步实现的教程与任务设计，不表示相关后端已经完成。

本教程分为 **11 个阶段、66 个主线小任务**，编号为 T00.1～T10.6。阶段是能力里程碑，小任务才是每次学习和提交的单位。完整任务卡见 [66 个小任务](tasks.md)，每张卡都有目标、阅读入口、实施练习、验收和交付要求。第一阶段的操作命令另见 [TASK-000](getting-started.md)。

本次修订将 **RISC-V Target 内的 `-mcpu=vortex` CPU/subtarget** 明确为主线入口。新增 T01 的 6 项 CPU 接入任务，原 T01～T09 顺延为 T02～T10。具体职责、选项组合规则与源码分工以 [架构方案](architecture.md) 为准。

维护位置固定为本仓库 `docs/codex/llvm-hip-vortex/`，入口见 [README](README.md)。后续架构、任务与命令直接更新本目录现有文件，通过 Git 提交记录版本，不另建日期/版本副本。

## 1. 最终做成什么

采用 LLVM 23.1.4 的 RISCV Target，在其中注册初版 RV64 的 `vortex` CPU，提供 `-mcpu=vortex` 默认配置及 `xvortex` 指令扩展；在这个 subtarget 上实现 SIMT 和 kernel ABI。Clang 复用 HIP 语法能力，新增 Vortex 设备语义与 host/device 工具链，独立原生 HIP runtime 对接 Vortex SDK。最终让你构建的 LLVM 23 编译受支持的 HIP 程序，并在 SimX 上验证结果。

```text
同一个 HIP 源文件
  ├─ host 编译 → x86 对象：kernel 注册、启动 stub、HIP API 调用
  └─ device 编译（RISC-V，-mcpu=vortex）→ RISC-V LLVM IR
                    → Vortex SIMT lowering + RISC-V/Vortex 指令选择
                    → device ELF → .vxbin + 参数元数据
  → 封装/嵌入设备镜像 → 链接 host 与 libhip_vortex
  → Vortex module / queue / buffer API → SimX → CPU 参考结果校验
```

第一版完成以下子集：RV64、单设备、默认 stream、单源文件、多次 kernel 启动、`int`/`float` 运算、设备指针与固定宽度标量参数、`__global__`、`threadIdx`/`blockIdx`/`blockDim`/`gridDim`、`<<<>>>`、分配/拷贝/同步/释放。这里的完成标准是端到端正确执行，不是“能生成汇编”。

共享内存、barrier、原子、多个 stream 按后续任务增加。RV32、设备动态并行、跨文件 device linking、完整数学库、纹理、WMMA、PyTorch/ROCm 库兼容不作为第一版目标。先选一种优化流水线和指令选择路径验证，不同时承诺 SelectionDAG 与 GlobalISel。

## 2. 固定基线，防止学习对象不断变化

以下是 2026-11-17 已记录的 WSL 环境快照；本次文档整理未重新执行完整 LLVM 构建或 SimX smoke。开始学习时按 [起步任务](getting-started.md) 核对实际状态。构建命令见 [build.md](build.md)，产物与执行接口见 [compiler-sim-contract.md](compiler-sim-contract.md)。

| 对象 | 当前基线 | 教程中的作用 |
|---|---|---|
| 新编译器 | `/home/kaikai/vortex-word/llvm-project`，`dev/vortex`，`llvmorg-23.1.4`，`7a941dfb2877a0b8cf30323fefa85ad019e0b0f5` | 你实现的主体 |
| Vortex SDK/SimX | `/home/kaikai/vortex-word/vortex`，`26d2bc4b5409a35a111e8316ac3a87d07b15fc80` | 固定执行端、ABI 与测试输入 |
| 官方参考编译器 | `/home/kaikai/vortex-word/tools/llvm-vortex`，Clang 20.1.8，`f44a6bb2af4c62847585305bbdc760fbe0e3645f` | 对照 IR、汇编和执行结果 |
| 新编译器构建目录 | `/home/kaikai/vortex-word/build/llvm` | 已配置；本次检查尚无 clang/llvm-mc 成品 |
| 参考 SDK 构建目录 | `/home/kaikai/vortex-word/vortex/build64` | 已有 SimX、runtime 与 smoke 基线 |

当前 `build.sh` 配置 AMDGPU、RISCV、NVPTX、X86。它们用于阅读和对照；Vortex 开发主体在 RISCV 与 Clang HIP 接入处，不需要新建 `llvm/lib/Target/Vortex`。构建这些后端也不等于安装了 AMD/NVIDIA 的 HIP runtime。

当前参考模拟器配置为 RV64、1 cluster、1 core、每 core 4 warp、每 warp 4 thread，当前最大 block 为 16 thread；local memory 开启，A/C 扩展关闭。以实际能力查询和构建配置为准，不能照抄 CUDA 示例的 256-thread block。

## 3. 官方代码告诉我们什么

以下链接固定到参考提交；文中“建议实现”是本教程的设计，不表示官方已有该功能。LLVM 文件相对路径均以 `/home/kaikai/vortex-word/llvm-project` 为根；SDK 文件以 `/home/kaikai/vortex-word/vortex` 为根。

### 3.1 现有 HIP 测试通过，不代表原生 HIP 编译链存在

官方 [HIP 设计说明](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/docs/designs/hip_on_vortex_chipstar.md)明确区分了现有 chipStar/SPIR-V/PoCL 路径与尚未实现的原生 HIPVortex 方向。

阅读 SDK 的 `tests/hip/common.mk`、`tests/hip/vecadd`，追踪 `hipcc`、SPIR-V 产物、PoCL 与 SimX 的关系。现有测试适合当行为参考和后续复用输入，不能当成已经实现的原生 Clang HIPVortex 后端。本教程也不依赖该文档描述的可选 MLIR 方向。

### 3.2 Vortex 指令扩展是第一层，不是整个 GPU 后端

指令集的标准扩展配置、自定义操作、CSR 和已核对编码集中维护在 [架构方案第 6 节](architecture.md#vortex-isa)。先区分设备能力、SDK 包装与 LLVM 助记符/intrinsic 覆盖，再阅读下面的迁移入口。

[参考 RISCVInstrInfoVX.td](https://github.com/vortexgpgpu/llvm/blob/f44a6bb2af4c62847585305bbdc760fbe0e3645f/llvm/lib/Target/RISCV/RISCVInstrInfoVX.td) 给出 `VX_TMC`、`VX_SPLIT`、`VX_JOIN`、`VX_BAR` 等指令的 TableGen 定义。例如它们使用 CUSTOM0，opcode 为 `0x0b`，funct3 分别为 0、2、3、4。

将这份定义与 SDK `sim/simx/decode.cpp`、`hw/rtl/core/VX_decode.sv` 交叉核对：编译器输出的位字段必须被执行端按同一语义解释。MC 能编码/反汇编，只证明工具认识指令；不会自动把 C++ 的分歧 `if` 变成正确的 SIMT 控制流。新增定义还必须有 feature gating 与关闭 feature 的反例，不能只复制正例。

### 3.3 SIMT 的核心在 uniformity 与分歧控制流

[VortexBranchDivergence.cpp](https://github.com/vortexgpgpu/llvm/blob/f44a6bb2af4c62847585305bbdc760fbe0e3645f/llvm/lib/Target/RISCV/VortexBranchDivergence.cpp)使用 UniformityAnalysis、LoopInfo、RegionInfo、PostDominator 等分析；[RISCVTargetMachine.cpp](https://github.com/vortexgpgpu/llvm/blob/f44a6bb2af4c62847585305bbdc760fbe0e3645f/llvm/lib/Target/RISCV/RISCVTargetMachine.cpp)负责把 Vortex 相关处理放进编译流水线。

学习时先找“分歧来源 → 分支分类 → CFG 处理 → split/join 插入 → 最终指令”的链条。迁移到 LLVM 23 要逐项确认分析接口和 pass 接入时机，不直接复制旧版本的注册方式。`threadIdx` 是典型分歧来源，block 维度等在相应执行范围内一致；“地址一致”不能直接推出“加载值一致”，每线程私有存储尤其要审查。对未知情况先保守处理，再做 uniform 优化。

### 3.4 kernel 入口有真实 ABI，别把函数地址直接当整个程序入口

SDK [vx_spawn2.h](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/sw/kernel/include/vx_spawn2.h) 将 `__kernel` 标为 `vortex.kernel`，并使用 `used`/`retain`；`__UNIFORM__` 在 `vx_intrinsics.h` 中是 `vortex.uniform` annotation。新编译器能接受 annotate 语法，不表示已经实现了这些 annotation 的 Vortex 语义。

[RISCVVortexKEntry.cpp](https://github.com/vortexgpgpu/llvm/blob/f44a6bb2af4c62847585305bbdc760fbe0e3645f/llvm/lib/Target/RISCV/RISCVVortexKEntry.cpp) 扫描 kernel annotation，生成 `__vx_kentry_<函数名>` alias，供打包器建立入口表。保留属性避免仅由设备调度器引用的函数被链接垃圾回收。

SDK `sw/kernel/src/vx_start.S` 的 `__vx_cta_entry` 建立执行状态，从 CTA_ENTRY CSR 取得 kernel 地址，从 MSCRATCH CSR 取得参数区指针并放入 `a0`，然后间接调用 kernel。`sw/kernel/scripts/vxbin.py` 枚举入口 alias，并生成带符号表的 `.vxbin`。因此 HIP 的多形参 kernel 需要一个与这个 ABI 匹配的 wrapper/入口和参数布局，添加 alias 本身不能完成适配。

### 3.5 HIP frontend、driver、runtime 各自都有工作

LLVM 23 的 [Driver.cpp](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.4/clang/lib/Driver/Driver.cpp) 中，`getOffloadingDeviceToolChain` 已有 AMDGPU/HIPSPV 路径。这里是设计 Vortex toolchain 的阅读入口；不是把 AMD 目标 triple 改成 RISC-V 就能得到合法的 HIP 设备 ABI。

[CGCUDANV.cpp](https://github.com/llvm/llvm-project/blob/llvmorg-23.1.4/clang/lib/CodeGen/CGCUDANV.cpp) 可用于追踪 HIP host stub、镜像注册和 kernel launch。先用 `-emit-llvm` 查看实际生成的 host IR，再确定要提供的注册与启动符号；其中涉及 `__hipRegisterFatBinary`、`__hipRegisterFunction`、`hipLaunchKernel` 等。头文件声明、生成的调用约定和 runtime 实现必须一致，不能只实现几个公开 HIP API。

SDK [vortex2.h](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/sw/runtime/include/vortex2.h) 提供 buffer、module、queue、event 接口。原生 runtime 应围绕当前 API 设计：`vx_buffer_create`、`vx_buffer_address`、`vx_module_load_file`、`vx_module_get_kernel`、`vx_enqueue_launch`、队列读写和 event 等待。不要沿用旧文档里不同版本的内存接口名。

建议把 runtime 放在 LLVM 仓库外，例如 `/home/kaikai/vortex-word/hip-vortex`；LLVM 仓库维护编译器修改和 lit 测试。这里只约定结构，尚未创建 runtime 项目。

## 4. 十一个阶段与依赖

按验收结果推进，每阶段保留命令、输入、IR/汇编或执行证据。以下各阶段的测试都是待实现后的验收要求，不是当前环境已经全部通过的声明。

| 阶段 | 新增能力 | 主要代码入口 | 必须达到的验收结果 |
|---|---|---|---|
| T00 | 编译基线与 ABI 理解 | build.sh、demo、vx_start.S、vortex2.h | LLVM 23 标准 RV64 编译成功；参考 SimX smoke 通过；提交 ABI 分析记录 |
| T01 | Vortex CPU/subtarget 与选项契约 | RISCVProcessors.td、TargetParser、RISC-V driver | -mcpu=vortex 可识别，默认 ISA/ABI 正确，显式 -march 与错误目标组合可解释 |
| T02 | Vortex MC 最小切片 | RISCVFeatures.td、RISCVInstrInfo.td、新增扩展 td | tmc/split/join/bar 编码、反汇编、feature 关闭与非法操作数测试 |
| T03 | IR intrinsic、CSR 与 annotation 语义 | IntrinsicsRISCV.td、RISCV lowering/TTI、Clang RISCV target | IR 到 Vortex 指令；分歧来源识别；普通 RISC-V 无行为变化 |
| T04 | 原生 kernel ABI 与镜像 | kernel-entry pass、startup、link64.ld、vxbin.py | 新 LLVM 编译的无分歧 native vecadd/demo 经 ELF→vxbin→SimX 结果正确 |
| T05 | SIMT 分歧与重新汇合 | 官方 divergence pass 与 LLVM 23 pipeline | 混合 lane 的 if/else、嵌套分支、循环及尾部边界在 O0/O2 正确 |
| T06 | 最小原生 HIP runtime 底座 | 独立 runtime + vortex2.h | 不经过 HIP frontend，用 module API 加载 kernel，分配/拷贝/启动/同步/释放正确 |
| T07 | HIP device-only 编译 | Clang HIP target/ABI、builtins、拟新增 HIPVortex toolchain | 真正的 __global__ 多参数 kernel 编译为可执行镜像，由手写 host 启动正确 |
| T08 | HIP host/device 一体编译 | Driver actions、host CodeGen、fatbin、注册、launch stub | 普通 HIP vecadd 的 <<<>>> 全链路正确，完成第一版 HIP 子集 |
| T09 | shared memory 与 barrier | 地址空间/对象布局、local memory、barrier lowering/runtime | 跨 warp reduction 与 tiled sgemm 正确，静态/动态共享内存均有测试 |
| T10 | 原子与 stream/event 扩展 | A 扩展、memory ordering、队列/event 映射 | 开启匹配硬件配置后 atomicAdd 正确；多 stream 顺序与事件依赖正确 |

主线依赖为 `T00 → T01 → T02 → T03 → T04 → T05 → T06 → T07 → T08 → T09 → T10`。先建立 CPU 与 ISA 选择契约，再实现指令、SIMT 和 HIP。各阶段内部依编号推进；如果测试暴露前一阶段缺失语义，回到对应小任务修复并重验。T06 的 runtime 设计可以提前阅读，但以已通过执行验收的镜像作为实现输入。

每阶段恰好有 6 个主线任务，详见 [任务卡目录](tasks.md)。T00 是学习与基线任务，不强制产生后端 patch；T02 以后按实际修改提交，测试需要检验语义或错误行为。

### T00：第一份任务，先建立你能解释的基线

独立任务书见 [TASK-000-baseline.md](getting-started.md)。这一步先不修改后端。现有 `build.sh` 只验证了配置，先完整构建，再复跑参考 smoke，画清楚一个 native demo 的参数和入口链路。

### T01：CPU/subtarget 接入，作为首个编译器阶段

先定义 `vortex` 的 RV64 CPU 配置、默认 ISA/ABI、扩展开关和保守调度策略，再接通 Clang 与 LLVM 工具。ISA 能力使用 `xvortex` 等 feature 描述，指令和 pass 查询实际 feature；kernel annotation 负责入口语义，CPU 名不把普通函数自动变成 kernel。

按 [任务卡 T01.1～T01.6](tasks.md) 完成 CPU 契约、extension/parser、ProcessorModel、Clang driver、LLVM 工具和选择矩阵测试。首个代码提交聚焦 feature/parser 或 CPU 注册中的一个最小闭环，不同时加入指令和 HIP runtime。

本阶段明确验证 `-mcpu=vortex`、显式 `-march`、错误 RV32 目标与普通 RISC-V 的组合。Vortex kernel/HIP device 编译若选项删除必需能力，应有明确诊断；普通 RISC-V 编译保留上游 ISA 选择规则。通过后仅表示工具能正确选择 Vortex subtarget，尚未支持其特殊指令。

### T02：特殊指令的 MC 支持

只做四条 MC 指令，不在这个提交里移植分歧 pass 或添加 HIP runtime。

1. 复用 T01 已建立的 `xvortex` 开关，为扩展指令文件接入 feature 谓词。
2. 对照官方 td 和 SimX/RTL，明确每条指令的 opcode、funct3、funct7、固定 rd/rs2、输入输出寄存器。
3. 用 `llvm-mc -triple=riscv64 -mattr=+xvortex -show-encoding` 验证编码，并用生成的对象配合 `llvm-objdump` 验证反汇编。
4. 在 `llvm/test/MC/RISCV` 添加 lit/FileCheck 测试：四条正例、`-xvortex` 拒绝、错误操作数。检查普通 RISC-V 编码不变。
5. 同时验证 CPU 默认通路和显式 feature 通路；T01 已处理 CPU/ISA 选择，本阶段检验它们确实约束新增指令。T03 再验证这些选择如何传递到 IR 和 intrinsic lowering。

交付：一个聚焦的代码 diff、一张编码核对表、测试命令与结果。通过后只能称“MC 切片完成”，不能称“Vortex kernel 已可运行”。

### T03：从指令定义走到 LLVM IR 语义

先支持启动/线程标识所需的最小集合，再按 T05 需要补全控制指令，包括可能用到的 split_n、pred、伪指令等。阅读参考 `llvm/include/llvm/IR/IntrinsicsRISCV.td`、RISCV 指令选择、TTI 的分歧来源与 annotation 处理。

为每个 intrinsic 写出：参数/返回类型、RV64 宽度、是否有副作用、是否访问内存、是否 convergent、哪些优化可移动或合并它。屏障和 lane 控制不能随意标成纯函数。测试优化前后 IR 与最终汇编，不只测试 O0。验证 T01 的 `-mcpu`/`-march`/feature 选择贯穿 Clang→IR→llc；确保没有必需 feature 的普通 RISC-V 函数不会误入 Vortex pass。

### T04：先跑通 native kernel，暂不增加 HIP 变量

采用参考 device runtime、startup、链接脚本、LLD 和打包器，只替换 kernel 编译与需要迁移的 compiler pass。记录哪些组件仍来自参考工具链，后面再替换。首个 kernel 使用现有 demo 的单指针参数 ABI，工作量覆盖完整 block，避免引入 lane 间不同路径。

检查 ELF 中入口、保留属性、栈/启动流程和 `.vxbin` 入口表，再检查 CPU 对照结果。现成 demo host 的 `kernel_arg_t` 是 40 字节，字段偏移为 0、4、8、16、24、32；它不是任意 HIP kernel 的通用 host。

已有 `scripts/run-kernel.sh demo 文件` 仅适合参数布局及计算约定与 demo 一致的镜像。`scripts/validate-compiler.sh` 后续可检查新编译器对 demo/sgemm 的接入，但其“通过”仍包含复用参考 runtime/链接器的限定，不能写成全部工具链已迁移。

### T05：正确处理分歧，再打开常见边界判断

将官方大 pass 拆成可理解的小任务：分析、CFG 变换、mask 保存/恢复、汇合点、循环退出。先画每个测试的 lane 路径，再看生成的 split/join。不要通过修改 SimX 语义来掩盖编译错误。

最低用例：奇偶线程 if/else、两层嵌套分支、不同线程循环次数、break/continue、分支后的共同写回，以及 `N=37` 的 vecadd 尾部保护。所有会分歧的路径必须在同一 warp 内真的出现；全体线程走同一路径不构成有效分歧测试。O0/O2 分开验收，整数严格比较，浮点使用预先约定容差，输出加哨兵验证未激活 lane 没有越界写入。

### T06：runtime 先用显式 module launch 验证

此时先不依赖 `<<<>>>` 和自动 fatbin 注册。显式加载 T04/T05 的镜像，用 Vortex buffer/queue/module API 完成执行，逐个建立 HIP 公开 API 的对应行为。

`hipMalloc` 返回的设备地址应关联到 SDK buffer，并支持指针加偏移后的范围查找；不能把设备地址当作可直接解引用的 host 指针。定义清楚零长度、越界、无效句柄、错误码、资源销毁顺序。先支持默认 stream；异步 API 如果暂时采用阻塞实现，要明确其能力边界，不能宣称已支持多队列并发。

### T07：独立打通 HIP device 编译

确定 RISC-V HIP 的 target 选择方式及诊断，接入 Clang HIP 语义、设备 builtins 与可用头文件。先用 device-only 命令，保证没有 SPIR-V/PoCL 中间层，检查真实 RISC-V IR、目标 DataLayout 和 device ELF。

建议生成一个接收参数区指针的 Vortex 入口 wrapper，内部按固定布局解包后调用 HIP kernel 实现。参数元数据至少包含 kernel 标识、入口、参数大小/对齐/偏移、参数区总大小、共享内存需求。host 的 `void** args` 不包含这些布局信息，不能直接 memcpy 指针数组当成参数区。RV64 host/device 指针宽度相同也不意味着所有类型布局自动相同。

第一批参数限定为设备指针、int32/uint32、int64/uint64、float；暂不支持任意类对象/按值复杂结构。覆盖混合参数顺序、对齐、两种 kernel 签名、重复启动。检查 calling convention、address space、kernel 保留和 host/device 函数可见性。此阶段用手写 module host 运行 HIP device 产物。

### T08：连接 HIP host stub 与设备镜像

先用 `-###` 看 Clang jobs，再分别检查 host/device IR，最后执行完整命令。阅读 HIPSPV 的构建编排和 LLVM 23 AMDGPU 路径，但 Vortex 的链接、打包和运行时各自实现。

从一个 kernel/一个翻译单元开始：设备镜像封装 → host 注册 → host function 到设备入口的映射 → 启动配置 → 参数打包 → queue launch。根据生成 IR 核对注册、注销、配置压栈/出栈和 launch 所需符号，不预设仅实现 `hipLaunchKernel` 就足够。随后加入两个 kernel、不同签名、反复启动与释放测试。

第一版终点：用户源码包含 `hipMalloc`、H2D 拷贝、`vecadd<<<grid,block>>>`、`hipDeviceSynchronize`、D2H 拷贝、CPU 校验、`hipFree`，由新 LLVM 编译并在 SimX 上运行。测试一个整除规模和一个带尾部判断规模，保留设备产物来源，防止误用参考编译器生成的旧镜像。

### T09–T10：逐步增加 GPU 常用能力

共享内存要先确定静态对象与动态区域如何布局、每 block 是否独立、对齐和容量如何检查。`__syncthreads()` 既要有执行汇合，也要保证约定范围的内存可见性与编译器重排限制；仅把函数名替换为一条 barrier 指令不够。当前配置下使用不超过 16-thread 的 block，并选择能跨多个 warp 的用例。

原子任务先更换为匹配 A 扩展的 simulator/runtime/device 编译配置，再测试 atomicAdd 与竞争正确性；不能只在编译器启用 A 而模拟器仍关闭。stream/event 后续检查队列内顺序、跨队列依赖、异步 host 缓冲区生命周期和销毁等待。SDK 支持队列不表示已经完整满足 HIP 所有 stream 语义。

## 5. 教学与提交方式

每个任务交付四件事：设计说明、最小代码修改、能暴露错误的测试、执行证据。MC/IR/CodeGen 用 LLVM lit/FileCheck，执行语义用独立 SimX 测试。编译成功、镜像合法、执行正确分别记录。

建议每次只推进一个任务：你先给出方案或 patch，我围绕官方代码解释其作用、检查语义与测试漏洞，再进入下一步。错误优先按 host/runtime → 参数与入口 ABI → IR/SIMT → ISA 编码 → simulator 配置定位；具体排查顺序按证据调整，不把所有失败归到指令选择。

每个小任务的记录可从 [证据模板](evidence-template.md) 复制。任务状态只有“待做、进行中、待评审、通过、受阻”；所有任务初始为待做，现有参考环境通过记录不自动算作新后端任务完成。记录里注明新编译器、参考编译器、预编译库各自负责的部分。

## 6. 最后可以做成什么样子

### 6.1 三个可运行里程碑

| 完成位置 | 你做出的东西 | 可以演示的程序 | 结论边界 |
|---|---|---|---|
| T01.6 | RISC-V 内可选择的 Vortex CPU/subtarget | 用 -mcpu=vortex 编译不含特殊指令的 RV64 标量函数 | 选项与目标选择完成，尚未证明特殊指令或 kernel 可执行 |
| T04.6 | LLVM 23 上的 Vortex 指令与 native kernel 基本链路 | 使用既有 ABI 的无 lane 分歧 vecadd/demo，经 ELF、vxbin 在 SimX 执行 | 已有原生设备编译能力，尚无 HIP 源码支持 |
| T05.6 | 能处理已测试的 SIMT 分支与循环的后端 | 带边界保护的 vecadd、奇偶分支、每线程不同迭代次数的循环 | 对规定控制流集合通过 O0/O2 验证，复杂未覆盖 CFG 仍需诊断或补测试 |
| T08.6 | 原生 HIP 最小编译链和 runtime | 普通 HIP vecadd、SAXPY、两个不同签名 kernel 连续启动 | 单设备、单翻译单元、默认 stream、受限参数类型的 HIP 子集 |

T09 完成后增加静态/动态 shared memory、block barrier、跨 warp reduction 和小规模 tiled SGEMM。T10 完成后，在匹配配置下增加 32 位整数 atomicAdd、histogram，以及明确支持语义的 stream/event 链式执行。异步顺序正确并不代表 SimX 一定能展示硬件并发或加速。

### 6.2 用户最终怎样写程序

下面是 T08 的目标输入示意，属于将来要验收的例子。本次文档更新没有创建可用 HIP runtime；最终头文件与错误处理支持需由相应任务实现。

```cpp
#include <hip/hip_runtime.h>
#include <cstdio>

__global__ void vecadd(const float* a, const float* b, float* c, int n) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i < n)
    c[i] = a[i] + b[i];
}

int main() {
  constexpr int n = 37;
  float a[n], b[n], c[n];
  for (int i = 0; i < n; ++i) {
    a[i] = float(i);
    b[i] = float(2 * i);
  }
  float *da = nullptr, *db = nullptr, *dc = nullptr;
  // 示例省略逐次错误检查；正式验收用例必须检查所有 API 返回值。
  hipMalloc(reinterpret_cast<void**>(&da), sizeof(a));
  hipMalloc(reinterpret_cast<void**>(&db), sizeof(b));
  hipMalloc(reinterpret_cast<void**>(&dc), sizeof(c));
  hipMemcpy(da, a, sizeof(a), hipMemcpyHostToDevice);
  hipMemcpy(db, b, sizeof(b), hipMemcpyHostToDevice);
  constexpr int block = 8; // 符合当前配置；正式运行先查询设备限制。
  vecadd<<<(n + block - 1) / block, block>>>(da, db, dc, n);
  hipDeviceSynchronize();
  hipMemcpy(c, dc, sizeof(c), hipMemcpyDeviceToHost);
  bool ok = true;
  for (int i = 0; i < n; ++i)
    ok = ok && (c[i] == a[i] + b[i]);
  hipFree(da);
  hipFree(db);
  hipFree(dc);
  std::puts(ok ? "PASS" : "FAIL");
  return ok ? 0 : 1;
}
```

目标是用户写标准 HIP 子集源码，不再手动编写 `kernel_arg_t`、入口 alias、`.vxbin` 打包命令或 Vortex host launch。编译链自动完成这些步骤，runtime 在配置好的 SimX 环境执行。

拟定用户界面可以是 `hipcc-vortex vecadd.hip -o vecadd`，随后运行 `./vecadd`；这里的 `hipcc-vortex` 是 T08/T10 中待设计的入口脚本名称，不是当前已有命令。底层 Clang 应能通过 `-###` 显示真实 host/device jobs，方便你调试，而不是把工作全部隐藏在脚本里。

### 6.3 最终仓库应交付什么

1. **LLVM 23 分支**：`-mcpu=vortex` CPU/subtarget、`xvortex` ISA 扩展、SIMT pass、kernel ABI、Clang HIP 接入，以及分层 lit 测试。
2. **独立 hip-vortex runtime 项目**：公开子集头文件、host runtime、设备支持头/库、参数与镜像格式说明、构建和安装规则。
3. **可运行示例与测试集**：vecadd、SAXPY、分歧/循环、reduction、SGEMM、histogram、stream/event 依赖；标注各自要求的扩展与配置。
4. **工具与说明**：编译入口、镜像检查、SimX 运行入口、版本清单、支持矩阵、已知限制、从干净目录复现的命令。
5. **验证报告**：区分 LLVM 23 编译对象与仍复用的参考库，报告 O0/O2、错误用例、配置一致性与结果。主线先允许复用已固定的设备库；只有实际重编并通过测试的库才能标记为 LLVM 23 构建。

完成后，你拥有的是一套可教学、可调试、可扩展的原生 HIP/Vortex 编译系统原型。真实硬件速度、完整 HIP 兼容或大型应用可用性，需要独立验证，不能由 SimX 样例通过直接推出。

### 6.4 主线结束后的专题

以下不计入 66 个主线任务，可按实际需求继续拆解：设备数学库与更多类型；复杂 C++/按值结构体 ABI；跨翻译单元 device linking；常量/全局对象；warp/subgroup 操作；RV32；真实硬件部署；性能优化与大型 HIP 应用移植。每个专题都应先定义支持子集，再增加源码、负例和执行测试。
