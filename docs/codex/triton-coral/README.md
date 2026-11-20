# 《Triton Coral 后端开发实战：从编译器骨架到硬件执行》全书目录

更新日期：2026-11-20（Asia/Shanghai）。

这是一套专为边缘 NPU/AI 芯片编译器开发者打造的实战教程，系统记录并教学如何在 OpenAI Triton 编译器体系下，从零实现 Google Coral Edge TPU / Coral NPU（RV32IMF_Zve32x + Zvt 矩阵加速扩展）的专用计算后端与执行运行时。

全书采用**“大课（章节）包含小课（小节）”**的书籍化结构，彻底摒弃生硬的工程代号，带你一步步打通从 Python 前端语法解析、MLIR 方言降级、C++ Pass 管道到硬件与仿真器真实执行的完整技术链路。

每个小章节均独立成文，包含：
1. **这节课做什么**（支持语法、涉及方言、实现注意）
2. **核心代码实现**（关键代码与补丁）
3. **解释说明与注释**（设计原理与底层机制）
4. **测试与验证代码**（可复现的简明断言与 lit 命令）

---

## 全书目录导航

### 第 1 章：验证 Triton 后端发现与 C++ 插件骨架（阶段 S0）
- [1.1 节：确认工具链、后端发现与 C++ 扩展](tutorials/ch01-skeleton/01-toolchain-discovery.md) `[已完成]`
- [1.2 节：约定 RV32 v2 参数与地址约定](tutorials/ch01-skeleton/02-abi-contract.md) `[已完成]`
- [1.3 节：补齐 CoralOptions 正式选项与 TTIR 生成](tutorials/ch01-skeleton/03-frontend-options.md) `[当前小课]`

### 第 2 章：标量语法降级与单核 AOT 执行闭环（阶段 S1）
- [2.1 节：空 Kernel LLVM 降级 Pass 与流水线接入](tutorials/ch02-scalar-single-core/01-empty-kernel-pass.md) `[下一小课]`
- [2.2 节：标量访存：无掩码 i32 load/store 转换](tutorials/ch02-scalar-single-core/02-scalar-load-store.md) `[待实现]`
- [2.3 节：标量算术：constexpr 常量与整数加法](tutorials/ch02-scalar-single-core/03-scalar-arithmetic.md) `[待实现]`
- [2.4 节：运行时入口包装与 ABI v2 绑定](tutorials/ch02-scalar-single-core/04-runtime-wrapper.md) `[待实现]`
- [2.5 节：生成可检查的静态 RV32 ELF](tutorials/ch02-scalar-single-core/05-static-elf.md) `[待实现]`
- [2.6 节：从加载段打包 AOT 镜像与装载清单](tutorials/ch02-scalar-single-core/06-aot-packager.md) `[待实现]`
- [2.7 节：启动 core0 并关联每次加载与完成](tutorials/ch02-scalar-single-core/07-core0-execution.md) `[待实现]`
- [2.8 节：完成第一份真实单核闭环报告](tutorials/ch02-scalar-single-core/08-scalar-report.md) `[待实现]`

### 第 3 章：Block、Mask 与张量条件选择（阶段 S2）
- [3.1 节：将规则 block、算术与选择降低成有界循环](tutorials/ch03-block-mask/01-vector-add-loop.md) `[待实现]`
- [3.2 节：只访问有效 lane，并正确实现显式 other](tutorials/ch03-block-mask/02-mask-guard.md) `[待实现]`
- [3.3 节：让 core0 顺序执行一个以上逻辑 program](tutorials/ch03-block-mask/03-sequential-multi-program.md) `[待实现]`
- [3.4 节：覆盖长度、布局别名和 BLOCK 的正负边界](tutorials/ch03-block-mask/04-block-boundary.md) `[待实现]`

### 第 4 章：JIT 运行时与动态特化（阶段 S3）
- [4.1 节：接通 Coral driver 与 launcher 的真实分派](tutorials/ch04-jit-runtime/01-driver-dispatch.md) `[待实现]`
- [4.2 节：实现 buffer 生命周期和 v3 六运行参数](tutorials/ch04-jit-runtime/02-buffer-lifecycle-v3-abi.md) `[待实现]`
- [4.3 节：实现可复现的 JIT 特化和缓存](tutorials/ch04-jit-runtime/03-jit-cache.md) `[待实现]`
- [4.4 节：用标准 JIT 验收单核基础能力](tutorials/ch04-jit-runtime/04-jit-acceptance.md) `[待实现]`

