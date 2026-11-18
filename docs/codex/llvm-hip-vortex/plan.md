# LLVM 23 原生 HIP/Vortex 教程与任务路线

设计基线：2026-11-17；更新日期：2026-11-18（Asia/Shanghai）。本文是供你逐步实现的教程与任务设计，不表示相关后端已经完成。

本教程改为 **从 HIP 源程序出发的 10 课学习主线**，先理解语法、AST、语义检查和 IR，再按实际需要引入 Vortex CPU、指令、ABI、SIMT 与 runtime。第 1 课的可执行练习见 [getting-started.md](getting-started.md)。

原有 **11 个工程能力分组、66 项任务**（T00.1～T10.6）保留为 [验收账本](tasks.md)，不再作为从头顺序阅读的课程。已有 ID、进度和证据保持不变；课程号 L01～L10 只组织教学，不新增一套互相冲突的任务状态。技术结构仍采用 RISC-V 内的 mcpu=vortex，详见 [架构方案](architecture.md)。

维护位置固定为本仓库 `docs/codex/llvm-hip-vortex/`，入口见 [README](README.md)。后续架构、任务与命令直接更新本目录现有文件，通过 Git 提交记录版本，不另建日期/版本副本。

<a id="tutorial-route"></a>

## 0. 从一个 HIP 程序出发的十课教程

### 0.1 教学方式

以前的目录适合工程验收，但把 CPU/指令定义放在学习起点，太晚才能看见 HIP 程序本身。本次保留技术设计，改用一个不断升级的小程序串起各层：`store42 → 按线程写索引 → 整块 vecadd → 带边界的 vecadd → 标准 HIP 启动 → reduction`。

“从语法开始”是先理解并复用 Clang 已有能力。HIP 头文件通常把 __global__/__device__/__host__ 展开成 Clang 属性；<<<>>> 的解析和 host/device 语义检查也已有实现。先观察 AST/Sema，找到缺失的 Vortex 连接点，再修改编译器，不从自写 HIP Parser 开始。

每课采用固定结构：本课问题 → 最小输入 → 讲解已有机制 → 运行命令并观察产物 → 自己完成一个小改动 → 正例/反例验收 → 下一课。源码只读本课需要的少数入口，ABI/性能/完整支持矩阵按用到的层次展开。

第一至三课可以用已安装参考 Clang 做观察实验。修改和验收 LLVM 23 功能前，必须构建新编译器并重跑相同实验；参考工具的结果不会自动成为新编译器的通过记录。

### 0.2 课程目录

| 课号 | 本课问题与程序变化 | 看见/交付什么 | 关联工程任务（按子项使用） |
|---|---|---|---|
| L01 | Clang 怎样认识 __global__？写出 store42 | 预处理与 AST，理解宏和属性 | T00.1；T07.2 的观察前置 |
| L02 | 谁可以调用谁？<<<>>> 是什么？ | host/device 反例、CUDAKernelCallExpr | T07.2、T08.1 的观察前置 |
| L03 | 设备函数怎样变成 RISC-V IR？ | 单线程 store42 的 IR 与缺失信息表 | T00.3、T03.5、T07.3 的前置 |
| L04 | 哪一小段代码需要为 Vortex 增加？ | 新 LLVM 中 kernel 识别、设备配置与 driver 的最小切片 | T03.5、T07.1/T07.2；需要时引入 T01 |
| L05 | 怎样让一个线程真的写回 42？ | 真实 ELF/vxbin、启动与参数桥接、SimX 输出 | T04 子项、T06 的 SDK 使用基础 |
| L06 | threadIdx 从哪里来？扩为整块 vecadd | CSR/builtin、指令链路与多线程结果 | T01/T02/T03 子项、T07.3 |
| L07 | 加上 if(i<n) 为什么需要 SIMT？ | 分歧/汇合、循环、晚期分支与 N=37 结果 | T05；T02/T03 的必要补全 |
| L08 | 如何把手工 host 变成普通 HIP 程序？ | API、参数自动打包、注册、<<<>>> 全链路 | T06/T07 剩余项、T08 |
| L09 | 多个线程如何协作？做 reduction | shared、block barrier，再到 tiled SGEMM | T09 |
| L10 | 怎样扩展并交付？ | 选定的原子/stream/event、复现和支持矩阵 | T10；未覆盖工程任务回填 |

