# 10.1 节：建立可解释的单缓冲性能基线

## 1. 这节课做什么
- **功能目标**：建立可解释的单缓冲性能基线。
- **支持语法**：`性能剖析与分项耗时模型`
- **涉及方言**：耗时基线评估
- **阶段标记**：`S9-01`（所属章节：第 10 章：类型扩展与执行优化）
- **实现注意**：模型周期和宿主耗时分开。预热策略、配置和输入应可复现。

## 2. 核心代码实现
现有 `device/profile.h` 定义 32 字节性能记录，kernel 实际读取设备 CSR。算子产物与运行报告由 `tools/die/operators.py` 管理。[设备采样](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/device/profile.h) · [报告实现](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/tools/die/operators.py)

```c
static inline CoralCounterSample coral_counter_sample(void) {
  CoralCounterSample sample;
  __asm__ volatile("csrr %0, mcycle\n\tcsrr %1, minstret"
                   : "=r"(sample.cycle), "=r"(sample.instret) :: "memory");
  return sample;
}
```

## 3. 解释说明与注释
`device/add.c` 和 `device/complex.c` 在源码划定的采样区间读两次计数。共享记录先写各字段，经 fence 后发布 `PROFILE_MAGIC`。宿主报告区分每核 `minstret` 差值、全局 START/END 周期跨度、RTL 派发次数和宿主仿真耗时。多核并行时全局算子跨度不能用各核周期求和。

## 4. 测试与验证代码
用已构建的控制固件与仿真器运行一个算子。在 Zvt/存储分支切换镜像时先确认固件与仿真器配置兼容。

```bash
cd /home/compiler-1/work/coral/coralnpu
python3 experiments/multicore/tools/ncoral.py op list
python3 experiments/multicore/tools/ncoral.py op run gemm --rows 7
```

已有记录覆盖 23 项 RVV RTL 用例和 5 项报告校验，ADD 从 1 到 128 元素的总退休指令由 41 增至 416。命令输出的 `profile.json` 记录数值检查、实际计数和镜像版本。这份基线对应已有 C/RVV 算子。[指标口径](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/docs/operator_profiling.md) · [验证结果](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/docs/profiling_verification.md)
