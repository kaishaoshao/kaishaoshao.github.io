# LLVM 23 HIP 支持 Vortex 教程总览

更新日期：2026-11-19（Asia/Shanghai）。本教程指导你在 LLVM 23.1.4 的 RISC-V Target 之上，逐步实现对开源 GPGPU Vortex 的原生 HIP 编译支持与运行时闭环。

---

## 1. 教程定位与核心目标

### 1.1 为什么做这个项目？
目前官方 Vortex 对 HIP 的支持主要基于 **chipStar + SPIR-V + PoCL** 路径（将 HIP 转为 SPIR-V，再由 OpenCL 驱动执行）。
本教程的目标是构建**端到端原生 HIP 支持（Native HIPVortex）**：
- 让 Clang 直接识别 `-mcpu=vortex` 并生成 Vortex RISC-V 机器码；
- 让设备端编译直接生成 `.vxbin` 可执行镜像；
- 通过独立的原生 HIP Runtime（基于 Vortex SDK `vortex2.h`）实现内存管理与 Kernel 启动；
- 最终在 SimX 周期级仿真器上端到端验证执行结果，并与 CPU 参考实现对比。

### 1.2 核心架构决策
- **复用 RISCV Target**：不新建独立的 `llvm/lib/Target/Vortex`，所有修改直接建构在现有的 `llvm/lib/Target/RISCV` 后端与 Clang HIP 前端接入层。
- **三层解耦原则**：
  1. `-mcpu=vortex`：负责选择默认处理器配置与标准扩展（RV64IMAFD + Zicond + XVortex）；
  2. `xvortex` 扩展 feature：负责控制特殊 SIMT 指令（TMC、SPLIT、JOIN、BAR 等）的谓词与 pass 开关，代码中查询 feature 而非硬编码 CPU 名字；
  3. 函数属性与元数据：负责区分逻辑 HIP Kernel（`vortex-hip-kernel`）与单参数区原生启动入口（`vortex.kernel`）。
- **执行端闭环**：以 Vortex SimX 仿真器为硬件验收标准，以精确读回数据为通过依据，不以“仅生成汇编”或“参考编译器通过”代替自编后端的通过记录。

---

## 2. 六阶段学习路线与演进逻辑

教程摒弃了一次性写完所有后端 pass 才能运行的传统思路，采用**从最小单线程程序到复杂应用，步步有执行、步步有反馈**的演进路径：

```text
L01 HIP 前端观察 → L02 Vortex 编译入口 → L03 store42 单核执行
       ↓
L04 带边界 vecadd → L05 普通 HIP 全链路 <<<>>> → L06 已有程序移植
```

| 阶段 | 核心任务 | 必须看见的标志性产物 | 对应工程验收 |
|---|---|---|---|
| **[L01](getting-started.md#lesson-1)** | **看懂 HIP 前端**：观察宏展开、AST 节点（`CUDAGlobalAttr`）、非法调用拦截与设备 IR 生成 | 获得 `device.ll`，解释从源码到 IR 的过程及与 Vortex 的缺口 | T00.1 / T00.3 |
| **[L02](plan.md#l02)** | **建立 Vortex 编译入口**：注册 `xvortex` 扩展、`-mcpu=vortex` CPU 模型、第一条 TMC 指令 MC 编码、打上 `vortex-hip-kernel` 标记 | 编译出 `store42.o` 设备目标文件，反汇编核对指令 | T01.1～T01.6 / T02.3 |
| **[L03](plan.md#l03)** | **执行 store42**：手写 native wrapper 与参数桥接，链接参考启动库并在 SimX 执行单线程 Kernel | **在 SimX 上从 Host 真实读回 42**（改值改指针可复现变化） | T04 子项 / T06 基础 |
| **[L04](plan.md#l04)** | **多线程与边界处理**：接入 CTA CSR（`threadIdx`/`blockIdx`）、SIMT 分歧分析与 `vx_split`/`vx_join` 控制流生成 | N=32 和 N=37 的 vecadd 在 SimX 正确运行，尾部混合 lane 无越界写 | T03 / T05 / T07.3 |
| **[L05](plan.md#l05)** | **普通 HIP 全链路**：实现最小原生 Runtime，自动生成参数描述与包装器，接通 `<<<>>>` 自动启动 | 用户源码使用标准 `hipMalloc`/`hipMemcpy`/`<<<>>>`，一键全自动编译执行 | T06 / T07 / T08 |
| **[L06](plan.md#l06)** | **移植真实 HIP 程序**：选择已有测试样例（如 SDK vecadd/sgemm），排查缺口并按需扩展 Shared Memory / Barrier / 原子等 | 固定来源的已有 HIP 源码经新工具链在 SimX 跑通并通过原验证标准 | T09 / T10 按需回填 |

---

## 3. 教程文档体系与查阅指南

为避免信息混乱，本目录下的文档具有严格的分工与单一事实来源（Single Source of Truth）：

| 文件 | 作用与查阅时机 |
|---|---|
| **[README.md](README.md)** | **全局入口**：架构方案概述、固定文档索引与更新规范 |
| **[architecture.md](architecture.md)** | **底层架构契约**：ISA 编码位段表、CSR 分布、CPU/Feature 组合规则、内存模型与设计边界 |
| **[plan.md](plan.md)** | **详细实施路线图**：六大阶段与 28 个小阶段的具体改动点、源码落点与正反例测试说明 |
| **[tasks.md](tasks.md)** | **工程验收账本**：保留的 11 个分组、66 项标准工程验收卡（T00.1～T10.6），作为严谨交付账本 |
| **[getting-started.md](getting-started.md)** | **起步操作手册**：L01 的完整实操命令与输出样例，附录包含环境与 ABI 基线（T00） |
| **[build.md](build.md)** | **构建与编译指南**：LLVM 编译脚本参数、目标组合、并行度与环境要求 |
| **[compiler-sim-contract.md](compiler-sim-contract.md)** | **软硬件接口规范**：SimX 与编译产物的两个启动 PC、寄存器约定、参数内存布局（逐字节对照） |
| **[evidence-template.md](evidence-template.md)** | **任务验收模板**：记录每次测试的输入、命令、真实输出、工具版本与反例验证 |

---

## 4. 实践准则与避坑要点

1. **不要一次性做大补丁**：每一个阶段（如 L02、L03）都细分为多个可独立编译、独立验证的小 Commit。
2. **区分三类测试结果**：
   - 官方参考工具链（Clang 20 + chipStar）的跑通结果不能作为自己新编译器的通过证据；
   - 手写桥接/单步执行通过不能等同于“自动 HIP 流程已打通”；
   - 静态检查与反汇编正确不能代替 SimX 实际执行正确。
3. **两个启动 PC 绝不能混淆**：
   - `program_pc`：是固定的模块基地址，执行 `_start`/`__vx_cta_entry` 用于建栈与初始化；
   - `kernel_pc`：是通过 `CTA_ENTRY` CSR 动态传入的实际 Kernel 函数入口。
4. **多形参 Kernel 必须走包装解包**：
   - 硬件单指针参数约定（`MSCRATCH` -> `a0`）与 C++ 多形参必须通过 Wrapper 转接，不可直接把用户多参函数当 native 入口。