课程表列的是学习关联，不表示一节课就完成整组任务。允许先做隔离实验和局部实现；声称某个工程阶段完整通过时，仍需满足其全部验收条件。

### L01：认识现有 HIP 语法能力

使用 [第 1 课练习](getting-started.md#lesson-1) 的两个函数：device helper `twice` 和 kernel `store42`。先不引入 threadIdx、动态分配、特殊指令或 SimX。

自己完成：查看 __global__ 宏展开，定位 AST 中的 CUDAGlobalAttr/CUDADeviceAttr，再增加一个 __host__ 函数和一个未标记函数，比较其语义。AST 使用 CUDA 前缀是共享实现的命名，不表示输入被当成 NVIDIA 程序。

本课终点：能解释“属性已被识别”和“设备程序已可运行”的区别。第一课不要求完成 LLVM 全量构建和所有硬件配置分析。

### L02：语义检查与 kernel 调用表达式

先用最小反例观察 host 直接调用 device 函数为何被拒绝。可复用第一课的宏，另外写：

```cpp
__device__ int device_only() { return 7; }
int main() { return device_only(); }
```

用第一课的 HIP host-only 语法检查命令运行，预期失败；记录错误位置和说明，不只记录非零返回值。反方向的 device→host 调用要在设备语义检查中观察，不能假定 host-only 检查已覆盖两个方向。

随后观察 <<<>>>。下面是供 **AST 实验** 使用的完整最小输入；函数声明只满足本实验的查找与类型检查，不是 runtime 实现或最终公开 ABI。

```cpp
#define __global__ __attribute__((global))
struct dim3 {
  unsigned x, y, z;
  constexpr dim3(unsigned x=1, unsigned y=1, unsigned z=1)
      : x(x), y(y), z(z) {}
};
using hipStream_t = void*;
extern "C" int __hipPushCallConfiguration(
    dim3, dim3, __SIZE_TYPE__=0, hipStream_t=nullptr);
__global__ void store42(int* out) { *out = 42; }
void launch(int* out) { store42<<<1,1>>>(out); }
```

将其保存为自己的实验文件，按 L01 的 `-fsyntax-only -Xclang -ast-dump` 模式检查，查找 CUDAKernelCallExpr 和实际引用的配置函数。2026-11-18 的参考 Clang 实验观察到 __hipPushCallConfiguration；新 LLVM/不同模式以生成结果为准。此输入不能被当作已经可以链接运行的 HIP 应用。

自己完成：指出 grid/block 参数、普通 kernel 参数和隐式配置调用分别在 AST 哪一部分。阅读入口为 Clang `SemaCUDA.cpp` 的执行配置与 target 检查，再阅读 CodeGen 中 host stub 的相关位置，暂不实现整套 runtime。

### L03：从设备函数到 RISC-V IR

复用 L01 的 attributes.hip，做一个隔离的设备前端实验：

```bash
"$HIP_TUTORIAL_CLANG" -cc1 \
  -triple riscv64-unknown-elf -target-cpu generic-rv64 \
  -target-feature +m -target-feature +f -target-feature +d \
  -target-abi lp64d -x hip -fcuda-is-device \
  -emit-llvm -O0 -o artifacts/tutorial/l01/device.ll \
  artifacts/tutorial/l01/attributes.hip
```

这是 Clang 内部 cc1 接口的教学实验，绕过了正式 offload driver；它不是已经支持 HIPVortex 公共命令的证据。先使用 generic-rv64，因为一个简单 store 尚不需要 Vortex 特殊指令。

自己完成：查找 target triple/DataLayout、两个函数、store i32 42、函数属性与 calling convention；检查哪些 HIP 信息保留下来，哪些不够下游识别 kernel。参考实验生成了 RISC-V IR，但并没有自动得到 SDK 所需的 native 入口/参数 wrapper。不能用函数名字或某个通用属性猜测“这就是可启动的 Vortex kernel”。

本课终点：画出 AST→IR，并列出下一课要补的连接信息。可以进一步用相同设备语义模式检查 device 调用 host 的反例，预期诊断失败。

### L04：第一次定制编译器，只补一个连接点

从这里开始构建并使用 LLVM 23，方法见 [build.md](build.md) 和 [T00 工程基线附录](getting-started.md#engineering-baseline)。先重跑 L01～L03，记录与参考工具的差异。

第一个源码练习建议是：在 **RISC-V HIP 设备上下文** 为逻辑 kernel 保留一个稳定、可测试的标记，普通 device helper 不产生该标记。先写 CodeGen 正例/反例，再选择具体 IR 表达；阅读 CodeGenModule.cpp 中 CUDAGlobalAttr 的处理和 RISC-V target 接口，而不是先扩展词法/语法规则。

逻辑 HIP kernel 标记与 SDK 的 `vortex.kernel` 原生单参数区入口契约要区分；直接把多参数 HIP body 当 native 入口会传错参数。后续生成 wrapper 时再建立二者的对应。

接下来按需要加入 mcpu=vortex 的默认设备配置和 HIP device-only driver 路由，让正常 driver 命令也能产生已观察到的设备 IR。每次只提交一个连接点；接受 CPU 参数、生成 IR 与生成可执行 kernel 分别验收。

### L05：第一个可执行结果，只有一个线程

保持 `store42(int* out)`，launch 限定一个 block、一个线程。这个范围可先绕开线程坐标和 lane 分歧，让问题集中在对象、链接、启动与参数上。

用固定 SDK 做 host 分配/启动/读回；允许先写教学用 native wrapper/参数桥接，并复用参考 startup/设备库/链接工具。明确记录哪些部分手工生成、哪些由新 LLVM 产生；手工桥接通过只算分层实验，不算完整原生 HIP 支持。不要把任意 store42 镜像直接交给只认 demo/sgemm ABI 的现有 runner。

自己完成：把 out 的设备地址装入参数区，检查公共启动 PC/kernel PC/args，再在 SimX 读回 42。下一课保留这条启动链，只扩展线程计算。完整阶段出口仍需逐步替换手工桥接并回填 T04/T06 对应验收。

### L06：把一个线程扩展成一组线程

先让每个线程写自己的索引，再做无尾部判断的 vecadd，例如 N=32、block=8。此时引入 threadIdx/blockIdx/blockDim、CTA CSR 和 builtin，按需要补 CPU/features、intrinsic 与 MC 指令。

自己完成：解释每个线程写哪里，验证 1D/2D 坐标和多 block，确保所选规模每个线程都访问合法范围。普通算术继续复用 RISC-V；不要为 vecadd 的加法单独发明 GPU 指令。

### L07：只加一个边界判断，学习 SIMT

将输入改为 N=37，并增加 `if(i<n)`，使同一 warp 内同时有有效/越界 lane。由这个具体变化引出 divergence、active mask、split/join、汇合点和 uniformity。

自己完成：先实现一个简单分支，再增加 if/else、嵌套、循环和提前退出。用哨兵验证无越界写入，保存 O0/O2 的 IR、MIR/汇编与结果；追查 select 等晚期展开是否产生额外分支。暂不支持的结构明确诊断，不能跳过转换后默默运行。

### L08：让用户真正写普通 HIP 程序

复用已经正确执行的设备代码，把手工 host 改为 hipMalloc/hipMemcpy/hipDeviceSynchronize 等公开 API，冻结所选 HIP 声明版本；再接通 L02 已观察的 <<<>>> host stub、镜像注册与参数打包。

自己完成：逐项将教学 wrapper/参数元数据/镜像封装自动化，检查错误和资源生命周期。最终运行 [目标 HIP vecadd](#62-用户最终怎样写程序)，用户无需手工适配 native ABI；此时才达到原生 HIP 最小闭环。两个不同签名 kernel 连续启动是本课后半部分的必需回归。

### L09：从 vecadd 到 block 协作

在相同编译/启动链上加入静态与动态 shared memory、__syncthreads()，先做小规模跨 warp reduction，再做 tiled SGEMM。保持当前设备的合法 block 大小。

自己完成：画每轮读写和同步关系，验证不同 block 的共享区隔离，以及 shared/global 互读的内存可见性。kernel 边界线程仍须满足合法 barrier 参与条件，不能把算法错误当后端错误。

### L10：扩展与交付

按需要加入匹配 A 配置的整数 atomicAdd、histogram、stream/event；没有需求的高级特性不提前放到第一条执行链。最后从干净构建目录复现，并回填已有工程任务的支持矩阵和证据。

自己完成：从 host 可执行文件追到设备镜像、参数描述、编译选项和库来源，确认无旧产物误用；区分 API 错误、进程故障和超时。完整数学库、RV32、跨文件链接、真实硬件与性能优化仍属于独立专题。

### 0.3 已核对的教学实验与证据边界

2026-11-18 使用现有参考 Clang 20.1.8 核对了预处理、属性 AST、host→device 非法调用、device→host 非法调用、RISC-V device IR 和 <<<>>> AST。合法观察命令退出 0，两个非法调用退出 1 并给出 target 调用诊断；device IR 中可见 store i32 42，launch AST 中可见 CUDAKernelCallExpr。

这些结果只证明参考编译器的隔离前端能力，不是 LLVM 23、新的 driver、Vortex kernel ABI 或 SimX 执行的新通过记录。后面所有“自己完成”仍是留给你的实现任务。本次没有替你修改编译器/runtime。

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

第一版完成以下子集：x86_64 Linux host、RV64 device、单设备、约定的 legacy 默认 stream、单源文件、多次 kernel 启动、`int`/`float` 运算、设备指针与固定宽度标量参数、`__global__`、`threadIdx`/`blockIdx`/`blockDim`/`gridDim`、`<<<>>>`、分配/拷贝/同步/释放和启动错误检查。这里的完成标准是端到端正确执行，不是“能生成汇编”。详细支持边界见 [实现契约](architecture.md#implementation-contracts)。

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

## 4. 工程能力分组与完整验收依赖

以下保留 11 个分组和原有任务编号，作为工程能力账本；它们不是 L01～L10 的授课顺序。每组保留命令、输入、IR/汇编或执行证据。表中的测试是该能力完整实现后的验收要求，不是当前已经全部通过的声明。

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

原工程链 `T00 → T01 → T02 → T03 → T04 → T05 → T06 → T07 → T08 → T09 → T10` 保留为完整能力出口的保守核对顺序。学习按第 0 节课程推进，可以先做 frontend 隔离实验和跨分组的局部实现；例如输出设备 IR 不要求先实现 HIP runtime。声称设备执行或某组完整通过时，必须补齐相关 CPU/ISA/ABI/runtime 依赖，不能把观察实验当成全组通过。

每组保留 6 项工程任务，详见 [任务卡目录](tasks.md)。前几课以观察和小练习为主；首次源码修改后按实际变化提交，测试检验新增语义或错误行为。既有任务状态不因授课重排而重置。

### T00：工程环境与 ABI 基线

操作说明保留在 [getting-started.md 的工程附录](getting-started.md#engineering-baseline)。参考工具的第一课语法实验可以先做；进入 LLVM 23 源码修改和执行验收前，再按需完成构建、参考 smoke 和 native ABI 核对。

### T01：CPU/subtarget 接入能力

先定义 `vortex` 的 RV64 CPU 配置、默认 ISA/ABI、扩展开关和保守调度策略，再接通 Clang 与 LLVM 工具。ISA 能力使用 `xvortex` 等 feature 描述，指令和 pass 查询实际 feature；kernel annotation 负责入口语义，CPU 名不把普通函数自动变成 kernel。

按 [任务卡 T01.1～T01.6](tasks.md) 核对 CPU 契约、extension/parser、ProcessorModel、Clang driver、LLVM 工具和选择矩阵测试。本组实现拆成小提交，在 L04～L06 按需引入；它不再规定整个教程的第一个源码改动。第一次定制练习见 L04 的 HIP kernel 识别连接点。

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

每个小任务的记录可从 [证据模板](evidence-template.md) 复制。任务状态只有“待做、进行中、待评审、通过、受阻”；任务初始为待做，后续以用户进度和实际证据为准，不因文档修订重置。现有参考环境通过记录不自动算作新后端任务完成。记录里注明新编译器、参考编译器、预编译库各自负责的部分。

## 6. 最后可以做成什么样子

### 6.1 目标选择与可运行里程碑

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

#define HIP_CHECK(call) do {                                      \
  const hipError_t error = (call);                                \
  if (error != hipSuccess) {                                      \
    std::fprintf(stderr, "%s: %s\n", #call, hipGetErrorString(error)); \
    return 1;                                                    \
  }                                                              \
} while (false)

__global__ void vecadd(const float* a, const float* b, float* c, int n) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i < n)
    c[i] = a[i] + b[i];
}

int main() {
  constexpr int n = 37;
  float a[n], b[n], c[n] = {};
  for (int i = 0; i < n; ++i) {
    a[i] = float(i);
    b[i] = float(2 * i);
  }
  float *da = nullptr, *db = nullptr, *dc = nullptr;
  HIP_CHECK(hipMalloc(reinterpret_cast<void**>(&da), sizeof(a)));
  HIP_CHECK(hipMalloc(reinterpret_cast<void**>(&db), sizeof(b)));
  HIP_CHECK(hipMalloc(reinterpret_cast<void**>(&dc), sizeof(c)));
  HIP_CHECK(hipMemcpy(da, a, sizeof(a), hipMemcpyHostToDevice));
  HIP_CHECK(hipMemcpy(db, b, sizeof(b), hipMemcpyHostToDevice));
  constexpr int block = 8; // 符合当前配置；正式运行先查询设备限制。
  vecadd<<<(n + block - 1) / block, block>>>(da, db, dc, n);
  HIP_CHECK(hipGetLastError());
  HIP_CHECK(hipDeviceSynchronize());
  HIP_CHECK(hipMemcpy(c, dc, sizeof(c), hipMemcpyDeviceToHost));
  bool ok = true;
  for (int i = 0; i < n; ++i)
    ok = ok && (c[i] == a[i] + b[i]);
  HIP_CHECK(hipFree(da));
  HIP_CHECK(hipFree(db));
  HIP_CHECK(hipFree(dc));
  std::puts(ok ? "PASS" : "FAIL");
  return ok ? 0 : 1;
}
```

目标是用户写标准 HIP 子集源码，不再手动编写 `kernel_arg_t`、入口 alias、`.vxbin` 打包命令或 Vortex host launch。编译链自动完成这些步骤，runtime 在配置好的 SimX 环境执行。

示例遇到错误即返回非零；完整失败路径的资源回收还要通过 T06/T08 的生命周期测试。它要求 runtime 提供 launch 错误状态，不能仅以所有 API 都返回成功来通过。这个目标示例尚未由新后端编译执行。

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

<a id="implementation-review"></a>

## 7. 开发前审阅结论与验收矩阵

审阅日期：2026-11-18。主线架构继续采用 RISCV Target + mcpu=vortex；本轮完善边界、依赖与测试，不新增任务编号或后端实现。P0 表示对应里程碑通过前必须解决，P1 表示该能力引入时落实。

| 优先级 | 原有不足/需要确认的细节 | 本轮补充与必须交付的证据 | 对应任务 |
|---|---|---|---|
| P0 | 顶部旧注释仍描述不同的启动模型 | 分开 program_pc/kernel_pc/args，按实际代码、DCR、ELF 核对；两个 kernel 交替启动 | T04.1～T04.6 |
| P0 | 单看入口 alias 或文件存在不足以证明可执行 | 验证公共入口、镜像基址、BSS 范围、入口表和 CTA slot 复用 | T04.2～T04.6 |
| P0 | O0 必需转换与优化 pipeline 的关系不具体 | optnone 下不漏跑 SIMT；O2 后不破坏 mask/CFG；失败有最小 IR | T03.1、T05.1～T05.5 |
| P0 | IR 转换之后仍可能出现新分支 | 检查 select/custom inserter 等机器级展开，保存 MIR/最终汇编与混合 lane 执行结果 | T03.6、T05.5 |
| P0 | 头文件和设备库依赖未独立列出 | 公开 API 实现前固定 HIP 声明版本，再审查 runtime wrapper/math/stdlib、sysroot 和库来源 | T06.1、T07.2、T07.5 |
| P0 | 参数打包缺少可逐字节复核的实例 | vecadd 建议 32 字节布局、kind/offset/align、wrapper 和版本化描述匹配 | T07.3～T07.4、T08.4 |
| P0 | 公开 API 与隐式 host ABI 边界不足 | 从 host IR 提取实际符号/签名；固定 dim3/stream/默认流模式与注册时序 | T08.1～T08.4 |
| P0 | 最小样例没有检查 launch 与同步错误 | 加入错误状态 API；正式样例逐次检查，错误不能静默当成功 | T06.6、T08.4～T08.6 |
| P0 | 框架可配置能力容易被当成固定 GPU 参数 | 查询真实 warp/block/shared 限制；检查溢出、形状和编译时假设 | T01.6、T06.1、T06.5 |
| P1 | private/global/shared 与 helper 调用边界未冻结 | 地址空间/转换/alias 表；private 栈及非内联调用测试；unsupported 清单 | T05.5、T07.3、T09.1 |
| P1 | barrier 只看指令存在会遗漏内存可见性 | shared/global 互读、多 warp、多轮 barrier 与重排测试 | T09.4～T09.6 |
| P1 | 原子、异步接口的名称容易代替语义验收 | atomicity/order/scope 分开；buffer/module/host 参数生命周期和 event 依赖 | T10.2～T10.5 |
| P1 | 线程/block 推进假设及故障通道没有分层 | 不依赖所有 block 同驻留；区分 API 错误、进程终止与超时，保存有界测试证据 | T05.6、T06.6、T10.5 |
| P1 | 一个版本号或源文件名不足以标识兼容性 | 分开 ISA、native ABI、参数容器、host ABI 和构建指纹；避免旧镜像/缓存误判 | T07.4、T08.2、T10.6 |
| P1 | 调试和复现证据的格式不统一 | 保存实际 clang jobs、IR/ELF/map、链接来源和配置；区分静态检查/参考执行/新后端执行 | 各阶段、T10.6 |

更详细的冻结点见 [架构实现契约](architecture.md#implementation-contracts)，启动与参数例子见 [compiler-sim-contract.md](compiler-sim-contract.md)。

审阅建议的先后顺序是：先冻结 native 启动与 ABI，验证一个可运行切片，再完善 SIMT；进入 HIP 前确定头文件/设备库/参数格式；接 host stub 时同时做错误与资源生命周期测试。共享内存、原子及异步继续按既有阶段增加，不把可选能力提前变成首个闭环的必要前置。

本轮文档审阅不等于矩阵各项已通过。源码核对、布局检查、参考工具结果和实际新后端执行分别记录，后续直接回填现有任务证据。
