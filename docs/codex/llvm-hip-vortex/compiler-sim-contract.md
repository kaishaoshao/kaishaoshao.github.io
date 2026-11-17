# 编译器输出与 SimX 的接口

当前固定为 Vortex 3.0、RV64、默认硬件配置。

```text
你的 LLVM
  → 设备 kernel.o 与启动代码
  → 链接 kernel.elf（device runtime + libc + compiler-rt + link64.ld）
  → vxbin.py 打包 .vxbin
  → x86 host 经 Vortex SDK 加载和启动
  → SimX 执行设备指令
  → 下载结果，与 CPU 参考值比较
```

SimX 不解析 HIP 源码。结构正确的 ELF / `.vxbin` 还需要匹配指令集、启动流程、线程语义及参数 ABI，才能正确运行。

## 编译与链接

验收脚本使用 `vortex/tests/regression/common.mk` 的实际配置：

- ELF64 little-endian，RISC-V ET_EXEC。`.o` / ET_REL 必须先链接。
- target：`riscv64-unknown-elf`；默认 `rv64imafd` / `lp64d`，加 `+xvortex` 和 `+zicond`。A/C 等扩展要与模拟器配置一致。
- 原生 RV64 测试使用 `STARTUP_ADDR=0x180000000`、`-mcmodel=medany` 及 `sw/kernel/scripts/link64.ld`。
- 链接 `libvortex2.a`，编译并链接 KMU 启动代码。
- kernel 带 `vortex.kernel` annotation，后端生成 `__vx_kentry_<name>` 符号。`kernel_main` 在模块中暴露为 `main`。
- 启动代码建立栈等状态，读取选中的 kernel entry，将参数缓冲区指针放到 `a0` 后调用 kernel。设备启动入口与 kernel body 的函数入口有区别。

本地参考文件：

```text
vortex/tests/regression/common.mk
vortex/sw/kernel/include/vx_spawn2.h
vortex/sw/kernel/src/vx_start.S
vortex/sw/kernel/scripts/link64.ld
vortex/sw/kernel/scripts/vxbin.py
vortex/sw/runtime/include/vortex2.h
```

## 两个现成 host 的参数布局

默认类型与自然对齐下：

| host | 字段 | 类型 | 字节偏移 |
|---|---|---|---|
| demo | num_tasks | uint32_t | 0 |
| demo | task_size | uint32_t | 4 |
| demo | dim_x | uint32_t | 8 |
| demo | src0_addr | uint64_t | 16 |
| demo | src1_addr | uint64_t | 24 |
| demo | dst_addr | uint64_t | 32 |
| sgemm | size | uint32_t | 0 |
| sgemm | A_addr | uint64_t | 8 |
| sgemm | B_addr | uint64_t | 16 |
| sgemm | C_addr | uint64_t | 24 |

demo 参数结构 40 字节，默认 TYPE=int；sgemm 参数结构 32 字节，默认 TYPE=float。计算和矩阵布局以对应 kernel.cpp 与 CPU 参考实现为准。

`run-kernel.sh` 通过 host 的 `-k` 加载指定产物，不重新编译该输入 kernel；每次运行目录位于 `artifacts/runs/`。

## 新编译器验收

```bash
cd /home/kaikai/vortex-word
bash scripts/validate-compiler.sh /你的LLVM构建或安装目录
```

每次生成新的 `build/compiler-check.XXXXXX`，防止复用旧 kernel 导致假通过。被测 clang++ 编译 kernel 和启动代码；参考工具链提供已有 device runtime、LLD、打包与反汇编工具。它验证设备编译接入，不证明整个 runtime 已由新 LLVM 重编，也不证明完整 HIP 兼容。

后续应自行扩展分歧分支、共享内存 reduction、barrier、原子操作和更多 host/runtime 验收用例。
