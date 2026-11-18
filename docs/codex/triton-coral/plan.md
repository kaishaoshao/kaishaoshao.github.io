# Triton Coral 实施计划

更新日期：2026-11-18（Asia/Shanghai）。本文件在固定路径持续维护，变更记录见 Git 历史。

配套文件：[任务数据](plan.json)、[任务表](tasks.xlsx)、[目录与维护说明](../README.md)。

## 持续维护方式

实施说明、结构化任务和任务表固定为 `plan.md`、`plan.json`、`tasks.xlsx`。修改任务或验收时同步三者，保留已有任务 ID、状态与证据。具体规则见 [AGENTS.md](../AGENTS.md)。

## 已确定的实施顺序

先用最小 TTIR 子集跑通真实 AOT 单核执行，再补齐基本 Triton 语义和标准 JIT；之后引入 Ascend 版 TTS/Linalg、RVV、多核和多级存储优化。

默认执行顺序为 **S0 → S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8 → S9**。按此顺序学习与实现，验收后再推进。任务表的“技术前置”只列实际依赖，例如 Zvt 不是多核调度的前置；实施优先级不应被误当成硬件依赖。

| 阶段 | 先实现什么 | 任务 | 验收出口 | 通过标准 |
| --- | --- | --- | --- | --- |
| S0 | 最小基线与接口 | S0-01～S0-03 | G0 | 现有 Triton 与固定 Coral SDK 可构建；最小参数、设备地址及一核执行约定清晰。 |
| S1 | 真实 AOT 单核闭环 | S1-01～S1-06 | G1 | Triton 源码生成真实 ELF，由控制 CPU 装载到 core0，拷贝和加法结果正确。 |
| S2 | 基本 Triton block 语义 | S2-01～S2-04 | G2 | arange、mask、program_id 和一核顺序多 program 正确。 |
| S3 | 标准 JIT 与运行接口 | S3-01～S3-04 | G3 | 通过 `kernel[grid](...)` 完成编译、参数封装、执行和取回结果。 |
| S4 | Ascend TTS 与 Linalg | S4-01～S4-06 | G4 | 已支持用例迁移到结构化流水线，JIT 与 AOT 结果均保持正确。 |
| S5 | 单核 RVV | S5-01～S5-03 | G5 | 结构化流水线生成实际 RVV 指令，向量与归约结果正确。 |
| S6 | 参数化多核调度 | S6-01～S6-04 | G6 | 同一组逻辑 program 在当前可用核子集上正确执行。 |
| S7 | DMA 与多级存储 | S7-01～S7-05 | G7 | HBF/DRAM/SRAM/DTCM 的显式搬运、计算和回写正确。 |
| S8 | Zvt 与矩阵扩展 | S8-01～S8-04 | G8 | 合法 Triton dot 形状映射到 Coral Zvt 子块并通过数值及指令验证。 |
| S9 | 重叠与性能优化 | S9-01～S9-03 | G9 | 功能回归稳定，优化有可解释的周期及资源证据。 |

## 首个里程碑：G1 真实 AOT 单核执行

目标是让源码经过真实转换与代码生成，在 Coral core0 上算对。G1 的全部前置任务仅为 **S0-01、S0-02、S0-03、S1-01、S1-02、S1-03、S1-04、S1-05**；不包含 TTS、Linalg、RVV、DMA、多核调度或自定义方言。

```text
Triton Python / ASTSource
  → TTIR 的明确标量子集
  → LLVM Dialect（必要时使用 Arith/CF 等标准操作）
  → LLVM IR
  → 固定 Coral SDK 的 clang / ld.lld
  → 真实静态 RISC-V ELF
  → 宿主提取加载段、打包控制 CPU 启动镜像
  → 控制 CPU 装载并启动 Coral core0
  → 独立读取与验证输出
```

