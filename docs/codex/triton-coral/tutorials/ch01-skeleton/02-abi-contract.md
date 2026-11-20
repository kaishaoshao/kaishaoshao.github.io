# 1.2 节：核对 RV32 v2 参数与地址约定

## 1. 这节课做什么

**S0-02**。直接读取现有固件用的 `NcKernelArgs`，核对编译器入口以后要遵循的字节布局和地址。设备基线为 `coralnpu@f9ab975c`。

## 2. 核心代码实现

`experiments/multicore/device/task_abi.h` 中，参数帧类型和常量如下。[设备 v2 头文件](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/device/task_abi.h)

```c
#define NC_KERNEL_ABI 2u
#define NC_ARGS_ADDRESS 0x00010000u

typedef struct {
  uint32_t abi, size, program_id[3], grid[3], core_id;
  uint32_t bindings[3], scalars[4], done;
} NcKernelArgs;
```

| 字段 | 字节偏移 | 含义 |
| --- | --- | --- |
| `abi`、`size` | 0、4 | 固定为 2、68。 |
| `program_id[3]` | 8–19 | 逻辑 program 的三个轴。 |
| `grid[3]` | 20–31 | 各轴的逻辑 program 数。 |
| `core_id` | 32 | 这次执行使用的物理 Coral 核。 |
| `bindings[3]` | 36–47 | 三个 RV32 设备地址槽。 |
| `scalars[4]` | 48–63 | 四个 32 位标量槽。 |
| `done` | 64 | 完成标志的设备地址。 |

## 3. 解释说明与注释

`queued_demo.c::start()` 在 Zvt 分支为每个选中核清零共享完成槽，然后把 68 字节写到该核的 DTCM `0x00010000`。当前调用方用 `{t->program_id+rank, 0, 0}` 和 `{t->grid, 1, 1}` 填三轴字段，物理核号单独填。`zvt.c::kernel_entry()` 检查版本和大小，写回结果后执行 `fence rw,rw`，再通过 `done` 指针写入 1。已有 RVV add 仍走 `kernel_abi.h` 中的 `ClusterArgs` v1。[固件调用方](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/die/firmware/queued_demo.c) · [设备 kernel](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/device/zvt.c)

## 4. 测试与验证代码

直接用 RV32 Clang 核对固件头文件。2026-11-20 在 compiler-1 通过。

```bash
cd /home/compiler-1/work/coral/coralnpu
sdk=/home/compiler-1/work/coral/coralnpu-compiler/out/llvm-zvt/install
"$sdk/bin/clang" --target=riscv32-unknown-elf -march=rv32imf -mabi=ilp32 \
  -std=c11 -ffreestanding -I experiments/multicore/device -x c -fsyntax-only - <<'C'
#include <stddef.h>
#include "task_abi.h"
_Static_assert(NC_KERNEL_ABI == 2, "ABI version");
_Static_assert(NC_ARGS_ADDRESS == 0x10000, "parameter base");
_Static_assert(sizeof(NcKernelArgs) == 68, "frame size");
_Static_assert(offsetof(NcKernelArgs, program_id) == 8, "program_id");
_Static_assert(offsetof(NcKernelArgs, grid) == 20, "grid");
_Static_assert(offsetof(NcKernelArgs, core_id) == 32, "core_id");
_Static_assert(offsetof(NcKernelArgs, bindings) == 36, "bindings");
_Static_assert(offsetof(NcKernelArgs, scalars) == 48, "scalars");
_Static_assert(offsetof(NcKernelArgs, done) == 64, "done");
C
```

教程的 `examples/abi.py` 使用同一布局，可以用 `test_v2_layout_and_capacity` 复核宿主打包。Triton 生成入口的验收见 [2.4 节](../ch02-scalar-single-core/04-runtime-wrapper.md)。
