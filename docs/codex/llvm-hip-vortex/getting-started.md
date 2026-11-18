# 第 1 课：Clang 怎样理解 HIP 语法

更新日期：2026-11-18（Asia/Shanghai）。先从本课开始，课程目录见 [十课教学主线](plan.md#tutorial-route)。原有 T00 工程基线保留在本文件附录，不再是第一课的全部前置条件。

<a id="lesson-1"></a>

## 本课的问题和目标

本课只回答：`__global__`、`__device__` 写进文件后，Clang 怎样识别它们？你会创建一个最小 HIP 文件，依次查看预处理和 AST。暂不链接、不运行 GPU，也不修改 LLVM 源码。

HIP 这些限定符通常通过头文件宏展开为 Clang 属性。这里手工写出同样的属性宏，是为观察机制；不能把限定符定义为空，也不能用普通 C++ 模式忽略属性来冒充 HIP 支持。后续会使用真正的 Vortex HIP 支持头。

## 准备观察用的编译器

在 WSL Ubuntu-22.04 的 Bash 中执行：

```bash
bash
cd /home/kaikai/vortex-word
export HIP_TUTORIAL_CLANG=/home/kaikai/vortex-word/tools/llvm-vortex/bin/clang++
"$HIP_TUTORIAL_CLANG" --version
mkdir -p artifacts/tutorial/l01
```

这个路径是已安装的参考 Clang 20.1.8。第一至三课可先用它观察已有语法能力；你自己的 LLVM 23 构建完成后，修改 HIP_TUTORIAL_CLANG 指向新工具并重做实验。每次记录实际版本，不把参考工具结果写成新 LLVM 已通过。

## 写出最小程序

```bash
cat > artifacts/tutorial/l01/attributes.hip <<'EOF'
#define __global__ __attribute__((global))
#define __device__ __attribute__((device))
#define __host__ __attribute__((host))

__device__ int twice(int v) {
  return v * 2;
}

__global__ void store42(int* out) {
  *out = 42;
}
EOF
```

twice 是 device helper，store42 是逻辑 kernel。本课不调用它们，不需要 threadIdx、hipMalloc 或设备 runtime。

## 第一步：先看宏展开

```bash
"$HIP_TUTORIAL_CLANG" -x hip --offload-host-only -nogpuinc -nogpulib \
  -E -P artifacts/tutorial/l01/attributes.hip \
  > artifacts/tutorial/l01/attributes.ii

cat artifacts/tutorial/l01/attributes.ii
```

应看到 __global__/__device__ 变成相应 `__attribute__`。`-x hip` 选择语言，host-only 只做本次观察所需的 host 编译路径；nogpuinc/nogpulib 避免本实验依赖默认 GPU 支持头和库。这个无 include 的小例子不要求先安装完整 ROCm。

自己回答：宏展开之后谁负责识别属性？为什么把 __global__ 定义为空会丢失语义？

## 第二步：再看 AST

```bash
"$HIP_TUTORIAL_CLANG" -x hip --offload-host-only -nogpuinc -nogpulib \
  -fsyntax-only -Xclang -ast-dump \
  artifacts/tutorial/l01/attributes.hip \
  > artifacts/tutorial/l01/attributes.ast.txt

rg 'FunctionDecl|CUDADeviceAttr|CUDAGlobalAttr' \
  artifacts/tutorial/l01/attributes.ast.txt
```

观察重点：twice 对应 CUDADeviceAttr，store42 对应 CUDAGlobalAttr。AST 地址和位置会变化，不比较固定十六进制地址。Clang 的 CUDA/HIP 共享了部分实现和节点命名，CUDA 前缀不代表此程序选择了 NVIDIA 后端。

本命令只做预处理/解析/语义分析和 AST 输出，没有生成可运行设备镜像。host-only 的成功也不意味着设备侧所有语义已经检查完。

## 自己完成的小练习

1. 新增一个显式 __host__ 函数，查看对应属性。
2. 新增一个未标记的普通函数，解释它默认在哪一侧使用。默认 host 语义不一定表现为一个显式 CUDAHostAttr 节点。
3. 用自己的话写出“宏 → 属性 → AST”三个层次，指出哪部分是 Clang 已有能力。
4. 说明本课为什么没有证明 Vortex kernel 能在 SimX 运行。

本课交付：最小输入、预处理结果、AST 摘要和上述回答。使用 [证据模板](evidence-template.md) 记录课程号 L01 和实际工具版本；关联任务只记录本课覆盖的部分，不自动把整个 T07 标为完成。

## 本课完成后

进入 plan.md 中的 L02：先观察非法 host/device 调用，再看 <<<>>> 的 CUDAKernelCallExpr；L03 才观察设备 IR。到 L04 首次修改编译器之前，再完成必要的 LLVM 23 构建与基线核对。

2026-11-18 已在参考 Clang 20.1.8 上核对本课的预处理与属性 AST，命令成功；也做了后续课的两个非法调用、launch AST 和设备 IR 隔离实验。记录详见 [课程证据边界](plan.md#03-已核对的教学实验与证据边界)。本课不包含新 LLVM 23 或新 SimX 执行通过记录。

<a id="engineering-baseline"></a>

## 附录：保留的 T00 工程基线任务

原有状态和证据按实际进度保留。这个附录用于工程环境和 ABI 基线验收，本身不修改后端；按课程需要在首次源码修改/执行验收前完成相关项，不要求第一课先读完它。

这是 T00 阶段的操作任务书，对应 [详细任务卡](tasks.md) 中 T00.1～T00.6。记录时使用 [证据模板](evidence-template.md)，总览末尾说明 [最终可以做成什么](plan.md#6-最后可以做成什么样子)。

| 小任务 | 本文对应内容 | 独立交付 |
|---|---|---|
| T00.1 | 第 2 节：版本与能力 | 版本/配置表 |
| T00.2 | 第 3 节：完整构建 | 构建日志、工具与 target 清单 |
| T00.3 | 第 4 节：标准 RV64 | add.ll/add.s 与解释 |
| T00.4 | 第 5 节：参考执行基线 | 五项 smoke 日志 |
| T00.5 | 第 6 节：官方代码与 ABI | 参数布局、调用链与源码分析 |
| T00.6 | 第 7～8 节及总结 | 分层验收计划、七个问题的回答 |

### 1. 为什么先做这一步

目前参考 Clang 20.1.8 + SDK + SimX 已有通过记录；你自己的 LLVM 23.1.4 只完成了 CMake 配置，尚未生成编译器。先区分“标准 RISC-V 编译器正常”“参考 Vortex 系统正常”“新编译器已支持 Vortex”三个结论，后续才能定位错误。

本任务结束时，你应能回答：SimX 执行哪个文件、kernel 地址从哪里来、参数指针如何到达 a0，以及为什么普通 RISC-V 后端还不能直接运行 HIP。

### 2. 固定工作目录与记录

在 WSL Ubuntu-22.04 的 Bash 中运行以下命令；这是操作说明，本次教程设计没有代你执行完整构建。

```bash
bash
cd /home/kaikai/vortex-word
mkdir -p artifacts/tutorial/t00

git -C llvm-project branch --show-current
git -C llvm-project rev-parse HEAD
git -C llvm-project status --short
git -C vortex rev-parse HEAD
tools/llvm-vortex/bin/clang --version
```

预期 LLVM 分支 `dev/vortex`，HEAD `7a941dfb2877a0b8cf30323fefa85ad019e0b0f5`；SDK HEAD `26d2bc4b5409a35a111e8316ac3a87d07b15fc80`。当前 `.gitignore` 修改和未跟踪的 `build.sh` 是已存在的构建准备，不要为清理状态而删除它们。如果你已经有新的修改，先记录，后续验收以实际 commit/diff 为准。

新建 `/home/kaikai/vortex-word/artifacts/tutorial/t00/evidence.md`，记录版本、命令和结果，错误也保留原始诊断。

### 3. 编译 LLVM，并验证四个后端

```bash
cd /home/kaikai/vortex-word/llvm-project
set -o pipefail
./build.sh 2>&1 | tee ../artifacts/tutorial/t00/build.log

../build/llvm/bin/clang --version
../build/llvm/bin/llvm-config --targets-built
../build/llvm/bin/llc --version

# 后续 MC/IR 测试所需工具；显式构建 FileCheck，避免依赖默认目标集合。
cmake --build ../build/llvm --parallel 4 \
  --target llvm-mc llvm-objdump llc opt FileCheck
```

验收：构建命令成功，输出包含 AMDGPU、RISCV、NVPTX、X86。默认 4 个编译任务、1 个链接任务；遇到内存不足先降低并行度并保留失败日志，不同时修改编译器代码。

这些工具来自 `build/llvm/bin`。不要把 `tools/llvm-vortex/bin` 的输出误记成 LLVM 23 构建结果。

### 4. 用新 Clang 编译最小标准 RV64 函数

```bash
cd /home/kaikai/vortex-word
cat > artifacts/tutorial/t00/add.c <<'EOF'
int add(int a, int b) {
  return a + b;
}
EOF

build/llvm/bin/clang --target=riscv64-unknown-elf \
  -march=rv64imafd -mabi=lp64d -O2 -S \
  artifacts/tutorial/t00/add.c -o artifacts/tutorial/t00/add.s

build/llvm/bin/clang --target=riscv64-unknown-elf \
  -march=rv64imafd -mabi=lp64d -O2 -S -emit-llvm \
  artifacts/tutorial/t00/add.c -o artifacts/tutorial/t00/add.ll
```

验收：生成 RISC-V 汇编及 IR，能解释参数/返回值和 IR 的 target triple/DataLayout。这里没有链接 libc、没有启动代码，也没有 Vortex 指令；它仅验证标准 RISC-V 编译路径。不要把这个 `.s` 或 `.o` 直接交给 SimX 当完整 kernel。

### 5. 复跑参考工具链的执行基线

```bash
cd /home/kaikai/vortex-word
set -o pipefail
bash scripts/run-smoke.sh 2>&1 | tee artifacts/tutorial/t00/reference-smoke.log
```

验收：native demo、native sgemm、OpenCL vecadd、现有 chipStar 路径的 HIP vecadd/sgemm 五项通过。逐项日志位于 `/home/kaikai/vortex-word/logs/latest-smoke`。这一步仍用参考工具链，不证明 LLVM 23 已支持 Vortex/HIP。

如果参考基线失败，先修复配置或依赖，再开始后端任务；不要把失败写成“新 pass 有问题”。SimX 是 CPU 上的功能模拟器，运行速度或输出中的周期数不能据此作真实硬件性能结论。

### 6. 按顺序阅读官方代码，写出 ABI 链路

所有路径位于 `/home/kaikai/vortex-word/vortex` 下：

| 顺序 | 文件 | 要回答的问题 |
|---|---|---|
| 1 | `tests/regression/demo/kernel.cpp`、`common.h` | kernel 输入是什么？二维线程坐标如何映射到数组？ |
| 2 | `tests/regression/demo/main.cpp` | buffer 设备地址、module、kernel handle 和参数区如何准备？ |
| 3 | `sw/kernel/include/vx_spawn2.h`、`vx_intrinsics.h` | kernel/uniform annotation 是什么？threadIdx 与 blockIdx 如何取得？ |
| 4 | `sw/runtime/include/vortex2.h` | vx_launch_info_t 的 args_host/args_size、grid/block 和 kernel 字段是什么？ |
| 5 | `sw/kernel/src/vx_start.S` | __vx_cta_entry 怎样建立状态并调用 kernel？ |
| 6 | `sw/kernel/scripts/vxbin.py` | 如何发现 __vx_kentry_*？为什么 kernel_main 暴露成 main？ |
| 7 | `tests/regression/common.mk` | target、ABI、startup、runtime、链接地址和打包命令是什么？ |

再阅读参考编译器的 [RISCVVortexKEntry.cpp](https://github.com/vortexgpgpu/llvm/blob/f44a6bb2af4c62847585305bbdc760fbe0e3645f/llvm/lib/Target/RISCV/RISCVVortexKEntry.cpp)：区分 Clang 已能生成 annotation 与 Vortex pass 实际消费 annotation 的责任。

在 evidence.md 中交付以下内容：

1. 一条你自己画出的链路：host buffer → 设备地址 → 参数 blob → launch → CSR → a0 → kernel → 结果读回。
2. demo 参数字段类型、偏移、总大小；解释三个 uint32_t 后为什么不能立刻放第一个 uint64_t。
3. 用源码位置说明程序启动入口、kernel body、入口 alias 各是什么。
4. 解释 `used`/`retain`、kernel annotation、uniform annotation 分别解决什么问题。
5. 指出 threadIdx 与 block 维度的 uniformity 有何差别；说明为什么 lane 内分歧会改变后端工作量。
6. 列出 `validate-compiler.sh` 中被测编译器负责什么、哪些组件仍复用参考版本。
7. 用三句话区分现有 chipStar HIP 路径与你将实现的原生 HIP 路径。

参考布局供核对：`num_tasks@0`、`task_size@4`、`dim_x@8`、`src0_addr@16`、`src1_addr@24`、`dst_addr@32`，总计 40 字节。需要解释原因，不能只抄这个数字。

### 7. 一个可选的诊断练习

阅读 `/home/kaikai/vortex-word/scripts/validate-compiler.sh` 后，可以尝试：

```bash
cd /home/kaikai/vortex-word
bash scripts/validate-compiler.sh /home/kaikai/vortex-word/build/llvm
```

未添加 Vortex 扩展的 LLVM 23 在这个验证中失败是预期现象；具体最早诊断取决于它碰到的扩展、编译选项和源码。记录第一处实际错误，不预设一定是哪一条。此时不要通过删除自定义指令、跳过 kernel 入口生成或替换成参考 compiler 来制造通过。

这个命令不是 T00 的通过条件；它是后续 T04/T05 的接入检查之一。当前脚本不是完整 HIP conformance 测试。

### 8. 完成条件与下一任务

- [ ] LLVM 23 完整构建成功，版本和四个 target 有记录。
- [ ] add.c 的 RV64 汇编与 IR 来自新编译器。
- [ ] 参考五项 smoke 全部通过，有日志。
- [ ] evidence.md 包含版本、ABI 链路、参数布局和七个问题的回答。
- [ ] 能清楚说明“本任务还没有为 LLVM 23 添加 Vortex/HIP 实现”。

附录完成后按 [课程主线](plan.md#tutorial-route) 继续。CPU、指令和 ABI 仍要实现，但按 L04～L07 的程序演进逐步引入；T01～T10 是工程验收分组，不要求为了开始学习语法就先完成整个 CPU 或指令阶段。
