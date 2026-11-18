# LLVM HIP/Vortex 文档维护约定

适用范围：本目录及其子目录。遵守上级约定；本文件补充本主题的固定文件和验收范围。

- 文档主线为 RISCV Target 内的 `-mcpu=vortex` CPU/subtarget、`xvortex` 扩展、SIMT/kernel ABI、Clang HIP 与独立 runtime。初版 RV64，以 SimX 验收。
- 后续同主题修改原地更新 README.md、architecture.md、plan.md、tasks.md、getting-started.md、build.md、compiler-sim-contract.md、evidence-template.md，不新增按日期/版本/会话命名的重复文档。
- 这些 Markdown 文件是本主题维护入口，不要求创建 Triton Coral 主题使用的 JSON/Excel 文件。
- 保持架构、阶段、任务依赖与验收一致；已有任务 ID、用户进度和证据不得因重新生成而重置。调整已有任务范围时说明需要复核什么。
- 用户希望学习实现，文档更新不自动授权实现编译器/runtime。示意命令和拟新增接口要标明尚未实现，计划不能写成测试通过。
- 教学主线按 plan.md 的 L01～L10，从 HIP 语法/AST/Sema/IR 的最小实验开始，按程序演进引入 Vortex 后端；不将先完成 CPU/MC 的工程清单重新变成第一课前置。保留 T00～T10/66 项作为工程验收账本，不重置原有进度。
- 区分参考 LLVM 20/chipStar 路径、新 LLVM 23 生成的设备代码、复用的设备库；区分 CPU 识别、MC/IR、镜像合法与 SimX 执行正确。
- 记录 host/device 目标隔离、mcpu/march/feature/ABI、实际硬件配置、O0/O2 与结果依据；不以 SimX 时间推断真实硬件性能。
- 日期使用 Asia/Shanghai；历史环境验证记录保留原日期，不能因文档更新改写成当天重新验证。
- 仅提交本主题及必要目录索引的修改，检查相对链接、任务 ID 唯一性、阶段依赖和 git diff；不夹带其他主题的工作或生成博客资源。
