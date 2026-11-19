# LLVM 23 原生 HIP/Vortex 教程与任务路线

设计基线：2026-11-17；更新日期：2026-11-19（Asia/Shanghai）。本文是供你逐步实现的教程与任务设计，不表示相关后端已经完成。

本教程采用 **6 个阶段的最小实现主线**：`store42 → vecadd → 一个已有 HIP 程序`。先观察 Clang 的语法/AST/Sema/IR，再按程序需要修改后端、ABI 和 runtime；第 3 阶段就执行设备代码，第 5 阶段接通普通 HIP 启动，第 6 阶段移植已有程序。第一个可用版本不以所有高级能力完成为前提。

原有 **11 个工程能力分组、66 项任务**（T00.1～T10.6）保留为 [验收账本](tasks.md)，不作为授课顺序或运行第一个程序的全部前置。课程号 L01～L06 只组织教学，每阶段拆成多个小实验和提交；减少阶段数不表示减少必需的实现工作。原课程号的对应关系见第 0.4 节，已有 ID、进度和证据不重置。技术结构仍采用 RISC-V 内的 mcpu=vortex，详见 [架构方案](architecture.md)。

维护位置固定为本仓库 `docs/codex/llvm-hip-vortex/`，入口见 [README](README.md)。后续直接更新现有文件，通过 Git 记录版本，不另建日期/版本副本。

<a id="tutorial-route"></a>

## 0. 从第一个 kernel 到已有程序的六阶段教程

### 0.1 教学方式

教学围绕同一条执行链升级程序：`store42 → 按线程写索引 → 整块 vecadd → 带边界的 vecadd → 普通 HIP 启动 → 已有 HIP 程序`。先得到可观察结果，再用具体问题引出机制。shared、原子、stream/event、设备库等按目标程序需求增加，不全部放在首次移植之前。

“从语法开始”是理解并复用 Clang 已有能力。HIP 限定符通常展开成 Clang 属性；<<<>>> 的解析和 host/device 语义检查也已有实现。先观察 AST/Sema，找到 Vortex 缺失的连接点，不从自写 HIP Parser 开始。

每个小实验采用固定结构：问题 → 最小输入 → 现有机制与源码入口 → 命令和产物 → 自己完成一个小改动 → 正例/反例验收 → 下一步。每次只引入一个可解释的变化；ABI/优化/完整支持矩阵在用到时查阅。