这遵循 MLIR 的“转换到可导出方言，再翻译为 LLVM IR”机制。[MLIR LLVM IR Target](https://mlir.llvm.org/docs/TargetLLVMIR/)

| 项目 | G1 的确定范围 |
| --- | --- |
| 源程序 | INT32 拷贝与加一；由真实 TTIR 决定计算，不用固定结果模板。 |
| 执行配置 | grid=1，仅启用 core0；输入输出在共享 SRAM 合法区域。 |
| 代码与参数 | 使用已约定入口包装、参数框架、栈和完成状态，检查 ITCM/DTCM 容量。 |
| 装载 | ELF 是真实产物；宿主可先解析加载段，控制 CPU 执行装载，不要求首版固件具备 ELF 文件解析器。 |
| 指令 | 先用已确认的 RV32 整数能力；明确 target/features，不自动启用未验证的浮点或新指令。 |
| 数据搬运 | 控制 CPU 首版可用现有 host 访问装载小数据，不依赖 DMA。 |
| 通过依据 | 改变输入和源程序，数值、保护区、完成状态以及源码到 ELF 的来源链均正确。 |
| 边界 | compile() 返回字节不代表执行通过；真实 AOT 执行也不代表标准 JIT 已通过。 |

首批三个实现提交建议：

1. **最小 TTIR 到 LLVM IR**：支持的操作、类型转换、合法性检查及 IR 回归。
2. **入口包装与静态 ELF**：启动、参数、链接脚本、加载段与容量检查。
3. **AOT 执行和数值验收**：打包、真实控制 CPU 装载、core0 执行、G1 报告。

## 从开始保留的约定

S0 仅约定 ABI 版本、逻辑 program/grid、设备地址、region/owner 的含义、当前可用核和权限边界。可先写入参数和简单元数据，不要求先做完整资源图、全局内存分配器或三套自定义方言。单核阶段使用同一套可扩展约定，多核阶段再落实完整调度和资源校验。

HBF 是 High Bandwidth Flash，计算平面只读；3D DRAM 承担存储。多层路径按实际可达性选择，DRAM 暂存显式表达，缓存策略单独定义。四核及现有容量属于当前原型实例，不能把未来 N 核的规划检查写成硬件执行成功。

## 方言与结构化主线的接入规则

- **S1/S2**：只实现有限 TTIR 子集的正确转换，用标准 LLVM/SCF 等表示，不先造 Coral 方言。
- **S4**：在 AOT 和 JIT 已有数值基线后，接入 Ascend 版 TTS 和 Linalg。所核对版本的 TTS 包含 `get_structured_state`，用于传递指针结构分析的 offset/stride 等循环状态；具体移植范围以固定来源提交为准。[Ascend 版定义](https://github.com/triton-lang/triton-ascend/blob/main/third_party/ascend/include/Dialect/TritonStructured/IR/TritonStructuredDialect.td)
- **S4**：优先在 tensor 阶段保留结构，随后做需要的 Bufferization。自定义 tensor 操作如参与该过程，应提供相应接口/外部模型。[MLIR Bufferization](https://mlir.llvm.org/docs/Bufferization/)
- **迁移规则**：旧最小路径只作短期差分参考。已有 S1/S2/S3 用例在新主线通过后，停止扩张旧路径并移除冗余。
- **S5**：正式 RVV lowering 在结构化主线实现一次。
- **S6/S7/S8**：分别在需要控制、搬运、目标 tile 语义时实现 `coral_rt`、`coral_mem`、`coral`。这些命名及操作是拟议设计，不代表仓库已经实现。

| 方言/模块 | 职责 | 何时接入 | 首批范围 | 约束 |
| --- | --- | --- | --- | --- |
| tt / TTIR | 前端逻辑 block、指针和计算 | S0 起使用 | S1 仅标量；S2 扩展有限 block 子集 | 首个闭环无需 TTS 或 Linalg |
| LLVM / Arith / CF / SCF | 最小代码生成、算术和必要循环 | S1 起使用 | TTIR 子集直接到 LLVM，必要时过标准循环 | RV32 data layout 与固定宽度整数正确 |
| tts（Ascend 版） | 结构化指针状态和循环携带信息 | G3 通过后接入 | get_structured_state 及配套分析/转换 | 需固定来源并适配 LLVM 24；最终消除占位状态 |
| linalg / tensor | 结构化逐元素、归约和矩阵计算 | G3 通过后接入 | generic、广播、归约；矩阵扩展在 S8 | 保持结构做优化，既有 AOT/JIT 回归不退步 |
| bufferization / memref | buffer、alias、容量与生命周期 | 结构化计算接通后 | 所需接口/外部模型，标准 memref 布局 | 不能将 mask、owner 或生命周期丢失 |
| vector / RVV lowering | 目标宽度、mask、重排及归约 | G4 通过后实现 | strip mining 与目标合法化 | 逻辑 BLOCK 与 VLEN 分开，检查实际机器指令 |
| coral_rt | 控制 CPU 的启动与多核任务依赖 | G5 通过后实现 | launch、dispatch、join 等拟议接口 | 核内与控制作用域分开；软件事件非全局隐式 barrier |
| coral_mem | 带归属的存储、局部布局和搬运 | G6 通过后实现 | region/view、copy_async、wait 等拟议接口 | HBF 只读、DTCM owner、路径、容量和可见性需验证 |
| coral | Zvt 等目标独有的 tile 计算 | 需要 tile 目标语义时实现 | tile_mma 等拟议接口 | 形状、类型、状态和效果合法；普通算术复用标准方言 |
| HFusion / HIVM / HACC / Transform | 参考分层、结构化接口与调度方式 | 按后续实际需求选择 | 只借鉴适合 Coral 的职责和机制 | 不为第一个闭环引入整套 Ascend 编译与运行依赖 |

## 多核与多级存储的实施边界

| 对象 | 必须保留的约定 | 何时实现 | 当前原型 | 验证要求 |
| --- | --- | --- | --- | --- |
| 最小 ABI | 版本、参数布局、设备地址、逻辑 ID/grid | S0 约定；S1 执行；S3 通用化 | 现有 v2 可用于最初用例 | 兼容扩展带版本，单核与多核复用明确协议 |
| 核拓扑 | 物理核数、可用掩码、逻辑 grid 分开 | S0 记录；S6 实现完整 placement | 当前物理 4 核，可启用子集 | 实际 1/2/4 核子集执行；未来 N 核先静态检查 |
| 共享全局地址 | region、合法范围、预留区与权限 | S0 约定；S1/S2 实际使用 | 共享 SRAM 16 KiB；trace 区预留 | 真实指针及保护区受检，不把宿主地址当设备地址 |
| 每核 ITCM/DTCM | 所属核、加载段、参数、栈和 scratch | S1 最小容量检查；S6/S7 扩展 | 当前 ITCM 8 KiB、DTCM 32 KiB 每核 | 私有区逐核分配，容量/存活区不重叠 |
| HBF | 只读来源、有效范围、合法访问路径 | S0 记录约束；S7 实现搬运 | 窗口 [0x80000000,0xc0000000) | 拒绝计算平面的写入；窗口大小不等同实际物理容量 |
| 3D DRAM | 读写、容量、布局和生命周期 | S0 记录约束；S7 使用 | 窗口 [0x60000000,0x70000000) | 只承担存储；staging 显式，缓存策略另行设计 |
| 分片及局部副本 | 全局 tensor、分片范围、局部 owner | S2 保持逻辑索引；S6/S7 落实 | 先共享地址，再显式局部化 | 不重复添加 program 偏移，禁止错误共享私有存储 |
| 访问可达性 | CPU、核、DMA 到各 region 的合法路径 | S0 记录当前使用路径；S7 校验全图 | 当前 AXI 与 host 窗口 | 每项 copy 都有路径，不假设任意两层可互拷 |
| DMA 资源 | 通道、粒度、对齐、并发和互斥 | S7 实现；S9 优化 | 当前单通道、4B 对齐、单 outstanding beat | 不超发；不能靠扩大拷贝范围处理不合法尾部 |
| 任务与可见性 | 启动、生产者完成、消费者可见和失败 | S1 基本完成；S6/S7 完整依赖 | 当前无一致性缓存；DMA 等待最终成功写响应 | 后继等待可见完成；序号匹配，超时后未停止不得复用，DMA 失败可有部分输出 |
| 队列与事件 | 槽位、fan-in、generation 与引用回收 | S6 完整实现 | 32 任务槽、64 事件、最多 2 直接前驱 | 长 grid 窗口式提交，失败不被伪报成功 |
| LLVM 地址与类型 | 物理映射和 LLVM address space 分开 | S1 确立；S4/S7 持续保留 | RV32、小端；TTIR 使用固定宽度整数 | index 降低匹配 data layout；不能静默截断或任意赋空间编号 |
| 缓存身份 | SDK/补丁、ABI、生成器与影响代码的布局 | S3 基础缓存；S6/S7 扩展计划标识 | kernel 与 Launch Plan 可分开缓存 | 拓扑变化重规划；代码相关布局变化重新编译 |
| 重叠与双缓冲 | 端口、buffer 生命周期与资源锁 | S9，正确单缓冲通过后 | 当前同核 DMA/kernel 互斥 | 先跨核重叠，放宽同核互斥需新的硬件/资源证明 |
| 性能证据 | 设备周期和宿主仿真时间分别记录 | S1 留证；S9 分项分析 | 外部存储模型使用合成延迟与背压 | 模型结果不宣称真实器件频率、带宽或峰值吞吐 |

## 实施前需固定的细节

本次审查保持 S0～S9 的默认顺序与 42 个任务 ID，只补充对应阶段的实现要求；这些细节不要求在 G1 前完成后续阶段的实现。

| 编号 | 需要补充的内容 | 明确要求 | 验证方式 | 对应任务 |
| --- | --- | --- | --- | --- |
| D01 | 参数与调用 ABI | RV32/ILP32、小端、字段偏移/宽度/对齐、16B 栈对齐、保留区和协议版本形成一张明确布局表。 | 固件与 wrapper 对同一参数样本解码一致，拒绝版本/范围错误。 | S0-02,S1-02 |
| D02 | ELF 与装载 | 静态链接；约定段地址字段、检查文件/内存范围、加法溢出、入口、BSS、段权限和 ISA 属性；未解析运行库 helper 明确失败。 | 损坏、截断、重叠、越界、入口错误及未支持指令均有诊断。 | S1-03,S1-04 |
| D03 | 整数与 mask 语义 | INT32 模运算和 signed/unsigned 扩展清楚；不能擅加 LLVM 溢出承诺；other 未定义时不要求其无效 lane 为零。 | O0/O2 最小用例、边界整数、全假/混合 mask 与无 UB 参考。 | S1-01,S2-02,S2-04 |
| D04 | 别名与标量化 | 保留 block tensor SSA 的 load/compute/store 次序；不相交、精确原地和部分重叠区分处理。部分重叠不等于普遍非法 Triton。 | 合法原地结果正确，部分重叠按已声明策略保持语义或诊断，不能静默误算。 | S2-01,S4-05 |
| D05 | 启动与完成身份 | 提交序号、完成序号、核与镜像身份关联；旧完成清理和代码装载后的取指可见性按真实硬件确认。 | 连续切换代码、输入及核时不串扰；旧完成和过期句柄不会完成新调用。 | S1-05,S6-03 |
| D06 | JIT 运行协议与计时 | 明确零 grid、串行 stream、buffer 生命期和冷启动桥的行为；区分编译/装载/启动开销与设备 kernel 周期。 | 重复调用、零工作、异步误用/失效对象和缓存配置变化有结果或清晰诊断。 | S3-01,S3-02,S9-01 |
| D07 | TTS 迁移收敛 | S4 先做来源固定和小规模兼容试验；列明移植范围与停止条件，保留正确基线，覆盖现有支持项后统一主线。 | 前端可达 IR 与 S1/S2/S3 原有回归通过，不引入 G1 的高级依赖。 | S4-01,S4-06 |
| D08 | 故障、部分输出与恢复 | DMA 失败可能留下部分输出；超时不等于停止。定义等待/复位范围、幂等重试条件和失效对象。 | 中途错误、依赖失败、超时与恢复后重启；停止确认前禁止复用旧资源。 | S7-03,S7-05 |
| D09 | Zvt 布局和数值 | 从合法前端 dot 出发，检查 signedness、累加规则、pack/transpose 与本地 tile 布局，分别度量转换开销。 | 每种支持布局逐项数值和指令验证；不把其他 dtype 自动视为通过。 | S8-01,S8-04 |
| D10 | 支持范围与证据 | 每阶段记录操作/类型/布局/能力白名单；编译、静态资源检查和执行证据分开，错误包含阶段、位置及相关配置。 | 输入、TTIR、LLVM、ELF、镜像、目标配置和结果可对应；不支持项有明确错误。 | S0-03,S1-06 |

整数 lowering 需保持源语义，LLVM 的溢出标记不能凭猜测添加。[LLVM LangRef](https://llvm.org/docs/LangRef.html#add-instruction)

首版选择标准 RV32/ILP32 调用边界，显式记录参数和栈约定；具体工具链及目标能力仍须核对，引用开发中的文档不等于自动支持其所有 ABI 变体。[RISC-V psABI](https://riscv-non-isa.github.io/riscv-elf-psabi-doc/)
## 分阶段任务明细

下列 42 项均为待实现计划。已有后端注册、LLVM 绑定、手写固件或 RTL 演示不计作 Triton 自动生成代码的完成证据。

## S0 最小基线与接口

出口：**G0**。现有 Triton 与固定 Coral SDK 可构建；最小参数、设备地址及一核执行约定清晰。

本阶段范围：不接入 TTS/Linalg，不实现完整拓扑分析器或三套自定义方言。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S0-01 | 确认固定工具链与构建 | 确认现有 backend 注册、Coral SDK、LLVM/MLIR 头库及 RISC-V target。只检查当前闭环所需依赖。 | 无 | 可复现的版本和构建记录 | LLVM 版本与补丁一致，现有插件可导入；此项不要求 TTS 编译成功。 |
| S0-02 | 约定最小参数与地址接口 | 首版确定 RV32/ILP32、小端、参数块版本及各字段 offset/width/alignment、16B 栈对齐和区域边界。只实现 core0 所需最小接口，逻辑 ID 与物理核分开。 | S0-01 | 一页最小 ABI 及地址说明 | 编译器、入口和控制固件共享明确字节布局；不从宿主 void* 或结构体大小推断设备 ABI，版本或越界不匹配应拒绝。 |
| S0-03 | 建立首批源程序与诊断入口 | 保存拷贝/加一的真实前端 TTIR、支持操作和类型白名单、阶段 IR、错误及数值参考。明确不支持项的诊断位置和配置。 | S0-02 | 可重复的源程序与构建入口 | 未知操作、类型和配置给出阶段及源位置；保存输入、IR、ELF、配置和结果的来源，不以改名或 payload 存在验收。 |

建议代码位置：

- **S0-01**：cmake/llvm-info.json；Coral CMake。
- **S0-02**：device/task_abi.h；runtime 适配设计。
- **S0-03**：现有 Coral 用例；测试及 debug 入口。

## S1 真实 AOT 单核闭环

出口：**G1**。Triton 源码生成真实 ELF，由控制 CPU 装载到 core0，拷贝和加法结果正确。

本阶段范围：先限定 INT32、grid=1、共享 SRAM；不要求标准 JIT、RVV 或 DMA。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S1-01 | 实现最小 TTIR 到 LLVM 转换 | 转换函数、指针、i32 load/store、必要整数算术和 return。直接用 LLVM Dialect，必要时用 Arith/CF；不经过 TTS/Linalg。 | S0-03 | 由真实 TTIR 生成的 LLVM IR | LLVM verifier 通过；改变源码会改变计算。INT32 加法按 32 位模运算验证，不能无依据添加 nsw/nuw；最小例在 O0/O2 下与无 UB 参考一致。 |
| S1-02 | 实现 kernel 入口包装 | 入口按已约定参数框架读取设备参数、设置栈、调用生成函数并发布完成状态。控制 CPU 与 Coral kernel 的 ISA 配置分开。 | S1-01,S0-02 | 可裸机执行的入口与参数绑定 | 参数、栈、完成标志和 DTCM 预留区不重叠；非法配置不启动。 |
| S1-03 | 生成真实静态 RISC-V ELF | 首版明确调用固定 SDK 的 clang/ld.lld 编译 LLVM IR 并链接入口和脚本。记录 target、ABI、features 和未解析符号。 | S1-02 | ELF、符号/段信息及最小元数据 | ELF32/小端/RISC-V、ISA 属性、ABI、入口和 PT_LOAD 正确；初期静态链接，未解析 helper、动态重定位或未支持指令必须诊断。 |
| S1-04 | 建立 AOT 镜像打包 | 宿主按加载段打包，显式约定 p_vaddr/p_paddr 的使用；检查文件范围、filesz<=memsz、地址加法溢出、段权限、对齐、重叠和 BSS 零填充。 | S1-03 | 来源可追踪的启动镜像与 manifest | 损坏/截断 ELF、越界或重叠加载段、区域不匹配及入口不在合法代码区均被拒绝；保存 ELF 与加载段哈希。 |
| S1-05 | 接通真实 core0 执行 | 控制 CPU 装载、初始化参数/完成状态并启动 core0。定义每次提交的序号和完成匹配；依据实际核能力确认代码装载后的取指可见性。 | S1-04 | 真实 AOT 执行入口 | 连续运行不同代码和输入正确；旧完成标志不能使新调用提前结束，trap/超时有诊断，未确认停止的核不能被直接复用。 |
| S1-06 | 验收第一个端到端 | 运行拷贝与加一，改变输入及源码并检查独立参考、输出保护区和实际执行证据。 | S1-05 | G1 单核闭环报告 | AST/TTIR、LLVM IR、ELF、加载镜像及数值结果完整对应；编译成功或存在字节 payload 不算通过。 |

建议代码位置：

- **S1-01**：lib/Conversion/MinimalTritonToLLVM；triton_coral.cc。
- **S1-02**：runtime/start.S；入口 wrapper。
- **S1-03**：backend/compiler.py；runtime/link.ld。
- **S1-04**：AOT 打包工具；控制固件生成器。
- **S1-05**：控制固件；仿真执行桥。
- **S1-06**：AOT 数值回归与报告。

## S2 基本 Triton block 语义

出口：**G2**。arange、mask、program_id 和一核顺序多 program 正确。

本阶段范围：先用正确的标量循环；不扩展任意 gather/scatter、浮点或原子操作。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S2-01 | 支持 block 与基本张量操作 | 将有限 block 子集正确降低为标量循环，保持 tensor SSA 的加载、计算、写回顺序；仅在证明无依赖时融合循环，不按元素交错执行改变别名语义。 | S1-06 | 基本 block 语义 | 先支持不相交 buffer 和已验证的原地计算；部分重叠访问须保持源语义或明确诊断，不能把标量循环结果错误归因于 Triton。 |
| S2-02 | 实现真正受保护的 masked 访存 | mask 控制实际 load/store，保留 other 和尾部语义。对无法支持的访问明确拒绝，不扩大访存范围。 | S2-01 | mask 与边界转换 | 全假 mask 不访存，other 显式给值时精确保持；未给 other 的无定义 lane 不能擅自当零或参与有效输出，尾部和保护区受检。 |
| S2-03 | 支持逻辑 program 与顺序 grid | 将 program_id/num_programs 读取到 ABI，先支持 1D grid，由 core0 顺序执行多个 program。 | S2-02 | 多 program 单核启动 | grid 大于物理核数仍正确；核号不替代逻辑 ID，参数更新与前次执行完成有序。 |
| S2-04 | 验收基本 Triton 程序 | 测试 N=1/3/37/128/1000、多个 BLOCK 与 grid。N=0 使用 grid=1 验证全假 mask。按实际容量放置输入输出。 | S2-03 | G2 语义回归报告 | 增加边界整数、全假/混合 mask、合法原地及重叠策略测试；N=0 与零 grid 是不同情况，零 grid 的 API 行为在 S3 单独定义。 |

建议代码位置：

- **S2-01**：MinimalTritonToLLVM；基础转换模式。
- **S2-02**：基础访存转换及测试。
- **S2-03**：kernel 参数；控制 runtime。
- **S2-04**：源程序、pytest 与 RTL 回归。

## S3 标准 JIT 与运行接口

出口：**G3**。通过 `kernel[grid](...)` 完成编译、参数封装、执行和取回结果。

本阶段范围：可继续复用冷启动仿真桥；不要求 PyTorch 完整设备适配和常驻 mailbox。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S3-01 | 实现真实 driver 和 launcher 接口 | 按本地 CompiledKernel 实际调用链补齐启动、设备/串行 stream 及装载接口。明确激活 Coral，移除无条件激活和伪零计时。 | S2-04 | 能够执行的 driver | 明确首次调用、重复调用及零 grid 的行为；启动路径不依赖 CUDA。冷启动计时和 kernel 设备周期分别报告，未计入完成等待的时间不作执行耗时。 |
| S3-02 | 提供设备 buffer 与显式拷贝 | 提供设备分配、合法范围、region/owner、参数打包和结果取回；初期以共享 SRAM 为主，不要求完整 Torch 设备适配。 | S3-01 | 设备 buffer 接口与参数布局 | buffer 的范围、别名 view、生命周期和 owner 明确；执行中的参数/输出在确认完成或恢复前不能释放复用，禁止宿主指针或失效 buffer 启动。 |
| S3-03 | 接通 JIT 调用与缓存 | 支持 `kernel[grid](...)` 的常量/运行参数。复用已有 AOT 仿真桥也可形成首版 JIT；缓存绑定 LLVM、补丁、ABI、代码生成及目标配置。 | S3-02 | 可调用的 JIT 及正确缓存 | 相同配置可命中，配置变化能失效；源码和输入变化产生正确结果。冷启动开销如实记录。 |
| S3-04 | 验收标准 JIT 闭环 | 覆盖重复调用、常量特化、数据变化、缓存、错误、超时与计时；和 AOT 参考交叉核对。 | S3-03 | G3 JIT 验收报告 | 用户从 Triton 调用即可得到真实结果；不会把只有 compile() 的测试写成 JIT 执行通过。 |

建议代码位置：

- **S3-01**：backend/driver.py；launcher。
- **S3-02**：runtime buffer API；仿真桥。
- **S3-03**：backend/compiler.py；driver；metadata。
- **S3-04**：JIT/运行时回归。

## S4 Ascend TTS 与 Linalg

出口：**G4**。已支持用例迁移到结构化流水线，JIT 与 AOT 结果均保持正确。

本阶段范围：这时才选择并适配 Ascend TTS 提交；不导入整套 CANN/HIVM 后端。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S4-01 | 选择并适配 Ascend 版 TTS | 先以最小兼容性试验固定 Ascend 来源，列出需移植的 TTS、分析、接口和 LLVM 24 差异；保留授权信息。适配成本超出预定范围时先收敛子集，G1/G3 正确基线不回退。 | S3-04 | 可构建的 Ascend TTS 子集 | 注册、parse/print、verifier 和最小 pass 通过。来源不等同微软另一版本。 |
| S4-02 | 实现规则指针结构分析 | 识别 base、offset、stride、shape 和连续维，保持逻辑 buffer 身份；先支持已验收源程序，再加规则 2D 访问。 | S4-01 | 结构化访问结果 | 连续、stride、广播和边界正确；无法分析的访问有明确 fallback 或错误。 |
| S4-03 | 处理循环携带结构状态 | 借鉴 get_structured_state 及循环状态传递，处理 scf.for 回边、合流和 offset/stride。明确 index 与 TTIR 固定宽度整数区别。 | S4-02 | 可验证的循环地址转换 | 多轮循环地址正确；RV32 类型转换不会静默截断或丢失 stride；最终占位状态可消除。 |
| S4-04 | 接入 Linalg/Tensor 计算 | 将逐元素、广播、形状和基础整数归约映射到标准结构化操作。保留 mask 和 load/store 的真实边界。矩阵扩展留到 S8。 | S4-03 | 结构化计算 IR | 索引图、形状、初值和 signedness 正确，已验收用例在新路径保持语义。 |
| S4-05 | 完成优化、Bufferization 与 LLVM 降低 | 先做必要 tensor 变换，再 Bufferization 或使用已选 buffer 语义路径。处理 alias、容量、生命周期、index/data layout 和合法性。 | S4-04 | 可生成 ELF 的结构化流水线 | 无错误复用和容量越界，接口模型齐全，最终没有无法导出 LLVM 的 tt/tts/linalg 残留。 |
| S4-06 | 迁移并统一主流水线 | 对 S1/S2/S3 用例做新旧路径差分。最小路径仅作短期参考；覆盖一致后统一主线，停止扩张旧路径并移除冗余。 | S4-05 | G4 结构化主线报告 | 已有 AOT/JIT、mask、原地与错误用例在新路径通过；收敛标准是全部已声明支持项覆盖，旧最小路径随后移除，不能无限期双线维护。 |

建议代码位置：

- **S4-01**：Dialect/TritonStructured；适配记录。
- **S4-02**：Analysis/PtrAnalysis；TritonToStructured。
- **S4-03**：TritonToStructured；SCF 模式。
- **S4-04**：Conversion/TritonToLinalg。
- **S4-05**：Pipelines；Bufferization；标准 LLVM 转换。
- **S4-06**：backend stages；lit/pytest/RTL 回归。

## S5 单核 RVV

出口：**G5**。结构化流水线生成实际 RVV 指令，向量与归约结果正确。

本阶段范围：RVV 正式 lowering 只在结构化主线实现一次。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S5-01 | 实现目标宽度向量化 | 在结构化主线对 Linalg/Vector 做 strip mining 和合法化。BLOCK 与目标 VLEN 分开，处理 VL、mask、对齐与尾部。 | S4-06 | 真实 RVV kernel | 反汇编存在 RVV 运算及所需配置指令；大 BLOCK 仍正确，不能仅靠 LLVM IR 中的 vector 类型验收。 |
| S5-02 | 实现核内整数向量归约 | 支持已声明的整数 sum 等归约及必要重排；保留初值、扩展、尾部和溢出约定。浮点模式另行验收。 | S5-01,S4-04 | 核内归约实现 | 多个长度与独立参考一致，源程序不含隐式跨核协作或非法 lane-varying 标量。 |
| S5-03 | 验收单核 RVV 主线 | 比较标量参考与 RVV 结果，记录实际指令、资源、数值、AOT/JIT 和错误回归。 | S5-02 | G5 RVV 报告 | 正确性、指令和资源检查通过；当前 VLEN=128 为目标配置实例，不能宣称任意 VLEN 已执行验证。 |

建议代码位置：

- **S5-01**：Transforms/Vectorize；LLVM lowering。
- **S5-02**：归约与 RVV 转换。
- **S5-03**：单核 RVV 回归。

## S6 参数化多核调度

出口：**G6**。同一组逻辑 program 在当前可用核子集上正确执行。

本阶段范围：先用共享全局地址；不把多核完成与 DMA 局部化绑定。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S6-01 | 实现参数化可用核配置 | 将早期接口约定落实为目标配置和 placement 校验。区分物理核数、可用掩码、逻辑 grid 与 region 访问权限。 | S5-03 | 可配置的多核目标 | 当前实际 1/2/4 核子集可选，不能向不存在的核发任务；未来 N 核只能先做静态规划校验。 |
| S6-02 | 实现 coral_rt 控制方言与计划 | 这时才建立 launch/dispatch/join 等必要自定义控制语义，并降低到控制 CPU 的任务/事件调用；沿用早期 manifest 的版本化约定。 | S6-01 | 多核 Launch Plan | 核内代码与控制计划作用域清楚；逻辑任务、placement、失败与完成事件可验证。 |
| S6-03 | 实现调度、参数隔离和有界队列 | 先让各核访问共享全局数据。每核独立参数和 scratch；按现有 32 任务、64 事件及最多两个直接前驱推进和回收。 | S6-02 | 共享地址上的并发启动 | 长 grid 不耗尽事件；每核镜像身份、参数、scratch 与提交序号独立；换 kernel 等待核空闲及装载可见，旧完成不能误完成新任务。 |
| S6-04 | 验收多核语义 | 对照 core0 顺序和多核执行，覆盖 grid 小于/大于核数、重复启动、不同分配、异常、超时及多维 grid 扩展。 | S6-03 | G6 多核报告 | 任务无遗漏重复，私有隔离及共享可见性正确；不隐式添加所有 program 参与的全局 barrier。 |

建议代码位置：

- **S6-01**：TargetSpec；runtime 配置。
- **S6-02**：Dialect/CoralRT；Runtime lowering。
- **S6-03**：控制固件 scheduler；队列适配。
- **S6-04**：多核数值及调度回归。

## S7 DMA 与多级存储

出口：**G7**。HBF/DRAM/SRAM/DTCM 的显式搬运、计算和回写正确。

本阶段范围：先使用单缓冲和现有互斥规则，不抢先放宽同核 DMA/kernel 互斥。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S7-01 | 实现 coral_mem 与区域资源模型 | 落实 HBF、DRAM、共享 SRAM、各核 DTCM/ITCM 的 owner、容量、权限、对齐和可达路径。新增真正需要的存储/view/copy 语义。 | S6-04 | 显式分层 buffer 与搬运契约 | HBF 写、非法私有 owner、容量超限和不存在的路径被拒绝；物理地址映射不等同 LLVM 地址空间编号。 |
| S7-02 | 生成 tile 访问范围与局部布局 | 分析连续范围、stride、mask、对齐、alias 和生命周期，分配局部副本并改写 tile 内索引，保留全局 tensor 身份。 | S7-01,S4-02 | 静态内存和访问计划 | 参数、栈、scratch、数据容量不重叠；局部指针不会重复加 program 偏移，尾部不扩大越界访问。 |
| S7-03 | 降低 DMA、依赖与完成可见性 | 按实际 DMA 的 4B 对齐、不重叠、单通道和单 beat 约束生成 NC_COPY/NC_KERNEL 及事件。必要的多前驱依赖显式合并。 | S7-02,S6-03 | 可执行的搬运与计算计划 | 消费者等待可见完成；读写失败报告已完成字节和错误任务，输出可能部分写入，不承诺回滚。重试只在证明幂等或重新初始化后允许。 |
| S7-04 | 先验证一核多层搬运 | 先执行 HBF 到 DRAM 再到核内 DTCM、计算、DRAM 回写的显式单缓冲路径。共享 SRAM 仅按需要参与，其他路径以后按能力选择。 | S7-03 | 一核多层存储报告 | HBF 零写入，DRAM 只存储；staging、局部计算及回写逐项正确，容量/边界/权限错误可诊断。 |
| S7-05 | 再验证多核多层搬运 | 在已有一核正确路径上增加分片和核归属。测试长任务图、共享 DMA 争用、私有区、buffer 复用、失败和背压。 | S7-04,S6-04 | G7 分层存储报告 | 加入搬运中途错误、依赖失败和超时；未确认总线/核停止前不复用 buffer、事件或代码。资源无法局部恢复时按明确的重置范围恢复并使旧句柄失效。 |

建议代码位置：

- **S7-01**：Dialect/CoralMem；region 规划。
- **S7-02**：AccessRange；PromoteToLocal；MemoryPlan。
- **S7-03**：CoralMemToRuntime；DMA 适配。
- **S7-04**：一核分层运行用例。
- **S7-05**：多核分层回归。

## S8 Zvt 与矩阵扩展

出口：**G8**。合法 Triton dot 形状映射到 Coral Zvt 子块并通过数值及指令验证。

本阶段范围：已有 16×16×4 微内核不直接视为合法 Triton 源形状；BF16/FP32 分别验收。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S8-01 | 接入合法 dot 与矩阵语义 | 核对当前 Triton 前端允许的 dot 形状和类型，再转 Linalg 矩阵操作并拆分为硬件子块。已有 K=4 微内核只作子块参考。 | S5-03,S4-04 | 前端可达的矩阵 IR | 输入 signedness、累加类型、K 分块和尾部正确，测试源程序符合本地前端约束。 |
| S8-02 | 实现 coral tile 计算方言 | 此时引入 coral.tile_mma 等确有目标语义的操作。首版可在 buffer 阶段匹配合法 tile；若前移到 tensor 阶段则补齐所需接口模型。 | S8-01 | 有 verifier 的 tile 操作 | 形状、布局、输入与累加类型、tile 状态及内存效果明确，不重复定义普通算术。 |
| S8-03 | 降低到已验证 Zvt 接口 | 核对固定 SDK 的真实 intrinsic 或微内核接口，处理装载、tile 状态、累加与输出。微内核调用路径与内联 lowering 分别记录。 | S8-02 | 真实 Zvt 目标代码 | 实际指令/派发证据匹配，副作用不会被优化器错误删除或重排。 |
| S8-04 | 验收矩阵执行 | 先在单核验证 INT8 到 INT32，再复用多核及分层路径。矩阵先按 M/N 输出分块，跨核归约另用显式阶段。 | S8-03,S7-05 | G8 Zvt 报告 | 逐项核对独立 INT64 参考、signedness、累加/溢出、矩阵布局、pack/transpose 和边界；布局转换成本纳入测量，INT8 通过不推广到其他类型。 |

建议代码位置：

- **S8-01**：TritonToLinalg；矩阵合法化。
- **S8-02**：Dialect/Coral；LinalgToCoral。
- **S8-03**：CoralToLLVM；Zvt 封装。
- **S8-04**：矩阵数值/指令回归。

## S9 重叠与性能优化

出口：**G9**。功能回归稳定，优化有可解释的周期及资源证据。

本阶段范围：双缓冲、更多类型及融合按需求扩展；模型延迟不代表物理带宽。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S9-01 | 建立可解释的性能基线 | 分别记录编译、启动、kernel、DMA、争用及控制周期和宿主仿真耗时。关联目标配置、源码、固件和二进制。 | S7-05 | 分项性能基线 | 报告编译、打包、仿真启动、装载、kernel 与回传的边界，按真实时间基准比较；模型周期和宿主耗时分开，不以虚构或未归一化计时宣称吞吐。 |
| S9-02 | 逐步实现重叠和双缓冲 | 先重叠不同核的搬运/计算；只有端口、buffer 不相交和生命周期有证明时，才放宽同核互斥或增加预取/双缓冲。 | S9-01 | 有证据的流水线优化 | 不覆盖仍在消费的 buffer，不超发 DMA；每次优化同时给出正确性和周期证据。 |
| S9-03 | 按需求扩展算子与类型 | 在稳定主线上逐项加入融合 epilogue、卷积、更多类型及非规则访问；每项明确所需硬件能力与独立数值规则。 | S9-02,S8-04 | 逐项支持清单及 G9 报告 | 有转换、目标代码和数值证据，未验证能力保持明确边界，不以更换后缀或宿主代算替代。 |

建议代码位置：

- **S9-01**：profiling；回归报告。
- **S9-02**：资源调度；生命周期；队列锁粒度。
- **S9-03**：Linalg 扩展；Coral 转换；数值测试。

## 统一验收与推进规则

1. 每个阶段都有实际可观察的出口；编译、数值、资源和异常结果分别记录。未通过本阶段验收，不为追求方言数量而扩张范围。
2. G1 验证 AOT，G3 验证标准 JIT；G5 再验证实际 RVV。每个“通过”都对应真实执行或明确标注的静态检查。
3. 首版以 INT32 及必要的 i1 mask 为主要支持范围。i64、浮点、原子、任意 gather/scatter 和完整 Torch 设备集成逐项定义与验收。
4. 部分多核或存储变化只需重新规划；影响 tile、布局或目标指令的变化需要重新生成 kernel，并更新缓存身份。
5. 记录源码、工具链/补丁、ABI、IR、ELF、控制镜像、配置和输出的来源关系。单个成功固定样例不能代替变化输入、尾部和失败用例。
6. 修改 Triton 编译器时遵守其仓库 AGENTS.md：修改 native/compiler 后先在 Triton 根目录运行 make，再执行相应 lit/pytest；仅 Python 修改按规则选择检查。pytest 使用 -s --tb=short。执行前核对仓库最新说明，IR 用例保持前端可达，优先扩展已有测试文件。
7. 核数、存储容量、DMA 并发和可见性按实际硬件能力验收；当前单通道与同核 DMA/kernel 互斥不能凭计划自行取消。
8. 不预设日历工期。每完成一个出口更新任务状态及下一阶段工作量；先把 G1 跑通，再估计后续迁移成本。

## 实现基线

实现起点采用 2026-11-17 的核查记录：triton-coral 为 dev/triton-coral 的 4f045a9d77；Coral 原型为 dev/ncoral-hbf-3dpim 的 f9ab975c。进入 S0 时复核当前工作树和工具链；已有骨架与硬件演示不代表本计划的端到端任务已经完成。

任务状态与实现证据持续更新在 [plan.json](plan.json) 和 [tasks.xlsx](tasks.xlsx) 中。后续修改直接更新本文件，不另建日期或版本副本。

## 官方参考

- [Ascend 版 TTS 定义](https://github.com/triton-lang/triton-ascend/blob/main/third_party/ascend/include/Dialect/TritonStructured/IR/TritonStructuredDialect.td)
- [Ascend 编译链说明](https://github.com/triton-lang/triton-ascend/blob/main/docs/en/architecture_design_and_core_features.md)
- [AscendNPU-IR 架构](https://github.com/Ascend/AscendNPU-IR/blob/master/docs/source/en/introduction/architecture.md)
- [MLIR 到 LLVM](https://mlir.llvm.org/docs/TargetLLVMIR/)
- [MLIR Bufferization](https://mlir.llvm.org/docs/Bufferization/)
- [MLIR Linalg](https://mlir.llvm.org/docs/Dialects/Linalg/)

- [LLVM 整数语义](https://llvm.org/docs/LangRef.html#add-instruction)

- [RISC-V 调用及 ELF ABI](https://riscv-non-isa.github.io/riscv-elf-psabi-doc/)
