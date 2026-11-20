# 《LLVM 后端实战：从零构建 Vortex GPGPU 的 Native HIP 编译器》

用 LLVM 23.1.4 的 RISC-V 后端为 Vortex GPGPU 接入原生 HIP。全书有 12 章、38 节。第 1～10 章从 HIP 语法起步，完成 `store42`、并行 vecadd 和已有 HIP 程序移植。第 11～12 章按需增加共享内存、原子和异步支持。

章号指阅读顺序，L01～L06 对应工程里程碑，小课原有实验编号继续用于记录结果。第 1～5 章有操作命令、源码示例或运行记录，第 6～12 章给出实现提纲和验收目标。

[开始阅读第 1 章](chapters/01-hip-frontend/README.md) · [直接运行第一个 ELF](chapters/03-store42/00-direct-elf.md) · [看看最后能做成什么](plan.md#6-最后可以做成什么样子)

## 全书目录

[序章](#序章-原生编译链会接通哪些层) · [进阶篇](#第四篇-按需扩展-gpu-能力) · [附录](#附录与后续专题)

## 第一篇 从 HIP 语法到 Vortex 目标代码

完成 HIP 前端观察、逻辑 kernel 标记和第一条 Vortex 指令，得到可链接的设备对象。

<a id="第-1-课clang-hip-前端机制与语法探索l01"></a>

### [第 1 章 读懂 HIP 前端](chapters/01-hip-frontend/README.md)（L01）

- <a id="12-编写第一个-hip-探测程序"></a>[L01.1 宏展开与属性 AST](chapters/01-hip-frontend/01-attributes.md)
- <a id="13-剖析-clang-astkernel-属性与--解析"></a>[L01.2 调用侧限制与启动表达式](chapters/01-hip-frontend/02-sema-launch.md)
- <a id="14-生成设备标量-ir-与关键断层分析"></a>[L01.3 设备 IR 与后续接口](chapters/01-hip-frontend/03-device-ir.md)

<a id="第-2-课后端基建处理器模型自定义指令与-kernel-标记l02"></a><a id="第-2-章-接通-vortex-编译入口l02"></a>

### [第 2 章 让 Clang 保留 kernel 身份](chapters/02-vortex-codegen/README.md)（L02）

- <a id="21-架构三层解耦原则cpufeature-与-kernel-标记"></a>[L02.1 设计逻辑 kernel 标记](chapters/02-vortex-codegen/01-kernel-marker-design.md)
- <a id="24-在-clang-codegen-中标记-vortex-hip-kernel"></a>[L02.2 发射并核对标记](chapters/02-vortex-codegen/02-emit-kernel-marker.md)

### [第 3 章 配置 Vortex CPU 并定义 TMC](chapters/02-vortex-codegen/chapter-03-cpu-and-tmc.md)（L02）

- <a id="22-注册-xvortex-扩展与--mcpuvortex-处理器模型"></a>[L02.3 接通 CPU、feature 和 ABI 选择](chapters/02-vortex-codegen/03-cpu-and-features.md)
- <a id="23-手算与编码首条自定义指令-vx_tmc-的-mc-编解码支持"></a>[L02.4 实现第一条专用指令 TMC](chapters/02-vortex-codegen/04-tmc-mc.md)
- <a id="25-编译首个设备目标文件-store42o"></a>[L02.5 生成第一个设备对象](chapters/02-vortex-codegen/05-device-object.md)

## 第二篇 从设备对象到多线程执行

直接运行 ELF，接通 SDK 的启动和读回，再加上多线程与控制流。

<a id="第-3-课执行闭环在-simx-硬件模拟器上跑通-store42l03"></a><a id="31-极简闭环架构全景与数据流"></a><a id="第-3-章-在-simx-上执行-store42l03"></a>

### [第 4 章 链接并直接运行设备 ELF](chapters/03-store42/README.md)（L03）

- [L03.0 直接用 SimX 运行 ELF](chapters/03-store42/00-direct-elf.md)
- [4.2 从设备对象链接独立 ELF](chapters/03-store42/00-link-standalone.md)
- [4.3 用入口地址和退出码排查故障](chapters/03-store42/00-diagnose-standalone.md)

### [第 5 章 通过 SDK 传参与启动 kernel](chapters/03-store42/chapter-05-sdk-launch.md)（L03）

- [L03.1 验证输出 buffer 和设备地址](chapters/03-store42/01-device-buffer.md)
- <a id="32-硬件启动与多形参解包native-wrapper-设计原理"></a>[L03.2 用 wrapper 解包一个指针](chapters/03-store42/02-argument-wrapper.md)
- <a id="33-符号契约深究vxbinpy-与-__vx_kentry_-导出机制"></a><a id="34-裸机固件链接正确复用预编译启动汇编与静态库"></a><a id="37-实战踩坑手记与故障排除faq"></a>[L03.3 链接启动代码并检查镜像](chapters/03-store42/03-link-and-package.md)
- <a id="35-host-侧控制基于-vortex-20-异步队列的驱动实现"></a><a id="36-simx-实测从硬件显存读回-42"></a>[L03.4 用 SDK 提交首个 launch](chapters/03-store42/04-sdk-launch.md)
- [L03.5 重编并证明结果来自新镜像](chapters/03-store42/05-rebuild-and-check.md)

<a id="第-4-课走向真正-simt多线程与分支分歧控制l04-进阶预备"></a><a id="第-4-章-多线程-vecadd-与分支分歧l04"></a>

### [第 6 章 线程坐标与整块 vecadd](chapters/04-simt-vecadd/README.md)（L04）

- <a id="41-从单线程到多线程网格维度与-csr-线程索引"></a>[L04.1 读取 CTA 坐标并写回索引](chapters/04-simt-vecadd/01-thread-coordinates.md)
- [L04.2 做无尾部判断的 vecadd](chapters/04-simt-vecadd/02-vecadd.md)

### [第 7 章 尾部判断、分歧与汇合](chapters/04-simt-vecadd/chapter-07-divergence.md)（L04）

- <a id="42-当多线程遭遇-if-gid--n分支分歧与活跃掩码"></a><a id="43-为什么需要-vx_split--vx_join-与分歧分析-pass"></a>[L04.3 引入混合 lane 的尾部判断](chapters/04-simt-vecadd/03-divergence.md)
- <a id="44-l04-的里程碑带边界检查的并行加法-vecadd"></a>[L04.4 检查汇合与优化回归](chapters/04-simt-vecadd/04-reconvergence.md)

## 第三篇 原生 HIP 与源码移植

把手写的启动链收进 runtime 和编译器，移植 Vortex SDK 的已有样例。

<a id="第-5-课内存层次与通信原语l05-进阶展望"></a><a id="第-5-章-自动编译并启动普通-hipl05"></a>

### [第 8 章 实现 HIP runtime 的基本接口](chapters/05-hip-runtime/README.md)（L05）

- [L05.1 验证最小内存 API](chapters/05-hip-runtime/01-memory-api.md)
- [L05.2 验证显式模块启动和资源持有](chapters/05-hip-runtime/02-module-launch.md)

### [第 9 章 自动编译并启动普通 HIP](chapters/05-hip-runtime/chapter-09-offload.md)（L05）

- [L05.3 自动生成 wrapper 与参数描述](chapters/05-hip-runtime/03-generate-wrapper.md)
- [L05.4 接通 host stub、配置和注册](chapters/05-hip-runtime/04-host-stub.md)
- [L05.5 衔接设备链接、嵌入与 host 链接](chapters/05-hip-runtime/05-offload-link.md)
- [L05.6 验收普通 HIP 的端到端执行](chapters/05-hip-runtime/06-hip-end-to-end.md)

<a id="第-6-课复杂算子与已有程序移植l06-进阶展望"></a><a id="第-6-章-移植一个已有-hip-程序l06"></a>

### [第 10 章 移植一个已有 HIP 程序](chapters/06-porting/README.md)（L06）

- [L06.1 盘点已有源码依赖](chapters/06-porting/01-inventory.md)
- [L06.2 尝试用原生链路编译](chapters/06-porting/02-first-build.md)
- [L06.3 给一个真实缺口补测试和实现](chapters/06-porting/03-close-a-gap.md)
- [L06.4 对照 CPU 运行原程序](chapters/06-porting/04-cpu-reference.md)
- [L06.5 从干净产物复现并交付](chapters/06-porting/05-reproduce.md)

## 第四篇 按需扩展 GPU 能力

根据目标程序选择共享内存、同步、原子或异步练习。这些课沿用 T09、T10 的验收。

### [第 11 章 共享内存与块内同步](chapters/07-shared-memory/README.md)

- [11.1 为每个 block 布置共享内存](chapters/07-shared-memory/01-local-memory-layout.md)
- [11.2 从 BAR 指令接到块内屏障](chapters/07-shared-memory/02-block-barrier.md)
- [11.3 用 reduction 和 tiled SGEMM 验收](chapters/07-shared-memory/03-cooperative-kernels.md)

### [第 12 章 原子、异步执行与交付](chapters/08-atomics-and-async/README.md)

- [12.1 在匹配的 A 配置中实现 atomicAdd](chapters/08-atomics-and-async/01-atomic-add.md)
- [12.2 接通 stream 和队列内顺序](chapters/08-atomics-and-async/02-stream-order.md)
- [12.3 用事件连接两个 stream](chapters/08-atomics-and-async/03-event-lifetime.md)
- [12.4 发布可复现的原型](chapters/08-atomics-and-async/04-release-reproduction.md)

<a id="序章项目背景与分层架构理念"></a><a id="11-什么是-native-hip与-chipstarpocl-的本质区别"></a>

## 序章 原生编译链会接通哪些层

Vortex SDK 的参考 HIP 示例通过 chipStar、SPIR-V 和 PoCL 执行。沿书中的实现路线，Clang 生成 RV64 设备 IR，复用 RISC-V 的标量代码生成，再加入 Vortex 的 SIMT 能力。另一条 host 编译路径生成启动和注册代码，通过 runtime 将设备镜像交给 Vortex SDK。[参考路径源码入口](plan.md#31-现有-hip-测试通过不代表原生-hip-编译链存在)

```text
HIP 源码
  ├─ x86_64 host 编译 → 镜像注册和启动 stub → 原生 HIP runtime
  └─ RV64 device 编译 → LLVM IR → RISC-V 和 Vortex 指令 → 设备镜像
```

`-mcpu=vortex` 选择设备 CPU 及默认 feature，`xvortex` 控制扩展指令和相关转换，逻辑 kernel 标记为下游生成启动入口提供依据。第 2 章做逻辑标记，第 3 章做 CPU 与扩展指令。需要时再查阅对应的指令集和参数约定。[架构方案](architecture.md)

## 附录与后续专题

- [T00 工程基线](getting-started.md#engineering-baseline)和[构建说明](build.md)用于准备或重建工具。
- [架构与指令集](architecture.md#vortex-isa)和[编译器与 SimX 接口](compiler-sim-contract.md)用于查阅 CPU、CSR、SIMT 和启动 ABI。
- [工程验收与证据](plan.md#implementation-review)、[66 项任务账本](tasks.md)和[记录模板](evidence-template.md)用于跟踪已覆盖的行为。
- [后续专题](plan.md#64-首个移植结果之后的专题)继续涵盖跨文件设备链接、更多设备库和模拟器性能分析。

[返回主题首页](README.md)
