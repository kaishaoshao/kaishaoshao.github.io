# L05.2 验证显式模块启动和资源持有

让 runtime 通过模块、kernel handle 与默认队列提交已跑通的设备镜像。

> 本节是实验提纲。通过标准用于实现后的验收。

- **操作** 复用 L03 的 `store42` 镜像，接通显式加载、kernel 查找、参数复制、提交和等待。明确提交后谁持有模块与被引用的 buffer。
- **测试与通过标准** 用同一 host staging 区提交两次，分别填入不同的输出设备地址，完成后两个输出都为 42。试一次超限 block 或不存在的 kernel 名，并检查错误和清理路径。按所定契约验证执行中 free/unload 要等待、拒绝或延迟实际释放。
- **实现注意** SDK 复制参数字节并持有 kernel/module，runtime 仍需保证其中设备地址引用的 buffer 在完成前有效。传参快照与对象生命周期分别检查。[队列提交契约](../../compiler-sim-contract.md#提交时机快照与对象生命周期)

---

[上一节 · L05.1](01-memory-api.md) · [本章目录](README.md) · [下一节 · L05.3](03-generate-wrapper.md)
