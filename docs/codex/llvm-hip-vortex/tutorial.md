# LLVM 23 HIP 支持 Vortex 教程：L01、L02 与 L03 全流程实战指南

更新日期：2026-11-20（Asia/Shanghai）。
本文档系统总结与说明 **L01（HIP 前端探索）**、**L02（Vortex 编译入口与后端首批改动）** 以及 **L03（首个 Kernel 在 SimX 模拟器上跑通并读回 42）** 的全部已提交实现、代码细节、底层设计原理、踩坑排错与复现验证步骤。

---

## 目录

1. [项目背景与分层架构理念](#1-项目背景与分层架构理念)
2. [L01 探索：看懂 Clang HIP 前端机制与缺口（Commit: `c447d813c`）](#2-l01-探索看懂-clang-hip-前端机制与缺口)
3. [L02 实战一：注册 xvortex 扩展与 -mcpu=vortex CPU（Commit: `2cbb216a2`）](#3-l02-实战一注册-xvortex-扩展与--mcpuvortex-cpu)
4. [L02 实战二：首条自定义指令 vx_tmc 的 MC 编解码支持（Commit: `0d3d3fcd2`）](#4-l02-实战二首条自定义指令-vx_tmc-的-mc-编解码支持)
5. [L02 实战三：为逻辑 Kernel 打上 IR 标记并生成首个设备对象（Commit: `d558c7fd0`）](#5-l02-实战三为逻辑-kernel-打上-ir-标记并生成首个设备对象)
6. [L03 实战：首个单线程 Kernel store42 在 SimX 上跑通并读回 42（Commit: `ebb09fb51`）](#6-l03-实战首个单线程-kernel-store42-在-simx-上跑通并读回-42)
7. [常见排错与踩坑指南（Troubleshooting & FAQs）](#7-常见排错与踩坑指南troubleshooting--faqs)
8. [阶段总结与 L04（多线程 SIMT 与分支分歧）展望](#8-阶段总结与-l04多线程-simt-与分支分歧展望)

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

## 6. L03 实战：首个单线程 Kernel store42 在 SimX 上跑通并读回 42

- **对应 Git 提交**：`ebb09fb51`
- **对应工程计划**：[L03：执行第一个 kernel，主机读回 42](plan.md#l03执行第一个-kernel主机读回-42)（含 L03.1～L03.5 全套验收）
- **本地实验源码**：`llvm/unittests/Vortex/L03/`

### 6.1 实验目标与全栈闭环架构
L03 的核心任务是验证**“由新编译器生成的设备目标代码是否能在真实的硬件模拟器（SimX）上执行并正确读回显存结果”**。
这是一个真正意义上的“源码到硬件模拟执行”端到端（End-to-End）闭环：
```text
[store42.hip] ──(新Clang -cc1)──> [store42.ll] ──(新LLC -mcpu=vortex)──> [store42.o]
                                                                             │
[kernel_wrapper.cpp] ──────────────────(新Clang++)───────────────────> [kernel_wrapper.o]
                                                                             │
                                              (链接: vx_start.S.2.o + link64.ld + libvortex2.a)
                                                                             │
                                                                             ▼
[vxbin.py 打包] <─────────────────────────────────────────────────────── [kernel.elf]
      │
      ▼
[kernel.vxbin] (内含 VXSYMTAB 符号表, 导出 "main" @ 0x180000060)
      │
      ▼ (Host 调用 vortex2.h 运行时 API 加载并 Launch)
[host_store42] ──(VORTEX_DRIVER=simx)──> [SimX 模拟器执行] ──> 显存读回: 42 (SUCCESS!)
```

### 6.2 模块一：设备端编译与参数解包 Wrapper
- **源码文件**：[store42.hip](file:///home/kaikai/vortex-word/llvm-project/llvm/unittests/Vortex/L03/store42.hip)、[kernel_wrapper.cpp](file:///home/kaikai/vortex-word/llvm-project/llvm/unittests/Vortex/L03/kernel_wrapper.cpp)

#### 1. 业务 Kernel（`store42.hip`）
```cpp
#define __global__ __attribute__((global))

__global__ void store42(int* out) {
  *out = 42;
}
```
经过新编译器两步生成目标文件：
1. `clang -cc1 -triple riscv64-unknown-elf -target-cpu vortex -target-abi lp64d -x hip -fcuda-is-device -emit-llvm -O2 store42.hip -o /tmp/store42.ll`
2. `llc -mtriple=riscv64 -mcpu=vortex -filetype=obj /tmp/store42.ll -o store42.o`

#### 2. 参数解包桥接与符号契约（`kernel_wrapper.cpp`）
- **为什么需要 Wrapper？**
  用户编写的逻辑 Kernel 是多参数的（`store42(int* out)`），但在硬件层面，Vortex 启动架构（KMU + `vx_start.S`）在 `MSCRATCH` CSR 中只传递一个统一的参数包指针（通过寄存器 `a0` 传给入口）。因此需要一个单指针入口接收 `kernel_arg_t*`，解包出字段后再调用 `store42`。
- **符号导出契约（`__vx_kentry_`）**：
  Vortex 的打包脚本 `vxbin.py` 扫描 ELF 符号表时，只提取前缀为 `__vx_kentry_` 的符号，并将 `__vx_kentry_kernel_main` 规范化为模块公开名称 `"main"`。为了让 Host 端的 `vx_module_get_kernel(module, "main", &kernel)` 成功解析，我们在 Wrapper 中定义 alias：
```cpp
#include <stdint.h>

struct kernel_arg_t {
  uint64_t out_addr;
};

// 引用新编译器生成的 store42 符号(C++名称粉碎)
extern "C" void _Z7store42Pi(int* out);

// Vortex 硬件约定的单指针入口
extern "C" __attribute__((used, retain)) void kernel_main(kernel_arg_t* arg) {
  _Z7store42Pi(reinterpret_cast<int*>(arg->out_addr));
}

// vxbin.py 扫描 __vx_kentry_<kernel> 导出符号表，将 __vx_kentry_kernel_main 映射为 "main"
extern "C" __attribute__((used, retain)) void __vx_kentry_kernel_main(kernel_arg_t* arg)
    __attribute__((alias("kernel_main")));
```

### 6.3 模块二：设备固件链接与 .vxbin 打包
- **脚本文件**：[build-00.sh](file:///home/kaikai/vortex-word/llvm-project/llvm/unittests/Vortex/L03/build-00.sh)

#### 1. 链接为 RISC-V 裸机可执行 ELF
链接步骤的关键点在于正确复用预编译的启动汇编与静态库：
```bash
"$REF_TOOLS/clang++" --target=riscv64-unknown-elf -march=rv64imafd -mabi=lp64d \
    -mcmodel=medany -nostartfiles -nostdlib \
    -Wl,-Bstatic,--gc-sections,-T,"$VORTEX_HOME/sw/kernel/scripts/link64.ld",--defsym=STARTUP_ADDR=0x180000000 \
    "$BASELINE/sw/kernel/vx_start.S.2.o" kernel_wrapper.o store42.o \
    -L "$BASELINE/sw/kernel" -lvortex2 \
    -L "$TOOLS/libc64/lib" -lm -lc \
    "$TOOLS/libcrt64/lib/baremetal/libclang_rt.builtins-riscv64.a" \
    -o kernel.elf
```
- `-nostartfiles -nostdlib`：禁用默认宿主启动文件和动态库；
- `vx_start.S.2.o`：包含 KMU 调度入口、WARP 初始化与 CSR 分发的预编译目标文件；
- `--defsym=STARTUP_ADDR=0x180000000`：设置固件启动基地址；
- `-lvortex2`：Vortex 设备端核心运行时库。

#### 2. 打包生成 `.vxbin` 镜像
通过 `vxbin.py` 提取 LOAD 段并生成符号表尾部（`VXSYMTAB`）：
```bash
OBJCOPY="$REF_TOOLS/llvm-objcopy" python3 "$VORTEX_HOME/sw/kernel/scripts/vxbin.py" kernel.elf kernel.vxbin
```
使用 `inspect-kernel.py` 检视打包成果：
```json
{
  "format": "vxbin",
  "memory_start": "0x180000000",
  "memory_end": "0x180001000",
  "kernels": [
    {
      "name": "main",
      "address": "0x180000060"
    }
  ],
  "payload_bytes": 4096
}
```
可以看到内核 entry 成功导出为 `main`，入口 PC 为 `0x180000060`。

### 6.4 模块三：Host 驱动与 SimX 模拟执行
- **源码与执行脚本**：[host_store42.cpp](file:///home/kaikai/vortex-word/llvm-project/llvm/unittests/Vortex/L03/host_store42.cpp)、[run-sim.sh](file:///home/kaikai/vortex-word/llvm-project/llvm/unittests/Vortex/L03/run-sim.sh)

Host 端基于 Vortex 官方推荐的 `vortex2.h` 异步运行时架构编写：
1. **打开设备与创建命令队列**：
   ```cpp
   vx_device_h device = nullptr;
   RT_CHECK(vx_device_open(0, &device));
   vx_queue_h queue = nullptr;
   vx_queue_info_t qi = { sizeof(qi), nullptr, VX_QUEUE_PRIORITY_NORMAL, 0 };
   RT_CHECK(vx_queue_create(device, &qi, &queue));
   ```
2. **显存申请与内核加载**：
   ```cpp
   vx_buffer_h dst_buf = nullptr;
   RT_CHECK(vx_buffer_create(device, sizeof(int), VX_MEM_WRITE, &dst_buf));
   kernel_arg_t args = {};
   RT_CHECK(vx_buffer_address(dst_buf, &args.out_addr));

   vx_module_h module = nullptr;
   RT_CHECK(vx_module_load_file(device, "kernel.vxbin", &module));
   vx_kernel_h kernel = nullptr;
   RT_CHECK(vx_module_get_kernel(module, "main", &kernel));
   ```
3. **配置单线程 Launch 与读回验证**：
   ```cpp
   vx_launch_info_t li = {};
   li.struct_size  = sizeof(li);
   li.kernel       = kernel;
   li.args_host    = &args;
   li.args_size    = sizeof(args);
   li.ndim         = 1;
   li.grid_dim[0]  = 1;
   li.block_dim[0] = 1;

   vx_event_h launch_ev = nullptr;
   RT_CHECK(vx_enqueue_launch(queue, &li, 0, nullptr, &launch_ev));

   int result = 0;
   vx_event_h read_ev = nullptr;
   RT_CHECK(vx_enqueue_read(queue, &result, dst_buf, 0, sizeof(int), 1, &launch_ev, &read_ev));
   RT_CHECK(vx_event_wait_value(read_ev, 1, VX_TIMEOUT_INFINITE));

   assert(result == 42);
   ```

### 6.5 执行验证
执行 `bash run-sim.sh`，终端完整输出：
```text
=== kernel.vxbin 打包成功 ===
{
  "format": "vxbin",
  "memory_start": "0x180000000",
  "memory_end": "0x180001000",
  "kernels": [
    {
      "name": "main",
      "address": "0x180000060"
    }
  ],
  "payload_bytes": 4096
}
=== Running host_store42 on SimX ===
>>> [Host] Opening Vortex SimX device...
>>> [Host] Allocating device buffer...
>>> [Host] Device buffer address: 0x30000
>>> [Host] Loading kernel.vxbin...
>>> [Host] Enqueue launch on SimX...
>>> [Host] Read back value from SimX: 42

============================================
  SUCCESS! SimX returned 42 from store42!   
============================================
```

---

## 7. 常见排错与踩坑指南（Troubleshooting & FAQs）

在 L03 的开发与排查过程中，我们遇到了几个典型的硬核问题，在此沉淀为排错手册：

### 7.1 `'VX_types.h' file not found` 报错
- **现象**：链接或汇编 `vx_start.S` 时，报 `fatal error: 'VX_types.h' file not found`。
- **根因**：`VX_types.h` 是 Vortex 在配置构建时动态生成的文件（位于 `build64/sw/VX_types.h`），并不在源码树中。且 `vx_start.S` 需要包含几十个由硬件参数派生的 `-DVX_CFG_*` 宏定义和 sysroot 下的 `<newlib.h>`。
- **解法**：不直接从源码重新编译 `vx_start.S`，而是直接链接 Vortex 构建好的预编译目标文件 `$BASELINE/sw/kernel/vx_start.S.2.o`。

### 7.2 打包后 `kernel.vxbin` 内核列表为空（`"kernels": []`）
- **现象**：`inspect-kernel.py kernel.vxbin` 显示 `"kernels": []`，Host 端随后在 `vx_module_get_kernel` 报错找不到 `"main"`。
- **根因**：`vxbin.py` 依靠符号名前缀识别内核入口。它只检索以 `__vx_kentry_` 开头的符号，并且将 `__vx_kentry_kernel_main` 重命名映射为公开的 `"main"`。如果 C++ 代码中只导出了普通函数名 `kernel_main`，则会被忽略。
- **解法**：在 Wrapper 中为 `kernel_main` 添加别名：
  `extern "C" void __vx_kentry_kernel_main(kernel_arg_t* arg) __attribute__((alias("kernel_main")));`。

### 7.3 Vortex 2.0 API 适配踩坑
- **现象**：编译 `host_store42.cpp` 报 `vx_dev_open`、`grid`、`vx_event_wait` 未声明或结构体不匹配。
- **根因**：Vortex 2.0 进行了运行时接口重构（定义在 `vortex2.h`），全面采用异步队列模型（Command Queue）与引用计数体系。
- **解法**：
  - 打开/释放设备：`vx_device_open(0, &device)`，`vx_device_release(device)`；
  - 队列/模块释放：`vx_queue_release(queue)`，`vx_module_release(module)`；
  - Launch 描述符：使用 `ndim=1`，`grid_dim[3]` 与 `block_dim[3]` 数组；
  - 内存读取：`vx_enqueue_read(queue, host_dst, dev_src, offset, size, n_wait, wait_events, out_event)`。

---

## 8. 阶段总结与 L04（多线程 SIMT 与分支分歧）展望

### 8.1 阶段里程碑总结
经过 L01、L02、L03 三个阶段的渐进式演进，Native HIP on Vortex 已经取得了阶段性重大突破：
- **L01**：摸清了 Clang HIP 前端机制，明确了标量 IR 到硬件设备执行之间的缺口；
- **L02**：在 RISC-V 后端成功打通了 `-mcpu=vortex`、`xvortex` 扩展、自定义 SIMT 指令 `vx_tmc`，并在 IR 上标记了逻辑 Kernel 属性；
- **L03**：成功实现了全链路打通，首次在 SimX 周期级模拟器上运行了由新 LLVM 编译出的 HIP Kernel，并正确读回了显存数值 `42`！

### 8.2 L04 下一步规划：从单线程迈向真正 SIMT
L03 目前运行的是单线程（1 Block, 1 Thread）并且没有分歧控制。L04 的目标是**跑通具有实际计算意义的多线程 Kernel（带边界检查的 `vecadd`）**：
1. **接入线程与块内索引 Builtins**：实现 `threadIdx.x`、`blockIdx.x`、`blockDim.x` 映射到 Vortex 特殊 CSR（如 `VX_CSR_THREAD_ID` 等）；
2. **SIMT 分歧控制流 Lowering**：当多线程遇到 `if (gid < n)` 时，生成 Vortex 专有的分支分歧与活跃线程掩码控制逻辑（`vx_split` / `vx_join` / `vx_tmc`）；
3. **多线程 SimX 验证**：在 SimX 上启动多个 Warp/Thread，验证并行加法及边界条件下的结果正确性。

