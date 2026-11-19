# LLVM HIP/Vortex 文档维护约定

适用范围：本目录及其子目录。遵守上级约定；本文件补充本主题的固定文件和验收范围。

- 文档主线为 RISCV Target 内的 `-mcpu=vortex` CPU/subtarget、`xvortex` 扩展、SIMT/kernel ABI、Clang HIP 与独立 runtime。初版 RV64，以 SimX 验收。
- 后续同主题修改原地更新 README.md、architecture.md、plan.md、tasks.md、getting-started.md、build.md、compiler-sim-contract.md、evidence-template.md，不新增按日期/版本/会话命名的重复文档。
- 这些 Markdown 文件是本主题维护入口，不要求创建 Triton Coral 主题使用的 JSON/Excel 文件。
- 保持架构、阶段、任务依赖与验收一致；已有任务 ID、用户进度和证据不得因重新生成而重置。调整已有任务范围时说明需要复核什么。
- 用户希望学习实现，文档更新不自动授权实现编译器/runtime。示意命令和拟新增接口要标明尚未实现，计划不能写成测试通过。
- 教学主线按 plan.md 的六阶段 L01～L06：HIP 前端 → Vortex 编译入口 → store42 执行 → 带边界 vecadd → 普通 HIP 流程 → 已有程序移植。L02 开始修改后端，L03 就有执行结果；shared/原子/stream/event 等按程序需求补齐，不作为首个移植的全部前置。每阶段拆成小实验，不将完整 CPU/MC 工程组变成第一课前置。保留 T00～T10/66 项、状态和证据；旧课程号按 plan.md 第 0.4 节映射，不把旧 L06 观察记录写成新 L06 移植通过。
- 区分参考 LLVM 20/chipStar 路径、新 LLVM 23 生成的设备代码、复用的设备库；区分 CPU 识别、MC/IR、镜像合法与 SimX 执行正确。
- 记录 host/device 目标隔离、mcpu/march/feature/ABI、实际硬件配置、O0/O2 与结果依据；不以 SimX 时间推断真实硬件性能。
- 日期使用 Asia/Shanghai；历史环境验证记录保留原日期，不能因文档更新改写成当天重新验证。
- 仅提交本主题及必要目录索引的修改，检查相对链接、任务 ID 唯一性、阶段依赖和 git diff；不夹带其他主题的工作或生成博客资源。
- 每阶段写清问题、固定输入、源码入口、逐步操作、预期观察/错误、交付和下一步。L01 的完整命令集中在 getting-started.md，plan.md 组织实现步骤，architecture.md/接口契约作为按需参考，避免复制相互漂移的大段教程。
- examples/l01 的 HIP 夹具与 run_l01.py 仅验证前端观察，不实现 backend/runtime、不执行 GPU；结果存放于 WSL artifacts。check_docs.py 检查文档/任务/输入一致性；不提交生成日志/IR/report.json，也不新增重复的课程状态数据。
- 能力依赖以 tasks.md 的依赖表为准，不要求先完成所有 SIMT 才写 runtime，也不把 shared 全部完成作为原子/异步实验前置。保留既有任务 ID/状态，范围澄清注明受影响任务。
- 不把“缺少 Vortex native 入口契约”写成“IR 没有任何属性”；store42 不要求 SIMT 指令，通用 uniform-work-group-size 不能唯一标识 kernel。CPU 默认能力与实际配置匹配，明示参考 rv64imafd 含 A、默认 SimX A/C 关闭的差异。
