# 第 3 章 在 SimX 上执行 store42（L03）

先把新 LLVM 编译的 `store42` 链接成可由 SimX 直接执行的 ELF。再通过 Vortex SDK 在 host 分配显存、传递指针并读回结果，建立普通 HIP 启动将复用的执行链。

## 本章目录

- [L03.0 直接用 SimX 运行 ELF](00-direct-elf.md)
- [L03.1 验证输出 buffer 和设备地址](01-device-buffer.md)
- [L03.2 用 wrapper 解包一个指针](02-argument-wrapper.md)
- [L03.3 链接启动代码并检查镜像](03-link-and-package.md)
- [L03.4 用 SDK 提交首个 launch](04-sdk-launch.md)
- [L03.5 重编并证明结果来自新镜像](05-rebuild-and-check.md)

## 开始前

已有 L02 的编译器与单核示例。L03.0 使用 SimX 命令行程序，L03.1～L03.5 使用 SDK 的 SimX runtime、参考启动代码和链接脚本。[SimX 构建](../../build.md#simx-build)

| 启动方式 | 输出地址与结果 |
|---|---|
| SimX 直接加载 ELF | `_start` 把输出地址放到 `a0`，设备侧比较后返回状态 |
| SDK 加载 `.vxbin` | host 把输出地址写入参数区，wrapper 从参数区解包，host 经队列读回输出 |

已有直接 ELF 的正反例结果和 SDK 首次读回记录，详见对应小节。[参数接口](../../compiler-sim-contract.md#l03-walkthrough)

## 完成这一章

交付直接 ELF 的两种退出码、SDK 启动的设备输出以及所用的镜像和命令。用独立镜像验证重新编译后能分别读回 42 和 43，然后沿用 SDK 启动链开始多线程练习。

---

[上一章](../02-vortex-codegen/README.md) · [全书目录](../../tutorial.md) · [下一章](../04-simt-vecadd/README.md)
