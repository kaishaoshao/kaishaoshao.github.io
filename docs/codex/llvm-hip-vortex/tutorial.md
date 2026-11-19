# LLVM 23 HIP 支持 Vortex 教程：L01 与 L02 实现实战指南

更新日期：2026-11-19（Asia/Shanghai）。
本文档系统总结与说明 **L01（HIP 前端探索）** 与 **L02（Vortex 编译入口与后端首批改动）** 的全部已提交实现、代码细节、底层设计原理与复现验证步骤。

---

## 目录

1. [项目背景与分层架构理念](#1-项目背景与分层架构理念)
2. [L01 探索：看懂 Clang HIP 前端机制与缺口（Commit: `c447d813c`）](#2-l01-探索看懂-clang-hip-前端机制与缺口)
3. [L02 实战一：注册 xvortex 扩展与 -mcpu=vortex CPU（Commit: `2cbb216a2`）](#3-l02-实战一注册-xvortex-扩展与--mcpuvortex-cpu)
4. [L02 实战二：首条自定义指令 vx_tmc 的 MC 编解码支持（Commit: `0d3d3fcd2`）](#4-l02-实战二首条自定义指令-vx_tmc-的-mc-编解码支持)
5. [L02 实战三：为逻辑 Kernel 打上 IR 标记并生成首个设备对象（Commit: `d558c7fd0`）](#5-l02-实战三为逻辑-kernel-打上-ir-标记并生成首个设备对象)
6. [阶段总结与 L03（SimX 执行闭环）衔接](#6-阶段总结与-l03simx-执行闭环衔接)

---

## 1. 项目背景与分层架构理念

### 1.1 为什么自研 Native HIP 支持？
官方 Vortex 目前支持 HIP 的主流途径是基于 **chipStar + SPIR-V + PoCL**：
```text
HIP 源码 → Clang/hipcc (编译为 SPIR-V) → PoCL 驱动翻译为 OpenCL/Vortex 内核 → 执行
```
这种间接路径依赖庞大的第三方兼容层，无法直接控制后端的指令调度、寄存器分配与 SIMT 分歧转换。
本项目的目标是**在 LLVM 23.1.4 的 RISCV Target 中实现原生 HIP 编译支持（Native HIPVortex）**：
```text
HIP 源码 ─┬─> Host 编译 (x86_64)   ──> 注册镜像 / Kernel 启动 Stub / HIP API
          └─> Device 编译 (riscv64) ──> LLVM IR ──> SIMT Lowering ──> Vortex 指令 ──> .vxbin
```

### 1.2 架构三层解耦原则
为保持与上游 RISC-V 后端的最大兼容性，架构采取三层严格解耦：
1. **处理器模型 `-mcpu=vortex`**：负责默认 ISA 组合（RV64IMAFD + Zicond + XVortex，默认关闭 A/C 扩展）与保守调度模型。
2. **能力特性 `xvortex`**：负责管理特殊 SIMT 指令（TMC、SPLIT、JOIN、BAR 等）的谓词与 pass 开关，代码中绝不硬编码 CPU 名，只查 feature。
3. **入口属性与元数据**：负责在 IR 区分“多形参逻辑 Kernel”与“单指针原生启动入口”。

---

## 2. L01 探索：看懂 Clang HIP 前端机制与缺口

- **对应 Git 提交**：`c447d813c`
- **对应工程验收**：[T00.1](tasks.md)、[T00.3](tasks.md)
- **本地实验源码**：`llvm/unittests/Vortex/101/`

### 2.1 实验目的
不修改任何编译器代码，利用编译好的 Clang 前端，观察 Clang 是如何解析 HIP 代码的，并找出“已有前端能力”与“Vortex 设备端可运行”之间的断层。

### 2.2 核心观察与实验步骤

#### 实验 1.1：属性宏展开与 AST 映射
输入文件 `attributes.hip`：
```cpp
#define __global__ __attribute__((global))
#define __device__ __attribute__((device))

__device__ int twice(int v) { return v * 2; }
__global__ void store42(int* out) { *out = 42; }
```
- **宏展开观察**（`-E -P`）：`__global__` 被展开为标准的 Clang 属性 `__attribute__((global))`。
- **AST 观察**（`-fsyntax-only -Xclang -ast-dump`）：
  - `twice` 节点挂载了 `CUDADeviceAttr`；
  - `store42` 节点挂载了 `CUDAGlobalAttr`；
  - **结论**：Clang 的 CUDA/HIP 前端共享语法树定义，前端解析完全正常。

#### 实验 1.2：调用限制与启动表达式
- **Host→Device 非法调用**：在普通 Host 函数中直接调用 `twice()` 会被 Clang 拦截报错（`reference to __device__ function in __host__ context`）。
- **启动表达式 `<<<>>>`**：AST 中解析为 `CUDAKernelCallExpr`，并隐式引入 `__hipPushCallConfiguration` 调用。

#### 实验 1.3：生成标量设备 IR
通过 `-cc1 -triple riscv64-unknown-elf -target-cpu generic-rv64 -x hip -fcuda-is-device -emit-llvm` 生成 `device.ll`：
```llvm
define dso_local void @_Z7store42Pi(ptr %out) {
  store i32 42, ptr %out, align 4
  ret void
}
```

### 2.3 L01 结论：我们发现了什么缺口？
1. Clang 前端天然支持 HIP 语法与属性解析；
2. **关键断层**：生成的标量 IR 中丢失了 `__global__` 属性，且没有 Vortex 专用的 CPU 配置、SIMT 控制流指令与入口 ABI 桥接。必须开始修改 LLVM 后端！

---

## 3. L02 实战一：注册 xvortex 扩展与 -mcpu=vortex CPU

- **对应 Git 提交**：`2cbb216a2`
- **对应工程验收**：[T01.1～T01.6](tasks.md)
- **测试脚本**：`llvm/unittests/Vortex/102/build.sh`

### 3.1 修改文件 1：[RISCVFeatures.td](file:///home/kaikai/vortex-word/llvm-project/llvm/lib/Target/RISCV/RISCVFeatures.td)
在 Vendor Extensions 区域末尾添加：
```tablegen
//===----------------------------------------------------------------------===//
// Vortex Extensions
//===----------------------------------------------------------------------===//
def FeatureVendorXVortex
    : RISCVExtension<1, 0, "Vortex SIMT extension">;
def HasVendorXVortex
    : Predicate<"Subtarget->hasVendorXVortex()">,
      AssemblerPredicate<(all_of FeatureVendorXVortex), "'XVortex' (Vortex SIMT extensions)">;
```
- **原理解析**：TableGen 的 `RISCVExtension` 模板会自动根据名字截取 `extName = "XVortex"`，转为小写扩展名 `xvortex`，并在 `RISCVGenSubtargetInfo.inc` 中自动生成 `Subtarget->hasVendorXVortex()` 查询接口。

### 3.2 修改文件 2：[RISCVProcessors.td](file:///home/kaikai/vortex-word/llvm-project/llvm/lib/Target/RISCV/RISCVProcessors.td)
在文件末尾定义 Vortex 处理器模型：
```tablegen
def VORTEX : RISCVProcessorModel<"vortex",
                                RocketModel,
                                [Feature64Bit,
                                 FeatureStdExtI,
                                 FeatureStdExtM,
                                 FeatureStdExtF,
                                 FeatureStdExtD,
                                 FeatureStdExtZicsr,
                                 FeatureStdExtZifencei,
                                 FeatureStdExtZicond,
                                 FeatureVendorXVortex]>;
```
- **原理解析**：
  - 调度模型选 `RocketModel`（成熟的顺序流水线模型，`CompleteModel = false`，未建模指令自动回退默认周期，极稳妥）；
  - 特性集包含 RV64IMAFD、Zicsr/Zifencei、Zicond（条件置零）以及我们定义的 `xvortex`；
  - 默认**不开启** A（原子）和 C（压缩指令），完全对齐 SimX 当前的硬件默认基线；
  - `DefaultMarch` 留空，TableGen 会按 RISC-V 规范顺序自动推导出规范 ISA 串：`rv64imafd_zicsr2p0_zifencei2p0_zicond1p0_xvortex1p0`。

### 3.3 验证结果与原理深究
1. **CPU/Feature 识别**：
   - `llc --mtriple=riscv64 --mcpu=help` -> 成功出现 `vortex`；
   - `llc --mtriple=riscv64 --mattr=help` -> 成功出现 `xvortex`。
2. **Clang Driver 的 Triple Promotion（自动纠正提升）**：
   - 当执行 `clang --target=riscv32-unknown-elf -mcpu=vortex -###` 时，发现命令没有报错，且 cc1 triple 变成了 `riscv64`。
   - **底层原因**：根据 [Driver.cpp:815-835](file:///home/kaikai/vortex-word/llvm-project/clang/lib/Driver/Driver.cpp#L815-L835)，Clang 发现用户未显式传 `-march` 时，优先信任 CPU 的默认位宽，自动将 `riscv32` 提升为 `riscv64`（官方 `sifive-u74` 等 64 位 CPU 行为完全相同）。
3. **RV32 负例拦截**：
   - 显式冲突传参 `clang --target=riscv32-unknown-elf -march=rv32i -mcpu=vortex` -> 正确报错：`clang: error: cpu 'vortex' does not support rv32`；
   - 底层工具校验 `llc -mtriple=riscv32 -mcpu=vortex` -> 正确报错：`LLVM ERROR: RV32 target requires an RV32 CPU`。

---

## 4. L02 实战二：首条自定义指令 vx_tmc 的 MC 编解码支持

- **对应 Git 提交**：`0d3d3fcd2`
- **对应工程验收**：[T02.3](tasks.md)
- **测试脚本**：`llvm/unittests/Vortex/102/build-02.sh`

### 4.1 指令作用与编码推导
`vx_tmc rs1`（Thread Mask Control）用于用 `rs1` 寄存器中的掩码更新当前 Warp 的活跃线程掩码。
- **指令位段格式（32 位 R-type）**：
  - `opcode`: `0b0001011`（`0x0b` / `OPC_CUSTOM_0`）
  - `funct3`: `0b000`（0）
  - `funct7`: `0b0000000`（0）
  - `rd`: `0`（`x0`）
  - `rs2`: `0`（`x0`）
  - `rs1`: 输入操作数寄存器
- **机器码手算核对（以 `vx_tmc a0` 为例）**：
  - `a0` 对应 `x10`（二进制 `01010`）；
  - 指令二进制：`0000000 00000 01010 000 00000 0001011`；
  - 16 进制：**`0x0005000b`**（小端字节序列：`0b 00 05 00`），与文档记录完全吻合。

### 4.2 代码改动

#### 1. 新建 [RISCVInstrInfoXVortex.td](file:///home/kaikai/vortex-word/llvm-project/llvm/lib/Target/RISCV/RISCVInstrInfoXVortex.td)
```tablegen
let hasSideEffects = 1, mayLoad = 0, mayStore = 0 in {
let Predicates = [HasVendorXVortex], DecoderNamespace = "XVortex" in {

def VX_TMC : RVInstR<0b0000000, 0b000, OPC_CUSTOM_0, (outs), (ins GPR:$rs1), "vx_tmc", "$rs1"> {
  let rd = 0;
  let rs2 = 0;
}

} // Predicates = [HasVendorXVortex], DecoderNamespace = "XVortex"
} // hasSideEffects = 1, mayLoad = 0, mayStore = 0
```

#### 2. 在 [RISCVInstrInfo.td](file:///home/kaikai/vortex-word/llvm-project/llvm/lib/Target/RISCV/RISCVInstrInfo.td) 中引入
```tablegen
include "RISCVInstrInfoXVortex.td"
```

#### 3. 在 [RISCVDisassembler.cpp](file:///home/kaikai/vortex-word/llvm-project/llvm/lib/Target/RISCV/Disassembler/RISCVDisassembler.cpp) 中注册反汇编表
```cpp
static constexpr FeatureBitset XVortexGroup = {RISCV::FeatureVendorXVortex};
...
// 在 DecoderList32 中添加：
{DecoderTableXVortex32, XVortexGroup, "Vortex simt extensions"},
```

### 4.3 验证结果
- **汇编正例**：`echo "vx_tmc a0" | llvm-mc -triple=riscv64 -mattr=+xvortex -show-encoding`
  - 成功输出：`vx_tmc a0 # encoding: [0x0b,0x00,0x05,0x00]`
- **反汇编往返**：`echo "0x0b 0x00 0x05 0x00" | llvm-mc -triple=riscv64 -mattr=+xvortex -disassemble`
  - 成功还原：`vx_tmc a0`
- **负例拦截**：不带 `+xvortex` 时汇编 `vx_tmc a0` -> 正确报错：`error: instruction requires the following: 'XVortex' (Vortex SIMT extensions)`。

---

## 5. L02 实战三：为逻辑 Kernel 打上 IR 标记并生成首个设备对象

- **对应 Git 提交**：`d558c7fd0`
- **对应工程验收**：[T02.3](tasks.md)、[T07.1](tasks.md)
- **测试脚本与输入**：`llvm/unittests/Vortex/102/build-03.sh`、`store42.hip`

### 5.1 为什么要打上 `"vortex-hip-kernel"` 标记？
1. **解决跨层信息丢失**：Clang AST 中的 `CUDAGlobalAttr` 在转为标量 LLVM IR 时会丢失；
2. **执行模型保护**：为 Kernel 加上 `noinline` 属性，防止优化器将其错误内联或当作未调用死代码消除；
3. **隔离多形参与单指针 ABI**：
   - 用户写的 HIP Kernel 是多形参的（如 `store42(int* out)`）；
   - Vortex 硬件启动约定（`vx_start.S`）只往 `a0` 传一个参数块指针；
   - 该标记用于明确告知后续 Pass：**“这是逻辑 Kernel 业务体，后续需要生成单指针 Wrapper 对其进行参数解包，绝不能直接当 native 单参数入口调用”**。

### 5.2 代码改动：[clang/lib/CodeGen/Targets/RISCV.cpp](file:///home/kaikai/vortex-word/llvm-project/clang/lib/CodeGen/Targets/RISCV.cpp)
在 `RISCVTargetCodeGenInfo::setTargetAttributes` 中增加逻辑：
```cpp
  if (CGM.getLangOpts().CUDAIsDevice && FD->hasAttr<CUDAGlobalAttr>()) {
    Fn->addFnAttr("vortex-hip-kernel");
    Fn->addFnAttr(llvm::Attribute::NoInline);
  }
```

### 5.3 验证结果：生成首个设备目标文件 `store42.o`
使用新 Clang 编译 `store42.hip`，并通过 `llc -mcpu=vortex` 输出 `.o` 目标文件：
1. **IR 属性核对**：
   - `_Z7store42Pi` 带有属性组：`attributes #1 = { ... noinline ... "vortex-hip-kernel" ... }`
   - `_Z5twicei`（辅助函数）没有该属性；
2. **反汇编检视**（`llvm-objdump -d store42.o`）：
   ```asm
   0000000000000008 <_Z7store42Pi>:
          8: 02a00593     	li	a1, 0x2a      # a1 = 42
          c: 00b52023     	sw	a1, 0x0(a0)   # *out = 42
         10: 00008067     	ret
   ```
   **至此，L02 阶段全部大功告成！**

---

## 6. 阶段总结与 L03（SimX 执行闭环）衔接

### 6.1 当前已构建的核心能力
- [x] Clang / LLC 完整识别 `-mcpu=vortex` 与 `xvortex` 扩展；
- [x] 成功实现第一条 Vortex 指令 `vx_tmc` 的汇编、反汇编与负例测试；
- [x] Clang CodeGen 正确识别 `__global__` 并打上 `"vortex-hip-kernel"` 标记；
- [x] 成功编译出首个由新编译器生成的设备端目标文件 `store42.o`。

### 6.2 下一步：L03 在 SimX 上跑通并读回 42
有了 `store42.o`，L03 的目标是：
1. 编写单参数 `kernel_wrapper.cpp`（解包 `a0` 中的输出指针并调用 `store42`）；
2. 配合 Vortex 原生启动代码 `vx_start.S` 链接出 `kernel.elf` 并由 `vxbin.py` 打包成 `kernel.vxbin`；
3. 编写 Host 端程序 `host_store42.cpp`（分配显存、加载模块、单线程 launch、读回数据）；
4. **在 SimX 周期级模拟器上运行，真实读回数字 `42`，完成首个端到端执行闭环！**
