# 9.3 节：按固定 SDK 生成可执行的 Zvt 指令

## 1. 这节课做什么
- **功能目标**：按固定 SDK 生成可执行的 Zvt 指令。
- **支持语法**：`Zvt 专用矩阵指令生成 (minit, mload, mmul 等)`
- **涉及方言**：Coral Zvt 指令集
- **阶段标记**：`S8-03`（所属章节：第 9 章：INT8 Matrix 语法与 Coral Zvt 矩阵加速）
- **实现注意**：核对 mstatus 使能及矩阵配置状态。矩阵活跃区间内要保护 mtype/altfmt，注意 vsetvli 的影响。

## 2. 核心代码实现
已有 INT8→INT32 microkernel 在 `coralnpu` 的 `experiments/multicore/device/zvt.c`。入口验证 v2 参数帧，用三个 binding 读取 A/B/C 地址。先设置 `mstatus` 中的 `0x60000000`，再用 `msetmtype`、`msettn`、`vtzero` 配置并清零 tile。接着四次 `vle8.v` 取数和 `vtmms.tvv` 累加，最后以 `vtmv.v.t`、`vse32.v` 写回各行并执行 `vtdiscard`。[含完整汇编与寄存器约束的源码](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/device/zvt.c)

## 3. 解释说明与注释
现有微内核的 16×16×4 分块使用有符号 INT8，结果逐项验证为 INT32。加载、配置、累加和取行放在同一 asm 块内，避免中间的 `vsetvli` 重置矩阵状态。已有 LLVM 补丁提供指令编码及工具链支持。后续 Triton 的 dot lowering 要从真实 TTIR 决定如何调用或生成该内核。[固定 LLVM 补丁](https://github.com/Learn-Compiler/coralnpu-compiler/blob/5c68026/llvm-project-0001-add-zvt-support.patch)

## 4. 测试与验证代码
在 compiler-1 已有 Zvt 固件中查指令，并以现有仿真入口验证设备执行。

```bash
cd /home/compiler-1/work/coral/coralnpu
sdk=/home/compiler-1/work/coral/coralnpu-compiler/out/llvm-zvt/install
"$sdk/bin/llvm-objdump" -d experiments/multicore/tools/die/logs/firmware/zvt.elf \
  | grep -E 'msetmtype|vtmms\.tvv|vtmv\.v\.t'
python3 experiments/multicore/tools/ncoral.py pipeline --zvt --test --jobs 2
```

历史记录中两组有符号 INT8 回归均逐项检查 1024 个输出，共四个核且每核 4 次矩阵派发，checksum 为 177。[执行验证](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/docs/dma_events_zvt_validation.json)
