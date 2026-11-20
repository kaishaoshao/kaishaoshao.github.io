# 第 5 章 自动编译并启动普通 HIP（L05）

把手写 host、参数区和镜像打包改为编译器与原生 runtime 的职责。完成后，普通 HIP 源码里的 `hipMalloc`、`hipMemcpy` 与 `<<<>>>` 可以把 vecadd 送到 SimX。

> 本章各节为实施提纲，列出实现顺序、测试输入和通过标准。

## 本章目录

- [L05.1 验证最小内存 API](01-memory-api.md)
- [L05.2 验证显式模块启动和资源持有](02-module-launch.md)
- [L05.3 自动生成 wrapper 与参数描述](03-generate-wrapper.md)
- [L05.4 接通 host stub、配置和注册](04-host-stub.md)
- [L05.5 衔接设备链接、嵌入与 host 链接](05-offload-link.md)
- [L05.6 验收普通 HIP 的端到端执行](06-hip-end-to-end.md)

## 开始前

L03 的 ABI 和 L04 的设备语义已经验证。只要有可运行的 L03 镜像，就可开始 L05.1～L05.2，等 L04 带边界 vecadd 通过后再做本阶段的最终执行验收。

最终阅读成果是一份使用 `hipMalloc`、`hipMemcpy` 和 `<<<>>>` 的普通 vecadd。[目标示例](../../plan.md#62-用户最终怎样写程序)

## 完成这一章

同一份 HIP 源码由新 LLVM 自动生成 host/device 产物，使用原生 runtime 在 SimX 正确运行。交付编译命令、镜像来源、支持子集和正负例结果，随后开始已有源码移植。

---

[上一章](../04-simt-vecadd/README.md) · [全书目录](../../tutorial.md) · [下一章](../06-porting/README.md)
