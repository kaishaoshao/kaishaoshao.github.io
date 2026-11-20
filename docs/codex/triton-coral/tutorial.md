# Triton Coral 后端开发实战教程：从编译器骨架到硬件执行

更新日期：2026-11-20（Asia/Shanghai）。

本文档是 **Triton Coral NPU 后端自研全流程教程** 的总览与学习路线图。全书按照“大课（章节）包含小课（小节）”的书籍体例组织，共规划 **10 门大课、44 个小章节**。每个小章节均独立成文，包含：**这节课做什么 + 核心代码实现 + 解释说明与注释 + 测试与验证代码**。

---

## 目录与全书导读

1. [项目背景与分层架构理念](#1-项目背景与分层架构理念)
2. [双层测试体系：开发内循环与阶段验收](#2-双层测试体系开发内循环与阶段验收)
3. [教程全景路线图（大课与小课目录）](#3-教程全景路线图大课与小课目录)
4. [常见问题与环境避坑指南](#4-常见问题与环境避坑指南)

---

## 1. 项目背景与分层架构理念

### 1.1 硬件目标与约束
Coral NPU 是一款面向边缘 AI 计算的高效能 RISC-V 协处理器：
- **核心架构**：RV32IMF_Zve32x，单核 Warp Size = 1（无 GPU 隐式 SIMT Warp 掩码）。
- **专用扩展**：Coral Zvt 矩阵乘加速部件（支持 16×16 等矩阵分块计算）。
- **分层内存**：
  - **ITCM（指令紧耦合内存）**：8 KiB（基址 `0x00000000`）。流水线有预取特性，`.text` 尾部需填充 256 字节 NOP（`0x13000000`）。
  - **DTCM（数据紧耦合内存）**：32 KiB（基址 `0x00010000`）。`0x00010000~0x000100FF` 为 256 字节参数预留区，`0x00010100` 起为数据区，顶部 `0x00018000` 为 16 字节对齐的栈顶。
  - **共享 SRAM / 3D DRAM / HBF**：更大容量的外部或片上存储，通过显式 DMA 搬运。

### 1.2 编译流设计思想
遵循**标准 MLIR 方言优先、适时引入硬件专用方言**的原则：
```text
Triton Python 源码 (@triton.jit)
  │ (Triton 前端 AST -> TTIR)
  ▼
MLIR Triton Dialect (tt)
  │ (第 1~3 课：标量与标准向量加法)
  ├───────────────────────────────────► 标准 MLIR LLVM 方言 ──► RV32 LLVM IR
  │ (第 4~5 课：二维结构化访存与循环)
  ├───────────────────────────────────► Ascend TTS / Linalg / Tensor ──► Bufferization
  │ (第 6 课：归约与前缀扫描)
  ├───────────────────────────────────► MLIR Vector Dialect ──► RVV 向量指令
  │ (第 7 课：多核控制流)
  ├───────────────────────────────────► coral_rt 方言 (Launch / Task / Event)
  │ (第 8 课：存储分层与 DMA)
  ├───────────────────────────────────► coral_mem 方言 (View / Copy / Wait)
  │ (第 9 课：矩阵乘)
  └───────────────────────────────────► Coral Tile Dialect ──► Coral Zvt 矩阵指令
```

---

## 2. 双层测试体系：开发内循环与阶段验收

为了避免繁琐的协议交互影响编码节奏，本教程实行**两层测试解耦**：

### 2.1 第一层：开发者日常内循环（Inner Loop）
在实现每个小课的功能时，**不需要启动复杂的板卡仿真器或完整的 JSON 适配器**，直接使用：
1. **Python 断言 / pytest**：直接测试 `compiler.py` 的 options 解析、异常拦截和 `make_llir` 导出。
2. **`triton-opt` + `llvm-lit` + `FileCheck`**：直接在 `examples/lit/` 下针对 `.mlir` 运行 pass，核验生成的 LLVM 方言或报错诊断（如 `CORALUNSUPPORTED`）。
3. **`llc` + `llvm-readelf`**：直接将导出的 LLVM IR 转为目标 ELF 对象，核验机器指令。

### 2.2 第二层：阶段端到端验收外循环（Outer Loop）
当一门大课的所有小课均已就绪，再使用 `run_stage.py` 驱动硬件适配器，验证控制 CPU 装载、core0 启动、内存一致性屏障与硬件写回结果。

---

## 3. 教程全景路线图（大课与小课目录）

### 第 1 章：验证 Triton 后端发现与 C++ 插件骨架（阶段 S0）

- [1.1 节：确认工具链、后端发现与 C++ 扩展](tutorials/ch01-skeleton/01-toolchain-discovery.md)：确认 LLVM 锁定信息、后端发现与 C++ 扩展。
- [1.2 节：约定 RV32 v2 参数与地址约定](tutorials/ch01-skeleton/02-abi-contract.md)：写清 RV32 v2 参数和最小地址约定。
- [1.3 节：补齐 CoralOptions 正式选项与 TTIR 生成](tutorials/ch01-skeleton/03-frontend-options.md)：让拷贝和加法通过正式 CoralOptions，并拒绝未知目标。

### 第 2 章：标量语法降级与单核 AOT 执行闭环（阶段 S1）

- [2.1 节：空 Kernel LLVM 降级 Pass 与流水线接入](tutorials/ch02-scalar-single-core/01-empty-kernel-pass.md)：在 make_llir 转换函数签名、指针和空返回，导出 RV32 LLVM IR。
- [2.2 节：标量访存：无掩码 i32 load/store 转换](tutorials/ch02-scalar-single-core/02-scalar-load-store.md)：将无掩码 I32 的拷贝降为 LLVM 访存。
- [2.3 节：标量算术：constexpr 常量与整数加法](tutorials/ch02-scalar-single-core/03-scalar-arithmetic.md)：接入 constexpr 常量和 I32 加法，沿用第一批的 LLVM IR 导出。
- [2.4 节：运行时入口包装与 ABI v2 绑定](tutorials/ch02-scalar-single-core/04-runtime-wrapper.md)：让入口按 v2 解析参数、调用 kernel 并发布完成。
- [2.5 节：生成可检查的静态 RV32 ELF](tutorials/ch02-scalar-single-core/05-static-elf.md)：生成可检查的静态 RV32 ELF。
- [2.6 节：从加载段打包 AOT 镜像与装载清单](tutorials/ch02-scalar-single-core/06-aot-packager.md)：从加载段打包 AOT 镜像与装载清单。
- [2.7 节：启动 core0 并关联每次加载与完成](tutorials/ch02-scalar-single-core/07-core0-execution.md)：启动 core0 并关联每次加载与完成。
- [2.8 节：完成第一份真实单核闭环报告](tutorials/ch02-scalar-single-core/08-scalar-report.md)：完成第一份真实单核闭环报告。

### 第 3 章：Block、Mask 与张量条件选择（阶段 S2）

- [3.1 节：将规则 block、算术与选择降低成有界循环](tutorials/ch03-block-mask/01-vector-add-loop.md)：将规则 block、算术与选择降低成有界循环。
- [3.2 节：只访问有效 lane，并正确实现显式 other](tutorials/ch03-block-mask/02-mask-guard.md)：只访问有效 lane，并正确实现显式 other。
- [3.3 节：让 core0 顺序执行一个以上逻辑 program](tutorials/ch03-block-mask/03-sequential-multi-program.md)：让 core0 顺序执行一个以上逻辑 program。
- [3.4 节：覆盖长度、布局别名和 BLOCK 的正负边界](tutorials/ch03-block-mask/04-block-boundary.md)：覆盖长度、布局别名和 BLOCK 的正负边界。

### 第 4 章：JIT 运行时与动态特化（阶段 S3）

- [4.1 节：接通 Coral driver 与 launcher 的真实分派](tutorials/ch04-jit-runtime/01-driver-dispatch.md)：接通 Coral driver 与 launcher 的真实分派。
- [4.2 节：实现 buffer 生命周期和 v3 六运行参数](tutorials/ch04-jit-runtime/02-buffer-lifecycle-v3-abi.md)：实现 buffer 生命周期和 v3 六运行参数。
- [4.3 节：实现可复现的 JIT 特化和缓存](tutorials/ch04-jit-runtime/03-jit-cache.md)：实现可复现的 JIT 特化和缓存。
- [4.4 节：用标准 JIT 验收单核基础能力](tutorials/ch04-jit-runtime/04-jit-acceptance.md)：用标准 JIT 验收单核基础能力。

### 第 5 章：二维结构化访存与循环（TTS / Linalg）（阶段 S4）

- [5.1 节：接入适合当前 LLVM 的最小 Ascend TTS 子集](tutorials/ch05-structured-tts/01-tts-subset.md)：接入适合当前 LLVM 的最小 Ascend TTS 子集。
- [5.2 节：分析二维指针的基址、偏移、步长和有效范围](tutorials/ch05-structured-tts/02-stride-layout.md)：分析二维指针的基址、偏移、步长和有效范围。
- [5.3 节：让循环状态与运行时分支保持源语义](tutorials/ch05-structured-tts/03-loop-dynamic-branch.md)：让循环状态与运行时分支保持源语义。
- [5.4 节：把二维计算和转置表示为 Tensor/Linalg 操作](tutorials/ch05-structured-tts/04-linalg-tensor.md)：把二维计算和转置表示为 Tensor/Linalg 操作。
- [5.5 节：完成 Bufferization、资源检查及 LLVM 降低](tutorials/ch05-structured-tts/05-bufferization-llvm.md)：完成 Bufferization、资源检查及 LLVM 降低。
- [5.6 节：把早期 kernel 收敛到结构化主线](tutorials/ch05-structured-tts/06-converge-structured.md)：把早期 kernel 收敛到结构化主线。

### 第 6 章：向量归约、前缀扫描与 RVV 指令生成（阶段 S5）

- [6.1 节：按目标 VLEN 和动态 VL 分段向量化](tutorials/ch06-vector-rvv/01-vlen-vectorization.md)：按目标 VLEN 和动态 VL 分段向量化。
- [6.2 节：实现 sum/max、并列 argmax 与整数扫描](tutorials/ch06-vector-rvv/02-reduce-scan.md)：实现 sum/max、并列 argmax 与整数扫描。
- [6.3 节：把设备指令证据纳入向量阶段的累计验收](tutorials/ch06-vector-rvv/03-rvv-instructions.md)：把设备指令证据纳入向量阶段的累计验收。

### 第 7 章：多维 Grid 与多核调度（coral_rt）（阶段 S6）

- [7.1 节：参数化核数及有效核掩码](tutorials/ch07-multicore-rt/01-core-mask.md)：参数化核数及有效核掩码。
- [7.2 节：定义可验证的 coral_rt 启动与依赖计划](tutorials/ch07-multicore-rt/02-coral-rt-dialect.md)：定义可验证的 coral_rt 启动与依赖计划。
- [7.3 节：接通有界队列、核内隔离及回收](tutorials/ch07-multicore-rt/03-bounded-queue-isolation.md)：接通有界队列、核内隔离及回收。
- [7.4 节：验证多核调度保持 Triton program 语义](tutorials/ch07-multicore-rt/04-multicore-semantics.md)：验证多核调度保持 Triton program 语义。

### 第 8 章：分层存储架构与显式 DMA（coral_mem）（阶段 S7）

- [8.1 节：定义存储区域、权限、owner 及容量](tutorials/ch08-tiered-memory/01-region-resource-model.md)：定义存储区域、权限、owner 及容量。
- [8.2 节：从 mask 与 stride 求出合法 tile 和 DMA 段](tutorials/ch08-tiered-memory/02-tile-dma-range.md)：从 mask 与 stride 求出合法 tile 和 DMA 段。
- [8.3 节：把 copy、launch、wait 和回写串成有序计划](tutorials/ch08-tiered-memory/03-dma-ordering-visibility.md)：把 copy、launch、wait 和回写串成有序计划。
- [8.4 节：先让一核完整搬入、计算并写回](tutorials/ch08-tiered-memory/04-single-core-tiered.md)：先让一核完整搬入、计算并写回。
- [8.5 节：在四核分层执行后验证错误与恢复](tutorials/ch08-tiered-memory/05-multicore-recovery.md)：在四核分层执行后验证错误与恢复。

### 第 9 章：INT8 Matrix 语法与 Coral Zvt 矩阵加速（阶段 S8）

- [9.1 节：提供 Coral 真实 dot 形状和类型契约](tutorials/ch09-matrix-zvt/01-dot-contract.md)：提供 Coral 真实 dot 形状和类型契约。
- [9.2 节：为合法矩阵建立可验证的 tile 表示](tutorials/ch09-matrix-zvt/02-tile-representation.md)：为合法矩阵建立可验证的 tile 表示。
- [9.3 节：按固定 SDK 生成可执行的 Zvt 指令](tutorials/ch09-matrix-zvt/03-zvt-instruction-gen.md)：按固定 SDK 生成可执行的 Zvt 指令。
- [9.4 节：核对矩阵结果、尾块和多核写回](tutorials/ch09-matrix-zvt/04-matrix-multicore-writeback.md)：核对矩阵结果、尾块和多核写回。

### 第 10 章：类型扩展与执行优化（阶段 S9）

- [10.1 节：建立可解释的单缓冲性能基线](tutorials/ch10-optimization-extension/01-profiling-baseline.md)：建立可解释的单缓冲性能基线。
- [10.2 节：证明跨核搬运和计算有实际重叠](tutorials/ch10-optimization-extension/02-double-buffering-overlap.md)：证明跨核搬运和计算有实际重叠。
- [10.3 节：按目标和模式逐项增加类型与算子](tutorials/ch10-optimization-extension/03-type-op-extension.md)：按目标和模式逐项增加类型与算子。

---

## 4. 常见问题与环境避坑指南

1. **Python 导入报 `NameError: name 'true' is not defined`**：
   - Python 中的布尔值为首字母大写 `True` / `False`。在 `CoralOptions` 中必须写 `sanitize_overflow: bool = False`。
2. **Triton 误回退到 NVIDIA 后端并寻找 `cuda.h`**：
   - 务必设置环境变量 `TRITON_BACKENDS_IN_TREE=1` 和 `TRITON_DEFAULT_BACKEND=coral`。
   - 检查 `python/triton/backends/coral` 软链接是否存在且指向 `third_party/coral/backend`。
3. **C++ Pass 头文件与源文件目录规范**：
   - 统一使用模块化子目录：`include/TritonCoralToLLVM/TritonCoralToLLVM.h` 与 `lib/TritonCoralToLLVM/TritonCoralToLLVM.cpp`。
4. **编译与工具链路径**：
   - 依赖的统一安装路径为 `/home/compiler-1/work/coral/coralnpu-compiler/out/llvm-zvt/install`。
   - 重新编译 C++ 插件时运行 `make BUILD_DIR=... PYTHON=...`，确保构建产物复制到 `python/triton/_C/libtriton.so`。
