# LLVM HIP 支持 Vortex

更新日期：2026-11-18（Asia/Shanghai）。本目录是该主题的持续维护入口，分支为 `dev/codex-docs`。后续修改直接更新下面的固定文件，变更历史通过 Git 提交查看。

## 已确定的方案

基于 LLVM 23.1.4，复用 RISCV Target，增加初版 RV64 的 `-mcpu=vortex` CPU/subtarget 和 `xvortex` 指令扩展；实现 Vortex SIMT、kernel ABI、Clang HIP 编译接入，以及对接 Vortex SDK 的独立原生 HIP runtime。以 SimX 为执行验收端。

这是供你实现的教程与计划。官方现有 chipStar/SPIR-V/PoCL HIP 路径作为对照，新 LLVM 的原生 HIP 子集需要按任务逐步实现，不能把参考路径的通过记录算成新后端通过。

## 固定文档目录

| 文件 | 内容 |
|---|---|
| [architecture.md](architecture.md) | 架构、CPU/ISA/ABI 职责、选项组合、源码落点及 Vortex 指令集 |
| [plan.md](plan.md) | 官方源码分析、11 阶段路线、里程碑、最终程序和支持边界 |
| [tasks.md](tasks.md) | 66 个详细任务：阅读、练习、验收、交付与排查 |
| [getting-started.md](getting-started.md) | T00 基线任务的具体命令和 ABI 阅读练习 |
| [build.md](build.md) | 现有 LLVM 分支和 build.sh 的使用说明 |
| [compiler-sim-contract.md](compiler-sim-contract.md) | 编译产物、启动、参数布局与 SimX 的接口 |
| [evidence-template.md](evidence-template.md) | 任务记录与验证证据模板 |
| [AGENTS.md](AGENTS.md) | 本主题的原地维护、状态保留和提交规则 |

## 学习顺序与最终成果

`T00 基线 → T01 CPU/subtarget → T02 特殊指令 → T03 IR/线程语义 → T04 native kernel → T05 SIMT → T06 runtime → T07 HIP device → T08 HIP 全链路 → T09 shared/barrier → T10 原子/stream/event/交付`

先阅读架构和计划，再按 tasks.md 一次推进一个小任务。完成 T08 后的目标是由新 LLVM 编译带 `__global__`、`hipMalloc`、`hipMemcpy` 和 `<<<>>>` 的 vecadd/SAXPY，通过原生 runtime 在 SimX 正确执行；后续增加 reduction、tiled SGEMM，以及匹配配置下的 histogram 和 stream/event 依赖示例。

认识设备指令时先读 [Vortex 指令集与 SIMT 执行模型](architecture.md#vortex-isa)：标准扩展、warp 控制、CSR、32 位编码与参考 llvm-mc 验证均在同一节持续维护。

完整 HIP 兼容、RV32、跨文件 device linking、真实硬件部署和大型应用移植属于后续专题。计划中的“能够支持”与已记录的“实际通过”分别维护。

## 使用与维护

- 文档中的 `/home/kaikai/vortex-word` 是已有 WSL 环境路径；其版本与构建状态是带日期的本机基线，其他机器应调整路径并重新验证。
- 本目录保存文档，不包含 LLVM/Vortex 源码、预编译工具链和已有 WSL 辅助脚本；命令依赖这些组件已按环境说明准备。
- 架构调整更新 architecture.md；阶段/成果更新 plan.md；任务范围/依赖/验收更新 tasks.md；涉及起步命令时同步 getting-started.md 和 build.md。
- 不创建 `v2`、`final`、按日期命名的重复计划或备份；任务 ID、状态和执行证据保留。提交前检查链接、任务编号和相关文档一致性。

返回 [Codex 文档目录](../README.md)。