### 第 5 章：二维结构化访存与循环（TTS / Linalg）（阶段 S4）
- [5.1 节：接入适合当前 LLVM 的最小 Ascend TTS 子集](tutorials/ch05-structured-tts/01-tts-subset.md) `[待实现]`
- [5.2 节：分析二维指针的基址、偏移、步长和有效范围](tutorials/ch05-structured-tts/02-stride-layout.md) `[待实现]`
- [5.3 节：让循环状态与运行时分支保持源语义](tutorials/ch05-structured-tts/03-loop-dynamic-branch.md) `[待实现]`
- [5.4 节：把二维计算和转置表示为 Tensor/Linalg 操作](tutorials/ch05-structured-tts/04-linalg-tensor.md) `[待实现]`
- [5.5 节：完成 Bufferization、资源检查及 LLVM 降低](tutorials/ch05-structured-tts/05-bufferization-llvm.md) `[待实现]`
- [5.6 节：把早期 kernel 收敛到结构化主线](tutorials/ch05-structured-tts/06-converge-structured.md) `[待实现]`

### 第 6 章：向量归约、前缀扫描与 RVV 指令生成（阶段 S5）
- [6.1 节：按目标 VLEN 和动态 VL 分段向量化](tutorials/ch06-vector-rvv/01-vlen-vectorization.md) `[待实现]`
- [6.2 节：实现 sum/max、并列 argmax 与整数扫描](tutorials/ch06-vector-rvv/02-reduce-scan.md) `[待实现]`
- [6.3 节：把设备指令证据纳入向量阶段的累计验收](tutorials/ch06-vector-rvv/03-rvv-instructions.md) `[待实现]`

### 第 7 章：多维 Grid 与多核调度（coral_rt）（阶段 S6）
- [7.1 节：参数化核数及有效核掩码](tutorials/ch07-multicore-rt/01-core-mask.md) `[待实现]`
- [7.2 节：定义可验证的 coral_rt 启动与依赖计划](tutorials/ch07-multicore-rt/02-coral-rt-dialect.md) `[待实现]`
- [7.3 节：接通有界队列、核内隔离及回收](tutorials/ch07-multicore-rt/03-bounded-queue-isolation.md) `[待实现]`
- [7.4 节：验证多核调度保持 Triton program 语义](tutorials/ch07-multicore-rt/04-multicore-semantics.md) `[待实现]`

### 第 8 章：分层存储架构与显式 DMA（coral_mem）（阶段 S7）
- [8.1 节：定义存储区域、权限、owner 及容量](tutorials/ch08-tiered-memory/01-region-resource-model.md) `[待实现]`
- [8.2 节：从 mask 与 stride 求出合法 tile 和 DMA 段](tutorials/ch08-tiered-memory/02-tile-dma-range.md) `[待实现]`
- [8.3 节：把 copy、launch、wait 和回写串成有序计划](tutorials/ch08-tiered-memory/03-dma-ordering-visibility.md) `[待实现]`
- [8.4 节：先让一核完整搬入、计算并写回](tutorials/ch08-tiered-memory/04-single-core-tiered.md) `[待实现]`
- [8.5 节：在四核分层执行后验证错误与恢复](tutorials/ch08-tiered-memory/05-multicore-recovery.md) `[待实现]`

### 第 9 章：INT8 Matrix 语法与 Coral Zvt 矩阵加速（阶段 S8）
- [9.1 节：提供 Coral 真实 dot 形状和类型契约](tutorials/ch09-matrix-zvt/01-dot-contract.md) `[待实现]`
- [9.2 节：为合法矩阵建立可验证的 tile 表示](tutorials/ch09-matrix-zvt/02-tile-representation.md) `[待实现]`
- [9.3 节：按固定 SDK 生成可执行的 Zvt 指令](tutorials/ch09-matrix-zvt/03-zvt-instruction-gen.md) `[待实现]`
- [9.4 节：核对矩阵结果、尾块和多核写回](tutorials/ch09-matrix-zvt/04-matrix-multicore-writeback.md) `[待实现]`

### 第 10 章：类型扩展与执行优化（阶段 S9）
- [10.1 节：建立可解释的单缓冲性能基线](tutorials/ch10-optimization-extension/01-profiling-baseline.md) `[待实现]`
- [10.2 节：证明跨核搬运和计算有实际重叠](tutorials/ch10-optimization-extension/02-double-buffering-overlap.md) `[待实现]`
- [10.3 节：按目标和模式逐项增加类型与算子](tutorials/ch10-optimization-extension/03-type-op-extension.md) `[待实现]`
