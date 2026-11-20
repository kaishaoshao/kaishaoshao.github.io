# 第 9 章 自动编译并启动普通 HIP

用同一份 HIP 源码自动生成设备 wrapper、host stub 和嵌入镜像，接通普通的 `<<<>>>` 启动。

> 本章提供实现提纲与验收目标。

## 本章目录

- [L05.3 自动生成 wrapper 与参数描述](03-generate-wrapper.md)
- [L05.4 接通 host stub、配置和注册](04-host-stub.md)
- [L05.5 衔接设备链接、嵌入与 host 链接](05-offload-link.md)
- [L05.6 验收普通 HIP 的端到端执行](06-hip-end-to-end.md)

## 开始前

以第 8 章的 runtime 与 L03 参数契约验证接口，最后用第 7 章的带边界 vecadd 验收执行。对照源码、编译任务和嵌入镜像。[目标 HIP 示例](../../plan.md#62-用户最终怎样写程序)

## 完成这一章

新 LLVM 自动生成 host/device 产物，原生 runtime 能在 SimX 正确执行同一个普通 HIP 用例。核对双 kernel、错误路径、镜像来源和优化级别。

---

[上一章](README.md) · [全书目录](../../tutorial.md) · [下一章](../06-porting/README.md)
