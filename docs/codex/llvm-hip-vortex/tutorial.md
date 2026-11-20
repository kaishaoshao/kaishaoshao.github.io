# 《LLVM 后端实战：从零构建 Vortex GPGPU 的 Native HIP 编译器》

用 LLVM 23.1.4 的 RISC-V 后端为 Vortex GPGPU 接入原生 HIP。全书按六章循序展开。你会先读懂 HIP 语法和设备 IR，再做第一处后端修改，让 `store42` 在 SimX 上运行，最后编译并移植普通 HIP 程序。

每章首页列出准备工作和通过标准。每节独立成页，带上、下节链接。L01 有完整观察命令，L02～L03 有源码示例、运行记录和待做的回归练习，L04～L06 已安排小课和验收提纲。

[开始阅读第 1 章](chapters/01-hip-frontend/README.md) · [直接运行第一个 ELF](chapters/03-store42/00-direct-elf.md) · [看看最后能做成什么](plan.md#6-最后可以做成什么样子)

## 全书目录

[序章](#序章-原生编译链会接通哪些层) · [附录与后续专题](#附录与后续专题)

<a id="第-1-课clang-hip-前端机制与语法探索l01"></a>

### [第 1 章 读懂 HIP 前端（L01）](chapters/01-hip-frontend/README.md)

从同一份 HIP 源码观察属性、语义和设备 IR。

- <a id="12-编写第一个-hip-探测程序"></a>[L01.1 宏展开与属性 AST](chapters/01-hip-frontend/01-attributes.md)
- <a id="13-剖析-clang-astkernel-属性与--解析"></a>[L01.2 调用侧限制与启动表达式](chapters/01-hip-frontend/02-sema-launch.md)
- <a id="14-生成设备标量-ir-与关键断层分析"></a>[L01.3 设备 IR 与后续接口](chapters/01-hip-frontend/03-device-ir.md)

<a id="第-2-课后端基建处理器模型自定义指令与-kernel-标记l02"></a>

### [第 2 章 接通 Vortex 编译入口（L02）](chapters/02-vortex-codegen/README.md)

添加 kernel 标记、选定 CPU 和 feature，实现第一条 TMC 的编解码。

- <a id="21-架构三层解耦原则cpufeature-与-kernel-标记"></a>[L02.1 设计逻辑 kernel 标记](chapters/02-vortex-codegen/01-kernel-marker-design.md)
- <a id="24-在-clang-codegen-中标记-vortex-hip-kernel"></a>[L02.2 发射并核对标记](chapters/02-vortex-codegen/02-emit-kernel-marker.md)
- <a id="22-注册-xvortex-扩展与--mcpuvortex-处理器模型"></a>[L02.3 接通 CPU、feature 和 ABI 选择](chapters/02-vortex-codegen/03-cpu-and-features.md)
- <a id="23-手算与编码首条自定义指令-vx_tmc-的-mc-编解码支持"></a>[L02.4 实现第一条专用指令 TMC](chapters/02-vortex-codegen/04-tmc-mc.md)
- <a id="25-编译首个设备目标文件-store42o"></a>[L02.5 生成第一个设备对象](chapters/02-vortex-codegen/05-device-object.md)

<a id="第-3-课执行闭环在-simx-硬件模拟器上跑通-store42l03"></a><a id="31-极简闭环架构全景与数据流"></a>

### [第 3 章 在 SimX 上执行 store42（L03）](chapters/03-store42/README.md)

先直接启动 ELF，再验证 SDK 传参、镜像入口与主机读回。

- [L03.0 直接用 SimX 运行 ELF](chapters/03-store42/00-direct-elf.md)
- [L03.1 验证输出 buffer 和设备地址](chapters/03-store42/01-device-buffer.md)
- <a id="32-硬件启动与多形参解包native-wrapper-设计原理"></a>[L03.2 用 wrapper 解包一个指针](chapters/03-store42/02-argument-wrapper.md)
- <a id="33-符号契约深究vxbinpy-与-__vx_kentry_-导出机制"></a><a id="34-裸机固件链接正确复用预编译启动汇编与静态库"></a><a id="37-实战踩坑手记与故障排除faq"></a>[L03.3 链接启动代码并检查镜像](chapters/03-store42/03-link-and-package.md)
- <a id="35-host-侧控制基于-vortex-20-异步队列的驱动实现"></a><a id="36-simx-实测从硬件显存读回-42"></a>[L03.4 用 SDK 提交首个 launch](chapters/03-store42/04-sdk-launch.md)
- [L03.5 重编并证明结果来自新镜像](chapters/03-store42/05-rebuild-and-check.md)

<a id="第-4-课走向真正-simt多线程与分支分歧控制l04-进阶预备"></a>

### [第 4 章 多线程 vecadd 与分支分歧（L04）](chapters/04-simt-vecadd/README.md)

读出线程坐标，完成多线程加法，再处理部分 lane 有效的尾部。

- <a id="41-从单线程到多线程网格维度与-csr-线程索引"></a>[L04.1 读取 CTA 坐标并写回索引](chapters/04-simt-vecadd/01-thread-coordinates.md)
- [L04.2 做无尾部判断的 vecadd](chapters/04-simt-vecadd/02-vecadd.md)
- <a id="42-当多线程遭遇-if-gid--n分支分歧与活跃掩码"></a><a id="43-为什么需要-vx_split--vx_join-与分歧分析-pass"></a>[L04.3 引入混合 lane 的尾部判断](chapters/04-simt-vecadd/03-divergence.md)
- <a id="44-l04-的里程碑带边界检查的并行加法-vecadd"></a>[L04.4 检查汇合与优化回归](chapters/04-simt-vecadd/04-reconvergence.md)

<a id="第-5-课内存层次与通信原语l05-进阶展望"></a>

### [第 5 章 自动编译并启动普通 HIP（L05）](chapters/05-hip-runtime/README.md)

让编译器和原生 runtime 生成入口、构建镜像并完成普通 HIP 启动。

- [L05.1 验证最小内存 API](chapters/05-hip-runtime/01-memory-api.md)
- [L05.2 验证显式模块启动和资源持有](chapters/05-hip-runtime/02-module-launch.md)
- [L05.3 自动生成 wrapper 与参数描述](chapters/05-hip-runtime/03-generate-wrapper.md)
- [L05.4 接通 host stub、配置和注册](chapters/05-hip-runtime/04-host-stub.md)
- [L05.5 衔接设备链接、嵌入与 host 链接](chapters/05-hip-runtime/05-offload-link.md)
- [L05.6 验收普通 HIP 的端到端执行](chapters/05-hip-runtime/06-hip-end-to-end.md)

<a id="第-6-课复杂算子与已有程序移植l06-进阶展望"></a>

### [第 6 章 移植一个已有 HIP 程序（L06）](chapters/06-porting/README.md)

用 SDK 的已有 HIP vecadd 找出实际缺口，补测试并对照 CPU 结果。

- [L06.1 盘点已有源码依赖](chapters/06-porting/01-inventory.md)
- [L06.2 尝试用原生链路编译](chapters/06-porting/02-first-build.md)
- [L06.3 给一个真实缺口补测试和实现](chapters/06-porting/03-close-a-gap.md)
- [L06.4 对照 CPU 运行原程序](chapters/06-porting/04-cpu-reference.md)
- [L06.5 从干净产物复现并交付](chapters/06-porting/05-reproduce.md)

<a id="序章项目背景与分层架构理念"></a><a id="11-什么是-native-hip与-chipstarpocl-的本质区别"></a>

## 序章 原生编译链会接通哪些层

Vortex SDK 的参考 HIP 示例通过 chipStar、SPIR-V 和 PoCL 执行。沿书中的实现路线，Clang 生成 RV64 设备 IR，复用 RISC-V 的标量代码生成，再加入 Vortex 的 SIMT 能力。另一条 host 编译路径生成启动和注册代码，通过 runtime 将设备镜像交给 Vortex SDK。[参考路径源码入口](plan.md#31-现有-hip-测试通过不代表原生-hip-编译链存在)

```text
HIP 源码
  ├─ x86_64 host 编译 → 镜像注册和启动 stub → 原生 HIP runtime
  └─ RV64 device 编译 → LLVM IR → RISC-V 和 Vortex 指令 → 设备镜像
```

`-mcpu=vortex` 选择设备 CPU 及默认 feature，`xvortex` 控制扩展指令和相关转换，逻辑 kernel 标记为下游生成启动入口提供依据。这三处连接依次在第 2 章练习。需要时再查阅对应的指令集和参数约定。[架构方案](architecture.md)

## 附录与后续专题

- [T00 工程基线](getting-started.md#engineering-baseline)和[构建说明](build.md)用于准备或重建工具。
- [架构与指令集](architecture.md#vortex-isa)和[编译器与 SimX 接口](compiler-sim-contract.md)用于查阅 CPU、CSR、SIMT 和启动 ABI。
- [工程验收与证据](plan.md#implementation-review)、[66 项任务账本](tasks.md)和[记录模板](evidence-template.md)用于跟踪已覆盖的行为。
- [后续专题](plan.md#64-首个移植结果之后的专题)包括共享内存与屏障、原子、异步队列、分块 SGEMM、跨文件设备链接和模拟器性能分析。

[返回主题首页](README.md)
