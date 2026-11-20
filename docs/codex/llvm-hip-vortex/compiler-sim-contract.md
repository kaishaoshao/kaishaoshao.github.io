# 编译器输出与 SimX 的接口

教程接口复核日期：2026-11-19。当前固定为 Vortex 3.0、RV64、默认硬件配置；2026-11-18 按固定 SDK `26d2bc4b5409a35a111e8316ac3a87d07b15fc80` 的实现补充本契约；以下区分现有 native ABI 与拟定 HIP 参数格式。

```text
你的 LLVM
  → 设备 kernel.o 与启动代码
  → 链接 kernel.elf（device runtime + libc + compiler-rt + link64.ld）
  → vxbin.py 打包 .vxbin
  → x86 host 经 Vortex SDK 加载和启动
  → SimX 执行设备指令
  → 下载结果，与 CPU 参考值比较
```

SimX 不解析 HIP 源码。ELF 和 `.vxbin` 仍需匹配指令集、启动流程、线程语义及参数 ABI。独立 SimX 命令行可以按 ELF 装载段与入口启动。L03.0 的 `_start` 自己准备 `a0` 中的输出指针，并在设备端比较结果。[直接 ELF 实验](chapters/03-store42/00-direct-elf.md)

## 编译与链接

验收脚本使用 `vortex/tests/regression/common.mk` 的实际配置：

