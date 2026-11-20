# 第 5 章 通过 SDK 传参与启动 kernel

沿 `host_store42.cpp`、参数区、`kernel_wrapper.cpp` 和 `.vxbin` 逐层验证参数怎样到达设备函数。

## 本章目录

- [L03.1 验证输出 buffer 和设备地址](01-device-buffer.md)
- [L03.2 用 wrapper 解包一个指针](02-argument-wrapper.md)
- [L03.3 链接启动代码并检查镜像](03-link-and-package.md)
- [L03.4 用 SDK 提交首个 launch](04-sdk-launch.md)
- [L03.5 重编并证明结果来自新镜像](05-rebuild-and-check.md)

## 开始前

准备能生成 `store42.o` 的 LLVM、SDK 的 SimX runtime、参考启动代码和链接脚本。SDK 把参数区指针交给 wrapper，wrapper 再取出指向输出 buffer 的地址。[参数接口](../../compiler-sim-contract.md#l03-walkthrough)

## 完成这一章

从 host 读回 42，核对 SDK 的两个 PC、参数区与镜像身份。再用一份重新编译的 `.vxbin` 验证 host 能读回 43。已有首次读回的运行记录，各节另列哨兵与负例练习。

---

[上一章](README.md) · [全书目录](../../tutorial.md) · [下一章](../04-simt-vecadd/README.md)
