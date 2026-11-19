# L01：从 HIP 源码观察 AST、语义检查与 RISC-V IR

更新日期：2026-11-19（Asia/Shanghai）。这是 [六阶段教程](plan.md#tutorial-route) 的第一阶段，包含 1.1～1.3 三个小实验。先做实验，再读对应解释；工程基线保留在文末附录，首次修改源码前按需完成。

<a id="lesson-1"></a>

## 开始前：本阶段回答什么

读完并完成实验后，你应能解释：Clang 怎样识别 __global__；为什么某些 host/device 调用非法；<<<>>> 在 AST 中是什么；一个 HIP 函数怎样生成 RISC-V IR，以及为什么这还不是可执行的 Vortex 镜像。

本阶段只观察已有能力，不改 Parser、后端或 runtime，也不启动 SimX。你已经在 LLVM 仓库提交的 `llvm/unittests/Vortex/101/` 实验继续保留；下面用固定输入补齐反例和启动表达式，避免覆盖你的原记录。

## 准备编译器、输入和输出目录

在 **WSL Ubuntu-22.04 的 Bash** 中执行。文档仓库路径按本机位置设置；其他机器修改 VORTEX_DOCS_ROOT 即可。

```bash
bash
export VORTEX_WORD_ROOT=/home/kaikai/vortex-word
export VORTEX_DOCS_ROOT=/mnt/c/Users/20327/Documents/ChatGPT/learn/kaishaoshao.github.io/docs/codex/llvm-hip-vortex
export HIP_TUTORIAL_CLANG="$VORTEX_WORD_ROOT/build/llvm/bin/clang++"
"$HIP_TUTORIAL_CLANG" --version
mkdir -p "$VORTEX_WORD_ROOT/artifacts/tutorial/l01"
export L01_OUT="$(mktemp -d "$VORTEX_WORD_ROOT/artifacts/tutorial/l01/manual-XXXXXX")"
cp "$VORTEX_DOCS_ROOT/examples/l01/"*.hip "$L01_OUT/"
printf '本次输出：%s\n' "$L01_OUT"
```

当前优先使用你构建的 LLVM 23。需要参考对照时，将 HIP_TUTORIAL_CLANG 显式改为 `/home/kaikai/vortex-word/tools/llvm-vortex/bin/clang++`，并使用新的输出目录，分别记录版本。不要因目录名含 llvm 就假定它是新编译器。

也可以先运行汇总检查，再逐条理解后面的命令：

```bash
python3 "$VORTEX_DOCS_ROOT/examples/run_l01.py" \
  --clang "$HIP_TUTORIAL_CLANG" \
  --output-root "$VORTEX_WORD_ROOT/artifacts/tutorial/l01"
```

检查脚本保存输入副本、SHA-256、完整命令、stdout/stderr、IR 和 report.json；每次创建独立目录。它检查七项前端观察（包括版本），两个反例应由编译器拒绝；只有诊断内容也匹配才算该反例通过。脚本通过不证明任何设备执行能力。

## 实验 1.1：宏和 AST

输入是 [attributes.hip](examples/l01/attributes.hip)：

```cpp
#define __global__ __attribute__((global))
#define __device__ __attribute__((device))
#define __host__ __attribute__((host))

__device__ int twice(int v) {
  return v * 2;
}

__global__ void store42(int* out) {
  *out = 42;
}
```

先看预处理，再看 AST：

```bash
"$HIP_TUTORIAL_CLANG" -x hip --offload-host-only -nogpuinc -nogpulib \
  -E -P "$L01_OUT/attributes.hip" > "$L01_OUT/attributes.ii"
cat "$L01_OUT/attributes.ii"

"$HIP_TUTORIAL_CLANG" -x hip --offload-host-only -nogpuinc -nogpulib \
  -fsyntax-only -Xclang -ast-dump "$L01_OUT/attributes.hip" \
  > "$L01_OUT/attributes.ast.txt"
rg 'FunctionDecl|CUDADeviceAttr|CUDAGlobalAttr' "$L01_OUT/attributes.ast.txt"
```

预期：预处理后限定符成为属性；twice 的 AST 带 CUDADeviceAttr，store42 带 CUDAGlobalAttr。CUDA 前缀来自 Clang 的共享实现，不表示选择了 NVIDIA 设备。地址和源码位置可变化，不比较固定 AST 十六进制地址。

这里用宏写出真实属性，方便观察；把 __global__ 定义为空会丢掉语义。-x hip 选择语言；host-only 只走本次观察所需的 host 路径；nogpuinc/nogpulib 排除默认 GPU 支持头/库。你尚未生成设备镜像，也尚未检查全部设备侧语义。

自己做：增加显式 __host__ 函数和未标记函数，解释各自的调用侧；默认 host 语义不一定对应一个显式 CUDAHostAttr。交付输入改动、AST 摘要和“宏→属性→AST”的解释。

<a id="l01-sema"></a>

## 实验 1.2：非法调用和启动表达式

先检查 [illegal-host-call.hip](examples/l01/illegal-host-call.hip)。host 函数直接调用仅 device 可用的函数，下面的编译命令**预期非零退出并给出 device_only 的调用侧诊断**：

```bash
"$HIP_TUTORIAL_CLANG" -x hip --offload-host-only -nogpuinc -nogpulib \
  -fsyntax-only "$L01_OUT/illegal-host-call.hip" \
  > "$L01_OUT/host-to-device.stdout.txt" 2> "$L01_OUT/host-to-device.stderr.txt"
cat "$L01_OUT/host-to-device.stderr.txt"
```

反方向使用设备语义检查：[illegal-device-call.hip](examples/l01/illegal-device-call.hip) 中，kernel 调用 host_only，下面也预期被拒绝。host-only 成功不能代替这一项。

```bash
"$HIP_TUTORIAL_CLANG" -cc1 -triple riscv64-unknown-elf \
  -target-cpu generic-rv64 -target-feature +m -target-feature +f -target-feature +d \
  -target-abi lp64d -x hip -fcuda-is-device -fsyntax-only \
  "$L01_OUT/illegal-device-call.hip" \
  > "$L01_OUT/device-to-host.stdout.txt" 2> "$L01_OUT/device-to-host.stderr.txt"
cat "$L01_OUT/device-to-host.stderr.txt"
```

最后观察 [launch-ast.hip](examples/l01/launch-ast.hip)：

```bash
"$HIP_TUTORIAL_CLANG" -x hip --offload-host-only -nogpuinc -nogpulib \
  -fsyntax-only -Xclang -ast-dump "$L01_OUT/launch-ast.hip" \
  > "$L01_OUT/launch.ast.txt"
rg 'CUDAKernelCallExpr|__hipPushCallConfiguration' "$L01_OUT/launch.ast.txt"
```

预期命令成功，AST 中有 CUDAKernelCallExpr 和配置函数引用。该夹具里的 dim3 与 __hipPushCallConfiguration 声明只为 AST 实验服务；没有实现函数，也没有冻结正式 HIP ABI，不能链接成可运行应用。

自己做：在 AST 中分别指出 grid/block、普通 kernel 参数、隐式配置调用。源码入口为 `clang/lib/Sema/SemaCUDA.cpp`，先追调用侧判定与执行配置，再在 L05 阅读 host stub。不要为通过反例而删除函数属性。

<a id="l01-ir"></a>

## 实验 1.3：生成设备 IR，判断还缺什么

```bash
"$HIP_TUTORIAL_CLANG" -cc1 -triple riscv64-unknown-elf \
  -target-cpu generic-rv64 -target-feature +m -target-feature +f -target-feature +d \
  -target-abi lp64d -x hip -fcuda-is-device \
  -emit-llvm -O0 -o "$L01_OUT/device.ll" "$L01_OUT/attributes.hip"
rg 'target |define |store i32 42|attributes #' "$L01_OUT/device.ll"
```

这里故意通过内部 cc1 接口选择 generic-rv64，绕过公共 HIP offload driver；因此 CPU 属性是 generic-rv64 很正常。+d 与 lp64d 配套，不能把它误抄成重复的 +f。IR 通常把 triple 规范化为 riscv64-unknown-unknown-elf，DataLayout 描述目标布局。

2026-11-19 对本机 Clang 23 的观察包括 `store i32 42`、target-cpu/target-features、convergent、optnone 和 uniform-work-group-size 等属性；两个函数都可带 uniform-work-group-size，不能据此唯一识别 kernel。参考 Clang 20 的属性形式略有不同，均以实际版本产物为准。

**正确结论是：Clang 已识别 HIP 函数并生成普通 RISC-V IR；尚未建立供 Vortex 下游稳定消费的逻辑 kernel 标识、native 参数入口和启动链。** 不能说“IR 完全没有属性/信息”，也不能说“没有 SIMT 指令就说明编译失败”。

store42 的函数体只做一次普通 store，本来不必出现 SPLIT/JOIN。后续特殊指令主要来自启动环境和真正需要分歧控制/同步的程序。CPU 选择、逻辑 kernel 标记、native wrapper、SIMT 转换是四件不同的工作，详见 [桥接关系](architecture.md#hip-ir-bridge)。

自己做：指出两个函数的真实符号、调用约定、目标属性和 store；解释为什么既不能用函数名，也不能只用 uniform-work-group-size 判定可启动入口。不要为了“IR 看起来像 GPU”给每个函数硬插一条 TMC。

## 本阶段交付与下一步

| 检查 | 应观察到什么 | 尚未证明什么 |
|---|---|---|
| 预处理、属性 AST | 宏展开、CUDAGlobalAttr/CUDADeviceAttr | Vortex kernel ABI |
| 两种非法调用 | 对应函数的调用侧诊断 | 完整 HIP/C++ 语义覆盖 |
| 启动 AST | CUDAKernelCallExpr、配置函数 | host runtime 已实现 |
| 设备 IR | RISC-V triple/DataLayout、函数和 store | 正式 driver、镜像与 SimX 执行 |

保存本次输出，并使用 [证据模板](evidence-template.md) 写下你的解释。run_l01.py 的 PASS 是观察检查通过；整个课程交付还包含阅读与回答，不能自动完成 T00/T07/T08 整组。

下一步进入 [L02](plan.md#l02)：先用已有源码定位 target CodeGen 的扩展点，再为逻辑 HIP kernel 设计最小标记及正/反例。基础 CPU/feature 和首条 MC 指令按小提交推进。

已记录的历史实验见 [证据与进度](plan.md#03-已核对的教学实验与证据边界)。2026-11-19 新增标准夹具在 Clang 23.1.4 和参考 Clang 20.1.8 各执行一次，七项观察检查全部通过；没有运行新后端设备镜像。

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
