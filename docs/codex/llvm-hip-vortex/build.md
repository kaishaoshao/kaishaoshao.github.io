# 构建准备：LLVM 编译器与 Vortex SimX

更新日期：2026-11-19（Asia/Shanghai）。本页区分两个不同目录里的 build.sh，先按用途选择。

| 你要构建什么 | 工作目录/脚本 | 输出 | 使用时点 |
|---|---|---|---|
| 新 LLVM 23 编译器 | llvm-project/build.sh | build/llvm、install/llvm | L02 首次源码改动前；后续增量编译 |
| 参考 Vortex SDK/SimX | vortex/build.sh | vortex/build64、build64/install | L03 执行前；修改 SDK/配置后重建 |

两个脚本已经存在于本机的各自源码树，不是本 Markdown 仓库内可自动下载的文件。新 LLVM 的构建与 Vortex/HIP 扩展完成分别验收。

<a id="llvm-build"></a>

## 1. LLVM 23 编译器

源码目录：`/home/kaikai/vortex-word/llvm-project`。

学习路线已改为 [从 store42 到已有 HIP 程序的六阶段教程](plan.md#tutorial-route)。L01 的三个前端实验可以先用已安装参考 Clang 做观察，不必等待完整 LLVM 构建；L02 修改源码前需构建 LLVM 23，并重跑前面的观察实验。参考编译器和新编译器的证据分开记录。

本地分支 `dev/vortex` 基于 LLVM 官方 tag `llvmorg-23.1.4`，基线提交为 `7a941dfb2877a0b8cf30323fefa85ad019e0b0f5`。`origin` 保留为 `git@github.com:Learn-Compiler/llvm-project.git`；`upstream` 是官方 `https://github.com/llvm/llvm-project.git`。2026-11-19 源码已包含用户提交 `c447d813c43ffd97e973c7e582175a60286c1b50`（构建脚本与 L01 实验），不要重置到基线。

### 首次构建与增量构建

```bash
cd /home/kaikai/vortex-word/llvm-project

# 只生成构建目录
./build.sh --configure-only

# 配置并编译
./build.sh

# 配置、编译并安装
./build.sh --install
```

默认构建 Clang、LLD 和 LLVM，目标为：

| target | 用途 |
|---|---|
| AMDGPU | AMD GPU 后端 |
| RISCV | RISC-V 后端，后续承载 Vortex 扩展 |
| NVPTX | NVIDIA GPU 的 PTX 后端 |
| X86 | 本机 host 代码生成 |

默认 Release、assertions=ON、4 个编译任务、1 个链接任务。可用 ccache 时自动启用；可用 LLD 时使用它链接。这里构建编译器和链接器，Vortex/HIP 扩展仍由你后续实现。

构建目录是 `/home/kaikai/vortex-word/build/llvm`，安装目录是 `/home/kaikai/vortex-word/install/llvm`。

```bash
# 调整并行度
JOBS=6 ./build.sh

# 指定其他构建/安装位置
BUILD_DIR=/绝对路径/build INSTALL_DIR=/绝对路径/install ./build.sh --install

# 传入额外 CMake 参数
./build.sh -- -DLLVM_ENABLE_ASSERTIONS=OFF
```

还可设置 `CC`、`CXX`、`BUILD_TYPE`、`ASSERTIONS`、`LINK_JOBS`。

编译完成后查看版本与后端：

```bash
../build/llvm/bin/clang --version
../build/llvm/bin/llvm-config --targets-built
../build/llvm/bin/llc --version
```

后续你的 Vortex 扩展实现好后，可将这个 build 目录直接交给已有 SimX 验收脚本：

```bash
cd /home/kaikai/vortex-word
bash scripts/validate-compiler.sh "$PWD/build/llvm"
```

构建记录：2026-11-17 配置/dry-run 是历史记录。2026-11-19 已查询本机 Clang 23.1.4（assertions 开启）、AMDGPU/RISCV/NVPTX/X86 四个目标，并确认 llvm-mc、FileCheck、llvm-lit 工具存在；本次未重新执行完整 LLVM 编译。源码 HEAD、--version 内嵌构建修订和构建日志分别记录，不能因提交了新实验就声称二进制也重新编译。

编译器修改后优先构建受影响工具，例如：

```bash
cmake --build /home/kaikai/vortex-word/build/llvm --parallel 4 \
  --target clang llvm-mc llvm-objdump llc opt FileCheck
```

随后对自己新增的对应测试做定向 lit/FileCheck，不每次运行全部后端测试。用户目前放在 llvm/unittests/Vortex/101 的手工教学输入继续保留，但没有因为目录名是 unittests 就自动注册到 CMake/lit；正式回归分别放入 Clang CodeGen/Sema/Driver 和 LLVM MC/CodeGen/Transforms 的相应测试目录。

<a id="simx-build"></a>

## 2. 参考 Vortex SDK/SimX

```bash
cd /home/kaikai/vortex-word/vortex
./build.sh --help
./build.sh --configure-only
./build.sh -j 4 --test
```

默认 RV64、4 个 make 任务，构建设备库、host stub、SimX/runtime 并安装到 build64/install；--test 运行 native demo。日志在 build64/build.log，可通过 BUILD_DIR、TOOLDIR、INSTALL_DIR 指定其他路径；不同主配置使用独立目录，不清理或覆盖另一配置来切换位宽。

该脚本已有一次 demo PASSED 的历史执行记录；本次文档复核没有重跑它，也不将它计为新 HIP 后端执行。它复用现有参考工具链：设备库当前用 RV64 GNU 工具链，demo 的设备应用由参考 Clang 编译。精确组件来源见实际命令，不统称为“全由 LLVM 23 构建”。

A/C 的启用状态来自所选 SDK/SimX 配置；参考 Makefile 含 A 的历史参数不能作为模拟器已开启 A 的依据，见 [配置差异](architecture.md#isa-config)。

## 3. 验收范围与实际编译选项

LLVM 工具的 Release 构建类型与被测 kernel 的 -O 级别是两件事。固定 SDK 的 regression/common.mk 默认给设备代码使用 O3，validate-compiler.sh 会复用它；该脚本通过不能直接写成 O0/O2 都通过。后续按任务单独选择模式并保存真实编译命令，尤其核对最后生效的 -O、target-cpu、features、ABI 与 sysroot。

先以 SelectionDAG 为本教程代码生成路径。GlobalISel、LTO、fast-math 和完整设备库不是首个闭环的必要条件；如果命令启用了未验收路径，应诊断或在支持矩阵中明确限制。

该验证脚本还会复用参考版本的 LLD、打包器与设备静态库。即使 build.sh 构建出了新 LLD，也不能据此宣称验收已使用它。host 为 WSL x86_64 Linux，device 为 RV64 baremetal；分别记录工具路径、头文件/sysroot 与链接库，避免意外引入宿主库。

完整设计与检查项见 [实现契约](architecture.md#implementation-contracts) 和 [验收矩阵](plan.md#implementation-review)。这些是后续任务要求，本次只重跑 L01 前端观察，未重新执行完整构建或五项 SimX smoke。
