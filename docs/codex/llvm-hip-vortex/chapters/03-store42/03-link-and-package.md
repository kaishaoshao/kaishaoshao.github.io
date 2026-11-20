# L03.3 链接启动代码并检查镜像

把设备对象、参考 startup 和所需库变成可由 SDK 加载的 `.vxbin`。

- **操作** 依据 SDK `tests/regression/common.mk` 和 `link64.ld` 选择链接步骤，记录参考 startup、库、LLD 和打包器的实际来源。
- **测试与通过标准** 用 `llvm-readelf -h -l -s -A` 核对 `kernel.elf` 的 `ET_EXEC`、`_start`、入口 alias、装载段和 `_edata/_end`。用 `scripts/inspect-kernel.py` 检查打包文件的映射范围和 `main` 入口，确认入口地址指向 wrapper。缺失入口名应在加载检查或查找 kernel 时显式暴露。
- **实现注意** 记录 `program_pc` 对应的公共 startup 和 `kernel_pc` 对应的 wrapper。留意链接器回收 section，以及 `.vxbin` 文件 payload 和含 BSS 的内存范围差异。复用 startup 时记录 TMC/WSYNC 来自参考环境。[启动路径](../../compiler-sim-contract.md#两个-pc-与真实启动路径)

## 从 ELF 到镜像入口

用户 `build-00.sh` 复用 SDK 的预编译 startup、库与链接脚本，把 `kernel_wrapper.o` 和新 LLVM 生成的 `store42.o` 链接起来。

```bash
"$REF_TOOLS/clang++" --target=riscv64-unknown-elf -march=rv64imafd -mabi=lp64d \
    -mcmodel=medany -nostartfiles -nostdlib \
    -Wl,-Bstatic,--gc-sections,-T,"$VORTEX_HOME/sw/kernel/scripts/link64.ld",--defsym=STARTUP_ADDR=0x180000000 \
    "$BASELINE/sw/kernel/vx_start.S.2.o" kernel_wrapper.o store42.o \
    -L "$BASELINE/sw/kernel" -lvortex2 \
    -L "$TOOLS/libc64/lib" -lm -lc \
    "$TOOLS/libcrt64/lib/baremetal/libclang_rt.builtins-riscv64.a" \
    -o kernel.elf
```

这里沿用参考工具的 `rv64imafd`，其中 A 与默认 SimX 的配置有差异。本例只读写普通内存，验证范围不含原子指令。若从源码编译 `vx_start.S`，通过 SDK 构建规则取得生成的 `VX_types.h` 与匹配的配置宏。

打包时，`sw/kernel/scripts/vxbin.py` 从 ELF 符号表获取 `__vx_kentry_*`，并将 `__vx_kentry_kernel_main` 映射为 `main`。遇到 `kernels: []`，先检查别名是否存在以及 `--gc-sections` 后是否仍被保留。用户记录的镜像报告中，`main` 对应 `0x180000060`，payload 为 4096 字节。复现时以本次链接的结果为准。

---

[上一节 · L03.2](02-argument-wrapper.md) · [本章目录](README.md) · [下一节 · L03.4](04-sdk-launch.md)
