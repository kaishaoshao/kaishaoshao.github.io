# L06.2 尝试用原生链路编译

先替换构建入口和链接配置，保存第一次真实的成功或失败。

> 本节是实验提纲。通过标准用于实现后的验收。

- **操作** 使用 L05 的编译入口和固定 SDK 源码，在独立输出目录构建，记录 host/device jobs 与链接库来源。
- **测试与通过标准** 检查设备产物为本次生成的 RV64 ELF/`.vxbin`，host 链接原生 runtime。遇到失败，留下原命令、退出码、首条相关诊断和发生层次，作为 L06.3 的复现输入。
- **实现注意** SDK 原 `tests/hip/common.mk` 用 chipStar、SPIR-V 与 PoCL。若跑参考构建作行为对照，用单独目录记录来源。[SDK 参考构建规则](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/tests/hip/common.mk)

---

[上一节 · L06.1](01-inventory.md) · [本章目录](README.md) · [下一节 · L06.3](03-close-a-gap.md)
