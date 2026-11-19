# Codex 文档目录

文档按主题放在固定目录中。后续修改直接更新原文件，版本和修改记录通过 Git 历史查看。

| 主题 | 实施计划 | 结构化数据 | 任务表 |
| --- | --- | --- | --- |
| Triton 支持 Coral | [plan.md](triton-coral/plan.md) | [plan.json](triton-coral/plan.json) | [tasks.xlsx](triton-coral/tasks.xlsx) |
| LLVM HIP 支持 Vortex | [plan.md](llvm-hip-vortex/plan.md) | — | [tasks.md](llvm-hip-vortex/tasks.md) |

Triton Coral 从已搭建的后端骨架开始。第一次跑样例请打开[教程入口](triton-coral/plan.md#第一次运行)，接着按[标量单核闭环](triton-coral/backend-skeleton.md)完成首个真实 AOT。S0–S9 各课都有代表用例、观察点和验收信号。回看 CMake、nanobind 与 Python 注册时读[骨架课](triton-coral/tutorials/01-backend-skeleton.md)。

LLVM HIP/Vortex 由 `store42` 逐步推进到普通 HIP vecadd 和已有程序移植。六个大阶段覆盖 28 个小阶段，每步说明目标、测试和实现注意点，并按完成范围回填 66 项工程任务。[教程目标与验收](llvm-hip-vortex/plan.md#stage-goals) · [完整 L01 命令](llvm-hip-vortex/getting-started.md) · [固定 HIP 输入](llvm-hip-vortex/examples/l01/) · [观察脚本](llvm-hip-vortex/examples/run_l01.py)

## 更新方式

1. 在已有主题目录修改文档，不新建按日期或版本号命名的副本。
2. Triton Coral 修改任务、依赖或验收时，同步该主题的 `plan.md`、`plan.json` 和 `tasks.xlsx`；LLVM HIP/Vortex 同步其架构、计划、任务及相关命令文档。
3. Triton Coral 任务状态以 `plan.json` 为准；各主题保留既有 ID、进度和验收证据。Excel 中的离线状态修改应先核对回写。
4. 检查相对链接及数据一致性，再提交到 Git。

具体协作规则见 [AGENTS.md](AGENTS.md)。
