# L05.3 自动生成 wrapper 与参数描述

让编译器从 kernel 签名建立入口和参数表，host 与设备按同一布局解包。

> 本节是实验提纲。通过标准用于实现后的验收。

- **操作** 比较 `store42(int*)` 与四参数 vecadd，生成 wrapper、入口名、参数 kind/size/alignment/offset 及格式版本。先用 device-only 产物和显式启动验证。
- **测试与通过标准** 检查 IR、ELF 入口和布局字节。采用文档的 32 字节示例时，三条设备地址位于 0/8/16，`n=37` 从偏移 24 处序列化为小端 `25 00 00 00`，尾部按约定补齐。未知版本、越界/重叠布局应被拒绝，两个签名分别读到正确值。
- **实现注意** host 的 `void**` 记录每个参数值在 host 端的位置，runtime 应读出值再序列化。将来支持零形参时，明确 SDK 的 `args_size=0` 可能走旧 ARG 路径，别沿用上一轮的参数状态。[参数布局](../../compiler-sim-contract.md#hip-参数布局示例拟定契约待实现)

---

[上一节 · L05.2](02-module-launch.md) · [本章目录](chapter-09-offload.md) · [下一节 · L05.4](04-host-stub.md)
