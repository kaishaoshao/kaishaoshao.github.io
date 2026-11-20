# 4.1 节：接通 Coral driver 与 launcher 的真实分派

## 1. 这节课做什么
- **功能目标**：接通 Coral driver 与 launcher 的真实分派。
- **支持语法**：`kernel[grid](...) JIT 调用语法`
- **涉及方言**：DriverBase / Launcher 接口
- **阶段标记**：`S3-01`（所属章节：第 4 章：JIT 运行时与动态特化）
- **实现注意**：设备执行要使用真实 buffer。实际分派与输出 ELF 的哈希要能对应。

## 2. 核心代码实现
目前 `third_party/coral/backend/driver.py` 已给出 Coral 目标、基础参数类型映射和 Torch CPU 设备占位。目标查询实现如下。

```python
    def get_current_target(self) -> GPUTarget:
        return GPUTarget("coral", arch="rv32imf_zve32x", warp_size=1)
```

配套的 `coralnpu-compiler` 已有独立的 IREE HAL 驱动、仿真执行接口和 simulator ELF loader。以后比较装载、地址布局和分派指标时先看这些实现。[HAL 执行接口](https://github.com/Learn-Compiler/coralnpu-compiler/blob/5c68026/runtime/driver/coralnpu_exec_backend.h) · [仿真 ELF loader](https://github.com/Learn-Compiler/coralnpu-compiler/blob/5c68026/runtime/sim/simulator_elf_loader.c)

## 3. 解释说明与注释
Triton 的 `is_active()` 当前恒真，`get_benchmarker()` 返回 0。现有 `test1.py` 只用它取目标再走 AOT 编译。真实 buffer 管理、launcher 和设备计时需要与实际运行后端接通。IREE HAL 的状态属于其独立调用路径。

## 4. 测试与验证代码
先按 [1.1 节](../ch01-skeleton/01-toolchain-discovery.md) 复跑后端发现与目标查询。接入 launcher 后，按 [S3 验收](../../plan.md#s3-jit-与特化调用) 用 `kernel[grid](...)` 检查确实启动了本次编译得到的 ELF，并读取经过对照的输出。
