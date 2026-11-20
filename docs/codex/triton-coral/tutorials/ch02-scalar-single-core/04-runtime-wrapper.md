# 2.4 节：运行时入口包装与 ABI v2 绑定

## 1. 这节课做什么
- **功能目标**：让入口按 v2 解析参数、调用 kernel 并发布完成。
- **支持语法**：`入口封装与硬件参数帧绑定`
- **涉及方言**：RISC-V 汇编 / 包装函数
- **阶段标记**：`S1-02`（所属章节：第 2 章：标量语法降级与单核 AOT 执行闭环）
- **实现注意**：对齐栈并保护参数区域。写回对消费者可见后再记录完成。

## 2. 核心代码实现
现有设备启动包装来自 `experiments/multicore/device/start.S`，在 RVV 和 Zvt 固件构建中复用。[完整启动源码](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/device/start.S)

```asm
.section .text.start,"ax",@progbits
.globl _start
.type _start,@function
_start:
  /* Each core has its own DTCM at the same local address. Stack is 16B aligned. */
  lui sp, 0x18
  lui a0, 0x10
#ifdef __riscv_vector
  /* Enable/dirty vector state before any RVV instruction. Controller stays RV32IM. */
  li t0, 0x600
  csrs mstatus, t0
#endif
  call kernel_entry
1:
  wfi
  j 1b
.size _start, .-_start
```

## 3. 解释说明与注释
`a0` 指向每核 DTCM 中的参数帧，`sp` 为 `0x00018000`。这个已有 wrapper 调用 `kernel_entry()`。以 v2 的 Zvt kernel 为例，版本校验、结果写回、fence 和置 done 在 `kernel_entry()` 里面，返回后由启动汇编进入 WFI。为 Triton 生成的入口保留这套控制约定，具体的 C 符号适配由本节后续实现。[已有 v2 调用实现](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/device/zvt.c)

## 4. 测试与验证代码
先按 [1.2](../ch01-skeleton/02-abi-contract.md) 校验 v2 字节布局，再对 2.5 节已有 `zvt.elf` 执行 `llvm-objdump -d`。查看 `_start` 的栈顶、入参、调用和 WFI。
