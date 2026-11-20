# L03.2 用 wrapper 解包一个指针

把 SDK 传入的单参数区与 `store42(int* out)` 的形参接起来。

- **操作** 先在 IR 层练习接收 `arg_blob` 的教学 wrapper，从偏移 0 读出设备指针，再调用本次实际符号对应的 body。随后对照本节的 C++ wrapper 核对参数布局和入口别名。[示意 IR](../../compiler-sim-contract.md#l03-walkthrough)
- **测试与通过标准** 合并后的 IR 通过 `opt -passes=verify -disable-output`。手工核对 8 字节参数区与一处解包。可用 `0x0102030405060708` 检查小端序列化结果 `08 07 06 05 04 03 02 01`，执行时改用 L03.1 取得的真实设备地址。
- **实现注意** startup 交给 wrapper 的 `a0` 指向参数区。wrapper 加载出的 out 才指向输出 buffer。保留 body 的类型、调用约定和对齐约束。

## 阅读实际的 wrapper

`llvm/unittests/Vortex/L03/kernel_wrapper.cpp` 中，SDK 启动代码从 `MSCRATCH` 取得参数包地址，再由 `a0` 传给入口。下面是这份教学桥接的核心代码。

```cpp
#include <stdint.h>

struct kernel_arg_t {
  uint64_t out_addr;
};

// 引用编译出的设备端符号
extern "C" void _Z7store42Pi(int* out);

// 硬件约定的单指针入口
extern "C" __attribute__((used, retain)) void kernel_main(kernel_arg_t* arg) {
  _Z7store42Pi(reinterpret_cast<int*>(arg->out_addr));
}

// 供 vxbin.py 识别的内核符号导出别名
extern "C" __attribute__((used, retain)) void __vx_kentry_kernel_main(kernel_arg_t* arg)
    __attribute__((alias("kernel_main")));
```

把参数值传到 `store42` 需要一次加载。`arg` 先指向参数包，`arg->out_addr` 给出真正的输出地址。独立 ELF 的 `_start` 可以直接为 `a0` 准备输出地址。后续自动 HIP 流程将在 L05.3 按签名生成这一层。

---

[上一节 · L03.1](01-device-buffer.md) · [本章目录](chapter-05-sdk-launch.md) · [下一节 · L03.3](03-link-and-package.md)
