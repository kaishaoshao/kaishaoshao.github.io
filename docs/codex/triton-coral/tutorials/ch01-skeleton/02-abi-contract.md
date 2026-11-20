# 1.2 节：约定 RV32 v2 参数与地址约定

## 1. 这节课做什么
- **功能目标**：写清 RV32 v2 参数和最小地址约定。
- **支持语法**：`指针参数与常量参数传递规范`
- **涉及方言**：task_abi v2 内存结构体
- **阶段标记**：`S0-02`（所属章节：第 1 章：验证 Triton 后端发现与 C++ 插件骨架）
- **实现注意**：`done` 是对齐的设备地址。逻辑 program ID 和物理核号分开。

## 2. 核心代码实现
```c
// experiments/multicore/device/task_abi.h (v2 ABI)
struct NcKernelArgs {
  uint32_t abi;            // offset 0, value = 2
  uint32_t size;           // offset 4, value = 68
  uint32_t program_id;     // offset 8
  uint32_t num_programs;   // offset 12
  uint32_t core_id;        // offset 16
  uint32_t binding_count;  // offset 20 (<= 3)
  uint32_t scalar_count;   // offset 24 (<= 4)
  uint32_t bindings[3];    // offset 28..39 (RV32 pointers)
  uint32_t scalars[4];     // offset 40..55 (32-bit values)
  uint32_t reserved[2];    // offset 56..63
  uint32_t done;           // offset 64 (device address to write 1)
};
```

## 3. 解释说明与注释
- **基址规范**：参数帧位于 DTCM `0x00010000`，大小 68 字节（最大占用前 256 字节参数预留区）。
- **完成通知**：Kernel 执行完毕后必须执行 `fence rw, rw`，然后向 `args->done` 地址写 `1`。
- **栈指针约定**：Core0 栈顶设置为 `sp = 0x00018000`（16 字节对齐）。

## 4. 测试与验证代码
```bash
cd /home/compiler-1/learn/kaishaoshao.github.io/docs/codex/triton-coral
/home/compiler-1/work/coral/triton-coral/.venv/bin/python -m unittest \
  -k test_v2_layout_and_capacity examples/test_suite.py
```
