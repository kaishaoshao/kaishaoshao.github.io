# L03.1 验证输出 buffer 和设备地址

先证明 host 能把一个已知值写入设备 buffer，再按顺序读回。

- **操作** 用 SDK 创建 device、queue 和 4 字节输出 buffer，查出它的 `uint64_t` 设备地址。写入 `-1`，等待完成后读回。
- **测试与通过标准** SDK 调用返回成功，读回仍是 `-1`，日志能对应 buffer 句柄、设备地址和本次传输。此项可与 wrapper 设计并行做。
- **实现注意** host 只能经 SDK 访问设备 buffer。将查询得到的地址保存为 RV64 参数值所需的 8 字节，host 指针只用于传输和准备参数。

## 输出地址从哪来

在 `llvm/unittests/Vortex/L03/host_store42.cpp` 中，`vx_buffer_create` 创建设备端 4 字节缓冲，`vx_buffer_address` 把它的设备地址写入 host 上的 `args.out_addr`。后续 launch 传递的是这个值的 8 个字节。可先把上传、读回 `-1` 做成一项独立练习，再接到完整 launch 中。

---

[上一节 · 4.3](00-diagnose-standalone.md) · [本章目录](chapter-05-sdk-launch.md) · [下一节 · L03.2](02-argument-wrapper.md)
