# 第一课：验证 Triton Coral 后端骨架

这课在 `triton-coral` 的 `dev/triton-coral@4f045a9d77` 上复跑过。完成后能解释 Coral 如何被 Triton 发现，以及 Python 的编译请求如何到达 C++ 扩展和各个编译阶段。骨架已搭好时直接做下面的冒烟检查。

## 1. 运行冒烟检查

在 `compiler-1` 的 Linux shell 执行。其他环境将第一行改为自己的 checkout。

```bash
cd /home/compiler-1/work/coral/triton-coral
git rev-parse --short HEAD
TRITON_CACHE_DIR="$(mktemp -d /tmp/coral-skeleton-XXXXXX)" \
  TRITON_BACKENDS_IN_TREE=1 TRITON_DEFAULT_BACKEND=coral \
  .venv/bin/python third_party/coral/unittest/test1.py
```

检查输出中的三个信号。后端列表含 `coral`，C++ 返回 `Hello from Coral backend!`，编译返回的 payload 以 `/* Coral RISC-V Binary:` 开头。脚本里的“端到端编译成功”表示骨架编译链走到了末端。此时 `elf` 键里存的是占位文本，core0 执行在第二课验收。

## 2. 顺着调用链读代码

| 顺序 | 在 Triton checkout 中打开 | 观察点 |
| --- | --- | --- |
| 1 | `third_party/coral/backend/name.conf`、`setup.py` | 后端名为 `coral`。构建和安装把 Python backend 接到插件发现机制。 |
| 2 | `third_party/coral/CMakeLists.txt`、`triton_coral.cc` | CMake 加入插件，nanobind 暴露 `triton._C.libtriton.coral`。用 `coral.hello()` 单独检查这一层。 |
| 3 | `third_party/coral/backend/driver.py` | `TRITON_DEFAULT_BACKEND=coral` 选择 Coral driver。driver 提供目标信息，真实 launcher 待 S3 接通。 |
| 4 | `third_party/coral/backend/compiler.py` | `add_stages` 注册 `ttir → llir → elf`。`make_ttir` 维护 kernel 名和元数据，后两段当前是占位。 |
| 5 | `third_party/coral/unittest/test1.py` | `ASTSource` 指定输入类型，调用编译入口并读出产物。脚本的 kernel 是标量拷贝，名字是 `add_kernel`。 |

读到 `compiler.py` 时做一个对照练习。跟踪 `metadata["name"]` 从 TTIR 函数名传到 payload 的过程，再找出这两个占位段分别需要替换成什么产物。开始实现前阅读[标量单核闭环](../backend-skeleton.md)。

## 3. 如果冒烟检查失败

| 现象 | 先检查什么 |
| --- | --- |
| 后端列表缺少 `coral` | 确认 Python 来自这份 checkout 的虚拟环境。检查 in-tree 的 `python/triton/backends/coral` 和包入口注册。 |
| 找不到 `triton._C.libtriton.coral` | 核对 `TRITON_PLUGIN_DIRS`、Coral CMake 和当前加载的 `libtriton`。修改 native 源码后按该 checkout 的构建说明重建。 |
| 开始找 `cuda.h` | 先验证 Coral 已被发现且 driver 实际选择 Coral，再排查 GPU 依赖。 |
| build 或 import 链接错误 | 对照 `cmake/llvm-info.json`，确认使用固定 LLVM revision、Zvt 补丁与 MLIR 头库。 |

**完成信号**  能复跑骨架冒烟，并能在代码里指出正式 LLVM 降低和真实 ELF 生成的接入点。回到[第一次运行](../plan.md#第一次运行)生成教学用的 INT32 TTIR。

