# LLVM HIP 支持 Vortex

更新日期：2026-11-18（Asia/Shanghai）。本目录是该主题的持续维护入口，分支为 `dev/codex-docs`。后续修改直接更新下面的固定文件，变更历史通过 Git 提交查看。

## 已确定的方案

基于 LLVM 23.1.4，复用 RISCV Target，增加初版 RV64 的 `-mcpu=vortex` CPU/subtarget 和 `xvortex` 指令扩展；实现 Vortex SIMT、kernel ABI、Clang HIP 编译接入，以及对接 Vortex SDK 的独立原生 HIP runtime。以 SimX 为执行验收端。

这是供你实现的教程与计划。学习从一个最小 HIP 程序的语法、AST 和 IR 开始，硬件/后端能力按需要引入。官方现有 chipStar/SPIR-V/PoCL HIP 路径作为对照，不能把参考路径的通过记录算成新后端通过。

## 固定文档目录

| 文件 | 内容 |
|---|---|
| [architecture.md](architecture.md) | 架构、CPU/ISA/ABI 职责、选项组合、指令集、实现边界与冻结点 |
| [plan.md](plan.md) | 从语法到执行的十课主线、源码分析、工程分组与最终成果 |
| [tasks.md](tasks.md) | 保留的 66 项工程验收任务及课程映射，不作为入门阅读顺序 |
| [getting-started.md](getting-started.md) | 第 1 课的可执行命令；附录保留 T00 构建/ABI 基线 |
| [build.md](build.md) | 现有 LLVM 分支和 build.sh 的使用说明 |
| [compiler-sim-contract.md](compiler-sim-contract.md) | 编译产物、两个启动 PC、native/HIP 参数布局与 SimX 的接口 |
| [evidence-template.md](evidence-template.md) | 任务记录与验证证据模板 |
| [AGENTS.md](AGENTS.md) | 本主题的原地维护、状态保留和提交规则 |

## 学习顺序与最终成果

`L01 语法/AST → L02 语义/启动表达式 → L03 设备 IR → L04 最小编译器改动 → L05 单线程 SimX → L06 多线程/builtins → L07 分歧控制流 → L08 HIP 全链路 → L09 block 协作 → L10 扩展与交付`

先做 [第 1 课](getting-started.md#lesson-1)，再按 [十课课程](plan.md#tutorial-route) 一次推进一个程序变化。每课包含问题、最小输入、机制、命令、自己完成的小改动和验收；原有 T00～T10/66 项作为工程账本保留状态。

L08 的目标是由新 LLVM 编译带 `__global__`、`hipMalloc`、`hipMemcpy` 和 `<<<>>>` 的 vecadd/SAXPY，通过原生 runtime 在 SimX 正确执行；后续增加 reduction、tiled SGEMM，以及匹配配置下的 histogram 和 stream/event 依赖示例。

认识设备指令时先读 [Vortex 指令集与 SIMT 执行模型](architecture.md#vortex-isa)：标准扩展、warp 控制、CSR、32 位编码与参考 llvm-mc 验证均在同一节持续维护。

学到对应层次时查阅 [实现边界与契约](architecture.md#implementation-contracts) 及 [审阅/验收矩阵](plan.md#implementation-review)：两个 PC、SIMT、包装头/设备库、参数、错误和生命周期分别展开；第一课不要求先消化整个工程清单。

完整 HIP 兼容、RV32、跨文件 device linking、真实硬件部署和大型应用移植属于后续专题。计划中的“能够支持”与已记录的“实际通过”分别维护。

## 使用与维护

- 文档中的 `/home/kaikai/vortex-word` 是已有 WSL 环境路径；其版本与构建状态是带日期的本机基线，其他机器应调整路径并重新验证。
- 本目录保存文档，不包含 LLVM/Vortex 源码、预编译工具链和已有 WSL 辅助脚本；命令依赖这些组件已按环境说明准备。
- 架构调整更新 architecture.md；阶段/成果更新 plan.md；任务范围/依赖/验收更新 tasks.md；涉及起步命令时同步 getting-started.md 和 build.md。
- 不创建 `v2`、`final`、按日期命名的重复计划或备份；任务 ID、状态和执行证据保留。提交前检查链接、任务编号和相关文档一致性。

返回 [Codex 文档目录](../README.md)。
