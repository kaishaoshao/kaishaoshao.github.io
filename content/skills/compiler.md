---
title: 编译器与工作工具链地址导航
date: 2026-10-15
tags: [compiler, llvm, gcc, mlir, tools]
---

# 编译器与工作工具链地址导航

本篇整理了日常开发与研究所需的各类主流编译器、底层工具链、DSL/AI 编译器及在线探索工具的官方地址、源码仓库与镜像源。

---

## 一、LLVM 核心生态与官方资源

| 项目 / 资源 | 官方地址 / 文档 | GitHub / 源码仓库 | 说明 |
| :--- | :--- | :--- | :--- |
| **LLVM Monorepo** | [llvm.org](https://llvm.org/) | [llvm/llvm-project](https://github.com/llvm/llvm-project) | 包含 LLVM Core, Clang, LLD, LLDB, MLIR, Flang, OpenMP 等全部子工程 |
| **LLVM 官方文档** | [llvm.org/docs](https://llvm.org/docs/) | - | 官方核心文档、架构设计与 Pass 编写手册 |
| **Clang** | [clang.llvm.org](https://clang.llvm.org/) | [llvm-project/clang](https://github.com/llvm/llvm-project/tree/main/clang) | C/C++/Objective-C 编译器前端与 AST 工具 |
| **LLVM Releases** | [releases.llvm.org](https://releases.llvm.org/) | [Releases Tags](https://github.com/llvm/llvm-project/releases) | 各版本预编译二进制包与源码 Tarball |
| **LLVM APT 源** | [apt.llvm.org](https://apt.llvm.org/) | - | Debian/Ubuntu 官方自动安装脚本与镜像源 (`llvm.sh`) |
| **LLVM Discourse** | [discourse.llvm.org](https://discourse.llvm.org/) | - | LLVM 官方社区论坛与 RFC 讨论区 |
| **LLVM Bug Tracker** | - | [LLVM Issues](https://github.com/llvm/llvm-project/issues) | 提交与检索 LLVM 各组件 Issue |

### 常用快速安装命令 (Ubuntu / Debian)

```bash
# 使用 LLVM 官方脚本自动配置源并安装最新稳定版 Clang/LLVM
bash -c "$(wget -O - https://apt.llvm.org/llvm.sh)"

# 或者指定安装特定大版本（如 LLVM 18 或 19）
wget https://apt.llvm.org/llvm.sh
chmod +x llvm.sh
sudo ./llvm.sh 19 all
```

### 推荐 LLVM CMake 构建参数模版

```bash
cmake -G Ninja -B build -S llvm \
  -DCMAKE_BUILD_TYPE=Release \
  -DLLVM_ENABLE_ASSERTIONS=ON \
  -DLLVM_ENABLE_PROJECTS="clang;lld;lldb" \
  -DLLVM_TARGETS_TO_BUILD="host;RISCV" \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  -DLLVM_USE_SPLIT_DWARF=ON
```

---

## 二、MLIR 与现代中间表示

| 项目 / 资源 | 官方地址 / 教程 | 仓库地址 | 说明 |
| :--- | :--- | :--- | :--- |
| **MLIR 官方主页** | [mlir.llvm.org](https://mlir.llvm.org/) | [llvm-project/mlir](https://github.com/llvm/llvm-project/tree/main/mlir) | 多层次中间表示框架（Multi-Level IR） |
| **MLIR Toy 教程** | [Toy Tutorial](https://mlir.llvm.org/docs/Tutorials/Toy/) | - | 从零实现完整方言与编译管线经典教程 |
| **IREE** | [iree.dev](https://iree.dev/) | [iree-org/iree](https://github.com/iree-org/iree) | 基于 MLIR 的端到端硬件加速器与移动端执行环境 |
| **CIRCT** | [circt.llvm.org](https://circt.llvm.org/) | [llvm/circt](https://github.com/llvm/circt) | 面向硬件设计的电路 IR（Circuit IR Compilers and Tools） |

---

## 三、GNU 工具链与 GCC 生态

| 项目 / 资源 | 官方主页 | 源码镜像 / 仓库 | 说明 |
| :--- | :--- | :--- | :--- |
| **GCC (GNU Compiler Collection)** | [gcc.gnu.org](https://gcc.gnu.org/) | [gcc-mirror/gcc](https://github.com/gcc-mirror/gcc) | GNU 经典编译器套件 (C, C++, Fortran, Go 等) |
| **GNU Binutils** | [gnu.org/software/binutils](https://www.gnu.org/software/binutils/) | [sourceware/binutils-gdb](https://sourceware.org/git/binutils-gdb.git) | 汇编器 (as)、链接器 (ld)、反汇编 (objdump, readelf) 等核心工具 |
| **GDB 调试器** | [gnu.org/software/gdb](https://www.gnu.org/software/gdb/) | [sourceware/binutils-gdb](https://sourceware.org/git/binutils-gdb.git) | GNU 源码级调试器 |
| **GLIBC** | [gnu.org/software/libc](https://www.gnu.org/software/libc/) | [sourceware/glibc](https://sourceware.org/git/glibc.git) | GNU C 标准运行库 |

---

## 四、体系结构与交叉编译工具链 (RISC-V / ARM)

| 项目 | 地址 / 仓库 | 描述 |
| :--- | :--- | :--- |
| **RISC-V GNU Toolchain** | [riscv-collab/riscv-gnu-toolchain](https://github.com/riscv-collab/riscv-gnu-toolchain) | 包含 riscv32/64-unknown-elf 与 linux-gnu 完整工具链编译脚本 |
| **Bootlin 预编译工具链** | [toolchains.bootlin.com](https://toolchains.bootlin.com/) | 极为方便的各类架构预编译交叉编译器下载站（RISC-V, ARM, MIPS 等） |
| **ARM GNU Toolchain** | [Arm 官方下载页](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads) | 官方提供的 AArch64 / Cortex-M 交叉编译器包 |
| **Spike (RISC-V ISA 模拟器)** | [riscv-software-src/riscv-isa-sim](https://github.com/riscv-software-src/riscv-isa-sim) | RISC-V 黄金参考模拟器，支持 RVV 向量扩展指令集验证 |
| **QEMU** | [qemu.org](https://www.qemu.org/) \| [qemu/qemu](https://github.com/qemu/qemu) | 用户态仿真与全系统模拟器 |

---

## 五、AI 编译器与计算图优化框架

| 框架 | 官方主页 | 源码仓库 | 核心定位 |
| :--- | :--- | :--- | :--- |
| **Apache TVM** | [tvm.apache.org](https://tvm.apache.org/) | [apache/tvm](https://github.com/apache/tvm) | 深度学习张量自动调优与代码生成端到端编译器 |
| **OpenXLA** | [openxla.org](https://openxla.org/) | [openxla/xla](https://github.com/openxla/xla) | Google 加速线性代数编译器，支持 JAX / TensorFlow / PyTorch |
| **Triton** | [triton-lang.org](https://triton-lang.org/) | [triton-lang/triton](https://github.com/triton-lang/triton) | OpenAI 开发的 Pythonic GPU 高性能算子编程与编译器 |
| **Halide** | [halide-lang.org](https://halide-lang.org/) | [halide/Halide](https://github.com/halide/Halide) | 图像处理与阵列计算语言，解耦算法与计算调度（Scheduling） |
| **Taichi (太极)** | [taichi-lang.cn](https://taichi-lang.cn/) | [taichi-dev/taichi](https://github.com/taichi-dev/taichi) | 针对图形学与物理仿真的高性能领域专用语言与 JIT 编译器 |

---

## 六、在线探索与分析利器

- **[Compiler Explorer (Godbolt)](https://godbolt.org/)**：不可或缺的在线汇编与代码生成对比工具，支持 GCC/Clang/Rustc 各版本及多种架构目标。
- **[LLVM Code Browser (Woboq)](https://code.woboq.org/llvm/)**：LLVM 源码的高精度在线符号交叉跳转与阅读器。
- **[Quick-Bench](https://quick-bench.com/)**：在线 C++ 微基准性能测试与汇编分析平台。
- **[AST Explorer](https://astexplorer.net/)**：语法树可视化解析工具。
- **[C++ Insights](https://cppinsights.io/)**：透视 C++ 编译器在模板展开、Lambda 生成等场景下的内部转换。

---

## 七、国内常用镜像源与下载加速

- **清华大学开源镜像站**：[mirrors.tuna.tsinghua.edu.cn](https://mirrors.tuna.tsinghua.edu.cn/)
- **中国科学技术大学开源镜像站**：[mirrors.ustc.edu.cn](https://mirrors.ustc.edu.cn/)
- **阿里云开源镜像站**：[developer.aliyun.com/mirror](https://developer.aliyun.com/mirror/)