L01 的三个观察实验可以先使用已安装参考 Clang。L02 修改 LLVM 23 前，必须构建新编译器并重跑观察实验。参考结果、手工桥接和全自动 HIP 执行分别记录。第一阶段实验命令见 [getting-started.md](getting-started.md#lesson-1)，后续未实现的接口不写成现有可用命令。

### 0.2 阶段目录与出口

| 阶段 | 程序与新增能力 | 必须看见的结果 | 关联工程任务（只验收覆盖的子项） |
|---|---|---|---|
| L01 | 看懂 HIP 前端：属性、调用限制、启动 AST、设备 IR | 能解释 store42 从源码到 IR 的过程及缺失连接 | T00.1/T00.3；T07.2/T07.3、T08.1 的观察前置 |
| L02 | 建立 Vortex 编译入口：CPU/feature、kernel 标记、首条 TMC MC 支持 | 新 LLVM 识别设备配置与入口信息，并生成对应设备对象 | T01；T02.3、T03.5、T07.1/T07.2 子项 |
| L03 | 执行 store42：参数 ABI、native wrapper、镜像、启动桥接 | SimX 执行新 LLVM 编译的函数体，主机读回 42 | T04 子项；T06 的 SDK 使用基础 |
| L04 | 多线程 vecadd：CTA builtins、必要 SIMT 控制、尾部保护 | N=32 和 N=37 正确，混合 lane 无越界写入 | T03/T05/T07.3 子项；T02.4 及必要补全 |
| L05 | 普通 HIP 流程：最小 API、参数打包、注册与 <<<>>> | 完整 HIP vecadd 自动编译启动；补充双 kernel 回归 | T06/T07/T08 中该子集所需项 |
| L06 | 移植一个已有 HIP 程序：盘点依赖、补缺口与测试 | 固定来源的程序由新链路在 SimX 执行，并与 CPU 参考一致 | 按缺口回填 T00～T08；需要 block 协作或原子/异步时选 T09/T10 子项 |

L03 是首个分层执行结果，仍可有显式教学桥接；L05 是最小可用的原生 HIP 流程；L06 是已有源码的移植验收。阶段通过不自动完成整组 Txx，运行一个程序也不代表完整 HIP 兼容。O0/O2、入口与参数、实际编译器来源等要求按本阶段执行范围落实。

<a id="l01"></a>

### L01：看懂 HIP 前端

**问题。** Clang 已经做了什么？从源码到设备 IR，还没有做什么？输入为 store42 和普通 device helper，暂不涉及线程编号。

**按顺序做。** 完整命令、固定输入、预期结果与解释集中在 [getting-started.md](getting-started.md#lesson-1)：1.1 预处理/属性 AST → 1.2 两种非法调用与启动 AST → 1.3 RISC-V device IR。也可运行 [run_l01.py](examples/run_l01.py) 保存七项观察的证据。

**读哪里。** 先在 AST 中找到 CUDAGlobalAttr，再阅读 SemaCUDA.cpp 的调用侧与配置检查；从 CodeGen 的函数属性/target hook 追到 IR。不要求第一天读完整个后端。

**应得出的结论。** 现有 Clang 已能保留部分 HIP/目标信息；缺少的是 Vortex 下游可稳定消费的入口契约和完整编译/执行连接。CPU 属性在本实验中是刻意选择的 generic-rv64，store42 本身无需 SIMT 控制指令。详细区分见 [桥接关系](architecture.md#hip-ir-bridge)。

**完成条件。** 观察检查通过，保存版本/输入/IR和解释；能够区分 AST 属性、IR 函数属性、逻辑 kernel 标记与 native 入口。这里没有设备执行，不能把这一步登记成 T07/T08 整组通过。

<a id="l02"></a>

### L02：建立 Vortex 编译入口，开始修改后端

**问题。** 下游怎样可靠地区分 HIP kernel 和 helper？怎样选择实际支持的设备指令？继续使用同一份 attributes.hip，每次只增加一个连接点。

**准备。** 使用你构建的 Clang 23 重跑 L01，记录源码 HEAD 与二进制 --version。没有成品时才按 [LLVM 构建步骤](build.md#llvm-build) 构建；不把“重跑完整构建”变成每次修改文档的要求。

| 小实验 | 你自己做的改动/分析 | 观察和测试 | 本步结束时停在哪里 |
|---|---|---|---|
| L02.1 | 追踪 FunctionDecl→CodeGen target hook；选定逻辑 HIP kernel 的 IR 表达 | 对照 kernel/helper 的实际属性，写出正例和反例 | 只确定标记语义，不生成 wrapper |
| L02.2 | 在 RISC-V HIP device 上下文发射标记 | kernel 有标记；helper、host job、普通 RV64 不误标；O0/O2 保留 | 下游可识别逻辑 kernel |
| L02.3 | 定义 xvortex feature、RV64 CPU 和匹配基线的默认 ISA/ABI | -###、IR target-cpu/features、llc/MC 选择、禁用/错误位宽 | CPU 选择正确，不等同可执行 |
| L02.4 | 只添加首条 TMC 的 TableGen/MC 支持 | 正确寄存器编码、反汇编、feature 关闭和非法操作数 | 工具认识一条指令 |
| L02.5 | 从同一 HIP 输入生成设备对象 | ELF machine/class、函数/标记和实际编译参数 | 对象可用于下一阶段链接 |

源码阅读先用这些**现有入口**定位，不根据旧版本行号直接插代码：

```bash
cd /home/kaikai/vortex-word/llvm-project
rg -n 'setTargetAttributes|SetLLVMFunctionAttributesForDefinition' clang/lib/CodeGen/CodeGenModule.cpp
rg -n 'setTargetAttributes|RISCVInterruptAttr' clang/lib/CodeGen/Targets/RISCV.cpp
rg -n 'OffloadUniformBlock|uniform-work-group-size' clang/lib/CodeGen/CGCall.cpp
```

本地基线的 RISCVTargetCodeGenInfo::setTargetAttributes 已存在，但其处理 interrupt 属性的早退不适合直接套用到 HIP 标记；先确认控制流与声明类型，再选择 target hook 或更合适的 CodeGen 入口。不要因为函数名叫 CodeGenModule 就把所有目标逻辑塞进公共路径。

标记的形式（函数属性/annotation/专用 metadata）先写成契约：触发条件、消费者、优化后的存续和负例。它表示“这是逻辑 HIP kernel”，不表示“这是 SDK 可以直接调用的单参数区函数”。不能直接把多形参 HIP body 标成 native vortex.kernel 而省略解包入口，也不能用函数名、norecurse 或 uniform-work-group-size 猜测 kernel 身份。

CPU/feature 在 T01 中核对。当前基线默认 A/C 关闭，新的 CPU 默认能力必须一致；SDK 参考命令含 A 的差异见 [ISA 配置](architecture.md#isa-config)。最终 xvortex 版本/ISA 字符串在实现时冻结，不提前虚构一个公共 --offload-arch 拼写。

TMC 的参考输入 `vx_tmc a0` 应编码为 `0x0005000b`，小端字节 `0b 00 05 00`。先用参考工具理解 [编码实验](architecture.md#66-编码长什么样)，再用新 llvm-mc 做定向正/反例。这里不要求 Clang 为任意 C++ 代码自动生成 TMC。

**提交与出口。** 标记、CPU/feature、MC 各自独立提交，并加对应的 Clang CodeGen/Driver、TargetParser、MC 测试。L02 出口是 kernel 信息和设备对象可检查，尚未证明启动或 SIMT；T01/T02/T03 只登记本次覆盖的子项。

<a id="l03"></a>

### L03：执行第一个 kernel，主机读回 42

**问题。** 同一个 store42 的 out 指针怎样从 host 到达设备函数？只启动一个 block、一个线程，将问题收敛到 ABI、链接和镜像。

**先读。** [compiler-sim-contract.md 的 L03 操作图](compiler-sim-contract.md#l03-walkthrough) 与 SDK demo 的 host 调用。使用 [Vortex 构建脚本](build.md#simx-build) 保持参考 SDK/SimX 当前可用。

| 小实验 | 操作 | 保存和判断什么 |
|---|---|---|
| L03.1 | 查询设备、分配 4 字节输出，取得设备地址；输出先置为非 42 | host 指针、设备地址、初始值有区别 |
| L03.2 | 给 L02 的逻辑 body 加教学用 IR wrapper，参数区为一个 8 字节设备地址 | wrapper 的 a0 是参数区指针，body 的 out 是解包后的地址 |
| L03.3 | 建立 native 入口 alias/保留规则，链接 startup、库和脚本，打包 vxbin | program_pc/kernel_pc/args 三者；ELF、BSS、导出表 |
| L03.4 | 用你写的小型 SDK host 加载并启动，再按依赖读回 | 来自本次镜像的 42；所有 SDK 返回值检查 |
| L03.5 | 改写入值并重新生成镜像，重复运行 | 结果跟随新输入，排除加载旧镜像；记录 O0/O2 与工具来源 |

初期允许手写 wrapper/alias 和复用固定的 startup、静态库、LLD、打包器。教学桥接要逐项标记；L05 再自动化这些步骤。**在 IR 层 wrapper 调用逻辑 body**，不等于允许在设备 C++ 源码里直接调用 __global__ 函数；后者受 HIP 语义限制。

store42 的 body 使用标准访存。TMC/WSYNC 来自启动/收尾环境；复用参考对象或 .insn 通路不算新 LLVM 已完整支持这些指令。不要为了看到 GPU 助记符而修改正确的 store 函数体。

**停下来的条件。** 若 alias 被删除、两个 PC 不匹配或 a0 指向错误布局，先修复这一层；没有真实读回 42 就不要扩到多线程。现有 run-kernel.sh 只接受 demo/sgemm 约定，不能直接启动这份 8 字节参数 ABI 的任意镜像。

**出口。** 新 LLVM 编译的 body 在 SimX 得到正确结果，来源、参数字节和链接依赖清楚。手工 host/入口仍允许；这不是自动 HIP 运行流程。

<a id="l04"></a>

### L04：扩成多线程 vecadd，并正确处理边界

**问题。** 每个线程的索引来自哪里？只增加一个边界判断，为什么会引入 SIMT 正确性问题？沿用 L03 的显式启动链。

| 小实验 | 最小输入变化 | 预期结果与排查重点 |
|---|---|---|
| L04.1 | 每线程写 gid；先做 1D，再单独测试合法 2D 坐标 | CTA CSR 对应正确，不用 lane ID 代替 threadIdx |
| L04.2 | 无尾部判断 vecadd，N=32、block=8、grid=4 | 32 个输出与 CPU 一致，无需为普通加法新造 opcode |
| L04.3 | 改成 N=37、block=8、grid=5，并加 if(i<n) | 最后 warp 内确实有混合 lane；输出尾部哨兵保留 |
| L04.4 | 同样输入分别 O0/O2；再加单臂 if 的分支后共同写回 | mask/汇合正确，检查 IR→MIR→最终汇编 |

源码按 `vx_spawn2.h 的 CTA 包装 → CSR 地址/语义 → Clang builtin/IR → RISCV lowering/TTI → SIMT pass/pipeline` 阅读。threadIdx 的读取主要复用标准 CSR 指令编码；新增的是目标语义和编译连接，不必新造读取坐标的 opcode。

对实际存在的分歧控制流，补齐 SPLIT/JOIN 及所需控制变体、分歧来源分析和汇合变换。不是“源码出现 if 就机械插一对指令”；优化可能消除/改写分支，最终应按语义与真实机器控制流判断。查 select/custom inserter 等晚期展开，不能只看 IR 中出现了 split/join。

使用合法的输入缓冲区和较长的输出哨兵区，检查全部有效输出以及未激活 lane 不写尾部。当前每 warp 4 thread，N=37/block=8 的最后一个 warp 有 1 个有效 lane 与 3 个无效 lane。记录实际配置，不将这个数字写成所有 Vortex 的固定限制。

**出口。** 多线程和带边界 vecadd 在 O0/O2 均正确；不支持的 CFG/调用要明确限制。if/else、嵌套、循环和提前退出继续按 T05 增量回归，不要求在首个 vecadd 前一次完成；但任何实际已产生的未支持分支不能被静默放过。

<a id="l05"></a>

### L05：接通普通 HIP 编译和启动流程

**问题。** 怎样让用户只写普通 HIP 源码，不再手工准备 wrapper、参数 blob 和 SDK launch？输入为 [目标 HIP vecadd](#62-用户最终怎样写程序)。

| 小实验 | 你自己实现的连接 | 对应验证 |
|---|---|---|
| L05.1 | 固定 HIP 声明版本，做最小 runtime 的分配/同步拷贝/释放 | 地址区间、偏移、错误返回、成功/失败路径清理；不先依赖 <<<>>> |
| L05.2 | 用显式 module launch 封装已跑通设备镜像 | 默认队列、参数快照、buffer/module 保活 |
| L05.3 | 自动生成 native wrapper、入口与参数描述 | 指针/标量类型与偏移一致；两个不同签名不混淆 |
| L05.4 | 从实际 host IR 提取注册/stub/配置/launch ABI，接入 runtime | 声明、签名、调用顺序和 main 前注册一致 |
| L05.5 | 连接 device-only jobs、链接/打包、镜像嵌入和 host 链接 | -### 与实际工具链一致，设备 CPU 不传给 x86 host |
| L05.6 | 用 <<<>>> 跑 N=37 vecadd；补双 kernel、重复启动、错误回归 | 自动流程与显式流程同结果，launch 错误和同步错误均检查 |

读取顺序为 `vortex2.h → queue/module 的实际实现 → CGCUDANV.cpp 的 host ABI → Driver/HIP 工具链 → 设备包装头`。函数名清单不能替代参数/调用约定；Clang 的通用 HIP runtime wrapper 也不能假定天然支持 RISC-V。

这里的最小公开 API 包含 hipMalloc/hipMemcpy/hipFree、同步、错误查询和所需的单设备能力查询。HIP 参数数组保存的是参数值的 host 地址；runtime 按设备元数据读取并序列化，不能直接复制 void**。见 [参数例子](compiler-sim-contract.md#hip-参数布局示例拟定契约待实现)。

**出口。** 新 LLVM 和原生 runtime 自动完成编译/封装/注册/传参并在 SimX 正确执行；用户不手写 native ABI。给出支持 API/类型/控制流矩阵，不宣称完整 HIP 兼容。hipcc-vortex 等入口名和公共选项在实现前仍是设计示意；文档没有提供假装可运行的命令。

进入 L06 不要求先完成多个 stream、完整数学库、shared 或跨文件设备链接。T08.6 的更完整工程回归仍独立登记，不因最小演示通过而整组勾选。

<a id="l06"></a>

### L06：移植一个已有 HIP 程序，按实际缺口完善

**问题。** 自写最小示例通过后，已有源码还会暴露什么差异？首先采用固定 SDK 的 [tests/hip/vecadd/main.cpp](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/tests/hip/vecadd/main.cpp)，保留 common.h、CPU 参考、输入种子和原验证标准。

| 小实验 | 操作 | 交付 |
|---|---|---|
| L06.1 | 固定来源与版本，盘点 include/API/kernel 特性/启动尺寸/验证方法 | 依赖表与未支持清单，先不改算法 |
| L06.2 | 替换旧 chipStar 构建入口，检查新 host/device jobs、镜像与库来源 | 首次真实编译/执行结果，失败也保留 |
| L06.3 | 把一个失败缩小到最小复现，定位声明、runtime、ABI、SIMT 或设备假设 | 能暴露错误的测试与独立小修复 |
| L06.4 | 重跑小测试和完整程序，覆盖小规模/整块/尾部 | N=1/32/37 等合法输入，O0/O2 与 CPU 对照 |
| L06.5 | 从干净输出目录复现并整理差异 | 原程序改动与编译器/runtime 修复分别记录，支持矩阵如实更新 |

固定 vecadd 的静态依赖不仅是内存 API：host 还调用 hipGetDevice、hipGetDeviceProperties、hipGetErrorString，根据 maxThreadsPerBlock 调整 block，并使用 host C++ 标准库；kernel 不用 shared、barrier、原子或 event。属性结构必须符合所选 HIP 版本的完整 ABI，不能截短为一个字段。原 Makefile 仍走参考 HIP 路径，复用源码不等于复用原执行证据。

每次依次做“保存失败 → 最小复现 → 定位层次 → 增加测试 → 自己修复 → 完整回归”。缺少 API 不一定需要新增机器指令；程序写死的 block/warp 假设也可能需要可移植修改。不要用空函数返回成功或替换成新算法来宣称移植完成。

**出口。** 第一个固定来源的已有 HIP 程序由新链路在 SimX 与 CPU 参考一致；记录改动、版本、配置、错误与结果。这里即可形成首个移植里程碑，后面的候选按需选择：

| 后续程序/需求 | 需要补齐的能力 | 任务范围 |
|---|---|---|
| 已有朴素 SGEMM | 2D 索引、循环、浮点、边界；读源码确认依赖 | T03/T05/T07/T08 的相关子项 |
| reduction、tiled SGEMM | shared、BAR、block 内可见性与重排约束 | T09 |
| histogram | 匹配 A 配置的整数 atomicAdd、竞争与内存顺序 | T10 原子子项 |
| 多段数据依赖 | stream/event、队列顺序、异步对象生命周期 | T10 异步子项 |

固定 SDK 的朴素 SGEMM 没有使用 shared/barrier，不能只凭名称要求先实现 T09。原子实验要单独构建匹配 A 的 simulator/runtime/device；当前默认关闭 A。设备库、warp 操作、真实硬件和性能优化继续按专题扩展，不是这次移植的全部前置。

<a id="backend-timing"></a>

### 后端修改与指令接入时点

| 时点 | 后端工作 | 通过后能说明什么 |
|---|---|---|
| L01 | 观察现有语法/IR，普通 store/add 先复用 RISCV | 找到缺失连接，不要求新增指令 |
| L02 | CPU/feature、kernel 标记、首条 TMC 的 MC 定义与负例 | 新工具认识目标与首条指令，能生成设备对象 |
| L03 | startup 所需 TMC/WSYNC、入口与参数桥接 | 首个单线程执行结果；复用组件单独标记 |
| L04 | CTA CSR/builtin、必要 SPLIT/JOIN 与 SIMT 转换 | 多线程及尾部混合 lane 结果正确 |
| L05 | 按实际需要补 ABI/lowering；主工作是 host/device 编排与 runtime | 自动 HIP 启动链正确，不要求发明新算术 opcode |
| L06 按需 | shared/BAR、标准原子、其他扩展 | 只对新增能力和匹配配置作执行结论 |

对每条专用指令分四层验收：**MC 编码 → intrinsic/lowering → 按程序语义自动生成 → SimX 执行**。`.insn` 发出原始编码或复用参考启动不等于四层全部完成。线程编号主要连接 CTA CSR 与 builtin，不必新造 opcode。

### 0.3 已核对的教学实验与证据边界

2026-11-18 使用现有参考 Clang 20.1.8 核对了预处理、属性 AST、host→device 非法调用、device→host 非法调用、RISC-V device IR 和 <<<>>> AST。合法观察命令退出 0，两个非法调用退出 1 并给出 target 调用诊断；device IR 中可见 store i32 42，launch AST 中可见 CUDAKernelCallExpr。

上述 2026-11-18 记录只证明当时参考编译器的隔离前端能力；下面单独补记新 Clang 的观察，不把两次记录混成设备执行证明。课程中的编译器/runtime 实现仍由你完成。

2026-11-19 再核对：LLVM 仓库 HEAD 为 `c447d813c43ffd97e973c7e582175a60286c1b50`（用户提交“完成L01的教程”）；保留其 `llvm/unittests/Vortex/101/` 输入与脚本。新 Clang 23.1.4 可用，--version 中嵌入的编译修订仍为原始基线 `7a941dfb...`，与后来提交实验文件的源码 HEAD 分开记录；四个构建目标均可查询。

本目录标准夹具用 Clang 23 与参考 Clang 20 验证（最终脚本各执行一次），七项前端观察均通过。证据分别在 `/home/kaikai/vortex-word/artifacts/tutorial/l01/run-jpow1h7p/report.json` 和 `run-1p_l56x3/report.json`；这些是本机产物，不在文档仓库中。新 Clang 中两个函数都可能带 uniform-work-group-size，这不是 Vortex kernel 标识。

用户原实验脚本的 +f 重复一次，应以本教程的 +m/+f/+d 与 lp64d 配套命令重做；本次没有修改你的 LLVM 源码/提交。该路径里的手工脚本尚不等于被 lit/CMake 注册的测试。未来编译器回归应分别放入 Clang CodeGen/Sema/Driver 或 LLVM MC/CodeGen/Transforms 的对应测试目录。

本轮还逐条执行了 L01 手工命令；用新 LLVM verifier 检查 L03 的示意 wrapper 结构，并用 rv64imfd/lp64d 生成标准 add 的汇编和 IR。wrapper 尚未链接或在 SimX 执行。这些证据不自动完成整组工程任务；目前没有本轮新 Vortex 后端设备镜像执行通过记录。

### 0.4 旧课程与六阶段的对应关系

| 原课程号（历史记录） | 当前阶段 |
|---|---|
| 旧 L01/L02/L03：AST、Sema/launch、IR | 新 L01 的 1.1/1.2/1.3 实验 |
| 旧 L04：最小编译器修改 | 新 L02 |
| 旧 L05：单线程执行 | 新 L03 |
| 旧 L06/L07：线程标识、分歧 | 新 L04 的 4.1/4.2 |
| 旧 L08：HIP 全链路 | 新 L05 |
| 旧 L09/L10：block 协作、扩展与交付 | 新 L06 按程序需要选做；复现与错误验证贯穿执行阶段 |

本次只调整教学组织，T00.1～T10.6 的工程范围、状态和原证据保留。旧 L06 的索引实验不能被改写成“新 L06 已有程序移植通过”。已有记录保留原课程号，并补充本表映射；新增记录使用“六阶段主线 Lxx/小实验”与关联 Txx.y，列出实际覆盖范围。2026-11-18 的参考前端记录映射至新 L01，仍不是新 LLVM 的执行证据。

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

以下保留 2026-11-17 的版本基线，并注明 2026-11-19 的工具与源码核对；没有重跑完整 LLVM 构建或五项 SimX smoke。开始学习时按 [起步任务](getting-started.md) 核对实际状态。构建命令见 [build.md](build.md)，产物与执行接口见 [compiler-sim-contract.md](compiler-sim-contract.md)。

| 对象 | 当前基线 | 教程中的作用 |
|---|---|---|
| 新编译器 | `/home/kaikai/vortex-word/llvm-project`，`dev/vortex`，`llvmorg-23.1.4` 基线 `7a941dfb...`，2026-11-19 源码 HEAD `c447d813c...` | 你实现的主体；与二进制内嵌修订分开记录 |
| Vortex SDK/SimX | `/home/kaikai/vortex-word/vortex`，`26d2bc4b5409a35a111e8316ac3a87d07b15fc80` | 固定执行端、ABI 与测试输入 |
| 官方参考编译器 | `/home/kaikai/vortex-word/tools/llvm-vortex`，Clang 20.1.8，`f44a6bb2af4c62847585305bbdc760fbe0e3645f` | 对照 IR、汇编和执行结果 |
| 新编译器构建目录 | `/home/kaikai/vortex-word/build/llvm` | 2026-11-19 查询到 Clang 23.1.4、四个 target 和 MC/FileCheck/lit 工具；完整构建日志另行留证 |
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

以下保留 11 个分组和原有任务编号，作为工程能力账本；它们不是 L01～L06 的授课顺序。每组保留命令、输入、IR/汇编或执行证据。表中的测试是该能力完整实现后的验收要求，不是当前已经全部通过的声明。

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

工程组按能力核对依赖，而不是要求整组串行完成。runtime 底座可在兼容 native 镜像可用后开始，不必先完成全部分歧/循环；原子与 stream/event 也不依赖 shared/reduction 全部完成。最小依赖表见 [任务账本](tasks.md#task-dependencies)。局部实现可跨组推进；声称完整组通过仍要逐项满足该组验收，不能用观察实验代替执行。

每组保留 6 项工程任务，详见 [任务卡目录](tasks.md)。第一阶段以观察和小练习为主；首次源码修改后按实际变化提交，测试检验新增语义或错误行为。既有任务状态不因授课重排而重置。

### T00：工程环境与 ABI 基线

操作说明保留在 [getting-started.md 的工程附录](getting-started.md#engineering-baseline)。参考工具的第一课语法实验可以先做；进入 LLVM 23 源码修改和执行验收前，再按需完成构建、参考 smoke 和 native ABI 核对。

### T01：CPU/subtarget 接入能力

先定义 `vortex` 的 RV64 CPU 配置、默认 ISA/ABI、扩展开关和保守调度策略，再接通 Clang 与 LLVM 工具。ISA 能力使用 `xvortex` 等 feature 描述，指令和 pass 查询实际 feature；kernel annotation 负责入口语义，CPU 名不把普通函数自动变成 kernel。

按 [任务卡 T01.1～T01.6](tasks.md) 核对 CPU 契约、extension/parser、ProcessorModel、Clang driver、LLVM 工具和选择矩阵测试。本组实现拆成小提交，在 L02～L04 按需引入；它不再规定整个教程的第一个源码改动。第一次定制练习见 L02 的 HIP kernel 识别连接点。

本阶段明确验证 `-mcpu=vortex`、显式 `-march`、错误 RV32 目标与普通 RISC-V 的组合。Vortex kernel/HIP device 编译若选项删除必需能力，应有明确诊断；普通 RISC-V 编译保留上游 ISA 选择规则。通过后仅表示工具能正确选择 Vortex subtarget，尚未支持其特殊指令。

### T02：特殊指令的 MC 支持

这一能力组覆盖四条 MC 指令，每条可单独提交并按课程需要完成；不在某一条指令的提交里同时移植整个分歧 pass 或添加 runtime。

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

教学执行里程碑是 L03 的 store42、L04 的带边界 vecadd、L05 的自动 HIP 流程和 L06 的首个已有程序。下表是更完整的工程能力出口；不要求先完成全部工程组才开始执行或移植。

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
3. **可运行示例与测试集**：最小主线的 store42、带边界 vecadd、双 kernel 回归和首个已有 HIP 程序；后续按需求增加 SAXPY、分歧/循环、reduction、SGEMM、histogram、stream/event。各项标注实际状态和配置，未实现的例子不作为第一轮完成条件。
4. **工具与说明**：编译入口、镜像检查、SimX 运行入口、版本清单、支持矩阵、已知限制、从干净目录复现的命令。
5. **验证报告**：区分 LLVM 23 编译对象与仍复用的参考库，报告 O0/O2、错误用例、配置一致性与结果。主线先允许复用已固定的设备库；只有实际重编并通过测试的库才能标记为 LLVM 23 构建。

完成后，你拥有的是一套可教学、可调试、可扩展的原生 HIP/Vortex 编译系统原型。真实硬件速度、完整 HIP 兼容或大型应用可用性，需要独立验证，不能由 SimX 样例通过直接推出。

### 6.4 首个移植结果之后的专题

66 项账本内尚未完成的 T09/T10 可继续按需求推进；它们不因第一轮六阶段结束而删除或标为通过。以下专题不计入现有 66 项的完整能力承诺，可按实际需求继续拆解：设备数学库与更多类型；复杂 C++/按值结构体 ABI；跨翻译单元 device linking；常量/全局对象；warp/subgroup 操作；RV32；真实硬件部署；性能优化与更大型 HIP 应用移植。首个小程序的移植已在 L06 开始，不再推迟到这些专题之后。每个专题都应先定义支持子集，再增加源码、负例和执行测试。

<a id="implementation-review"></a>

## 7. 开发前审阅结论与验收矩阵

审阅日期：2026-11-18；教程与依赖复核：2026-11-19。主线架构继续采用 RISCV Target + mcpu=vortex；本轮完善边界、依赖与测试，不新增任务编号或后端实现。P0 表示对应里程碑通过前必须解决，P1 表示该能力引入时落实。

| 优先级 | 原有不足/需要确认的细节 | 本轮补充与必须交付的证据 | 对应任务 |
|---|---|---|---|
| P0 | 顶部旧注释仍描述不同的启动模型 | 分开 program_pc/kernel_pc/args，按实际代码、DCR、ELF 核对；两个 kernel 交替启动 | T04.1～T04.6 |
| P0 | 把 IR 中缺少专用指令误判为前端失败 | 区分通用属性/逻辑 kernel/native 入口；store42 不要求 SPLIT/JOIN；正反例覆盖 marker | L01/L02、T03.5/T07.4 |
| P0 | CPU 默认能力与 SDK 参数混淆 | 明示参考 rv64imafd 含 A、SimX 默认 A/C 关闭；新默认按实际配置，审计库和镜像 | T01.1/T01.6、T04.3 |
| P0 | 工程依赖被写成全部串行前置 | 以任务账本的能力依赖推进，保留六阶段与原有任务状态 | 各阶段 |
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

审阅建议的先后顺序是：先冻结 native 启动与 ABI，验证一个可运行切片，再完善 SIMT；在首次设备链接前确认所用库，进入公开 HIP runtime/自动流程前确定声明、包装头和参数格式；接 host stub 时同时做错误与资源生命周期测试。共享内存、原子及异步继续按既有阶段增加，不把可选能力提前变成首个闭环的必要前置。

本轮文档审阅不等于矩阵各项已通过。源码核对、布局检查、参考工具结果和实际新后端执行分别记录，后续直接回填现有任务证据。
