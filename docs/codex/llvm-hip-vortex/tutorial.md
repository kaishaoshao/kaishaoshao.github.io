# 《LLVM 后端实战：从零构建 Vortex GPGPU 的 Native HIP 编译器》

更新日期：2026-11-20（Asia/Shanghai）。

这是一套专为系统软件开发者打造的实战教程，系统记录并教学如何在 LLVM 23.1.4 的 RISC-V 目标架构下，从零实现 Vortex GPGPU 的 Native HIP 编译器与执行运行时。

全书采用**“大课带小课”**的章节化书籍结构，彻底摒弃晦涩的工程代号，带你一步步打通从 HIP 前端语法解析、后端指令扩展、编译优化到硬件模拟器真实执行的完整技术链路。

---

## 全书目录

- [序章：项目背景与分层架构理念](#序章项目背景与分层架构理念)
- [第 1 课：Clang HIP 前端机制与语法探索（L01）](#第-1-课clang-hip-前端机制与语法探索l01)
  - [1.1 什么是 Native HIP？与 chipStar/PoCL 的本质区别](#11-什么是-native-hip与-chipstarpocl-的本质区别)
  - [1.2 编写第一个 HIP 探测程序](#12-编写第一个-hip-探测程序)
  - [1.3 剖析 Clang AST：Kernel 属性与 <<<>>> 解析](#13-剖析-clang-astkernel-属性与--解析)
  - [1.4 生成设备标量 IR 与关键断层分析](#14-生成设备标量-ir-与关键断层分析)
- [第 2 课：后端基建：处理器模型、自定义指令与 Kernel 标记（L02）](#第-2-课后端基建处理器模型自定义指令与-kernel-标记l02)
  - [2.1 架构三层解耦原则：CPU、Feature 与 Kernel 标记](#21-架构三层解耦原则cpufeature-与-kernel-标记)
  - [2.2 注册 xvortex 扩展与 -mcpu=vortex 处理器模型](#22-注册-xvortex-扩展与--mcpuvortex-处理器模型)
  - [2.3 手算与编码：首条自定义指令 vx_tmc 的 MC 编解码支持](#23-手算与编码首条自定义指令-vx_tmc-的-mc-编解码支持)
  - [2.4 在 Clang CodeGen 中标记 vortex-hip-kernel](#24-在-clang-codegen-中标记-vortex-hip-kernel)
  - [2.5 编译首个设备目标文件 store42.o](#25-编译首个设备目标文件-store42o)
- [第 3 课：执行闭环：在 SimX 硬件模拟器上跑通 store42（L03）](#第-3-课执行闭环在-simx-硬件模拟器上跑通-store42l03)
  - [3.1 极简闭环架构全景与数据流](#31-极简闭环架构全景与数据流)
  - [3.2 硬件启动与多形参解包：Native Wrapper 设计原理](#32-硬件启动与多形参解包native-wrapper-设计原理)
  - [3.3 符号契约深究：vxbin.py 与 __vx_kentry_ 导出机制](#33-符号契约深究vxbinpy-与-__vx_kentry_-导出机制)
  - [3.4 裸机固件链接：正确复用预编译启动汇编与静态库](#34-裸机固件链接正确复用预编译启动汇编与静态库)
  - [3.5 Host 侧控制：基于 Vortex 2.0 异步队列的驱动实现](#35-host-侧控制基于-vortex-20-异步队列的驱动实现)
  - [3.6 SimX 实测：从硬件显存读回 42！](#36-simx-实测从硬件显存读回-42)
  - [3.7 实战踩坑手记与故障排除（FAQ）](#37-实战踩坑手记与故障排除faq)
- [第 4 课：走向真正 SIMT：多线程与分支分歧控制（L04 进阶预备）](#第-4-课走向真正-simt多线程与分支分歧控制l04-进阶预备)
  - [4.1 从单线程到多线程：网格维度与 CSR 线程索引](#41-从单线程到多线程网格维度与-csr-线程索引)
  - [4.2 当多线程遭遇 if (gid < n)：分支分歧与活跃掩码](#42-当多线程遭遇-if-gid--n分支分歧与活跃掩码)
  - [4.3 为什么需要 vx_split / vx_join 与分歧分析 Pass](#43-为什么需要-vx_split--vx_join-与分歧分析-pass)
  - [4.4 L04 的里程碑：带边界检查的并行加法 vecadd](#44-l04-的里程碑带边界检查的并行加法-vecadd)
- [第 5 课：内存层次与通信原语（L05 进阶展望）](#第-5-课内存层次与通信原语l05-进阶展望)
- [第 6 课：复杂算子与已有程序移植（L06 进阶展望）](#第-6-课复杂算子与已有程序移植l06-进阶展望)

---

## 序章：项目背景与分层架构理念

### 为什么自研 Native HIP 支持？
官方 Vortex 目前支持 HIP 的主流途径是基于 **chipStar + SPIR-V + PoCL**：
```text
HIP 源码 → Clang/hipcc (编译为 SPIR-V) → PoCL 驱动翻译为 OpenCL/Vortex 内核 → 执行
```
这种间接路径依赖极其庞大的第三方跨平台兼容栈，无法直接控制后端的硬件指令选择、寄存器压力分配与专用 SIMT 分歧转换。

本项目的目标是**在 LLVM 23.1.4 的 RISCV Target 中实现原生 HIP 编译支持（Native HIPVortex）**：
```text
HIP 源码 ─┬─> Host 编译 (x86_64)   ──> 注册镜像 / Kernel 启动 Stub / HIP API
          └─> Device 编译 (riscv64) ──> LLVM IR ──> SIMT Lowering ──> Vortex 指令 ──> .vxbin
```

### 架构三层解耦原则
为保持与上游 RISC-V 后端的最大兼容性，避免侵入破坏通用 RISC-V 逻辑，架构采取三层严格解耦：
1. **处理器模型 `-mcpu=vortex`**：负责默认 ISA 组合（RV64IMAFD + Zicond + XVortex，默认关闭 A/C 扩展）与保守流水线调度模型；
2. **能力特性 `xvortex`**：负责管理特殊 SIMT 指令（TMC、SPLIT、JOIN、BAR 等）的谓词与 pass 开关，代码中绝不硬编码 CPU 名，只查 feature；
3. **入口属性与元数据**：负责在 IR 区分“多形参逻辑 Kernel”与“单指针原生启动入口”。

---

## 第 1 课：Clang HIP 前端机制与语法探索（L01）

- **对应 Git 提交**：`c447d813c`
- **本地实验源码**：`llvm/unittests/Vortex/101/`

### 1.1 什么是 Native HIP？与 chipStar/PoCL 的本质区别
HIP（Heterogeneous-compute Interface for Portability）是 AMD 主推的单源码异构编程模型。其语法高度对齐 CUDA，允许在同一个 `.hip` 或 `.cpp` 文件中同时书写 Host 代码与 Device 核函数。

在 Native HIP 体系中，Clang 驱动会自动发起两次编译（Two-Pass Compilation）：
1. **Device Pass**：使用 `-fcuda-is-device` 选项，将 `__global__` 函数编译为目标架构的设备机器码或二进制镜像；
2. **Host Pass**：将 `<<<grid, block>>>` 语法糖改写为运行时启动调用，并将设备镜像打包嵌入到 Host 二进制中。

### 1.2 编写第一个 HIP 探测程序
输入探测文件 `attributes.hip`：
```cpp
#define __global__ __attribute__((global))
#define __device__ __attribute__((device))

__device__ int twice(int v) { return v * 2; }
__global__ void store42(int* out) { *out = 42; }
```
我们先不写任何编译器后端逻辑，只使用 Clang 原生前端对其进行预处理和语法检查：
- **宏展开观察**（`clang -E -P attributes.hip`）：`__global__` 被直接展开为 Clang 原生内建的 `__attribute__((global))`；
- **设备/主机隔离校验**：在普通 Host 函数中直接调用 `twice()` 会被 Clang 前端直接拦截并报错：`reference to __device__ function in __host__ context`。

### 1.3 剖析 Clang AST：Kernel 属性与 <<<>>> 解析
使用 `-fsyntax-only -Xclang -ast-dump` 打印语法树，可以看到：
1. `twice` 节点被挂载了 `CUDADeviceAttr`；
2. `store42` 节点被挂载了 `CUDAGlobalAttr`；
3. 当解析到启动语法 `store42<<<1, 1>>>(ptr)` 时，AST 会将其解析为一个 `CUDAKernelCallExpr` 表达式，并在背后隐式插入参数推栈调用 `__hipPushCallConfiguration`。

### 1.4 生成设备标量 IR 与关键断层分析
执行前端命令生成标量设备 LLVM IR：
```bash
clang -cc1 -triple riscv64-unknown-elf -target-cpu generic-rv64 -x hip -fcuda-is-device -emit-llvm attributes.hip -o device.ll
```
产出的 IR 为：
```llvm
define dso_local void @_Z7store42Pi(ptr %out) {
  store i32 42, ptr %out, align 4
  ret void
}
```
**关键断层剖析**：
1. 前端生成的设备标量 IR 完全丢弃了 `__global__` 属性，无法区分哪些函数是外部可见的核函数入口；
2. 缺乏针对 Vortex 的处理器定义（`-mcpu=vortex`）；
3. 缺乏 Vortex SIMT 硬件指令（掩码控制、分支分歧）；
4. 缺乏多形参业务 Kernel 到 Vortex 单指针硬件启动 ABI 的桥接。
**因此，我们必须进入后端展开改造！**

---

## 第 2 课：后端基建：处理器模型、自定义指令与 Kernel 标记（L02）

- **对应 Git 提交**：`2cbb216a2`、`0d3d3fcd2`、`d558c7fd0`
- **本地测试脚本**：`llvm/unittests/Vortex/102/`

### 2.1 架构三层解耦原则：CPU、Feature 与 Kernel 标记
在引入后端改动时，严禁使用“特判 CPU 名称”的粗暴做法。我们必须遵循标准 LLVM 设计哲学：
- `RISCVProcessors.td` 定义 CPU，仅用于组合预设的 Feature 集合与流水线模型；
- `RISCVFeatures.td` 定义具体的 Feature（`FeatureVendorXVortex`），所有指令匹配、优化 Pass 均绑定在该 Feature 上；
- IR Function 属性标记用于指导 CodeGen 发射不同的函数序言（Prologue）与调用约定。

### 2.2 注册 xvortex 扩展与 -mcpu=vortex 处理器模型
#### 1. 注册扩展（[RISCVFeatures.td](file:///home/kaikai/vortex-word/llvm-project/llvm/lib/Target/RISCV/RISCVFeatures.td)）
```tablegen
def FeatureVendorXVortex
    : RISCVExtension<1, 0, "Vortex SIMT extension">;
def HasVendorXVortex
    : Predicate<"Subtarget->hasVendorXVortex()">,
      AssemblerPredicate<(all_of FeatureVendorXVortex), "'XVortex' (Vortex SIMT extensions)">;
```
TableGen 模板会自动生成小写扩展名 `xvortex`，并在 `Subtarget` 类中生成 `hasVendorXVortex()` 查询方法。

#### 2. 定义处理器（[RISCVProcessors.td](file:///home/kaikai/vortex-word/llvm-project/llvm/lib/Target/RISCV/RISCVProcessors.td)）
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
- 调度模型选用 `RocketModel`（成熟的顺序单发射模型，健壮稳妥）；
- 默认特性集合包含 RV64IMAFD、Zicsr、Zifencei、Zicond 与 `xvortex`；
- 默认**不开启** A（原子）与 C（压缩指令），完全对齐 SimX 当前的硬件配置。

### 2.3 手算与编码：首条自定义指令 vx_tmc 的 MC 编解码支持
`vx_tmc rs1`（Thread Mask Control）用于用寄存器 `rs1` 中的位掩码更新当前 Warp 的活跃线程掩码。

#### 1. 32 位 R-Type 指令格式推导
- `opcode`: `0b0001011`（`0x0b` / `OPC_CUSTOM_0`）
- `funct3`: `0b000`（0）
- `funct7`: `0b0000000`（0）
- `rd`: `0`（`x0`）
- `rs2`: `0`（`x0`）
- `rs1`: 操作数寄存器（以 `a0` 即 `x10` 为例，二进制为 `01010`）

二进制拼接：`0000000 00000 01010 000 00000 0001011` $\rightarrow$ 16 进制：**`0x0005000b`**（小端字节序：`0b 00 05 00`）。

#### 2. 代码实现
- 新建 [RISCVInstrInfoXVortex.td](file:///home/kaikai/vortex-word/llvm-project/llvm/lib/Target/RISCV/RISCVInstrInfoXVortex.td)：
  ```tablegen
  let hasSideEffects = 1, mayLoad = 0, mayStore = 0 in {
  let Predicates = [HasVendorXVortex], DecoderNamespace = "XVortex" in {
  def VX_TMC : RVInstR<0b0000000, 0b000, OPC_CUSTOM_0, (outs), (ins GPR:$rs1), "vx_tmc", "$rs1"> {
    let rd = 0;
    let rs2 = 0;
  }
  }
  }
  ```
- 在 [RISCVDisassembler.cpp](file:///home/kaikai/vortex-word/llvm-project/llvm/lib/Target/RISCV/Disassembler/RISCVDisassembler.cpp) 注册反汇编表：
  ```cpp
  static constexpr FeatureBitset XVortexGroup = {RISCV::FeatureVendorXVortex};
  {DecoderTableXVortex32, XVortexGroup, "Vortex simt extensions"},
  ```

### 2.4 在 Clang CodeGen 中标记 vortex-hip-kernel
在 [clang/lib/CodeGen/Targets/RISCV.cpp](file:///home/kaikai/vortex-word/llvm-project/clang/lib/CodeGen/Targets/RISCV.cpp) 中，拦截挂载了 `CUDAGlobalAttr` 的函数并赋予专用属性：
```cpp
if (CGM.getLangOpts().CUDAIsDevice && FD->hasAttr<CUDAGlobalAttr>()) {
  Fn->addFnAttr("vortex-hip-kernel");
  Fn->addFnAttr(llvm::Attribute::NoInline);
}
```
这保证了逻辑核函数不会被优化器随意内联或删除，同时也为后续参数打包提供了锚点。

### 2.5 编译首个设备目标文件 store42.o
```bash
clang -cc1 -triple riscv64-unknown-elf -target-cpu vortex -target-abi lp64d -x hip -fcuda-is-device -emit-llvm -O2 store42.hip -o store42.ll
llc -mtriple=riscv64 -mcpu=vortex -filetype=obj store42.ll -o store42.o
```
使用 `llvm-objdump -d store42.o` 检视反汇编：
```asm
0000000000000008 <_Z7store42Pi>:
       8: 02a00593     	li	a1, 0x2a      # a1 = 42
       c: 00b52023     	sw	a1, 0x0(a0)   # *out = 42
      10: 00008067     	ret
```
首个设备端目标文件顺利产出！

---

## 第 3 课：执行闭环：在 SimX 硬件模拟器上跑通 store42（L03）

- **对应 Git 提交**：`ebb09fb51`
- **本地实验源码**：`llvm/unittests/Vortex/L03/`

### 3.1 极简闭环架构全景与数据流
L03 的核心任务是验证**“新编译器生成的机器码能否在真实的周期级模拟器 SimX 上被加载并正确写入显存”**：
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

### 3.2 硬件启动与多形参解包：Native Wrapper 设计原理
Vortex 硬件在通过 KMU 启动一个 CTA（线程块）时，`vx_start.S` 会从 CSR `MSCRATCH` 读取启动参数包地址，并放入 `a0` 寄存器。
由于用户核函数 `store42(int* out)` 期望的是具体的指针参数，因此需要一个薄包装层 [kernel_wrapper.cpp](file:///home/kaikai/vortex-word/llvm-project/llvm/unittests/Vortex/L03/kernel_wrapper.cpp)：
```cpp
#include <stdint.h>

struct kernel_arg_t {
  uint64_t out_addr;
};

// 引用编译出的设备端符号
extern "C" void _Z7store42Pi(int* out);

// 硬件约定的单指针入口
extern "C" __attribute__((used, retain)) void kernel_main(kernel_arg_t* arg) {
  _Z7store42Pi(reinterpret_cast<int*>(arg->out_addr));
}

// 供 vxbin.py 识别的内核符号导出别名
extern "C" __attribute__((used, retain)) void __vx_kentry_kernel_main(kernel_arg_t* arg)
    __attribute__((alias("kernel_main")));
```

### 3.3 符号契约深究：vxbin.py 与 __vx_kentry_ 导出机制
Vortex 的固件打包工具 `vxbin.py` 扫描 ELF 符号表时，只抓取前缀为 `__vx_kentry_` 的符号：
```python
if not sym.startswith('__vx_kentry_'):
    continue
name = sym[len('__vx_kentry_'):]
if name == 'kernel_main':
    name = 'main'
entries.append((name, value))
```
如果 Wrapper 没有以 `__vx_kentry_` 导出，生成的 `.vxbin` 镜像中的内核表将为空（`"kernels": []`），导致 Host 无法通过名称查找到入口。

### 3.4 裸机固件链接：正确复用预编译启动汇编与静态库
构建脚本 [build-00.sh](file:///home/kaikai/vortex-word/llvm-project/llvm/unittests/Vortex/L03/build-00.sh) 中的链接命令：
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
- 直接链接预先构建的 `$BASELINE/sw/kernel/vx_start.S.2.o`，避开源码编译时缺失宏定义的问题；
- 使用专用裸机链接脚本 `link64.ld` 并指定入口地址 `STARTUP_ADDR=0x180000000`；
- 链接 `libvortex2.a` 硬件支持库。

### 3.5 Host 侧控制：基于 Vortex 2.0 异步队列的驱动实现
在 [host_store42.cpp](file:///home/kaikai/vortex-word/llvm-project/llvm/unittests/Vortex/L03/host_store42.cpp) 中，使用官方标准 `vortex2.h` API：
1. **初始化**：`vx_device_open(0, &device)` 与 `vx_queue_create`；
2. **显存申请与模块加载**：
   ```cpp
   vx_buffer_create(device, sizeof(int), VX_MEM_WRITE, &dst_buf);
   vx_module_load_file(device, "kernel.vxbin", &module);
   vx_module_get_kernel(module, "main", &kernel);
   ```
3. **单线程 Launch 描述符**：
   ```cpp
   vx_launch_info_t li = {};
   li.struct_size  = sizeof(li);
   li.kernel       = kernel;
   li.args_host    = &args;
   li.args_size    = sizeof(args);
   li.ndim         = 1;
   li.grid_dim[0]  = 1;
   li.block_dim[0] = 1;
   vx_enqueue_launch(queue, &li, 0, nullptr, &launch_ev);
   ```
4. **读回与同步**：
   ```cpp
   int result = 0;
   vx_enqueue_read(queue, &result, dst_buf, 0, sizeof(int), 1, &launch_ev, &read_ev);
   vx_event_wait_value(read_ev, 1, VX_TIMEOUT_INFINITE);
   ```

### 3.6 SimX 实测：从硬件显存读回 42！
运行 [run-sim.sh](file:///home/kaikai/vortex-word/llvm-project/llvm/unittests/Vortex/L03/run-sim.sh)，终端输出：
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
硬件模拟器执行完全正确，42 成功读回！

### 3.7 实战踩坑手记与故障排除（FAQ）
1. **Q: 为什么汇编 `vx_start.S` 报 `VX_types.h not found`？**  
   **A**: `VX_types.h` 是动态生成在构建目录中的，且源码还需要依赖数十个硬件宏。直接链接预构建的 `vx_start.S.2.o` 即可。
2. **Q: 为什么 `inspect-kernel.py` 报告 `kernels: []`？**  
   **A**: `vxbin.py` 只解析 `__vx_kentry_` 前缀，在 Wrapper 中为入口增加别名即可。
3. **Q: 为什么 Host 程序报结构体缺少 `grid` 字段？**  
   **A**: Vortex 2.0 运行时重构了数据结构，已改用 `ndim`、`grid_dim[3]` 和 `block_dim[3]` 数组。

---

## 第 4 课：走向真正 SIMT：多线程与分支分歧控制（L04 进阶预备）

### 4.1 从单线程到多线程：网格维度与 CSR 线程索引
L03 中我们只启动了 1 个线程，但真实 GPU 是大规模并行的：
- 线程通过 `threadIdx.x`、`blockIdx.x`、`blockDim.x` 唯一定位自己的计算元素：
  $$gid = blockIdx.x \times blockDim.x + threadIdx.x$$
- 在 Vortex 硬件中，线程索引并不存放在通用内存中，而是硬件在发射每个线程时动态写入特权 CSR 寄存器（如 `VX_CSR_CTA_THREAD_ID_X`）。
- **L04 的首要工作**：将这些内置变量在 LLVM 中转换为读取对应 CSR 的 Intrinsic 展开。

### 4.2 当多线程遭遇 if (gid < n)：分支分歧与活跃掩码
在并行计算中，数组大小不一定整除线程块大小，因此必然存在边界检查：
```cpp
__global__ void vecadd(float* a, float* b, float* c, int n) {
  int gid = blockIdx.x * blockDim.x + threadIdx.x;
  if (gid < n) {
    c[gid] = a[gid] + b[gid];
  }
}
```
在一个 Warp 内的多个线程中，某些线程满足条件，某些线程不满足条件，这就引发了著名的 **SIMT 分支分歧（Divergence）**。

### 4.3 为什么需要 vx_split / vx_join 与分歧分析 Pass
CPU 遇到分支直接跳转，但 SIMT 架构同一周期的所有活跃线程共享同一个 PC。
Vortex 处理分歧的硬件机制是：
1. **`vx_split`**：保存当前活跃掩码，根据条件评估各线程真伪，先激活满足 `then` 条件的线程执行；
2. **`vx_join`**：分支执行完毕后，恢复原先被压栈的活跃掩码，重新同步（Reconverge）。

在 LLVM 中，我们必须挂接 Divergence Analysis（分歧分析 Pass），在发现发散分支时，自动插入 `vx_split` 与 `vx_join` 指令。

### 4.4 L04 的里程碑：带边界检查的并行加法 vecadd
- 实现内置线程坐标读取；
- 实现分支分歧与掩码保存恢复；
- 在 SimX 上以 4 Warps $\times$ 4 Threads 并行计算 `vecadd`，验证边界之外的显存不被污染，且边界内计算完全正确。

---

## 第 5 课：内存层次与通信原语（L05 进阶展望）

- **5.1 本地共享内存（Local Memory / `__shared__`）**：
  Vortex 每个 Core 拥有片上高速 LMEM。映射 `__shared__` 变量到 LMEM 地址空间，实现同一个 Block 内线程的高速数据交换。
- **5.2 屏障与同步原语**：
  实现 `__syncthreads()` 映射到 Vortex 的硬件栅栏指令 `vx_bar`。
- **5.3 自动化驱动框架**：
  告别手工编写 `kernel_wrapper.cpp`，由 Clang 驱动自动生成参数打包 Stub，实现完全透明的 HIP 编程体验。

---

## 第 6 课：复杂算子与已有程序移植（L06 进阶展望）

- **6.1 经典矩阵乘法（SGEMM）移植**：
  引入分块共享内存、外积循环展开，衡量 Compute 与 Memory 的吞吐瓶颈。
- **6.2 跨编译单元链接（Device Linking）**：
  支持多个 `.hip` 文件独立编译设备目标后，通过设备链接器无缝合并为一个固件镜像。
- **6.3 性能调优实战**：
  分析 SimX 模拟器输出的时钟周期、IPC、D-Cache 命中率与 Warp 空闲统计，持续调优指令调度器与寄存器分配。
