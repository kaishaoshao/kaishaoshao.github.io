# LLVM/HIP 工程基线与 L01 实验索引

<a id="lesson-1"></a>

## L01 前端实验

准备编译器与输入，从章首页选择实验。[第 1 章 · 读懂 HIP 前端](chapters/01-hip-frontend/README.md)

- <a id="l01-attributes"></a>[L01.1 宏展开与属性 AST](chapters/01-hip-frontend/01-attributes.md)
- <a id="l01-sema"></a>[L01.2 调用侧限制与启动表达式](chapters/01-hip-frontend/02-sema-launch.md)
- <a id="l01-ir"></a>[L01.3 设备 IR 与后续接口](chapters/01-hip-frontend/03-device-ir.md)

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

参考 Clang 20.1.8 + SDK + SimX 有历史通过记录；2026-11-19 已实际查询到你构建的 Clang 23.1.4 和 AMDGPU/RISCV/NVPTX/X86 四个目标。完整构建日志与各项工程验收仍按实际证据记录。先区分“标准 RISC-V 编译器正常”“参考 Vortex 系统正常”“新编译器已支持 Vortex”三个结论，后续才能定位错误。

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

LLVM 分支 `dev/vortex` 的原始基线为 `7a941dfb2877a0b8cf30323fefa85ad019e0b0f5`；2026-11-19 你的提交已推进至 `c447d813c43ffd97e973c7e582175a60286c1b50`，包含 build.sh 与 L01 实验。SDK 固定 HEAD 为 `26d2bc4b5409a35a111e8316ac3a87d07b15fc80`。保留已有提交、构建文件与实验。如果你已经有新的修改，先记录，后续验收以实际 commit/diff 为准。

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
  -march=rv64imfd -mabi=lp64d -O2 -S \
  artifacts/tutorial/t00/add.c -o artifacts/tutorial/t00/add.s

build/llvm/bin/clang --target=riscv64-unknown-elf \
  -march=rv64imfd -mabi=lp64d -O2 -S -emit-llvm \
  artifacts/tutorial/t00/add.c -o artifacts/tutorial/t00/add.ll
```

验收：生成 RISC-V 汇编及 IR，能解释参数/返回值和 IR 的 target triple/DataLayout。这里没有链接 libc、没有启动代码，也没有 Vortex 指令；它仅验证标准 RISC-V 编译路径。此处显式不声明 A/C；这与 SDK 参考 Makefile 的含 A 参数有区别，见 [配置说明](architecture.md#isa-config)。不要把这个 `.s` 或 `.o` 直接交给 SimX 当完整 kernel。

### 5. 复跑参考工具链的执行基线

```bash
cd /home/kaikai/vortex-word
set -o pipefail
bash scripts/run-smoke.sh 2>&1 | tee artifacts/tutorial/t00/reference-smoke.log
```

验收：native demo、native sgemm、OpenCL vecadd、现有 chipStar 路径的 HIP vecadd/sgemm 五项通过。逐项日志位于 `/home/kaikai/vortex-word/logs/latest-smoke`。这一步仍用参考工具链，不证明 LLVM 23 已支持 Vortex/HIP。

如果参考基线失败，先修复配置或依赖，再开始后端任务；不要把失败写成“新 pass 有问题”。SimX 是在 host 上运行的 C++ 指令/时序模型；它的墙钟运行时间与模型周期都不能直接等同于 FPGA 实测性能。

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

附录完成后按 [课程主线](plan.md#tutorial-route) 继续。CPU、指令和 ABI 仍要实现，但按 L02～L04 的程序演进逐步引入；T01～T10 是工程验收分组，不要求为了开始学习语法就先完成整个 CPU 或指令阶段。
