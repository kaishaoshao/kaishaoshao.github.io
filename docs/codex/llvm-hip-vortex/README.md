# LLVM HIP 支持 Vortex

更新日期：2026-11-19（Asia/Shanghai）。本目录是该主题的持续维护入口，分支为 `dev/codex-docs`。后续修改直接更新下面的固定文件，变更历史通过 Git 提交查看。

## 已确定的方案

基于 LLVM 23.1.4，复用 RISCV Target，增加初版 RV64 的 `-mcpu=vortex` CPU/subtarget 和 `xvortex` 指令扩展；实现 Vortex SIMT、kernel ABI、Clang HIP 编译接入，以及对接 Vortex SDK 的独立原生 HIP runtime。以 SimX 为执行验收端。

这是供你实现的教程与计划。学习从一个最小 HIP 程序的语法、AST 和 IR 开始，硬件/后端能力按需要引入。官方现有 chipStar/SPIR-V/PoCL HIP 路径作为对照，不能把参考路径的通过记录算成新后端通过。

## 固定文档目录

| 文件 | 内容 |
|---|---|
| [tutorial.md](tutorial.md) | 教程总览、定位作用、六阶段演进路线与文档查阅指南 |
| [architecture.md](architecture.md) | 架构、CPU/ISA/ABI 职责、选项组合、指令集、实现边界与冻结点 |
| [plan.md](plan.md) | 六个大阶段与 28 个小阶段，含各步目标、测试、实现注意点和源码入口 |
| [tasks.md](tasks.md) | 保留的 66 项工程验收任务及课程映射，不作为入门阅读顺序 |
| [getting-started.md](getting-started.md) | 完整 L01：属性/AST、调用反例、启动表达式与设备 IR；附录为 T00 |
| [build.md](build.md) | 区分 LLVM 与 Vortex 两个 build.sh，工具状态、构建与验证范围 |
| [compiler-sim-contract.md](compiler-sim-contract.md) | 编译产物、两个启动 PC、native/HIP 参数布局与 SimX 的接口 |
| [evidence-template.md](evidence-template.md) | 任务记录与验证证据模板 |
| [examples/l01/](examples/l01/) | 固定的四份 HIP 观察输入 |
| [examples/run_l01.py](examples/run_l01.py) | 运行 L01 观察，保存版本、命令、结果与输入指纹 |
| [examples/check_docs.py](examples/check_docs.py) | 检查链接、任务/阶段编号、依赖和输入一致性 |
| [AGENTS.md](AGENTS.md) | 本主题的原地维护、状态保留和提交规则 |

## 怎么使用这套教程

第一次开始时只读 [L01 操作页](getting-started.md#lesson-1)，不必先读完架构契约。完成一个小实验，保存观察，再读 [plan.md](plan.md#tutorial-route) 中下一步的源码入口/改动/验收。需要 ABI/指令细节时才查 architecture.md 和 compiler-sim-contract.md；tasks.md 用于回填工程验收。

你已提交的 LLVM L01 实验保留，新 Clang 23 与参考 Clang 20 的标准前端观察也有记录，见 [进度与证据](plan.md#03-已核对的教学实验与证据边界)。可以先核对自己的理解，再进入 [L02 的第一个改动](plan.md#l02)。课程号和实验编号组织学习；T00～T10/66 项是验收账本，不另建互相冲突的 JSON/Excel 状态表。

所有命令分成“当前可运行的观察/构建”和“实现后的目标验证”。尚未实现的后端、host 入口与元数据不写成现有命令；前端检查 PASS、手工桥接执行和自动 HIP 执行分别记录。

## 学习顺序与最终成果

`L01 HIP 前端 → L02 Vortex 编译入口 → L03 store42 执行 → L04 带边界 vecadd → L05 普通 HIP 全链路 → L06 已有程序移植`

先看六个大阶段的目标和验收，再打开要做的小阶段。每个小阶段先说明目标，再列出测试输入、预期信号和实现注意点。完成后按覆盖范围回填原有 T00～T10 的 66 项工程任务。[大阶段目标与验收](plan.md#stage-goals) · [工程任务账本](tasks.md#task-dependencies)

L03 就在 SimX 读回 store42 的 42（允许明确标记的教学桥接）；L05 由新 LLVM 自动编译并通过原生 runtime 执行普通 HIP vecadd；L06 移植固定来源的已有 HIP 程序。shared、原子、stream/event 等按目标程序需要补齐，不是首个移植结果的全部前置。

后端从 L02 就开始改，第一条练习为 TMC 的 MC 支持；L04 接通线程标识和必要的分歧控制自动生成。具体时点与各层验收见 [后端接入表](plan.md#backend-timing)。

认识设备指令时先读 [Vortex 指令集与 SIMT 执行模型](architecture.md#vortex-isa)：标准扩展、warp 控制、CSR、32 位编码与参考 llvm-mc 验证均在同一节持续维护。

学到对应层次时查阅 [实现边界与契约](architecture.md#implementation-contracts) 及 [审阅/验收矩阵](plan.md#implementation-review)：两个 PC、SIMT、包装头/设备库、参数、错误和生命周期分别展开；第一课不要求先消化整个工程清单。

完整 HIP 兼容、RV32、跨文件 device linking、真实硬件部署和更大型应用移植属于后续专题；首个已有小程序的移植在 L06 开始。计划中的“能够支持”与已记录的“实际通过”分别维护。

## 容易混淆的三个判断

- IR 有 store i32 42：只证明生成了普通设备计算；它本来不必含 SIMT 指令。逻辑 kernel、native wrapper 和启动链见 [桥接关系](architecture.md#hip-ir-bridge)。
- Vortex 支持 RV32/RV64 标准组合：不表示当前构建启用所有扩展，也不表示新 CPU 第一版必须同时支持两种位宽。参考参数含 A 与 SimX 默认关闭 A 的差异见 [ISA 配置](architecture.md#isa-config)。
- 参考 SimX/chipStar 样例通过：不等于新 LLVM 原生 HIP 已通过；每份报告标清工具、库和镜像来源。

## 使用与维护

- 文档中的 `/home/kaikai/vortex-word` 是已有 WSL 环境路径；其版本与构建状态是带日期的本机基线，其他机器应调整路径并重新验证。
- 本目录保存教程和小型观察输入/检查脚本，不包含完整 LLVM/Vortex 源码、预编译工具链或本机辅助脚本；命令依赖这些组件已准备。生成日志、IR 和 report.json 放在 WSL artifacts，不提交到文档目录。
- 架构调整更新 architecture.md；阶段/成果更新 plan.md；任务范围/依赖/验收更新 tasks.md；涉及起步命令时同步 getting-started.md 和 build.md。
- 不创建 `v2`、`final`、按日期命名的重复计划或备份；任务 ID、状态和执行证据保留。提交前检查链接、任务编号和相关文档一致性。

返回 [Codex 文档目录](../README.md)。
