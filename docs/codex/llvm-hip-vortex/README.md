# LLVM HIP 支持 Vortex

更新日期为 2026-11-20（Asia/Shanghai）。

[打开全书目录](tutorial.md) · [开始第 1 章](chapters/01-hip-frontend/README.md) · [直接运行第一个 ELF](chapters/03-store42/00-direct-elf.md)

教程基于 LLVM 23.1.4，复用 RISC-V Target，逐步加入初版 RV64 的 `-mcpu=vortex`、`xvortex`、SIMT、kernel ABI 和原生 HIP runtime。六章共 29 节小课，从观察 HIP 语法开始，最后用 SimX 验收一个已有 HIP 程序。

每章首页有学习目标、准备工作和验收条件。每节有独立页面和前后导航。L01 可按命令做实验，L02～L03 有源码与运行示例，L04～L06 目前提供逐节提纲和通过标准。

## 查阅资料

| 资料 | 用途 |
|---|---|
| [全书目录](tutorial.md) | 六章阅读顺序，每章下列出全部小课 |
| [架构与指令集](architecture.md) | CPU、ISA、SIMT、指令编码与实现边界 |
| [工程计划与证据](plan.md) | 阶段验收、后端接入时点、历史实验、目标程序 |
| [66 项工程任务](tasks.md) | T00～T10 的验收条件、依赖与课程映射 |
| [工具构建](build.md)与[T00 工程基线](getting-started.md#engineering-baseline) | 准备 LLVM、Vortex SDK 和 SimX |
| [编译器与 SimX 接口](compiler-sim-contract.md) | 设备镜像、两个启动 PC、SDK 参数与拟定 HIP 参数布局 |
| [记录模板](evidence-template.md) | 保存工具版本、命令、输入和结果 |
| [L01 夹具](examples/l01/)与[观察脚本](examples/run_l01.py) | 验证宏、AST、调用诊断与设备 IR |
| [文档检查脚本](examples/check_docs.py) | 检查导航、任务编号、依赖与输入一致性 |

看见 `store i32 42` 时，先区分设备函数体、逻辑 kernel 标记和 wrapper 入口。判断一份结果的验证范围时，同时记录使用的编译器、库和设备镜像。参考工具链、手工启动与自动 HIP 启动各有自己的验收记录。[桥接关系](architecture.md#hip-ir-bridge) · [历史证据](plan.md#03-已核对的教学实验与证据边界)

## 更新方式

文档中的 `/home/kaikai/vortex-word` 对应已有的 WSL 环境。换机器时调整路径，重新记录版本和运行结果。日志、IR 和报告写到 WSL 的 artifacts 目录。

课程正文在 `chapters/` 中按编号原地更新，工程任务和已有证据以固定资料页为准。提交到 `dev/codex-docs` 之前运行 `python3 examples/check_docs.py`。[维护约定](AGENTS.md)

[返回 Codex 文档目录](../README.md)
