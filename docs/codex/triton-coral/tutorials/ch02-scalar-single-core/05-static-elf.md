# 2.5 节：生成可检查的静态 RV32 ELF

## 1. 这节课做什么
- **功能目标**：生成可检查的静态 RV32 ELF。
- **支持语法**：`静态 ELF32 生成与链接脚本`
- **涉及方言**：RV32IMF 机器码
- **阶段标记**：`S1-03`（所属章节：第 2 章：标量语法降级与单核 AOT 执行闭环）
- **实现注意**：检查 PT_LOAD、ISA、入口和 ITCM 容量。链接脚本预留的取指填充也占空间。

## 2. 核心代码实现
已有设备构建脚本 `tools/die/build_firmware.py` 对每个 C kernel 生成 `.ll`、`.s` 和 `.elf`。运行在 Coral 上的 add/complex/Zvt 使用设备的 `device/start.S` 与 `device/link.ld`，控制核另用 RV32IM 与 `die/firmware/link.ld`。链接步骤使用固定 SDK 的 Clang/LLD、`-mabi=ilp32`、`-nostdlib`、`--no-relax` 和 map 输出。[实际构建函数](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/tools/die/build_firmware.py)

## 3. 解释说明与注释
`device/link.ld` 的入口是 `_start`，ITCM 为 8 KiB，`.text` 使用 `FILL(0x13000000)` 填充至 256 字节边界。DATA 从 `0x10100` 开始，长度 `0x6f00`，保留参数及栈区。源码同时定义 RX 和 RW 的 `PT_LOAD`。已有自举镜像只走 ITCM 子集，Triton 的 `make_elf()` 接入时沿用相同地址及链接约定。[实际链接脚本](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/device/link.ld)

## 4. 测试与验证代码
```bash
cd /home/compiler-1/work/coral/coralnpu
sdk=/home/compiler-1/work/coral/coralnpu-compiler/out/llvm-zvt/install
"$sdk/bin/llvm-readelf" -h -l experiments/multicore/tools/die/logs/firmware/zvt.elf
```

2026-11-20 核对已有镜像为 ELF32、EXEC、RISC-V，入口为 0，RX LOAD 的文件与内存大小均为 `0x100`。它来自现有 C/Zvt 构建。Triton 内核的同项检查需使用实际 `make_elf()` 产物。