- ELF64 little-endian，RISC-V ET_EXEC。`.o` / ET_REL 必须先链接。
- target：`riscv64-unknown-elf`；参考 Makefile 写 `rv64imafd` / `lp64d`，加 `+xvortex` 和 `+zicond`；其中 A 与当前 SimX 默认关闭 A 存在差异。此处记录参考命令，不代表严格配置一致已验收；新 CPU 默认与库/镜像审计见 [ISA 配置](architecture.md#isa-config)。
- 原生 RV64 测试使用 `STARTUP_ADDR=0x180000000`、`-mcmodel=medany` 及 `sw/kernel/scripts/link64.ld`。
- 链接 `libvortex2.a`，编译并链接 KMU 启动代码。
- kernel 带 `vortex.kernel` annotation，后端生成 `__vx_kentry_<name>` 符号。`kernel_main` 在模块中暴露为 `main`。
- 启动代码建立栈等状态，读取选中的 kernel entry，将参数缓冲区指针放到 `a0` 后调用 kernel。设备启动入口与 kernel body 的函数入口有区别。

本地参考文件：

```text
vortex/tests/regression/common.mk
vortex/sw/kernel/include/vx_spawn2.h
vortex/sw/kernel/src/vx_start.S
vortex/sw/kernel/scripts/link64.ld
vortex/sw/kernel/scripts/vxbin.py
vortex/sw/runtime/include/vortex2.h
```


<a id="l03-walkthrough"></a>

## L03 操作图：单个 out 指针怎样到达 store42

下面说明 SDK 路径的参数接口。用户实验用手写 C++ wrapper 和参考启动对象接通了读回 42 的流程。随后的 IR 片段用于练习同一调用关系。[L03 SDK 运行记录](chapters/03-store42/04-sdk-launch.md)

```text
host 分配输出 buffer → 查询设备地址 out_addr
  → 序列化为 8 字节参数区（一个 RV64 设备指针）
  → vx_enqueue_launch(args_host 指向这 8 字节，args_size=8)
  → SDK 复制参数区，设备 startup 把参数区地址放到 a0
  → native wrapper 从偏移 0 读出 out_addr
  → 调用逻辑 store42(out_addr) → 写入 42
  → host 等待 launch，再读回输出验证
```

参数区地址与 out_addr 是两级不同的指针；a0 接到的不是输出 buffer 本身。host 上传/读回数据也要遵循 SDK 的 event/等待规则，不能先读旧值再等待 launch。

### 第一步：只建立可检查的 IR wrapper

下面片段用于追加到本阶段产生的设备 IR（教学示意，不是可独立链接的完整模块）。先确认 body 的真实符号与普通调用约定；当前最小输入观察到的名字是 _Z7store42Pi，不将 C++ 名字硬编码进正式生成器。

```llvm
define void @kernel_main(ptr %arg_blob) section ".vx_entry" {
entry:
  %out = load ptr, ptr %arg_blob, align 8
  call void @_Z7store42Pi(ptr %out)
  ret void
}

@__vx_kentry_kernel_main = alias void (ptr), ptr @kernel_main
```

wrapper 在 IR 层调用逻辑 body。设备 C++ 源码中直接调用 __global__ 函数仍受 HIP 语义检查，不能为了教学桥接把它改成允许的普通源级调用。

.vx_entry 由固定 link64.ld 的 KEEP 规则保留；正式生成器还要核对入口/别名的保留属性、重复生成和多 kernel 情形。不要只创建 alias 就假定底层函数不会被 --gc-sections 删除。L05 才自动生成这类入口与版本化参数描述。

### 第二步：逐层检查，不跳到模拟器

| 产物 | 检查 | 出错时先处理什么 |
|---|---|---|
| body.ll + wrapper | verifier、函数签名、指针宽度、偏移 0/对齐 8 | 不调用不存在或错误签名的 body |
| 设备对象 | RV64 ELF、实际 CPU/features、目标指令 | CPU/feature、lowering 或未支持指令 |
| kernel.elf | _start、__vx_cta_entry、kernel_main、alias、section/段地址、_edata/_end | startup/库、链接脚本、入口保留、BSS |
| kernel.vxbin | min/max_vma、payload、VXSYMTAB 的 main→wrapper PC | 打包器和 alias→导出名映射 |
| host launch | args_size=8、grid/block 各 1、kernel handle 指向 main | host 准备的布局、对象与事件依赖 |
| 输出 | 先初始化为非 42，再运行/等待/读回得到 42 | 本次镜像身份、参数、启动，再查 body |

链接继续参考固定 tests/regression/common.mk 的完整设备选项，并逐项记录 compiler/startup/libc/compiler-rt/LLD 来源。其原样参数含 A，与默认 SimX 的差异见 [ISA 配置](architecture.md#isa-config)；不要把复用参考库的桥接结果标成完整 ISA 对齐通过。当前脚本没有自动为任意新 ABI 生成 host。

### 第三步：写自己的最小 SDK host

按 demo/main.cpp 的真实 API 依次实现：device/queue 创建 → buffer 分配与设备地址查询 → module 加载和 main kernel 查找 → launch → 依赖 launch 的读回 → 等待 → 验证/释放。所有 SDK 返回值都检查，资源的成功/失败路径均清理。

launch_info 的关键字段是 struct_size、kernel、args_host、args_size、ndim、grid_dim、block_dim；用 sizeof 正确初始化结构版本。args_host 指向本次序列化的参数值，不能传 host 的 int*。用有界等待保存失败证据；SimX abort 的进程级故障不一定能变成 HIP 错误码。

每次保存三个不同的值：program_pc（公共 startup）、kernel_pc（wrapper）、args_addr（设备参数区）。先完成单线程，再沿用同一链路进入 L04 的线程编号。现成 demo 的 40 字节参数和下面 vecadd 的 32 字节参数都不能代替本实验的 8 字节布局。

## 两个现成 host 的参数布局

默认类型与自然对齐下：

| host | 字段 | 类型 | 字节偏移 |
|---|---|---|---|
| demo | num_tasks | uint32_t | 0 |
| demo | task_size | uint32_t | 4 |
| demo | dim_x | uint32_t | 8 |
| demo | src0_addr | uint64_t | 16 |
| demo | src1_addr | uint64_t | 24 |
| demo | dst_addr | uint64_t | 32 |
| sgemm | size | uint32_t | 0 |
| sgemm | A_addr | uint64_t | 8 |
| sgemm | B_addr | uint64_t | 16 |
| sgemm | C_addr | uint64_t | 24 |

demo 参数结构 40 字节，默认 TYPE=int；sgemm 参数结构 32 字节，默认 TYPE=float。计算和矩阵布局以对应 kernel.cpp 与 CPU 参考实现为准。

`run-kernel.sh` 通过 host 的 `-k` 加载指定产物，不重新编译该输入 kernel；每次运行目录位于 `artifacts/runs/`。

## 新编译器验收

```bash
cd /home/kaikai/vortex-word
bash scripts/validate-compiler.sh /你的LLVM构建或安装目录
```

每次生成新的 `build/compiler-check.XXXXXX`，防止复用旧 kernel 导致假通过。被测 clang++ 编译 kernel 和启动代码；参考工具链提供已有 device runtime、LLD、打包与反汇编工具。它验证设备编译接入，不证明整个 runtime 已由新 LLVM 重编，也不证明完整 HIP 兼容。

后续应自行扩展分歧分支、共享内存 reduction、barrier、原子操作和更多 host/runtime 验收用例。

## 两个 PC 与真实启动路径

固定 SDK 的 [queue.cpp](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/sw/runtime/common/queue.cpp) 分别设置程序启动地址和选中 kernel 的函数地址。不能只把符号表里查到的函数地址作为整个程序的启动地址。

| 值 | 当前实现如何使用 |
|---|---|
| program_pc / STARTUP_ADDR | 模块镜像基址；warp 从公共启动代码开始 |
| kernel_pc / KERNEL_ENTRY | 选中 kernel 的函数入口，通过 CTA_ENTRY CSR 提供 |
| args_addr / STARTUP_ARG | 设备侧参数区地址，通过 MSCRATCH CSR 提供 |

当前 `KMU_ENABLE` 路径中，`_start` 与 `__vx_cta_entry` 位于公共入口，建立栈等状态后读取 CTA_ENTRY 到 s11、MSCRATCH 到 a0，再间接调用 kernel；随后执行收尾的 wsync/tmc。后续 CTA 对 warp slot 的复用还依赖固定 dispatch window，不能随意改变其指令长度或插入代码。

同一 [vx_start.S](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/sw/kernel/src/vx_start.S) 的顶部旧注释以及部分设计说明仍描述每 kernel 两指令 stub；实际生效代码已使用分离的启动 PC/kernel PC。遇到这种差异，以固定提交的代码、生成 ELF 和 runtime 写入的 DCR 三方核对，不能单独照抄旧注释。参考入口 pass 生成的 alias 指向函数 body；alias 本身不负责建立栈。

T04 的检查要覆盖 `_start`/公共入口、镜像 min_vma 和 runtime program_pc 的一致性，kernel alias/导出名/kernel_pc 的一致性，以及 `a0` 的参数指针。用两个计算结果不同的 kernel 交替启动、多 block 和多轮 CTA slot 复用检验，不只验证单个首次 launch。

## native vxbin 与 HIP 元数据的边界

现有 [vxbin.py](https://github.com/vortexgpgpu/vortex/blob/26d2bc4b5409a35a111e8316ac3a87d07b15fc80/sw/kernel/scripts/vxbin.py) 输出两项 little-endian u64 地址边界、镜像 payload 和可选 VXSYMTAB footer。max_vma 覆盖 `_end` 等运行时范围；文件 payload 长度不能直接当作完整设备内存占用。

VXSYMTAB 提供名称和入口 PC，不包含 HIP 参数类型/对齐/偏移信息。T07 可先在设备镜像旁保存易检查的参数描述，T08 再把镜像与描述封装到 host 容器；保持两阶段同一版本契约。原型优先沿用 SDK vxbin loader，不为添加 HIP 参数表就同时修改其文件格式和调度 ABI。

## HIP 参数布局示例（拟定契约，待实现）

以 `vecadd(const float* a, const float* b, float* c, int32_t n)` 为例：设备指针宽 8 字节，int32_t 宽 4 字节，按自然对齐并将参数区尾部补齐至最大对齐，建议布局如下。实际生成器和 wrapper 必须根据目标 DataLayout/冻结的序列化规则验证。

| 参数 | 种类 | 字节数 | 对齐 | 偏移 |
|---|---|---|---|---|
| a | 设备地址 | 8 | 8 | 0 |
| b | 设备地址 | 8 | 8 | 8 |
| c | 设备地址 | 8 | 8 | 16 |
| n | int32 标量 | 4 | 4 | 24 |
| 尾部填充 | 置零 | 4 | — | 28 |

总大小 32 字节、对齐 8。它与 demo 的 40 字节参数结构是两份不同契约，不能直接互换。

2026-11-18 用参考 Clang 20.1.8、`--target=riscv64-unknown-elf -march=rv64imafd -mabi=lp64d` 对对应自然 C++ 结构做了 sizeof/alignof/offsetof 静态断言，32/8 字节及 0/8/16/24 偏移检查通过。这只核对参考目标的数据布局，不代表 LLVM 23 的参数生成器、wrapper 或端到端执行已完成。

host launch 的参数数组保存 `&da、&db、&dc、&n`，runtime 从这些 host 地址分别读取参数值，写入目标参数区。指针参数写入的是 da/db/dc 的设备地址值；不会把 `&da` 等 host 地址传给设备，也不能直接复制整个 void** 数组作为设备参数。wrapper 接收单一参数区指针，从规定偏移解包，在 IR/CodeGen 层调用 kernel 实现；这不是允许设备 C++ 源码直接调用 __global__ 函数。

最小元数据需明确：格式版本、kernel 标识和入口、每参数的 kind/size/alignment/offset、总大小和对齐、所需 ISA/ABI、静态共享内存与必要编译假设。对未知版本、参数数量不符、越界或重叠布局、超限资源有明确错误；不能依赖“碰巧和 host sizeof 相同”。

## 提交时机、快照与对象生命周期

固定 queue.cpp 在 `enqueue_launch` 时复制参数 blob，并 retain kernel 以保活其模块；这只涵盖该接口约定。HIP runtime 仍需保证在调用时正确复制参数值、在执行期间保活参数中引用的设备 buffer，并按契约处理 free/unload。不能把参数 blob 已复制等同于全部资源都已保活。

runtime 检查 grid/block 非零、checked 乘法、实际支持的 block 形状及资源上限；当前默认每 Core 4 warp × 4 thread 给出 16-thread 的 block 容量。shared 请求要合并静态和动态区域；不忽略 padding、溢出或能力查询失败。

最终还需核对新 ELF 与参考静态库的 ISA/ABI、实际使用的链接器、relocation/code model、数据/BSS/栈/TLS 和 compiler-rt 来源。当前参考 Makefile 使用 medany、裸机静态链接路径、禁用 RTTI/异常等选项；新 Clang 不能意外引入 host Linux crt、动态装载器或不匹配的设备库。

## 本节补充的证据边界

2026-11-18 对 queue.cpp、vx_start.S、vxbin.py 与 common.mk 做了源码核对。本节的 HIP 参数格式为教程设计，尚未由新 LLVM 生成；启动、生命周期和负例测试是后续验收要求。本次审阅没有新增 SimX 执行通过记录，也没有改动 SDK/编译器实现。
