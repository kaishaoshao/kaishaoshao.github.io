# Codex 文档目录

文档按主题放在固定目录中。后续修改直接更新原文件，版本和修改记录通过 Git 历史查看。

| 主题 | 实施计划 | 结构化数据 | 任务表 |
| --- | --- | --- | --- |
| Triton 支持 Coral | [plan.md](triton-coral/plan.md) | [plan.json](triton-coral/plan.json) | [tasks.xlsx](triton-coral/tasks.xlsx) |
| LLVM HIP 支持 Vortex | [教程目录](llvm-hip-vortex/tutorial.md) · [实施计划](llvm-hip-vortex/plan.md) | — | [tasks.md](llvm-hip-vortex/tasks.md) |

Triton Coral 从已搭建的后端骨架开始。第一次跑样例请打开[教程入口](triton-coral/plan.md#第一次运行)，全景路线图参考[教程总览](triton-coral/tutorial.md)，接着按[标量单核闭环](triton-coral/tutorials/ch02-scalar-single-core/01-empty-kernel-pass.md)完成首个真实 AOT。S0–S9 各课都有代表用例、观察点和验收信号。回看 CMake、nanobind 与 Python 注册时读[骨架课](triton-coral/tutorials/ch01-skeleton/01-toolchain-discovery.md)。

LLVM HIP/Vortex 按六章、29 节小课展开。从观察 HIP 前端起步，接通 Vortex 编译入口，让 `store42` 在 SimX 上执行，再做多线程 vecadd、自动 HIP 启动和已有程序移植。[全书目录](llvm-hip-vortex/tutorial.md) · [第 1 章实验](llvm-hip-vortex/chapters/01-hip-frontend/README.md)

## 更新方式

1. 在已有主题目录修改文档，不新建按日期或版本号命名的副本。
2. Triton Coral 修改任务、依赖或验收时，同步该主题的 `plan.md`、`plan.json` 和 `tasks.xlsx`；LLVM HIP/Vortex 同步其架构、计划、任务及相关命令文档。
3. Triton Coral 任务状态以 `plan.json` 为准；各主题保留既有 ID、进度和验收证据。Excel 中的离线状态修改应先核对回写。
4. 检查相对链接及数据一致性，再提交到 Git。

具体协作规则见 [AGENTS.md](AGENTS.md)。
