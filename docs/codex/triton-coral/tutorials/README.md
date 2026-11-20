# Triton Coral 实战教程分节索引

更新日期：2026-11-20（Asia/Shanghai）。

本目录包含 Triton Coral 后端自研全流程教程的各章节小课。全书按 10 门大课组织，每门大课细分为多个独立小节，按功能逐步递进推进。

---

## 章节目录

### [第 1 章：验证 Triton 后端发现与 C++ 插件骨架](ch01-skeleton/)
- [1.1 节：确认工具链、后端发现与 C++ 扩展](ch01-skeleton/01-toolchain-discovery.md)
- [1.2 节：约定 RV32 v2 参数与地址约定](ch01-skeleton/02-abi-contract.md)
- [1.3 节：补齐 CoralOptions 正式选项与 TTIR 生成](ch01-skeleton/03-frontend-options.md)

### [第 2 章：标量语法降级与单核 AOT 执行闭环](ch02-scalar-single-core/)
- [2.1 节：空 Kernel LLVM 降级 Pass 与流水线接入](ch02-scalar-single-core/01-empty-kernel-pass.md)
- [2.2 节：标量访存：无掩码 i32 load/store 转换](ch02-scalar-single-core/02-scalar-load-store.md)
- [2.3 节：标量算术：constexpr 常量与整数加法](ch02-scalar-single-core/03-scalar-arithmetic.md)
- [2.4 节：运行时入口包装与 ABI v2 绑定](ch02-scalar-single-core/04-runtime-wrapper.md)
- [2.5 节：生成可检查的静态 RV32 ELF](ch02-scalar-single-core/05-static-elf.md)
- [2.6 节：从加载段打包 AOT 镜像与装载清单](ch02-scalar-single-core/06-aot-packager.md)
- [2.7 节：启动 core0 并关联每次加载与完成](ch02-scalar-single-core/07-core0-execution.md)
- [2.8 节：完成第一份真实单核闭环报告](ch02-scalar-single-core/08-scalar-report.md)

### [第 3 章：Block、Mask 与张量条件选择](ch03-block-mask/)
- [3.1 节：将规则 block、算术与选择降低成有界循环](ch03-block-mask/01-vector-add-loop.md)
- [3.2 节：只访问有效 lane，并正确实现显式 other](ch03-block-mask/02-mask-guard.md)
- [3.3 节：让 core0 顺序执行一个以上逻辑 program](ch03-block-mask/03-sequential-multi-program.md)
- [3.4 节：覆盖长度、布局别名和 BLOCK 的正负边界](ch03-block-mask/04-block-boundary.md)

### [第 4 章：JIT 运行时与动态特化](ch04-jit-runtime/)
- [4.1 节：接通 Coral driver 与 launcher 的真实分派](ch04-jit-runtime/01-driver-dispatch.md)
- [4.2 节：实现 buffer 生命周期和 v3 六运行参数](ch04-jit-runtime/02-buffer-lifecycle-v3-abi.md)
- [4.3 节：实现可复现的 JIT 特化和缓存](ch04-jit-runtime/03-jit-cache.md)
- [4.4 节：用标准 JIT 验收单核基础能力](ch04-jit-runtime/04-jit-acceptance.md)

### [第 5 章：二维结构化访存与循环（TTS / Linalg）](ch05-structured-tts/)
- [5.1 节：接入适合当前 LLVM 的最小 Ascend TTS 子集](ch05-structured-tts/01-tts-subset.md)
- [5.2 节：分析二维指针的基址、偏移、步长和有效范围](ch05-structured-tts/02-stride-layout.md)
- [5.3 节：让循环状态与运行时分支保持源语义](ch05-structured-tts/03-loop-dynamic-branch.md)
- [5.4 节：把二维计算和转置表示为 Tensor/Linalg 操作](ch05-structured-tts/04-linalg-tensor.md)
- [5.5 节：完成 Bufferization、资源检查及 LLVM 降低](ch05-structured-tts/05-bufferization-llvm.md)
- [5.6 节：把早期 kernel 收敛到结构化主线](ch05-structured-tts/06-converge-structured.md)

### [第 6 章：向量归约、前缀扫描与 RVV 指令生成](ch06-vector-rvv/)
- [6.1 节：按目标 VLEN 和动态 VL 分段向量化](ch06-vector-rvv/01-vlen-vectorization.md)
- [6.2 节：实现 sum/max、并列 argmax 与整数扫描](ch06-vector-rvv/02-reduce-scan.md)
- [6.3 节：把设备指令证据纳入向量阶段的累计验收](ch06-vector-rvv/03-rvv-instructions.md)

### [第 7 章：多维 Grid 与多核调度（coral_rt）](ch07-multicore-rt/)
- [7.1 节：参数化核数及有效核掩码](ch07-multicore-rt/01-core-mask.md)
- [7.2 节：定义可验证的 coral_rt 启动与依赖计划](ch07-multicore-rt/02-coral-rt-dialect.md)
- [7.3 节：接通有界队列、核内隔离及回收](ch07-multicore-rt/03-bounded-queue-isolation.md)
- [7.4 节：验证多核调度保持 Triton program 语义](ch07-multicore-rt/04-multicore-semantics.md)

### [第 8 章：分层存储架构与显式 DMA（coral_mem）](ch08-tiered-memory/)
- [8.1 节：定义存储区域、权限、owner 及容量](ch08-tiered-memory/01-region-resource-model.md)
- [8.2 节：从 mask 与 stride 求出合法 tile 和 DMA 段](ch08-tiered-memory/02-tile-dma-range.md)
- [8.3 节：把 copy、launch、wait 和回写串成有序计划](ch08-tiered-memory/03-dma-ordering-visibility.md)
- [8.4 节：先让一核完整搬入、计算并写回](ch08-tiered-memory/04-single-core-tiered.md)
- [8.5 节：在四核分层执行后验证错误与恢复](ch08-tiered-memory/05-multicore-recovery.md)

### [第 9 章：INT8 Matrix 语法与 Coral Zvt 矩阵加速](ch09-matrix-zvt/)
- [9.1 节：提供 Coral 真实 dot 形状和类型契约](ch09-matrix-zvt/01-dot-contract.md)
- [9.2 节：为合法矩阵建立可验证的 tile 表示](ch09-matrix-zvt/02-tile-representation.md)
- [9.3 节：按固定 SDK 生成可执行的 Zvt 指令](ch09-matrix-zvt/03-zvt-instruction-gen.md)
- [9.4 节：核对矩阵结果、尾块和多核写回](ch09-matrix-zvt/04-matrix-multicore-writeback.md)

### [第 10 章：类型扩展与执行优化](ch10-optimization-extension/)
- [10.1 节：建立可解释的单缓冲性能基线](ch10-optimization-extension/01-profiling-baseline.md)
- [10.2 节：证明跨核搬运和计算有实际重叠](ch10-optimization-extension/02-double-buffering-overlap.md)
- [10.3 节：按目标和模式逐项增加类型与算子](ch10-optimization-extension/03-type-op-extension.md)
