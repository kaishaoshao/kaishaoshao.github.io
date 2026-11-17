# LLVM 23.1.4 开发分支与构建

源码目录：`/home/kaikai/vortex-word/llvm-project`。

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
