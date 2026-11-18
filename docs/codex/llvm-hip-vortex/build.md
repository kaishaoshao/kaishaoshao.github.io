# LLVM 23.1.4 开发分支与构建

源码目录：`/home/kaikai/vortex-word/llvm-project`。

学习路线已改为 [从语法到执行的十课教程](plan.md#tutorial-route)。L01～L03 可以先用已安装参考 Clang 做观察，不必等待完整 LLVM 构建；L04 修改源码前需构建 LLVM 23，并重跑前面的观察实验。参考编译器和新编译器的证据分开记录。

本地分支 `dev/vortex` 基于 LLVM 官方 tag `llvmorg-23.1.4`，基线提交为 `7a941dfb2877a0b8cf30323fefa85ad019e0b0f5`。`origin` 保留为 `git@github.com:Learn-Compiler/llvm-project.git`；`upstream` 是官方 `https://github.com/llvm/llvm-project.git`。

## 使用

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

验证记录：2026-11-17 已通过 Bash 语法检查、CMake 配置与 Ninja dry-run（包含四个后端、Clang、LLD、llc、llvm-config）。本次没有执行完整 LLVM 编译。

## 验收范围与实际编译选项

LLVM 工具的 Release 构建类型与被测 kernel 的 -O 级别是两件事。固定 SDK 的 regression/common.mk 默认给设备代码使用 O3，validate-compiler.sh 会复用它；该脚本通过不能直接写成 O0/O2 都通过。后续按任务单独选择模式并保存真实编译命令，尤其核对最后生效的 -O、target-cpu、features、ABI 与 sysroot。

先以 SelectionDAG 为本教程代码生成路径。GlobalISel、LTO、fast-math 和完整设备库不是首个闭环的必要条件；如果命令启用了未验收路径，应诊断或在支持矩阵中明确限制。

该验证脚本还会复用参考版本的 LLD、打包器与设备静态库。即使 build.sh 构建出了新 LLD，也不能据此宣称验收已使用它。host 为 WSL x86_64 Linux，device 为 RV64 baremetal；分别记录工具路径、头文件/sysroot 与链接库，避免意外引入宿主库。

完整设计与检查项见 [实现契约](architecture.md#implementation-contracts) 和 [验收矩阵](plan.md#implementation-review)。这些是后续任务要求，本次没有重新执行完整构建或 SimX smoke。
