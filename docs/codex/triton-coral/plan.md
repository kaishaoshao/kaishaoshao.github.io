# Triton Coral 开发教程与实施计划

更新日期 2026-11-19（Asia/Shanghai）。

**后端骨架已搭建。接下来让 `scalar_copy` 从 Triton 源码生成真实 RV32 ELF，在 core0 上写回 −37。** 先复跑 S0 的前端检查，再进入单核闭环。当前 `make_llir` 返回 TTIR 文本，`make_elf` 返回占位 `bytes`，这是骨架的验证边界。

已搭好环境可直接跳到[第一次运行](#第一次运行)。需要复核插件发现、构建和 C++ 注册时读[第一课：验证骨架](tutorials/01-backend-skeleton.md)。开始实现代码生成时读[第二课：标量单核闭环](backend-skeleton.md)。完整的阶段、任务和依赖另存于 [plan.json](plan.json) 与 [tasks.xlsx](tasks.xlsx)。

## 第一次运行

在 Linux 上进入文档仓库顶层。以下路径已在 `compiler-1` 核对，其他环境修改对应变量即可。

```bash
export CORAL_TUTORIAL="$PWD/docs/codex/triton-coral/examples"
export CORAL_REPO=/home/compiler-1/work/coral/triton-coral
export CORAL_PYTHON="$CORAL_REPO/.venv/bin/python"
export CORAL_LLVM_BUILD=/home/compiler-1/work/coral/coralnpu-compiler/out/llvm-zvt/build
export CORAL_TRITON_OPT="$CORAL_REPO/build/install/bin/triton-opt"
export CORAL_FILECHECK="$CORAL_LLVM_BUILD/bin/FileCheck"
export CORAL_TEST_OUT="$(mktemp -d /tmp/coral-tutorial-XXXXXX)"

"$CORAL_PYTHON" -m unittest discover -s "$CORAL_TUTORIAL" -p test_suite.py -q
"$CORAL_PYTHON" "$CORAL_TUTORIAL/dump_ttir.py" --stage S0 --case S0.frontend --output "$CORAL_TEST_OUT/s0"
cat "$CORAL_TEST_OUT/s0/S0.frontend.0.ttir"
```

前端应打印 `FRONTEND ONLY (coral): 1 TTIR specializations verified.`。打开 TTIR，确认入口是 `@scalar_copy`，函数体是加载、写回、返回。`frontend.json` 记录目标、选项来源和生成的文件。

| 看到什么 | 此时能确认什么 |
| --- | --- |
| 主机自检 `OK` | 独立参考、ABI 打包和证据校验器通过自检。 |
| `FRONTEND ONLY` | 从源程序生成并验证了 TTIR。默认使用教程选项。 |
| `PREPARED` | 已经写出 `request.json`，可以读参数或交给适配器。 |
| `PASS … [frontend]` 或 `[ir]` | 已验证适配器返回的指定编译检查点。 |
| `PASS … [aot]` 或 `[jit]` | 正例有真实 RTL/设备证据且结果正确。诊断用例的 PASS 表示预期错误被观察到。 |

## 源码目录与职责

目前 Coral 已由 Triton 发现并加载。保留 `third_party/coral/backend/`、`triton_coral.cc` 和已有冒烟测试。S1-01a 第一次引入成对的转换组件目录。目录名使用模块名 `TritonCoralToLLVM`，与 NVIDIA 和 AMD 后端的转换组件组织一致。[Triton NVIDIA 后端构建](https://github.com/triton-lang/triton/blob/main/third_party/nvidia/CMakeLists.txt) · [MLIR 的 pass 声明](https://mlir.llvm.org/docs/PassManagement/#declarative-pass-specification)

```text
triton-coral/
├── third_party/coral/
│   ├── CMakeLists.txt
│   ├── triton_coral.cc
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── name.conf
│   │   ├── compiler.py
│   │   └── driver.py
│   ├── include/TritonCoralToLLVM/       # S1-01a 新建
│   │   ├── CMakeLists.txt
│   │   ├── Passes.td
│   │   └── Passes.h
│   ├── lib/TritonCoralToLLVM/           # S1-01a 新建
│   │   ├── CMakeLists.txt
│   │   └── TritonCoralToLLVM.cpp
│   └── unittest/test1.py               # 已有骨架冒烟
├── python/test/backend/                # 正式编译入口的回归
└── test/                               # opt 可独立调用的 pass 回归
```

| 位置 | 职责 |
| --- | --- |
| `backend/compiler.py` | 验证目标与选项，组织 TTIR、LLVM IR、ELF 阶段，记录编译元数据。 |
| `backend/driver.py` | 发现设备，选择目标。S3 再接装载与启动。 |
| `triton_coral.cc` | 通过 nanobind 暴露 pass 添加函数。 |
| `include/TritonCoralToLLVM/` | 声明 pass、名称和依赖方言。CMake 将 `Passes.h.inc` 生成到 build 目录。 |
| `lib/TritonCoralToLLVM/` | 编写类型转换、conversion pattern 和合法性检查。CMake 以独立的 Triton 转换库构建。 |
| Coral 根目录 `CMakeLists.txt` | 串起声明生成、转换库与 Python 插件。 |

调用关系是 `compiler.py → triton_coral.cc → TritonCoralToLLVM → LLVM 方言`。回到 `make_llir()` 后，`llvm.to_module()` 导出 LLVM IR。这样修改一条 load/store 规则时，改动落在转换组件，Python 编译阶段沿用同一入口。

### 什么时候增加文件

| 时机 | 代码位置与职责 |
| --- | --- |
| S0-03 | 只改 `backend/compiler.py` 的选项和目标匹配。用已有构建跑 Python 前端，不触发 C++ 构建。 |
| S1-01a | 先构建并验证上述转换组件，再接 `make_llir()`。pass 使用正式绑定，测试从真实 TTIR 或标准 Triton 源程序开始。 |
| S1-01b/c | 在同一组件加无掩码访存、常量和加法。访存分支增长后可以在同目录拆出 `MemoryOpToLLVM.cpp`。 |
| S1-02/03 | `third_party/coral/backend/runtime/` 存放随 kernel 链接的 `start.S` 与 `link.ld`，由 `make_elf()` 使用。交付 wheel 时把这两份资源加入 Coral 包数据并检查安装后能读取。 |
| S2/S4 | S2 用现有 SCF 等方言表达 block 语义。S4 由二维访存和循环用例驱动 TTS 接入，再降低至 Linalg 并执行 bufferization。等第一条转换有可验证的输入与输出后，按转换名建对应的 `include/` 与 `lib/` 组件。 |
| S6–S8 | 编译期布局、搬运与 tile 约束放在相应转换库。出现新语义后，再按各自的用例增加 `include/Dialect/` 与 `lib/Dialect/` 下的方言组件。S7 先验证存储层级及搬运语义，S8 再定义 tile 操作。实际队列、DMA、取指可见性、HBF/3D DRAM 配置由设备实现提供。 |

`coralnpu-compiler` 提供固定 LLVM/MLIR SDK、RISC-V 目标代码生成和 Zvt 接口。`coralnpu` 提供 RTL、设备模型、控制固件和装载执行测试。Triton 侧通过版本化 ABI 和目标能力使用这些接口。逻辑 program ID 由编译语义确定，运行时根据核掩码和队列把程序分配给物理核。

教程的 `examples/kernels/` 保存 Triton 源程序，`examples/stage_cases/` 保存输入、参考值和负例。实现进入 Triton 仓库时，编译回归放在 `python/test/backend/test_coral_compile.py`，空 kernel 和未支持的访存分别用一个测试函数。需要通过 `triton-opt` 直接运行 pass 时，接 CLI 注册后再写 `test/TritonCoralToLLVM/` 的 lit 回归。真实执行用例交给 Coral 模型与固件测试，核对同一编译产物的装载和回读。

## 大阶段目标

| 阶段 | 先实现什么 | 任务 | 验收出口 | 通过标准 |
| --- | --- | --- | --- | --- |
| S0 | 骨架基线与前端核验 | S0-01～S0-03 | G0 | 固定构建可发现 Coral，正式选项可生成拷贝及加法 TTIR，未知目标有诊断。 |
| S1 | 标量语法与 AOT 执行 | S1-01～S1-06 | G1 | 标量 load/store、INT32 算术与 constexpr 由真实源码生成 ELF，在 core0 执行正确。 |
| S2 | block、mask 与选择 | S2-01～S2-04 | G2 | 三指针标准向量加法、arange、广播、where、constexpr 分支、mask 和顺序 grid 正确。 |
| S3 | JIT 与特化调用 | S3-01～S3-04 | G3 | 标准 JIT/缓存和设备 buffer 正确；v3 六运行参数 AOT/JIT 通过，v2 超容量明确拒绝。 |
| S4 | 二维访存与循环 / TTS-Linalg | S4-01～S4-06 | G4 | 二维 stride、广播、reshape/transpose、运行时 for/while/if 在结构化主线执行正确。 |
| S5 | 整数归约、扫描与 RVV | S5-01～S5-03 | G5 | sum/max 产生实际执行的 RVV 指令。argmax 并列与整数前缀扫描算对。 |
| S6 | 多维 grid 与多核 | S6-01～S6-04 | G6 | program_id/num_programs 覆盖 1/2/4 核二维 grid 及四核三维 grid。 |
| S7 | 同一语法的分层存储 | S7-01～S7-05 | G7 | 同一 block 源码经显式 HBF/DRAM/DTCM 搬运在单核及多核正确执行。 |
| S8 | dot 语法与 Zvt | S8-01～S8-04 | G8 | 合法 INT8 dot 源码完成形状契约、矩阵 lowering、tile 方言和真实 Zvt 执行。 |
| S9 | 类型扩展与执行优化 | S9-01～S9-03 | G9 | 可选语法按能力独立验收，重叠版本保持结果正确，性能报告记录实际周期。 |

## 逐阶段教程

第一批逐步推进。**S0-03** 只补正式前端选项；**S1-01a** 先按组件目录构建并测试原生 pass，再接已有 `make_llir()`，通过 `triton.compile()` 验证 RV32 LLVM IR 和 `tt.load` 负例。 [修改文件、代码与测试](backend-skeleton.md#第一批正式选项与空-kernel-接入编译流水线)

每课先跑一个代表用例，再实现该阶段需要的转换。能从源码生成的合法 IR 用 lit/FileCheck 核对。非法 IR、ABI 及运行时状态用 verifier 或断言。单核先打通 AOT，S3 加入标准 `kernel[grid](...)`，以后保留 AOT/JIT 两条回归。

下表中的源码检查用于观察 IR，主机自检用于验证参考实现和证据校验器。设备及诊断用例通过实际适配器运行，命令见[实现后怎么验收](#实现后怎么验收)。标为**待补**的测试应随对应 pass、固件或运行时一同实现。上游小步骤的设备复测要等所需执行路径接通。运行用例时按其所属阶段选择 `--stage`，例如 `S1.copy.jit` 属于 S3。

### S0 骨架基线与前端核验

**本阶段目标**  固定已搭好的 Coral 骨架和工具链，取得可重现的源码 TTIR。G0 还要补齐正式选项，并在选错目标时给出明确诊断。

从 `scalar_copy` 的 `@triton.jit`、两个 I32 指针和 `tl.load/store` 开始。看导出的 `tt.func`、`tt.load`、`tt.store`、`tt.return`。同时确认当前 Python 加载的是 Coral 后端。 [Kernel](examples/kernels/s1_scalar.py) · [用例和参考](examples/stage_cases/s0_frontend.py)

**动手入口**  生成源码 TTIR。

```bash
"$CORAL_PYTHON" "$CORAL_TUTORIAL/dump_ttir.py" --stage S0 --case S0.frontend \
  --output "$CORAL_TEST_OUT/s0-lesson"
```

| 小阶段 | 要完成的目标 | 测试与通过证据 | 实现注意 |
| --- | --- | --- | --- |
| S0-01 | 确认 LLVM 锁定信息、后端发现与 C++ 扩展。 | 运行 `third_party/coral/unittest/test1.py`，检查 `coral.hello()` 的输出。核对 `cmake/llvm-info.json` 的 revision、补丁和目标。 | 确认解释器来自当前 checkout。避免把环境中其他版本的 libtriton 当作当前构建。 |
| S0-02 | 写清 RV32 v2 参数和最小地址约定。 | 主机 `test_v2_layout_and_capacity`。待补固件与入口对同一字节样本解码的对照测试。 | `done` 是对齐的设备地址。逻辑 program ID 和物理核号分开。 |
| S0-03 | 让拷贝和加法通过正式 CoralOptions，并拒绝未知目标。 | 源码 `S0.frontend`、`S1.add` 加 `--backend-options`。诊断 `S0.bad-target` 由适配器验证。 | 教程默认补充选项。当前正式 `S1.add` 缺少 `sanitize_overflow`，先重现再修复。 |

**G0 验收**  拷贝和常量加法通过正式选项与 TTIR verifier，未知目标被明确拒绝。

### S1 标量语法与 AOT 执行

**本阶段目标**  先降低空函数，再降低标量访存和加法。G1 把同一份源码生成的 RV32 ELF 加载到 core0，实际写回 −37。 [单核课](backend-skeleton.md)

对照 `empty_kernel`、`scalar_copy`、`scalar_add`。逐步观察 LLVM 函数签名、标量访存、`arith.addi` 降低。 [Kernel](examples/kernels/s1_scalar.py) · [用例和参考](examples/stage_cases/s1_scalar.py)

**动手入口**  生成源码 TTIR。

```bash
"$CORAL_PYTHON" "$CORAL_TUTORIAL/dump_ttir.py" --stage S1 --case S1.copy \
  --output "$CORAL_TEST_OUT/s1-lesson"
```

| 小阶段 | 要完成的目标 | 测试与通过证据 | 实现注意 |
| --- | --- | --- | --- |
| S1-01a | 先验证原生 pass，再在 make_llir 导出 RV32 LLVM IR。 | 真实 TTIR 先用 `EMPTYLLVM` 验收。接入后用 `EMPTYLLIR` 与 LLVM verifier。 | 用 `triton.compile` 验证正式流水线。`S1.copy` 应在 `tt.load` 报未合法化。 |
| S1-01b | 将无掩码 I32 的拷贝降为 LLVM 访存。 | 从 `S1.copy` 生成 TTIR。对实际 pass 的输出检查一个输入 load、一个输出 store 及 verifier。 | 仅在 ABI 保证对齐时标注对齐。用非法张量或 mask 负例检查未支持的转换。 |
| S1-01c | 接入 constexpr 常量和 I32 加法，沿用第一批的 LLVM IR 导出。 | `S1.add` 看 `SCALAR`。对降低后的 LLVM IR 用 `FINALLLVM` 和 `opt -passes=verify`。`S1.wrap` 随 G1 检查结果。 | 保留 I32 回绕。对照拷贝和加法的 LLVM IR，确认计算来自源码，避免擅加 `nsw` 或 `nuw`。 |
| S1-02 | 让入口按 v2 解析参数、调用 kernel 并发布完成。 | 主机检查参数帧。接通启动器后运行 `S1.bad-abi`，非法版本请求应无 launch。 | 对齐栈并保护参数区域。写回对消费者可见后再记录完成。 |
| S1-03 | 生成可检查的静态 RV32 ELF。 | 对 `S1.copy` 实际 ELF 用 `llvm-readelf -h -l`。主机 `test_elf_placeholder_truncation_and_entry` 校验解析器。 | 检查 PT_LOAD、ISA、入口和 ITCM 容量。链接脚本预留的取指填充也占空间。 |
| S1-04 | 从加载段打包 AOT 镜像与装载清单。 | 待补实际打包器负例，覆盖截断、段重叠、越界、入口错误和 BSS 清零。 | 先确定使用 `p_vaddr` 还是 `p_paddr`，保留段权限和可追溯的哈希。 |
| S1-05 | 启动 core0 并关联每次加载与完成。 | 设备 `S1.copy` 写回 −37，`S1.reload` 在同一会话交替拷贝与加法。 | 缓存、取指可见性和完成标志按调用刷新。超时后先确认停止，再复用设备内存。 |
| S1-06 | 完成第一份真实单核闭环报告。 | 累计 S0–S1。对照 `S1.add` 的两组输入、`S1.wrap`、`S1.reload` 和 `S1.bad-abi`。 | 把源码、IR、ELF、装载记录和输出关联到同一调用。前端检查与真实执行分别记录。 |

**G1 验收**  core0 拷贝 −37。不同常量、INT32_MAX 回绕和同会话换代码都通过。非法 ABI 在启动前被拒绝。

### S2 block、mask 与选择

**本阶段目标**  在单核 AOT 上支持向量加法、张量选择与 mask。G2 验证 BLOCK=16 的尾块、全假 mask、原地更新以及顺序 grid。

37 个元素，BLOCK=16，三个 program。看两次 load 和一次 store 是否引用同一个 mask。最后一个 program 只有索引 32～36 有效。 [Kernel](examples/kernels/s2_block.py) · [用例和参考](examples/stage_cases/s2_block.py)

**动手入口**  生成源码 TTIR。

```bash
"$CORAL_PYTHON" "$CORAL_TUTORIAL/dump_ttir.py" --stage S2 --case S2.vector-add \
  --output "$CORAL_TEST_OUT/s2-lesson"
```

| 小阶段 | 要完成的目标 | 测试与通过证据 | 实现注意 |
| --- | --- | --- | --- |
| S2-01 | 将规则 block、算术与选择降低成有界循环。 | 源码 `S2.vector-add` 用 `VECADD` 检查两个 load 和一个 store 共用 mask。`S2.constexpr.0` 与 `S2.constexpr.1` 随 G2 对照。 | 保留整个逻辑 block 的访存依赖。先保证语义，再决定循环能否融合或展开。 |
| S2-02 | 只访问有效 lane，并正确实现显式 `other`。 | 设备 `S2.mask.n0.b16`、`S2.mask.n37.b16`、`S2.other`。主机 `test_mask_rejects_read_or_write_in_padding`。 | mask 为假的 lane 必须跳过真实访存。`other` 只决定 load 的结果。 |
| S2-03 | 让 core0 顺序执行一个以上逻辑 program。 | 设备 `S2.vector-add` 检查三次 launch 及输出。最后一个 program 只处理 32–36。 | 核号始终是 core0，program ID 仍须变化。参数复用要等上一个 program 完成。 |
| S2-04 | 覆盖长度、布局别名和 BLOCK 的正负边界。 | 累计 S0–S2。重点查 `S2.inplace`、`S2.bad-block` 及至少一组 BLOCK=64 尾块。 | N=0 的全假 mask 用例仍启动一个 program。零 grid 的处理在 S3 验证。 |

**G2 验收**  尾块只访问五个有效元素。`S2.other` 保持补充值，`S2.bad-block` 拒绝非法 BLOCK。N=0 全假 mask 仍有一个 program。

### S3 JIT 与特化调用

**本阶段目标**  让普通 Triton `kernel[grid](...)` 能在 Coral 上执行。G3 同时验收真实设备 buffer、v3 参数、缓存和零 grid。

准备同一会话的三次请求，前两次使用相同 constexpr，第三次改变 DELTA。阅读 `request.json` 的 `steps` 和 `cache_pattern`。 [Kernel](examples/kernels/s2_block.py) · [用例和参考](examples/stage_cases/s3_jit.py)

**动手入口**  准备执行请求。

```bash
"$CORAL_PYTHON" "$CORAL_TUTORIAL/run_stage.py" --stage S3 --case S3.cache --emit-only \
  --output "$CORAL_TEST_OUT/s3-lesson"
```

| 小阶段 | 要完成的目标 | 测试与通过证据 | 实现注意 |
| --- | --- | --- | --- |
| S3-01 | 接通 Coral driver 与 launcher 的真实分派。 | 主机 `test_jit_helper_uses_getitem_and_runtime_order` 先核对调用顺序。具备 buffer 后用 `S1.copy.jit` 检查实际路径。 | 设备执行要使用真实 buffer。实际分派与输出 ELF 的哈希要能对应。 |
| S3-02 | 实现 buffer 生命周期和 v3 六运行参数。 | 主机 `test_v3_six_scalar_roundtrip_and_offset`。设备 `S3.abi-v3` 写回 11。`S3.abi-v2-capacity` 与 `S3.bad-buffer` 在启动前拒绝。 | 保留 v2 兼容。按函数签名分别分配 binding/scalar 槽位，constexpr 仅用于编译。 |
| S3-03 | 实现可复现的 JIT 特化和缓存。 | 设备 `S3.cache` 同一会话应为 miss、hit、miss，同时对比输出。 | 运行时输入可变化。constexpr、代码相关的目标特性、ABI 与工具链身份变化应得到正确缓存行为。 |
| S3-04 | 用标准 JIT 验收单核基础能力。 | 累计 S0–S3。重点跑 `S2.vector-add.jit`、`S3.zero-grid`、`S3.abi-v3.jit`。 | 早期用例的 `.jit` 镜像归 S3。零 grid 要核对无 launch 和输出未变。 |

**G3 验收**  同一会话的缓存模式是 miss、hit、miss。零 grid 不启动。v3 六个运行参数产生 11，v2 容量不足被拒绝。

### S4 二维访存与循环 / TTS-Linalg

**本阶段目标**  用二维 stride、广播、转置和动态控制流推动结构化编译。G4 在同一条 TTS/Linalg 主线上跑通新语法与已有 AOT/JIT 回归。

读 5×7 的有效矩形。输入步长 11，输出步长 9。定位两种步长及列 bias 广播，明确 padding 应保持初值。 [Kernel](examples/kernels/s4_structured.py) · [用例和参考](examples/stage_cases/s4_structured.py)

**动手入口**  生成源码 TTIR。

```bash
"$CORAL_PYTHON" "$CORAL_TUTORIAL/dump_ttir.py" --stage S4 --case S4.stride-broadcast \
  --output "$CORAL_TEST_OUT/s4-lesson"
```

| 小阶段 | 要完成的目标 | 测试与通过证据 | 实现注意 |
| --- | --- | --- | --- |
| S4-01 | 接入适合当前 LLVM 的最小 Ascend TTS 子集。 | `structured-and-grid.test` 复跑源码。待补 TTS 构建、注册与真实 pass 的生成/解析检查。 | 固定来源提交，只引入当前指针状态和循环语义所需的接口。 |
| S4-02 | 分析二维指针的基址、偏移、步长和有效范围。 | 源码 `S4.stride-broadcast` 用 `STRIDE`。主机 `test_access_oracle_known_masks_and_strides`。设备对比有效区和 padding。 | 输入步长 11，输出步长 9。布局、mask 和别名一起传递给后续转换。 |
| S4-03 | 让循环状态与运行时分支保持源语义。 | `S4.loop.r0`、`S4.loop.r1`、`S4.loop.r3` 和 `S4.while.0`、`S4.while.1`。源码用 `LOOP`、`WHILE`。 | 零次循环也要返回初始值。指针状态的类型和顺序在迭代参数、yield 与结果中须一致。 |
| S4-04 | 将二维计算和转置表示为 Tensor/Linalg 操作。 | `S4.transpose` 用 `TRANSPOSE` 检查 2×4 到 4×2。`S4.stride-broadcast` 检查真实结构化 IR 及数值。 | 转置改变坐标映射。广播维度与底层物理 stride 分别建模。 |
| S4-05 | 完成 Bufferization、资源检查及 LLVM 降低。 | `S4.stride-broadcast.jit` 保存 `structured`、`bufferized`、LLVM 与 ELF。待补 Bufferization 非法别名与超容量负例。 | 追踪读写权限、别名和活跃区间。检查最终 LLVM 路径的合法性和临时区容量。 |
| S4-06 | 把早期 kernel 收敛到结构化主线。 | 累计 S0–S4。对照 `S1.copy.jit`、`S2.inplace.jit` 与当前阶段输出。 | 临时差分可使用旧路径。最终累计回归里的全部用例要绑定同一版主线。 |

**G4 验收**  运行 AOT/JIT 后比较有效区、padding 和循环边界。已有标量与 mask 用例在结构化主线继续通过。

### S5 整数归约、扫描与 RVV

**本阶段目标**  让整数归约真正执行 RVV，并扩展 argmax 与前缀扫描。G5 同时核对结果、尾块和机器指令。

观察 `tt.scan` 的方向和 axis，再对照 `reduce_sum`/`reduce_max` 的 `tt.reduce`。BLOCK=64 的扫描只保留 37 个有效前缀。 [Kernel](examples/kernels/s5_collectives.py) · [用例和参考](examples/stage_cases/s5_collectives.py)

**动手入口**  生成源码 TTIR。

```bash
"$CORAL_PYTHON" "$CORAL_TUTORIAL/dump_ttir.py" --stage S5 --case S5.scan \
  --output "$CORAL_TEST_OUT/s5-lesson"
```

| 小阶段 | 要完成的目标 | 测试与通过证据 | 实现注意 |
| --- | --- | --- | --- |
| S5-01 | 按目标 VLEN 和动态 VL 分段向量化。 | 待补向量 lowering 的跨 VLEN、尾部和 ISA 禁用检查。`S5.reduce_sum.n1000` 随归约接通后确认实际 RVV。 | BLOCK 是逻辑大小。推进索引用实际 VL，尾部的 mask 和初值要明确。 |
| S5-02 | 实现 sum/max、并列 argmax 与整数扫描。 | `S5.reduce_sum.n37`、`S5.reduce_max.n1000`、`S5.argmax.n1`、`S5.argmax.n5`、`S5.scan`。源码用 `REDUCE`、`SCAN`。 | 归约初值依算子而定。argmax 并列选左侧，最小值不能被 padding 抢占。 |
| S5-03 | 把设备指令证据纳入向量阶段的累计验收。 | 累计 S0–S5。sum/max 同时保存反汇编和指令轨迹，argmax 与 scan 对照每个结果。 | 把 RVV 事件绑定到当前 kernel 和实际执行区间。G5 后可独立推进浮点扩展。 |

**G5 验收**  sum/max 跨 VLEN 正确、尾块合法并有 RVV 轨迹。argmax 并列选左侧，扫描每一个有效前缀都正确。

### S6 多维 grid 与多核

**本阶段目标**  把逻辑 grid 分派给可用核。G6 用同一份 kernel 覆盖 1/2/4 核二维执行，以及四核上的 75 个三维 program。

跟踪 3×5×5 网格最后一个逻辑 program。坐标 `(2,4,4)` 写入下标 74，期望值 5442。 [Kernel](examples/kernels/s6_grid.py) · [用例和参考](examples/stage_cases/s6_grid.py)

**动手入口**  生成源码 TTIR。

```bash
"$CORAL_PYTHON" "$CORAL_TUTORIAL/dump_ttir.py" --stage S6 --case S6.grid.3d \
  --output "$CORAL_TEST_OUT/s6-lesson"
```

| 小阶段 | 要完成的目标 | 测试与通过证据 | 实现注意 |
| --- | --- | --- | --- |
| S6-01 | 参数化核数及有效核掩码。 | 设备 `S6.grid.5x13.mask1`、`S6.grid.5x13.mask3`、`S6.grid.5x13.mask15`。待补零掩码与不可用核配置负例。 | 物理容量来自实际 TargetSpec。运行掩码选择可用核的子集。 |
| S6-02 | 定义可验证的 coral_rt 启动与依赖计划。 | 待补计划 verifier，覆盖越界核、错误 owner、无效引用和环。主机 trace 可先检查错核或漏 launch。 | 在控制层管理任务与事件，保留逻辑 grid 坐标和依赖顺序。 |
| S6-03 | 接通有界队列、核内隔离及回收。 | 设备 `S6.grid.5x13.mask15` 有 65 个 program。核对队列槽位循环复用和完成关联。 | 每核参数、scratch、ELF 身份和提交序号独立。等待完成后才回收。 |
| S6-04 | 验证多核调度保持 Triton program 语义。 | 累计 S0–S6。`S6.grid.3d.jit` 核对全部 75 个结果，坐标 `(2,4,4)` 对应下标 74、结果 5442。 | 在整个轨迹检查唯一执行和正确坐标。继续保持一个 program 由一个核完整执行。 |

**G6 验收**  75 个三维 program 在四核上均执行一次。二维用例覆盖 1/2/4 核，输出与逻辑坐标对应。

### S7 同一语法的分层存储

**本阶段目标**  给同一 kernel 加入显式 HBF、3D DRAM 与 DTCM 布局、搬运和回写。G7 从一核扩展到四核，检查依赖、可见完成和故障恢复。

沿用 `block_add`。从请求中找出 HBF 输入、3D DRAM 工作区和各核 DTCM，理解输出回到 DRAM 的原因。 [Kernel](examples/kernels/s2_block.py) · [用例和参考](examples/stage_cases/s7_storage.py)

**动手入口**  准备执行请求。

```bash
"$CORAL_PYTHON" "$CORAL_TUTORIAL/run_stage.py" --stage S7 --case S7.tiers.mask1.jit --emit-only \
  --output "$CORAL_TEST_OUT/s7-lesson"
```

| 小阶段 | 要完成的目标 | 测试与通过证据 | 实现注意 |
| --- | --- | --- | --- |
| S7-01 | 定义存储区域、权限、owner 及容量。 | 设备诊断 `S7.hbf-write`、`S7.owner`。待补超区域容量、地址窗口及不可达路径的 verifier 负例。 | HBF 对计算平面只读，3D DRAM 承担存储，DTCM 归对应核。地址窗口与物理容量分别记录。 |
| S7-02 | 从 mask 与 stride 求出合法 tile 和 DMA 段。 | `S7.tiers.mask1` 的 257 元素尾块。主机 `test_mask_rejects_read_or_write_in_padding`、`test_rejects_missing_version_wrong_owner_and_alignment`。 | 物理搬运可覆盖已分配且合法的 padding，逻辑访存仍要满足 mask。拆分非连续段。 |
| S7-03 | 把 copy、launch、wait 和回写串成有序计划。 | 主机 `test_legal_dma_chain`、`test_rejects_input_dma_after_kernel`、`test_rejects_output_dma_before_kernel`。设备轨迹随 S7-04 接入。 | 消费者等待生产者可见完成。每次搬入和回写都要关联实际 buffer 版本。 |
| S7-04 | 先让一核完整搬入、计算并写回。 | 设备 `S7.tiers.mask1`、`S7.tiers.mask1.jit`。核对 HBF→DRAM→DTCM→DRAM 路径、保护区和数值。 | 先用单缓冲。等待写回结束后再读输出或回收暂存区。 |
| S7-05 | 在四核分层执行后验证错误与恢复。 | 累计 S0–S7。`S7.tiers.mask15.jit` 对照一核。`S7.dma-mid` 验证部分失败、停止、句柄失效与重启。 | 当前保持单 DMA 通道和同核互斥。部分输出留证，确认停止后再复用。 |

**G7 验收**  分层配置下 257 个元素正确，轨迹中有计算消费的副本和写回。部分失败后能停止、使句柄失效并重启。

### S8 dot 语法与 Zvt

**本阶段目标**  G5 后可并行开发标准 Triton INT8 `tl.dot` 的前端和 Zvt 降低。完整 G8 依赖 G7 的分层执行，要求 v3 参数、对齐和尾块矩阵的正确结果以及真实指令证据。

用提议的 INT8 下界观察 `tt.dot`。对照前端 16×16×32 tile 和设备的 K 子块，分开考虑尾块补零与累加类型。 [Kernel](examples/kernels/s8_dot.py) · [用例和参考](examples/stage_cases/s8_dot.py)

**动手入口**  用教程 dot 下界生成 TTIR。

```bash
"$CORAL_PYTHON" "$CORAL_TUTORIAL/dump_ttir.py" --stage S8 --case S8.dot.16x16x32.mask1 --tutorial-dot-contract \
  --output "$CORAL_TEST_OUT/s8-lesson"
```

| 小阶段 | 要完成的目标 | 测试与通过证据 | 实现注意 |
| --- | --- | --- | --- |
| S8-01 | 提供 Coral 真实 dot 形状和类型契约。 | `S8.dot.16x16x32.mask1` 用 `--backend-options` 生成 TTIR，检查 `DOT`。`S8.reject-v2` 验证容量诊断。 | 源码 tile、硬件 K 子块和运行时 M/N/K 分开。正式验收移除教程下界覆盖。 |
| S8-02 | 为合法矩阵建立可验证的 tile 表示。 | 待补 tile verifier 正负例，覆盖形状、布局、累加类型和状态活跃区间。17×19×35 用例随 S8-04 核对尾块。 | 第一版让 layout、pack 和尾块策略显式可检查。tail 需要合法补零与受控写回。 |
| S8-03 | 按固定 SDK 生成可执行的 Zvt 指令。 | 待补目标代码的汇编/反汇编回归。`S8.dot.16x16x32.mask1` 接通后检查实际 Zvt 轨迹。 | 核对 mstatus 使能及矩阵配置状态。矩阵活跃区间内要保护 mtype/altfmt，注意 vsetvli 的影响。 |
| S8-04 | 核对矩阵结果、尾块和多核写回。 | 累计 S0–S8。重点测 `S8.dot.17x19x35.mask1`、`S8.dot.17x19x35.mask15.jit` 和 `S8.reject-v2`。 | 先按 M/N 分块，每个输出 tile 有唯一写入者。完整报告里保留 padding、pack/transpose 和指令轨迹。 |

**G8 验收**  真实 AOT/JIT 的结果与独立 INT32 参考一致，同时验证 padding、Zvt 指令、矩阵状态和 v3 参数。

### S9 类型扩展与执行优化

**本阶段目标**  性能线从 G7 的分层执行开始，先测基线再试重叠。语法可在 G5 后按能力独立扩展，原子入门用例从 G6 后纳入累计回归。

同一 kernel 用单缓冲和双缓冲比较。检查 `buffer_policy` 和 `compare_single_buffer`，明确每份输入和输出的生存期。 [Kernel](examples/kernels/s2_block.py) · [用例和参考](examples/stage_cases/s9_extended.py)

**动手入口**  准备执行请求。

```bash
"$CORAL_PYTHON" "$CORAL_TUTORIAL/run_stage.py" --stage S9 --case S9.overlap.jit --emit-only \
  --output "$CORAL_TEST_OUT/s9-lesson"
```

| 小阶段 | 要完成的目标 | 测试与通过证据 | 实现注意 |
| --- | --- | --- | --- |
| S9-01 | 建立可解释的单缓冲性能基线。 | 以 `S7.tiers.mask15.jit` 校验输入与输出。保存编译、装载、执行、回传的分项记录，供 `S9.overlap` 对照。 | 模型周期和宿主耗时分开。预热策略、配置和输入应可复现。 |
| S9-02 | 证明跨核搬运和计算有实际重叠。 | `S9.overlap`、`S9.overlap.jit`。相同输入比较单/双缓冲输出、运行周期和真实重叠区间。 | 保护尚在消费的缓冲。通过证据区分重叠成立与性能收益。 |
| S9-03 | 按目标和模式逐项增加类型与算子。 | 按需选 `S9.fp32`、`S9.bf16`、`S9.gather`、`S9.scatter`、`S9.sort`、`S9.atomic-add`。已验收模式登记后进入累计回归。 | 限量样例只覆盖对应语义。单 program 原子通过后还需测试竞争、作用域和内存序。 |

**G9 验收**  保存单/双缓冲结果和周期。FP32、BF16、间接访存、排序、单 program 原子通过的模式分别登记。

### 阶段文件

kernel 放在首次引入的阶段。S0 复用 S1，S7 的分层存储与 S9 的重叠实验复用 S2。同一函数的尺寸、mask、dtype、核掩码和负例写进阶段用例。`suite.py` 汇总这些定义，S1/S2 的 `.jit` 镜像从 S3 验收。

| 阶段 | 开课 kernel 来源 | 阶段用例 |
| --- | --- | --- |
| S0 | [s1_scalar.py](examples/kernels/s1_scalar.py) | [s0_frontend.py](examples/stage_cases/s0_frontend.py) |
| S1 | [s1_scalar.py](examples/kernels/s1_scalar.py) | [s1_scalar.py](examples/stage_cases/s1_scalar.py) |
| S2 | [s2_block.py](examples/kernels/s2_block.py) | [s2_block.py](examples/stage_cases/s2_block.py) |
| S3 | [s2_block.py](examples/kernels/s2_block.py) | [s3_jit.py](examples/stage_cases/s3_jit.py) |
| S4 | [s4_structured.py](examples/kernels/s4_structured.py) | [s4_structured.py](examples/stage_cases/s4_structured.py) |
| S5 | [s5_collectives.py](examples/kernels/s5_collectives.py) | [s5_collectives.py](examples/stage_cases/s5_collectives.py) |
| S6 | [s6_grid.py](examples/kernels/s6_grid.py) | [s6_grid.py](examples/stage_cases/s6_grid.py) |
| S7 | [s2_block.py](examples/kernels/s2_block.py) | [s7_storage.py](examples/stage_cases/s7_storage.py) |
| S8 | [s8_dot.py](examples/kernels/s8_dot.py) | [s8_dot.py](examples/stage_cases/s8_dot.py) |
| S9 | [s2_block.py](examples/kernels/s2_block.py) | [s9_extended.py](examples/stage_cases/s9_extended.py) |

## 实现后怎么验收

适配器的实际路径必须由编译和运行时实现提供。接好后先跑单个用例，再扩大到当前阶段和累计回归。`--case` 必须使用精确 ID，可重复传入。`--list` 输出可运行的 ID 和模式。

```bash
# 接好自己的适配器后，设置 CORAL_ADAPTER 为该脚本的绝对路径。
: "${CORAL_ADAPTER:?先设置真实适配器的绝对路径}"
"$CORAL_PYTHON" "$CORAL_TUTORIAL/run_stage.py" --stage S1 --case S1.copy \
  --adapter "$CORAL_ADAPTER" --output "$CORAL_TEST_OUT/device"
"$CORAL_PYTHON" "$CORAL_TUTORIAL/run_stage.py" --stage S1 --cumulative \
  --adapter "$CORAL_ADAPTER" --output "$CORAL_TEST_OUT/regression"
```

`run_stage.py` 在输出目录下为每次运行创建独立子目录。失败时先看对应 case 的 `adapter.log` 和 `response.json`。通过后保存 `summary.json` 及编译、加载和设备证据。做语法扩展时累计用例总是走当前编译主线。

### 标准 JIT 调用

S3 用 Coral 设备 buffer 调用普通 Triton kernel，先等设备完成，再用宿主参考比较数值。正式适配器通过相同的 `kernel[grid](...)` 入口采集调用产物。

```python
import triton
from kernels.s2_block import vector_add

def launch_vector_add(x, y, z, n):
    block = 16
    return vector_add[(triton.cdiv(n, block),)](x, y, z, n, BLOCK=block)
```

### IR 回归

```bash
"$CORAL_LLVM_BUILD/bin/llvm-lit" -v "$CORAL_TUTORIAL/lit" \
  -Dpython="$CORAL_PYTHON" -Dfilecheck="$CORAL_FILECHECK" \
  -Dtriton_opt="$CORAL_TRITON_OPT" -Dout="$CORAL_TEST_OUT/lit"
```

可以传单个 `.test` 或 `.mlir` 文件来聚焦当前课。`-Dfrontend=cuda` 切到离线兼容检查。S8 的真实 Coral dot 回调就绪后，用 `-Ddot=1` 启用 Coral 模式的 dot 组。新增 C++/MLIR 转换后按编译器仓库说明重建 `triton-opt`，让 FileCheck 检查真实 pass 的输出。

小阶段表里的 FileCheck 前缀和主机测试名也可以单独运行。例如，生成 S2 的开课 TTIR 后检查 `VECADD`，或只跑 S7 的搬运乱序自检。

```bash
"$CORAL_FILECHECK" "$CORAL_TUTORIAL/ir_checks.txt" --check-prefix=VECADD \
  --input-file="$CORAL_TEST_OUT/s2-lesson/S2.vector-add.0.ttir"
"$CORAL_PYTHON" -m unittest discover -s "$CORAL_TUTORIAL" -p test_suite.py \
  -k test_rejects_input_dma_after_kernel -v
```

### 实测基线

compiler-1 固定基线：triton-coral dev/triton-coral@4f045a9d77，coralnpu dev/ncoral-hbf-3dpim@f9ab975c。已验证骨架注册与源码到 TTIR，当前 LLIR/ELF 为占位。真实单核 AOT、标准设备 JIT 与 ABI v3 固件待验收。

样例目录包含 24 个 kernel 和 132 个用例定义。`4f045a9d77` 的 Coral 教程选项在 S0～S7 验证 27 个特化，加入提议的 INT8 dot 下界后共 34 个。Coral 默认模式通过 4 组 lit，离线 CUDA 模式通过 5 组。正式 `CoralOptions` 的 `S1.add` 仍缺少 `sanitize_overflow`。同一提交的 `make_llir` 和 `make_elf` 留待单核闭环替换。

## 实施参考

这些表用于查依赖、设备边界和具体交付物。阅读教程时从上面的代表样例开始。

### 每个大阶段的测试

| 阶段 | 标准 Triton 源码用例 | 断言或 lit | 验收重点 |
| --- | --- | --- | --- |
| S0 | S0.frontend | scalar-and-block.test；正式选项检查；S0.bad-target | 确认注册与 LLVM，拷贝及加法经正式选项生成 TTIR，错误目标有诊断。 |
| S1 | S1.copy、S1.add、S1.wrap、S1.reload | verifier.mlir；S1.empty.llvm；S1.bad-abi | core0 真实 ELF 算对。先用 AOT 闭环，空函数先单独检查 LLVM 方言。 |
| S2 | S2.vector-add、S2.other、S2.inplace、S2.mask.* | VECADD 检查同一 mask；S2.bad-block；逻辑访存断言 | 37 元素或全假 mask 时仍只访问有效索引。输出、other、别名行为正确。 |
| S3 | S1.copy.jit、S2.vector-add.jit、S3.cache、S3.zero-grid、S3.abi-v3.jit | ABI codec 断言；S3.abi-v2-capacity、S3.bad-buffer | 标准 kernel[grid] 调用、缓存和零工作正确，六运行参数按 v3 传递。 |
| S4 | S4.stride-broadcast.jit、S4.transpose.jit、S4.loop.*、S4.while.* | structured-and-grid.test；真实 TTS、Linalg、Bufferization verifier | 非紧密 stride、转置、循环携带量和 0 次迭代算对。 |
| S5 | S5.reduce_sum.*、S5.reduce_max.*、S5.argmax.*、S5.scan.jit | REDUCE/SCAN；RVV 指令轨迹和 VLEN 边界 | 验证规约初值、argmax 并列、scan 前缀、RVV 尾块。 |
| S6 | S6.grid.*；含 S6.grid.3d.jit | GRID3D；逻辑 ID、核掩码、队列容量和回收断言 | 二维网格覆盖 1/2/4 核。四核三维网格的 75 个 program 不重不漏。 |
| S7 | S7.tiers.mask1.jit、S7.tiers.mask15.jit | S7.hbf-write、S7.owner、S7.dma-mid；搬运版本与完成顺序断言 | 同一 kernel 验证 HBF→3D DRAM→DTCM→3D DRAM。结果可见后回收。 |
| S8 | S8.dot.*；含 INT8 尾块 AOT/JIT | dot.test；S8.reject-v2；tile 合法性、Zvt 指令和状态断言 | 对齐和尾块矩阵都与参考相符，确认输入/累加类型和 Zvt 执行。 |
| S9 | S9.overlap.jit；按能力运行 S9.fp32、bf16、gather、scatter、sort、atomic-add 及 JIT 镜像 | advanced-source.test；跨核重叠、错误诊断、精度与作用域断言 | 基础能力分别登记。重叠对照结果与周期。原子扩展另测并发和内存序。 |

`*` 表示同族，使用 `--list` 查完整 ID。

### 真实执行适配器协议（版本2）

适配器在编译和运行时仓库实现。当前教程提供样例、ABI 参考打包器和证据校验器。实现适配器后，使用 `run_stage.py` 核对同一次调用的产物和输出。

1. runner 用同一个 Python 解释器执行 `coral_test_adapter.py --request request.json --response response.json`。请求和响应使用 `protocol: 2`。`nonce`、`request_sha256`、`kernel_source_sha256` 和 `pipeline: current-mainline` 共同标识请求。runner 保留独立参考，只把 `output_bindings` 发给适配器。

   适配器从 `kernels` 按函数名导入源码。`kernel_source_sha256` 使用 `kernels.source_sha256()` 计算，覆盖该包下所有 `.py` 文件名和源码，以统一换行后按文件名排序编码。记录自己的代码包摘要，便于发现适配器加载了另一份源码。
2. 顶层 `build` 记录 Triton、LLVM 和 Coral 提交，以及 `target`、`abi`、`abi_version`、源码摘要和 pipeline。每个 `artifact` 是 `{path, sha256}`，相对路径位于本用例目录。执行步骤另记录 `invocation` 的 `api`、`backend`、`kernel`、`grid`、`request_sha256`、`step` 和调用产物 ELF 的哈希。
3. `aot` 的调用入口标为 `aot_bridge`。`jit` 通过 [jit_entry.py](examples/jit_entry.py) 调用 `kernel[grid](...)` 并确认选择 Coral driver。两种模式都要核对执行 ELF 与调用产物的身份。

| 模式 | 要保存的证据 |
| --- | --- |
| `frontend` | 源码生成的 `ttir`，以及成功的 `verification.ttir`。 |
| `ir` | TTIR 证据和 `llvm_dialect`，以及成功的 `verification.llvm_dialect`。`empty_kernel` 只需函数、参数和返回。 |
| `aot` / `jit` | TTIR、真实 `llir`/`elf`/`trace`、LLVM/ELF 验证结果、调用记录和完整 `outputs`。`execution` 为 `rtl` 或 `device`。 |
| 零 grid | 标准 JIT 调用记录、没有 launch 的轨迹和保持原样的输出。可以直接返回。 |

#### 参数 ABI：G1保留v2，G3必须交付v3

现有v2结构来自coralnpu的experiments/multicore/device/task_abi.h：abi=2、size=68，3个binding/4个scalar，done位于offset64。S1/S2继续使用它。S3-02必须同时实现下表v3，编译器wrapper、控制固件和参数打包器分别以版本解析，不能只改宿主codec。v3仍放在0x00010000的前256B参数预留区，size=128；S8六参数M/N/K/SA/SB/SC正例必须使用v3，v2仅作为容量负例。

| 字段 | 字节偏移 | 字节数 | 约定 |
| --- | --- | --- | --- |
| abi | 0 | 4 | 值3 |
| size | 4 | 4 | 值128 |
| program_id[3] | 8 | 12 | 三轴逻辑ID |
| grid[3] | 20 | 12 | 三轴逻辑grid |
| core_id | 32 | 4 | 物理核编号 |
| binding_count | 36 | 4 | 0..8 |
| scalar_count | 40 | 4 | 0..12 |
| done | 44 | 4 | 设备完成标志地址 |
| bindings[8] | 48 | 32 | RV32设备指针 |
| scalars[12] | 80 | 48 | 32位运行参数，未用槽为0 |

所有字段小端32位，未用槽为0，binding_count<=8/scalar_count<=12。done是设备地址，不是内嵌布尔值；运行前校验其权限/范围/对齐。binding和scalar分别按函数声明中的运行参数顺序编号，constexpr不入帧；完整参数到槽位的映射写入编译产物metadata，不能依赖JSON字典排序。当前运行scalar只支持i32/u32字编码，其他类型须显式扩展，不得截断。零grid不创建执行帧。[abi.py](examples/abi.py)是已测试参考打包器，不代表固件已实现v3。S3.abi-v3及其JIT镜像验证六运行参数，S3.abi-v2-capacity/S8.reject-v2验证拒绝超容量。

#### 逻辑访存与物理搬运分开

trace={protocol:2,arguments:{binding:view_id},views:{view_id:描述},events:[...]}。每个view含binding、indices、region、address、owner、allocation、generation：indices把连续物理元素映射到全局buffer逻辑下标，address为该view首字节的RV32设备地址。DTCM owner必须是所属核，其他region的owner为null。arguments指向原始分配，包含完整逻辑范围；别名view必须映射到相同物理字节。

当前alias_of只声明同dtype、等长的精确原地view，不单独分配或用Y的初始哨兵覆盖X。部分重叠、跨dtype重解释等访问必须增加独立用例与oracle，或按当前支持边界明确诊断；这不表示它们在Triton中普遍非法。JIT的device_buffers必须是真实Coral设备buffer对象，由driver正确识别；不能用宿主数组或整数地址代替标准JIT参数。

- launch含唯一id、三轴program、core、start/end和reads/writes引用；每个引用为{view,version}。start/end是核实际执行区间，排队时间不能填入；同一核的program区间不得重叠。
- access含launch、binding、mode=read/write、view、version、index/count，index/count为逻辑元素下标/数量。校验器依据[access.py](examples/access.py)逐program检查mask、stride和方向；同一分配内的padding也不能被逻辑访问，不能只检查数组总长度。真实轨迹应采集退休后的逻辑访存，不把cache miss日志误当完整访问。
- DMA是独立的物理搬运事件，含唯一id、src/dst版本引用、source/destination region、core、start/end、bytes、success。view的逻辑下标/顺序和dtype必须保持，实际地址和字节数满足4B对齐，不支持重叠拷贝或HBF写；当前单DMA通道不能超发。
- DMA为满足粒度需要可搬运已经分配且允许读取的padding，必须在view中明确列出，不能越出allocation，也不能因此允许kernel逻辑读写mask=false的lane。非连续物理段应拆分成合法copy，禁止用向外取整掩盖越界。

#### 数据版本、完成可见性与复用

版本0仅代表原始参数区的初始内容及可证明的物理子view；局部副本不能凭空声明版本0。每个正版本必须由唯一DMA或kernel写入产生。校验器要求生产者end<=消费者start；DMA的end须对应真实消费者可见完成（含最终成功写响应），不是入队或宿主callback时刻。

kernel的逻辑读写必须引用它声明的版本。DMA用例中kernel应读写自己核的DTCM副本，输入要有对应搬入链，输出要经计算后的回写链到真实输出地址；仅出现HBF/DRAM/DTCM路径边不足以验收。任何其他写入若覆盖仍在消费的物理字节，或读引用已经被更新覆盖的旧版本，均拒绝；allocation/generation区分存储复用。

所有时间戳使用同一设备周期时基。guard_check须成功；rvv/zvt事件关联具体launch、core、PC和执行周期，不能用控制CPU或别的kernel指令充数。区域容量、权限、实际地址可达性和ELF装载仍须由TargetSpec/静态资源验证器与真实loader检查，轨迹结构校验不能替代这些硬件检查。

#### 错误、缓存和优化

负例status=error，diagnostic含code/stage/message。NC_ABI_VERSION、NC_ABI_CAPACITY、NC_INVALID_BUFFER、NC_READ_ONLY、NC_OWNER等是测试分类，适配器映射真实诊断。进入被测调用后，前置错误不得启动kernel/DMA或执行tensor访存；测试输入的预置初始化属于调用前准备。S7.dma-mid在成功搬运16B后注入错误，需dma_error/completed_bytes>0、真实停止确认及旧句柄失效/重启的恢复证据；部分输出不回滚。

S3.cache在同一会话依次执行三步，cache_hit=false/true/false，前两key相同第三不同；计时、原始缓存日志和代码身份对应。S9.overlap仍需单缓冲结果及周期对照、真实跨核DMA/计算重叠，并保持同核互斥；它不自动证明有加速，原始日志和资源生命周期仍需审查。

适配器是受信任的证据采集端；哈希和结构检查不能认证伪造文件。必须保留源码→IR→ELF→实际入口→原始设备轨迹的来源链。超时退出不等于核/DMA停止，确认停止或复位前不得复用资源。

### 支持能力与自动一致性检查

任务、阶段和语法白名单以 `plan.json` 为统一数据源，正文与 Excel 同步展示。每课概括、目标、测试与注意点记录于 `syntax_stages[].tutorial_checkpoints`。用例 ID 在各 `stage_cases/` 文件中维护，由 `suite.py` 汇总。修改测试范围或小阶段验收后运行下方检查。

```bash
"$CORAL_PYTHON" "$CORAL_TUTORIAL/check_plan.py" --workbook
```

默认 `testing.validated_capabilities` 为空。FP32、BF16、间接读写和排序按 `.basic.aot`、`.basic.jit` 分别记录，原子入门用例按 `atomic_add.single_program.aot` 或 `.jit` 记录。指定目标配置真实通过后登记。不同配置可通过 `--capabilities` 加载包含 `validated_capabilities` 的目标专用 JSON。

已登记模式自动进入--cumulative，包括G5后提前完成的S9类型分支。例如登记fp32.basic.aot后，S6累计回归会包含S9.fp32，不会错误加入尚未验证的BF16或FP32 JIT。--case只检查指定用例，不代表阶段累计出口通过；--include-optional用于主动尝试未验收项，不能自动登记支持。

### 从开始保留的约定

S0 仅约定 ABI 版本、逻辑 program/grid、设备地址、region/owner 的含义、当前可用核和权限边界。可先写入参数和简单元数据，不要求先做完整资源图、全局内存分配器或三套自定义方言。单核阶段使用同一套可扩展约定，多核阶段再落实完整调度和资源校验。

HBF 是 High Bandwidth Flash，计算平面只读；3D DRAM 承担存储。多层路径按实际可达性选择，DRAM 暂存显式表达，缓存策略单独定义。四核及现有容量属于当前原型实例，不能把未来 N 核的规划检查写成硬件执行成功。

### 方言与结构化主线的接入规则

- **S1/S2**：只实现有限 TTIR 子集的正确转换，用标准 LLVM/SCF 等表示，不先造 Coral 方言。
- **S4**：以新增的二维 stride、广播和循环语法为驱动，在 AOT/JIT 数值基线上接入最小 Ascend 版 TTS 和 Linalg。所核对版本的 TTS 包含 `get_structured_state`，用于传递指针结构分析的 offset/stride 等循环状态；具体移植范围以固定来源提交为准。[Ascend 版定义](https://github.com/triton-lang/triton-ascend/blob/main/third_party/ascend/include/Dialect/TritonStructured/IR/TritonStructuredDialect.td)
- **S4**：优先在 tensor 阶段保留结构，随后做需要的 Bufferization。自定义 tensor 操作如参与该过程，应提供相应接口/外部模型。[MLIR Bufferization](https://mlir.llvm.org/docs/Bufferization/)
- **迁移规则**：旧最小路径只作短期差分参考。已有 S1/S2/S3 用例在新主线通过后，停止扩张旧路径并移除冗余。
- **S5**：以 tl.sum/tl.max 和大 block 测试驱动正式 RVV lowering，只在结构化主线实现一次。G5 后类型扩展可独立推进。
- **S6/S7/S8**：分别在需要控制、搬运、目标 tile 语义时实现 `coral_rt`、`coral_mem`、`coral`。这些命名及操作是拟议设计，不代表仓库已经实现。

| 方言/模块 | 职责 | 何时接入 | 首批范围 | 约束 |
| --- | --- | --- | --- | --- |
| tt / TTIR | 前端逻辑 block、指针和计算 | S0 起使用 | S1 仅标量；S2 扩展有限 block 子集 | 首个闭环无需 TTS 或 Linalg |
| LLVM / Arith / CF / SCF | 最小代码生成、算术和必要循环 | S1 起使用 | TTIR 子集直接到 LLVM，必要时过标准循环 | RV32 data layout 与固定宽度整数正确 |
| tts（Ascend 版） | 结构化指针状态和循环携带信息 | G3 通过后接入 | 二维 stride/广播与循环指针状态所需的最小分析/转换 | 需固定来源并适配 LLVM 24；最终消除占位状态 |
| linalg / tensor | 结构化逐元素、归约和矩阵计算 | G3 通过后接入 | S4 二维逐元素/广播；S5 归约；S8 矩阵 | 保持结构做优化，既有 AOT/JIT 回归不退步 |
| bufferization / memref | buffer、alias、容量与生命周期 | 结构化计算接通后 | 所需接口/外部模型，标准 memref 布局 | 不能将 mask、owner 或生命周期丢失 |
| vector / RVV lowering | 目标宽度、mask、重排及归约 | G4 通过后实现 | tl.sum/tl.max、大 block、strip mining 与目标合法化 | 逻辑 BLOCK 与 VLEN 分开，检查实际机器指令 |
| coral_rt | 控制 CPU 的启动与多核任务依赖 | G5 通过后实现 | launch、dispatch、join 等拟议接口 | 核内与控制作用域分开；软件事件非全局隐式 barrier |
| coral_mem | 带归属的存储、局部布局和搬运 | G6 通过后实现 | region/view、copy_async、wait 等拟议接口 | HBF 只读、DTCM owner、路径、容量和可见性需验证 |
| coral | Zvt 等目标独有的 tile 计算 | 需要 tile 目标语义时实现 | tile_mma 等拟议接口 | 形状、类型、状态和效果合法；普通算术复用标准方言 |
| HFusion / HIVM / HACC / Transform | 参考分层、结构化接口与调度方式 | 按后续实际需求选择 | 只借鉴适合 Coral 的职责和机制 | 不为第一个闭环引入整套 Ascend 编译与运行依赖 |

### 多核与多级存储的实施边界

| 对象 | 必须保留的约定 | 何时实现 | 当前原型 | 验证要求 |
| --- | --- | --- | --- | --- |
| 最小 ABI | 版本、参数布局、设备地址、逻辑 ID/grid | S0 约定；S1 执行；S3 通用化 | 当前v2 68B/3 binding/4 scalar；规划v3 128B/8 binding/12 scalar | G1只用v2；S3-02必须交付v3，S8六scalar以v3执行。版本/size/count及越界一致检查 |
| 核拓扑 | 物理核数、可用掩码、逻辑 grid 分开 | S0 记录；S6 实现完整 placement | 当前物理 4 核，可启用子集 | 实际 1/2/4 核子集执行；未来 N 核先静态检查 |
| 共享全局地址 | region、合法范围、预留区与权限 | S0 约定；S1/S2 实际使用 | 共享 SRAM 16 KiB；trace 区预留 | 真实指针及保护区受检，不把宿主地址当设备地址 |
| 每核 ITCM/DTCM | 所属核、加载段、参数、栈和 scratch | S1 最小容量检查；S6/S7 扩展 | 当前每核 ITCM 8 KiB（.text 末 256B NOP 填充）、DTCM 32 KiB（前 256B 参数、中 0x6f00 数据、顶 4 KiB 栈） | 私有区逐核分配，容量/存活区不重叠；控制 LLVM 循环展开避免 ITCM 溢出 |
| HBF | 只读来源、有效范围、合法访问路径 | S0 记录约束；S7 实现搬运 | 窗口 [0x80000000,0xc0000000) | 拒绝计算平面的写入；窗口大小不等同实际物理容量 |
| 3D DRAM | 读写、容量、布局和生命周期 | S0 记录约束；S7 使用 | 窗口 [0x60000000,0x70000000) | 只承担存储；staging 显式，缓存策略另行设计 |
| 分片及局部副本 | 全局 tensor、分片范围、局部 owner | S2 保持逻辑索引；S6/S7 落实 | 先共享地址，再显式局部化 | 不重复添加 program 偏移，禁止错误共享私有存储 |
| 访问可达性 | CPU、核、DMA 到各 region 的合法路径 | S0 记录当前使用路径；S7 校验全图 | 当前 AXI 与 host 窗口 | 每项 copy 都有路径，不假设任意两层可互拷 |
| DMA 资源 | 通道、粒度、对齐、并发和互斥 | S7 实现；S9 优化 | 当前单通道、4B 对齐、单 outstanding beat | 不超发；不能靠扩大拷贝范围处理不合法尾部 |
| 任务与可见性 | 启动、生产者完成、消费者可见和失败 | S1 基本完成；S6/S7 完整依赖 | 当前无一致性缓存；DMA 等待最终成功写响应 | 版本生产者可见完成早于消费者；回写晚于计算，旧副本/过早复用拒绝；失败保留部分输出，恢复后再复用 |
| 队列与事件 | 槽位、fan-in、generation 与引用回收 | S6 完整实现 | 32 任务槽、64 事件、最多 2 直接前驱 | 长 grid 窗口式提交，失败不被伪报成功 |
| LLVM 地址与类型 | 物理映射和 LLVM address space 分开 | S1 确立；S4/S7 持续保留 | RV32、小端；TTIR 使用固定宽度整数 | index 降低匹配 data layout；不能静默截断或任意赋空间编号 |
| 缓存身份 | SDK/补丁、ABI、生成器与影响代码的布局 | S3 基础缓存；S6/S7 扩展计划标识 | kernel 与 Launch Plan 可分开缓存 | 拓扑变化重规划；代码相关布局变化重新编译 |
| 重叠与双缓冲 | 端口、buffer 生命周期与资源锁 | S9，正确单缓冲通过后 | 当前同核 DMA/kernel 互斥 | 先跨核重叠，放宽同核互斥需新的硬件/资源证明 |
| 性能证据 | 设备周期和宿主仿真时间分别记录 | S1 留证；S9 分项分析 | 外部存储模型使用合成延迟与背压 | 模型结果不宣称真实器件频率、带宽或峰值吞吐 |

### Triton 兼容目标与芯片支持边界

固定 Triton commit 的通用计算子集，按操作、dtype、布局和目标能力逐项扩展；不承诺全部 Python、厂商汇编或所有高级接口兼容。

按固定版本的 `triton.language` 导出维护覆盖账本。每个操作及代表性 dtype、rank、布局和同步作用域登记为待测、原生、合法展开或明确诊断。原生和展开都需独立参考及标准调用执行证据。对当前芯片无法实现的语义记录具体限制和诊断用例。按类别补齐以下项目，代表用例通过后再接入相应的上游 `python/test` 用例。

| 语法族 | 最少验证的扩展边界 |
| --- | --- |
| 整数、浮点与数学 | signed/unsigned 提升、转换、i64 数据、比较/位运算、除法；NaN/Inf/负零、舍入、溢出和数学函数误差。 |
| 张量构造、形状与寻址 | broadcast、reshape/trans、join/split、cat、gather、合法 scatter；正负 stride、尾块、别名与地址窗口。 |
| 循环与函数调用 | constexpr、静态展开、动态循环、分支、嵌套 JIT helper、不同迭代结果与循环携带值。 |
| 集合操作与随机数 | min/max/sum、带 combine 的 reduce/scan、sort/topk、histogram；随机算子按固定种子测确定性和分布约束。 |
| 矩阵、块指针与 descriptor | dot dtype/累加、精度、K 尾块、dot_scaled；固定版本支持的块指针/descriptor 检查 stride、边界、padding 和错误形状。 |
| 原子与同步 | 原子更新及旧值、CAS、竞争下的结果集合、acquire/release 和 scope；核内 barrier、跨 program 进展分别验证。 |
| 诊断、提示与目标扩展 | `static_assert` 的编译诊断、`device_assert` 的运行时报告、hint 前置条件和 RISC-V 汇编约束。单独记录其他目标绑定的接口。 |
| Python host 接口 | grid callable、constexpr cache、autotune/heuristics、stream 和设备集成，根据固定版本逐项启用。 |

S9 的 `atomic_add` 正例只测一个 program 的旧值和更新值。扩展 GPU scope 前，新增多核共享计数和不依赖执行顺序的旧值集合检查，再验证跨核可见性与内存序。descriptor 及其设备 API 在同一能力项中一起验收。语言族清单参考 [Triton language API](https://triton-lang.org/main/python-api/triton.language.html)，IR 测试命令参考 [LLVM lit](https://llvm.org/docs/CommandGuide/lit.html) 和 [FileCheck](https://llvm.org/docs/CommandGuide/FileCheck.html)。

硬件配置、编译通过、设备执行正确和性能达标分开记录。此矩阵为适配判断，不能替代自动生成 kernel 的执行证据。

| 能力 | 当前判断 | 实现与验收要求 | 对应任务 | 编译执行状态 |
| --- | --- | --- | --- | --- |
| 控制流与 constexpr | 原则上可支持 | 由固定前端产生合法 IR，循环/分支 lowering 保持语义与资源限制。 | S1-01,S2-01,S4-03,S9-03 | 未端到端验收 |
| grid 与逻辑 program | 可通过运行时实现 | 一个 program 初期放在一个核；逻辑 ID 独立于物理核号，多维 grid 后续扩展。 | S2-03,S6-01,S6-04 | 未端到端验收 |
| 形状、广播与重排 | 可通过转换实现 | 逻辑 tensor 分段映射到循环、RVV 和临时空间，BLOCK 不等于 VLEN。 | S2-01,S4-04,S5-01 | 未端到端验收 |
| 整数与宽位运算 | 先实现 INT32 子集 | 明确 signedness/模运算；i64 可合法展开，但不同于 64 位设备寻址。 | S1-01,S9-03 | 未端到端验收 |
| masked load/store | 可支持，必须保护真实访存 | 覆盖 other、尾部、非对齐和别名，mask 为假不触发访存。 | S2-02,S2-04,S7-02 | 未端到端验收 |
| 非规则 gather/scatter | 需逐项实现 | 寄存器 gather 不能证明任意地址向量访存；合法地址可按能力标量展开。 | S4-02,S9-03 | 未实现或未验收 |
| 归约、scan、sort、topk | 可通过算法实现 | 先验收整数归约，再分别实现扫描/排序/选择，检查临时空间与数值规则。 | S5-02,S9-03 | 未端到端验收 |
| FP32 与 BF16 | 多核配置已有硬件基础 | 检查转换、运算覆盖、特殊值、舍入和误差；不能用配置开关代替生成代码验收。 | S0-01,S5-03,S9-03 | 仅确认配置启用 |
| FP16/FP64/FP8 等格式 | 不能统一承诺 | 逐格式确定原生、软件展开或拒绝，类型转换和计算分别验证。 | S9-03 | 未逐格式验收 |
| dot 与 dot_scaled | 按类型及模式逐项支持 | 先落实 min_dot_size；输入、累加、精度、布局和 K 分块分别核对，INT8 不外推其他类型。 | S8-01,S8-04,S9-03 | 未端到端验收 |
| atomic 操作 | 完整链路尚未核实 | 不可分割读改写、旧值、内存序、作用域和全访问路径验证；不能以事件依赖替代。 | S6-02,S9-03 | 未建立完整支持证据 |
| barrier 与协作调度 | 必须区分同步范围 | 核内同步不是全 grid barrier；跨 program 轮询和协作内核另定义可见性及进展条件。 | S6-02,S6-04,S9-03 | 未验收协作能力 |
| tensor descriptor | 需要独立 lowering | 保留 shape/stride/padding/边界和对齐；选择普通访存或 DMA，不假设存在 NVIDIA TMA。 | S7-02,S9-03 | 尚未实现 |
| 内联汇编与厂商接口 | 存在目标相关边界 | Coral 汇编需匹配 RISC-V；PTX 和 CUDA 专用接口需改写、独立实现或明确拒绝。 | S0-03,S9-03 | 未声明直接兼容 |
| JIT 与设备运行时 | 需完整实现并独立验收 | 加载、分配、串行 stream、缓存、计时、错误和调试按范围建设，Torch 集成另列需求。 | S3-01,S3-04,S9-01 | 当前后端为骨架 |

#### 映射、存储与扩展原则

1. 一个 program 初期由一个核完整执行，多个 program 分配给多个核。program 内以循环/RVV 分段处理逻辑 tensor，后续再按需要研究 program 内跨核协作。
2. HBF 为只读来源，3D DRAM 承担全局工作数据，SRAM/DTCM 承担局部 tile。副本维护全局别名身份、写回和失效规则，完成事件说明具体消费者的可见性。
3. 原子操作须有覆盖相关访问路径的实现和内存模型。DMA 队列、软件事件、普通 AXI 仲裁及核内 barrier 均不自动提供跨核原子性。
4. 大容量 HBF/DRAM 不自动扩展 RV32 指针范围。窗口与物理容量分开，超窗口采用明确的分块/映射协议或报错，不能截断地址。
5. TTS/Linalg 和 Coral 自定义方言承载计算、存储、搬运与依赖语义，实际能力仍由 ISA、内存系统和运行时实现。保留 G1 的最小整数闭环，不把高级兼容项加入其前置。
6. G5 要求 sum/max 经 RVV 执行，以及 argmax 和整数前缀扫描通过数值验收。G5 后可独立推进 FP32/BF16 等扩展。GPU scope 原子还依赖共享内存和同步契约。

#### 固定基线的源码位置

核查日期为 2026-11-18。以下源码位置均相对 compiler-1 的 /home/compiler-1/work/coral 对应仓库，配合提交哈希定位。

| 核查项 | 仓库 | 分支 | 提交 | 源码位置 | 结论与边界 |
| --- | --- | --- | --- | --- | --- |
| 编译器执行链 | triton-coral | dev/triton-coral | 4f045a9d77 | third_party/coral/backend/compiler.py:86-96 | make_llir 返回输入文本，make_elf 返回占位字节，尚无真实 ELF 闭环证据。 |
| 浮点配置 | coralnpu | dev/ncoral-hbf-3dpim | f9ab975c | experiments/multicore/Cluster.scala:77-81 | enableFloat/enableZfbfmin 为 true，向量 BF16 随 RVV 启用；不是 Triton 执行验收。 |
| 存储锁请求 | coralnpu | dev/ncoral-hbf-3dpim | f9ab975c | experiments/multicore/die/Storage.scala:40 | 请求合法性要求 !a.lock.asBool；此路径拒绝锁请求，不能据此推断其他路径已支持完整原子。 |

#### 官方语义依据

原子操作含内存序和同步作用域，见 [atomic_add](https://triton-lang.org/main/python-api/generated/triton.language.atomic_add.html)。[debug_barrier](https://triton-lang.org/main/python-api/generated/triton.language.debug_barrier.html) 同步 block 内线程，不是全 grid barrier。

[dot](https://triton-lang.org/main/python-api/generated/triton.language.dot.html) 的类型、累加和精度选项分别验收。[类型提升规则](https://triton-lang.org/main/python-api/triton-semantics.html) 也属于数值契约。

[tensor descriptor](https://triton-lang.org/main/python-api/generated/triton.language.make_tensor_descriptor.html) 需保留布局和边界；NVIDIA TMA 是特定目标实现。[内联汇编](https://triton-lang.org/main/python-api/generated/triton.language.inline_asm_elementwise.html) 必须匹配目标汇编格式。

### 实施前需固定的细节

保留 S0～S9 主线与 42 个任务 ID，按语法增量调整任务范围。S9-03 改为仅依赖 S5-03 的独立类型分支；下列后续阶段细节不加入 G1 前置。

| 编号 | 需要补充的内容 | 明确要求 | 验证方式 | 对应任务 |
| --- | --- | --- | --- | --- |
| D01 | 参数与调用 ABI | RV32/ILP32、小端、字段偏移/宽度/对齐、16B 栈对齐、保留区和协议版本形成一张明确布局表。 | 固件与 wrapper 对同一参数样本解码一致，拒绝版本/范围错误。 | S0-02,S1-02 |
| D02 | ELF 与装载 | 静态链接；约定段地址字段、检查文件/内存范围、加法溢出、入口、BSS、段权限和 ISA 属性；未解析运行库 helper 明确失败。 | 损坏、截断、重叠、越界、入口错误及未支持指令均有诊断。 | S1-03,S1-04 |
| D03 | 整数与 mask 语义 | INT32 模运算和 signed/unsigned 扩展清楚；不能擅加 LLVM 溢出承诺；other 未定义时不要求其无效 lane 为零。 | 全假/混合mask、stride padding禁读写及O0/O2参考；逻辑访存与物理DMA分别验证。 | S1-01,S2-02,S2-04 |
| D04 | 别名与标量化 | 保留 block tensor SSA 的 load/compute/store 次序；不相交、精确原地和部分重叠区分处理。部分重叠不等于普遍非法 Triton。 | 合法原地结果正确，部分重叠按已声明策略保持语义或诊断，不能静默误算。 | S2-01,S4-05 |
| D05 | 启动与完成身份 | 提交序号、完成序号、核与镜像身份关联；旧完成清理和代码装载后的取指可见性按真实硬件确认。 | 连续切换代码、输入及核时不串扰；旧完成和过期句柄不会完成新调用。 | S1-05,S6-03 |
| D06 | JIT 运行协议与计时 | 明确零 grid、串行 stream、buffer 生命期和冷启动桥的行为；区分编译/装载/启动开销与设备 kernel 周期。 | 重复调用、零工作、异步误用/失效对象和缓存配置变化有结果或清晰诊断。 | S3-01,S3-02,S9-01 |
| D07 | TTS 迁移收敛 | S4 先做来源固定和小规模兼容试验；列明移植范围与停止条件，保留正确基线，覆盖现有支持项后统一主线。 | 前端可达 IR 与 S1/S2/S3 原有回归通过，不引入 G1 的高级依赖。 | S4-01,S4-06 |
| D08 | 故障、部分输出与恢复 | DMA 失败可能留下部分输出；超时不等于停止。定义等待/复位范围、幂等重试条件和失效对象。 | 中途错误、依赖失败、超时与恢复后重启；停止确认前禁止复用旧资源。 | S7-03,S7-05 |
| D09 | Zvt 布局和数值 | 从合法前端 dot 出发，检查 signedness、累加规则、pack/transpose 与本地 tile 布局，分别度量转换开销。 | 每种支持布局逐项数值和指令验证；不把其他 dtype 自动视为通过。 | S8-01,S8-04 |
| D10 | 支持范围与证据 | 每阶段记录操作/类型/布局/能力白名单；编译、静态资源检查和执行证据分开，错误包含阶段、位置及相关配置。 | 输入、TTIR、LLVM、ELF、镜像、目标配置和结果可对应；不支持项有明确错误。 | S0-03,S1-06 |
| D11 | program 到核的映射 | 一个 program 初期完整放在一个核，逻辑 tensor 在核内分段执行；多个 program 通过调度分配到可用核。核内 barrier 与跨 program 依赖分开。 | 单核顺序与多核执行一致；grid 大于核数、BLOCK 大于 VLEN 均正确。 | S2-03,S6-02,S6-04 |
| D12 | 浮点及数学语义 | 浮点/BF16 配置启用只作硬件基础。按 dtype 和操作验证类型提升、转换、舍入、NaN/Inf/非正规数/正负零、FMA 与归约误差。 | 按固定版本和精度约定比较独立参考；软件展开与原生路径分别记录，未验收格式明确拒绝。 | S0-01,S5-03,S9-03 |
| D13 | 原子与调度进展 | 设备原子须覆盖相关核和访问路径的不可分割读改写、返回值、内存序与作用域；队列事件和 AXI 仲裁不构成原子证明。跨 program 轮询另定义进展条件。 | 并发冲突更新、CAS/旧值、发布订阅及支持的轮询场景通过；不支持作用域或数据类型显式诊断。 | S6-02,S6-04,S9-03 |
| D14 | 局部副本与可见性 | 保留 DRAM 全局 buffer 和 SRAM/DTCM 副本的别名身份、读写集合、owner、写回和失效规则；完成事件明确表示目标消费者可观察数据。 | 正例与输入DMA晚于计算、回写早于计算、无版本、陈旧副本、错误owner/回写及早复用反例。 | S7-02,S7-03,S7-05 |
| D15 | 大容量和地址窗口 | 区分物理容量、32 位映射窗口、设备指针与 i64 数据计算。窗口切换若引入，需规定映射版本、指针有效期和在途任务互斥。 | 地址加法溢出和跨窗口访问有诊断或已验证分块；旧指针不得静默指向新窗口。 | S0-02,S7-01 |
| D16 | 高级接口与运行时边界 | descriptor 独立降低到合法访存/DMA，保持 shape/stride/padding；内联汇编匹配 RISC-V 目标。厂商专用接口和完整 Torch 设备适配不自动计入通用支持。 | descriptor 的边界/布局/对齐及错误输入逐项验证；不支持的 PTX/接口明确诊断，JIT/计时/调试分别留证。 | S3-01,S3-04,S9-03 |

整数 lowering 需保持源语义，LLVM 的溢出标记不能凭猜测添加。[LLVM LangRef](https://llvm.org/docs/LangRef.html#add-instruction)

首版选择标准 RV32/ILP32 调用边界，显式记录参数和栈约定；具体工具链及目标能力仍须核对，引用开发中的文档不等于自动支持其所有 ABI 变体。[RISC-V psABI](https://riscv-non-isa.github.io/riscv-elf-psabi-doc/)

### 分阶段支持的 Triton 语法与方言白名单

本表与 `plan.json` 同步。S1 从标量拷贝和常量加法开始，[标量课](backend-skeleton.md)给出实现顺序。S4 扩展布局和控制流，S5 加入整数归约和扫描。

| 阶段 | 支持的Triton语法/语义 | 对应IR/执行 | 方言与接口策略 | 明确边界 |
| --- | --- | --- | --- | --- |
| 骨架 | @triton.jit 的标量拷贝，仅 TTIR/占位产物 | tt.func / tt.load / tt.store / tt.return | 原生 tt；不新增方言 | 真实 ELF/执行仍待实现 |
| S0-03 | scalar_copy、scalar_add 的前端检查 | tt + arith.constant/addi | 补齐正式 CoralOptions；不新增方言 | block/mask、浮点、原子 |
| S1-01a | empty_kernel(X,Y): pass；指针在 ASTSource.signature 中声明 | tt.func / !tt.ptr<i32> / tt.return → LLVM 方言 → RV32 LLVM IR | 标准 LLVM；编译检查模式 ir | load/store/算术尚不进入这个微步 |
| S1-01b | 单元素 INT32 无 mask 拷贝 | tt.load/store → llvm.load/store | 标准 LLVM；运行接口保证4B对齐 | tensor指针、带mask访存、其他dtype |
| S1-01c | INT32 常量加法、constexpr 与回绕 | arith.constant/addi → LLVM IR | 标准算术转换；内部CFG按需降低 | 其他源算术、动态分支逐项扩展；不擅加nsw/nuw |
| S1-02～06 | 同一标量子集的真实 AOT | LLVM IR → 静态 ELF → core0 | 入口/链接/装载，v2足够 | JIT、block、RVV、DMA、多核 |
| S2 | arange、mask/other、where、constexpr if、双输入向量加法 | tt.make_range/addptr/broadcast + arith → scf/cf/LLVM | 正确标量循环；不新增方言 | 任意gather/scatter、浮点、原子 |
| S3 | 标准`kernel[grid](...)`、缓存与v3六运行参数 | 同S2 + driver/launcher/参数codec | 运行接口，v3为本阶段必需交付 | 完整Torch设备适配；超v3容量明确拒绝 |
| S4 | 二维 stride/广播、reshape/transpose、动态 for/while/if | tt → 最小tts分析 + Linalg/Tensor/SCF → Bufferization | 选择性移植Ascend tts，复用标准方言 | tl.sum/tl.max留S5，dot留S8 |
| S5 | sum/max/argmax、cumsum、跨 VLEN 的逻辑 block | Linalg/Vector → RVV | 不新增普通算术方言 | 未验证VLEN和浮点模式 |
| S6 | 一维至三维 program_id/num_programs | coral_rt → 控制CPU任务/事件 | 新增所需控制语义 | 隐式全grid barrier/未声明协作进展 |
| S7 | 同一源码在HBF/DRAM/DTCM显式局部化 | coral_mem → copy/wait与版本依赖 | 新增存储/搬运语义 | HBF写、未证明复用及同核DMA/kernel并发 |
| S8 | INT8 dot、v3六运行参数、矩阵分块 | tt.dot → Linalg → coral tile → Zvt | 新增目标tile语义；保护矩阵状态 | 非法形状、把INT8外推其他dtype/dot_scaled |
| S9-03 | 按能力ID独立扩展类型与算子 | 复用已有方言，新增语义单独定义 | 分别验收AOT/JIT，登记已通过模式 | 未验证能力不进入支持承诺 |

## 分阶段任务明细

这里保留 42 项实施任务及其稳定 ID。任务进度查看任务表，骨架与前端证据见[实测基线](#实测基线)。

### S0 任务明细

出口 **G0**。固定构建可发现 Coral，正式选项可生成拷贝及加法 TTIR，未知目标有诊断。

只做前端及接口基线；不要求 ELF 执行、TTS 或完整资源图。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S0-01 | 确认固定工具链与构建 | 固定 Triton commit、Coral SDK/LLVM 补丁、MLIR 头库和 RISC-V target；确认后端发现、软链接/entry_points 与 TRITON_DEFAULT_BACKEND=coral。记录实际浮点/BF16/RVV/Zvt 配置，只启用当前闭环能力。 | 无 | 可复现的版本和构建记录 | 版本、补丁、目标配置及插件发现可复现，不误回退到 NVIDIA；浮点/BF16 配置不算对应 kernel 已通过；不要求 TTS 编译成功。 |
| S0-02 | 约定最小参数与地址接口 | 首版确定 RV32/ILP32、小端、v2 参数块（0x00010000、bindings[3]/scalars[4]、done 为完成标志地址）各字段 offset/width/alignment、16B 栈对齐和区域边界。只实现 core0 所需最小接口，逻辑 ID 与物理核分开。 | S0-01 | 一页最小 ABI 及地址说明 | 编译器、入口和控制固件共享明确字节布局；明确 v2 槽位上限与版本扩展方式，不从宿主 void* 或结构体大小推断设备 ABI，版本或越界不匹配应拒绝。 |
| S0-03 | 建立首批源程序与诊断入口 | 用 scalar_copy、scalar_add 和 empty_kernel 固定 TTIR 样例。用 --backend-options 验证正式 CoralOptions，划定支持白名单，补未知目标诊断并检查用例清单。 | S0-02 | 可重复的源程序与构建入口 | 拷贝及加法使用正式选项生成合法 TTIR，空函数可单独生成。未知目标明确拒绝。check_plan.py 通过，前端和设备证据分别记录。 |

建议代码位置：

- **S0-01**：cmake/llvm-info.json；Coral CMake。
- **S0-02**：device/task_abi.h；runtime 适配设计。
- **S0-03**：本主题 examples；Coral 测试/debug 入口。

### S1 任务明细

出口 **G1**。标量 load/store、INT32 算术与 constexpr 由真实源码生成 ELF，在 core0 执行正确。

grid=1、共享 SRAM；标准 LLVM 方言，不引入 TTS/RVV/DMA。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S1-01 | 实现最小 TTIR 到 LLVM 转换 | 先构建 TritonCoralToLLVM 组件并验证 LLVM 方言，再接 make_llir 生成 RV32 LLVM IR。之后在同一组件加 i32 load/store、常量与 addi。源级动态分支留 S4。 | S0-03 | 由真实 TTIR 生成的 LLVM IR | 空函数 LLVM 方言 checkpoint/verifier 与标量 LLVM IR 均合法；G1 源白名单仅拷贝、常量加法和回绕。O0/O2 与无 UB 参考一致，不擅加 nsw/nuw；更多算术逐项加测试。 |
| S1-02 | 实现 kernel 入口包装 | 入口按 v2 参数框架（a0=0x00010000）校验 abi/size、设置 16B 对齐栈（sp=0x00018000）、读取设备参数、调用生成函数，并在返回前执行 fence rw,rw 后向 args->done 指向地址写 1。控制 CPU 与 Coral kernel 的 ISA 配置分开。 | S1-01,S0-02 | 可裸机执行的入口与参数绑定 | 参数、栈、完成标志和 DTCM 预留区不重叠；非法配置不启动，共享写结果对控制 CPU 可见后再发布完成标志。 |
| S1-03 | 生成真实静态 RISC-V ELF | 首版明确调用固定 SDK 的 clang/ld.lld 编译 LLVM IR 并链接入口和脚本（保留 .text 末 256B FILL(0x13000000) 预取 NOP 填充及 0x00010100/0x6f00 DATA 布局）。记录 target、ABI、features 和未解析符号。 | S1-02 | ELF、符号/段信息及最小元数据 | ELF32/小端/RISC-V、ISA 属性、ABI、入口、NOP 预取填充和 PT_LOAD 正确；初期静态链接，未解析 helper、动态重定位或未支持指令必须诊断。 |
| S1-04 | 建立 AOT 镜像打包 | 宿主按加载段打包，显式约定 p_vaddr/p_paddr 的使用；检查文件范围、filesz<=memsz、地址加法溢出、段权限、对齐、重叠和 BSS 零填充。 | S1-03 | 来源可追踪的启动镜像与 manifest | 损坏/截断 ELF、越界或重叠加载段、区域不匹配及入口不在合法代码区均被拒绝；保存 ELF 与加载段哈希。 |
| S1-05 | 接通真实 core0 执行 | 控制 CPU 装载、初始化参数/完成状态并启动 core0。定义每次提交的序号和完成匹配；依据实际核能力确认代码装载后的取指可见性。 | S1-04 | 真实 AOT 执行入口 | 连续运行不同代码和输入正确；旧完成标志不能使新调用提前结束，trap/超时有诊断，未确认停止的核不能被直接复用。 |
| S1-06 | 验收第一个端到端 | 运行 S1 拷贝、不同 constexpr、INT32 回绕及同会话换代码用例；非法 ABI 在启动前拒绝。对每个结果检查独立参考、保护区和真实执行证据。 | S1-05 | G1 单核闭环报告 | S1 全部用例通过；TTIR、LLVM、真实 ELF、加载镜像、配置和输出可追踪；旧完成或旧代码不能使新调用误通过。 |

建议代码位置：

- **S1-01**：Coral 的 `include/TritonCoralToLLVM/` 定义接口，`lib/TritonCoralToLLVM/` 实现转换。由 `triton_coral.cc` 绑定，`backend/compiler.py` 接入 `make_llir`。
- **S1-02**：`third_party/coral/backend/runtime/start.S`，链接进 kernel 的入口包装。
- **S1-03**：`third_party/coral/backend/compiler.py` 和 `backend/runtime/link.ld`，生成静态 RV32 ELF。
- **S1-04**：AOT 打包工具；控制固件生成器。
- **S1-05**：控制固件；仿真执行桥。
- **S1-06**：AOT 数值回归与报告。

### S2 任务明细

出口 **G2**。三指针标准向量加法、arange、广播、where、constexpr 分支、mask 和顺序 grid 正确。

先正确标量化；不强制引入新自定义方言或非规则 gather/scatter。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S2-01 | 支持 block 与基本张量操作 | 将有限 block 子集正确降低为 scf.for 标量循环（并控制 LLVM 循环展开因子以防 8 KiB ITCM 溢出），保持 tensor SSA 的加载、计算、写回顺序；仅在证明无依赖时融合循环，不按元素交错执行改变别名语义。 | S1-06 | 基本 block 语义 | 先支持不相交 buffer 和已验证的原地计算并满足 ITCM 8 KiB 约束；部分重叠访问须保持源语义或明确诊断，不能把标量循环结果错误归因于 Triton。 |
| S2-02 | 实现真正受保护的 masked 访存 | mask 控制实际 load/store，保留 other 和尾部语义。对无法支持的访问明确拒绝，不扩大访存范围。 | S2-01 | mask 与边界转换 | 全假 mask 不访存，other 显式给值时精确保持；未给 other 的无定义 lane 不能擅自当零或参与有效输出，尾部和保护区受检。 |
| S2-03 | 支持逻辑 program 与顺序 grid | 将 program_id/num_programs 读取到 ABI，先支持 1D grid，由 core0 顺序执行多个 program。一个 program 先由一个核完整执行，逻辑 tensor 在核内分段处理。 | S2-02 | 多 program 单核启动 | grid 大于物理核数仍正确；核号不替代逻辑 ID，参数更新与前次执行完成有序。后续多核复用此映射，不以物理 VLEN 限制逻辑 BLOCK。 |
| S2-04 | 验收基本 Triton 程序 | 运行 S2 的长度 0/1/3/37/128/1000、BLOCK=16/64、constexpr 分支、原地、显式 other 与非法 BLOCK 用例；按实际共享区容量分配。 | S2-03 | G2 语义回归报告 | S0～S2 累计回归通过；全假 mask 不访问输入输出，other 保持定义，尾部和原地正确；BLOCK=3 明确诊断。N=0 的 grid=1 与 S3 零 grid 分开。同时执行 S2.vector-add 的双输入三指针与 37 元素尾块。 |

建议代码位置：

- **S2-01**：沿用 Coral lowering；基础转换模式。
- **S2-02**：基础访存转换及测试。
- **S2-03**：kernel 参数；控制 runtime。
- **S2-04**：源程序、pytest 与 RTL 回归。

### S3 任务明细

出口 **G3**。标准 JIT/缓存和设备 buffer 正确；v3 六运行参数 AOT/JIT 通过，v2 超容量明确拒绝。

零 grid 可以不编译/不启动；完整 Torch 设备适配不在首版范围。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S3-01 | 实现真实 driver 和 launcher 接口 | 按本地 CompiledKernel 实际调用链补齐启动、设备/串行 stream 及装载接口。明确激活 Coral，移除无条件激活和伪零计时。 | S2-04 | 能够执行的 driver | 通过 jit_entry.launch 调用实际 `kernel[grid](...)`，Coral driver 选择及返回 CompiledKernel 的 ELF 与执行 ELF 哈希相符。AOT 不能冒充 JIT；零 grid 不启动，计时包含完成等待并分清冷启动。 |
| S3-02 | 提供设备 buffer 与显式拷贝 | 实现设备 buffer/别名 view 与显式拷贝；保留 v2（68B、3 binding/4 scalar），必须实现 v3（128B、8 binding/12 个32位 scalar）及编译器 wrapper/控制固件一致解析。v3 六参数正例和 v2 超槽位负例属于 G3，不依赖 DMA/多核。 | S3-01 | 设备 buffer 接口与参数布局 | S3.abi-v3 的 AOT/JIT 六运行参数均正确，v2 容量错误在启动前拒绝；头/size/count/空槽/地址/32位溢出校验通过。资源确认完成或恢复前不释放复用，宿主/失效指针不能启动。 |
| S3-03 | 接通 JIT 调用与缓存 | 支持 `kernel[grid](...)` 的常量/运行参数。复用已有 AOT 仿真桥也可形成首版 JIT；缓存绑定 LLVM、补丁、ABI、代码生成及目标配置。 | S3-02 | 可调用的 JIT 及正确缓存 | 相同配置可命中，配置变化能失效；源码和输入变化产生正确结果。冷启动开销如实记录。 |
| S3-04 | 验收标准 JIT 闭环 | 运行 S3.cache 的同会话三次调用：同常量换输入命中缓存，换 DELTA 重新特化；另测零 grid、失效 buffer、错误与真实计时。 | S3-03 | G3 JIT 验收报告 | S0～S3 累计通过，S1/S2 正例有实际 JIT 镜像用例；标准调用记录、ELF、cache key/hit 与运行结果对应。v3 六参数通过，零 grid 不启动，失效对象不发任务。 |

建议代码位置：

- **S3-01**：backend/driver.py；launcher。
- **S3-02**：runtime buffer API；仿真桥。
- **S3-03**：backend/compiler.py；driver；metadata。
- **S3-04**：JIT/运行时回归。

### S4 任务明细

出口 **G4**。二维 stride、广播、reshape/transpose、运行时 for/while/if 在结构化主线执行正确。

语法用例驱动 Ascend TTS/Linalg 的最小移植；不设置只有方言注册、没有新语法的验收阶段。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S4-01 | 为二维与循环语法接入 Ascend TTS | 先读取 strided_bias/loop_sum 的真实 TTIR，再固定 Ascend TTS 来源并试验最小指针分析/结构状态移植。适配 LLVM 24、接口和授权；以这些源程序定义移植边界。 | S3-04 | 可构建的 Ascend TTS 子集 | parse/print/verifier 和最小 pass 通过；二维/循环源程序能进入所选分析路径，不能仅用手写不可达 IR 宣布 TTS 接入完成。 |
| S4-02 | 实现规则指针结构分析 | 围绕 strided_bias 支持二维 rows[:,None]/cols[None,:]、SX/SY stride、行内广播和尾部 mask。保留全局 buffer 身份，未知布局 fallback 或诊断。 | S4-01 | 结构化访问结果 | 5×7 数据在 SX=11/SY=9 布局上结果正确，padding 不改写；源 TTIR 到结构化访问的索引映射可检查。 |
| S4-03 | 处理循环携带结构状态 | 围绕 loop_sum 和 scalar_while 实现运行时 for/while/标量 if、循环携带指针及合流。按需要使用 Ascend get_structured_state 与 SCF，区分 index 和固定宽度整数。 | S4-02 | 可验证的循环地址转换 | R=0/1/3、FLAG=0/1 均正确；循环前后和回边地址状态一致，没有静默截断；最终 TTS 占位状态消除。 |
| S4-04 | 接入 Linalg/Tensor 计算 | 把二维逐元素、广播、选择和循环计算映射到 Linalg/Tensor/SCF，保持 mask 和有效索引。S4 不新增 tl.sum；tl.sum/tl.max 明确由 S5 引入，矩阵由 S8 引入。 | S4-03 | 结构化计算 IR | strided_bias 的结构化计算与索引/初值/signedness 正确，for/while/标量 if 使用 SCF。S4 新语法在 AOT 和标准 JIT 两种模式均通过。S4.transpose 覆盖 reshape 与 2×4 到 4×2 重排，并断言展平后的顺序。 |
| S4-05 | 完成优化、Bufferization 与 LLVM 降低 | 先做必要 tensor 变换，再 Bufferization 或使用已选 buffer 语义路径。处理 alias、容量、生命周期、index/data layout 和合法性。 | S4-04 | 可生成 ELF 的结构化流水线 | 无错误复用和容量越界，接口模型齐全，最终没有无法导出 LLVM 的 tt/tts/linalg 残留。 |
| S4-06 | 迁移并统一主流水线 | 以 S4 新增二维/循环源程序和 S0～S3 既有用例统一结构化主线。迁移期做新旧差分，覆盖一致后停止扩张旧标量路径并移除冗余。 | S4-05 | G4 结构化主线报告 | S4 新语法及 S0～S3 累计 AOT/JIT 回归通过；Bufferization 与最终合法性检查通过。新增语法不能只用 AOT 验收；停止扩张旧路径并收敛主线。 |

建议代码位置：

- **S4-01**：Dialect/TritonStructured；适配记录。
- **S4-02**：Analysis/PtrAnalysis；TritonToStructured。
- **S4-03**：TritonToStructured；SCF 模式。
- **S4-04**：Conversion/TritonToLinalg。
- **S4-05**：Pipelines；Bufferization；标准 LLVM 转换。
- **S4-06**：backend stages；lit/pytest/RTL 回归。

### S5 任务明细

出口 **G5**。sum/max 产生实际执行的 RVV 指令。argmax 并列与整数前缀扫描算对。

整数归约为必需出口；FP32/BF16 在 G5 后可独立推进 S9-03，不必等多核/DMA/Zvt 或双缓冲。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S5-01 | 实现目标宽度向量化 | 在结构化主线对 Linalg/Vector 做 strip mining 和合法化，并在入口开启 mstatus.VS（0x600）。BLOCK 与目标 VLEN 分开，处理 VL、mask、对齐与尾部，同时限制循环展开防 8 KiB ITCM 溢出。 | S4-06 | 真实 RVV kernel | 反汇编存在 RVV 运算及所需配置指令；大 BLOCK 仍正确，不能仅靠 LLVM IR 中的 vector 类型验收。 |
| S5-02 | 实现核内整数向量归约 | 实现整数 tl.sum/tl.max 的 RVV lowering，保持初值、扩展、signedness 和尾部。再实现 argmax 并列规则和整数前缀扫描。 | S5-01,S4-04 | 核内归约实现 | sum/max 在长度 1/3/37/1000 与参考一致，含真实 RVV 反汇编和执行轨迹。argmax 并列与 INT32_MIN、cumsum 尾块通过 AOT/JIT 数值断言。 |
| S5-03 | 验收单核 RVV 主线 | 比较标量参考与 RVV 结果，记录实际指令、资源、数值、AOT/JIT 和错误回归。 | S5-02 | G5 RVV 报告 | S0～S5 累计 AOT/JIT、BLOCK>VLEN、尾部、数值、指令及资源检查通过；VLEN=128 仅为当前配置。G5 后可独立推进 S9-03，已验收类型按能力/模式清单进入累计回归。 |

建议代码位置：

- **S5-01**：Transforms/Vectorize；LLVM lowering。
- **S5-02**：归约与 RVV 转换。
- **S5-03**：单核 RVV 回归。

### S6 任务明细

出口 **G6**。program_id/num_programs 覆盖 1/2/4 核二维 grid 及四核三维 grid。

同步/调度语义引入 coral_rt；一个 program 初期仍由一个核完整执行。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S6-01 | 实现参数化可用核配置 | 将早期接口约定落实为目标配置和 placement 校验。区分物理核数、可用掩码、逻辑 grid 与 region 访问权限。 | S5-03 | 可配置的多核目标 | 当前实际 1/2/4 核子集可选，不能向不存在的核发任务；未来 N 核只能先做静态规划校验。 |
| S6-02 | 实现 coral_rt 控制方言与计划 | 这时才建立 launch/dispatch/join 等必要自定义控制语义，并降低到控制 CPU 的任务/事件调用；沿用早期 manifest 的版本化约定。 | S6-01 | 多核 Launch Plan | 核内代码与控制计划作用域清楚；逻辑任务、placement、失败与完成事件可验证。事件依赖不替代原子操作，核内 barrier 不解释为跨 program 全局 barrier。 |
| S6-03 | 实现调度、参数隔离和有界队列 | 先让各核访问共享全局数据。每核独立参数和 scratch；按现有 32 任务、64 事件及最多两个直接前驱推进和回收。 | S6-02 | 共享地址上的并发启动 | 长 grid 不耗尽事件；每核镜像身份、参数、scratch 与提交序号独立；换 kernel 等待核空闲及装载可见，旧完成不能误完成新任务。 |
| S6-04 | 验收多核语义 | 用 grid_ids 源程序测二维 program_id/num_programs、1×1/5×13 grid、core mask=1/3/15；比对顺序执行与真实 1/2/4 核，测试长 grid、隔离和失败。 | S6-03 | G6 多核报告 | S6 用例及已支持语法累计通过；每个三轴逻辑 ID 恰好执行一次，核心受可用掩码约束。无隐式全 grid barrier，未实现协作进展不作承诺。加入 3×5×5 的标准三维 grid，在四核上验证 75 个逻辑 program。 |

建议代码位置：

- **S6-01**：TargetSpec；runtime 配置。
- **S6-02**：Dialect/CoralRT；Runtime lowering。
- **S6-03**：控制固件 scheduler；队列适配。
- **S6-04**：多核数值及调度回归。

### S7 任务明细

出口 **G7**。同一 block 源码经显式 HBF/DRAM/DTCM 搬运在单核及多核正确执行。

引入 coral_mem；DMA 是后端计划，不增加伪造的 tl.dma 语法。先单缓冲，保持同核互斥。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S7-01 | 实现 coral_mem 与区域资源模型 | 落实 HBF、DRAM、共享 SRAM、各核 DTCM/ITCM 的 owner、容量、权限、对齐和可达路径。新增真正需要的存储/view/copy 语义。 | S6-04 | 显式分层 buffer 与搬运契约 | 拒绝 HBF 写、非法 owner、容量超限和不存在的路径。32 位映射窗口与物理容量、设备指针宽度分别记录；超窗口显式分块或诊断，禁止静默截断。 |
| S7-02 | 生成 tile 访问范围与局部布局 | 分析连续范围、stride、mask、对齐、alias 和生命周期，分配局部副本并改写 tile 内索引，保留全局 tensor 身份。 | S7-01,S4-02 | 静态内存和访问计划 | 参数/栈/scratch/数据不重叠；保留全局别名身份与局部 owner。逻辑访存按 program、读写方向、mask/stride 校验，padding 不得被逻辑读写；物理 DMA padding 搬运单独证明合法。 |
| S7-03 | 降低 DMA、依赖与完成可见性 | 按实际4B对齐、单通道、同核互斥约束降低 DMA。协议2用 view/分配generation/数据version/生产者关联 copy 和 kernel，end 定义为消费者可见完成；异常记录部分输出并传播失败。 | S7-02,S6-03 | 可执行的搬运与计算计划 | 拒绝输入copy晚于消费、回写早于计算、无生产者版本、陈旧副本、未结束消费者上的复用、错误owner和单通道超发；回写必须到真实输出区。失败不回滚，重试须证明幂等或重新初始化。 |
| S7-04 | 先验证一核多层搬运 | 先执行 HBF 到 DRAM 再到核内 DTCM、计算、DRAM 回写的显式单缓冲路径。共享 SRAM 仅按需要参与，其他路径以后按能力选择。 | S7-03 | 一核多层存储报告 | HBF 零写入，DRAM 只存储；staging、局部计算及回写逐项正确，容量/边界/权限错误可诊断。 |
| S7-05 | 再验证多核多层搬运 | 复用 block_add 执行 S7 的单/多核分层路径；注入 HBF 写、owner 错误与部分 DMA 失败，检查停止、恢复、句柄失效和重新启动。 | S7-04,S6-04 | G7 分层存储报告 | S7 正例、负例和累计回归通过；部分输出不回滚，停止前不复用资源，恢复证据含旧句柄失效及重启成功。错误码为测试协议，需在适配器中映射真实诊断。 |

建议代码位置：

- **S7-01**：Dialect/CoralMem；region 规划。
- **S7-02**：AccessRange；PromoteToLocal；MemoryPlan。
- **S7-03**：CoralMemToRuntime；DMA 适配。
- **S7-04**：一核分层运行用例。
- **S7-05**：多核分层回归。

### S8 任务明细

出口 **G8**。合法 INT8 dot 源码完成形状契约、矩阵 lowering、tile 方言和真实 Zvt 执行。

先实现 min_dot_size 回调；教程 INT8 下界不是已实现硬件能力。dot_scaled/其他 dtype 分别验收。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S8-01 | 接入合法 dot 与矩阵语义 | 以 G3 已完成的 ABI v3 承载 M/N/K/SA/SB/SC 六个运行参数。补齐真实 min_dot_size 与精度选项，再将 INT8 16×16×32 源转换到矩阵/tile；硬件 K 子块与前端形状分开。 | S5-03,S4-04 | 前端可达的矩阵 IR | 无需教程提议回调即可生成合法 dot TTIR；AOT/JIT 均使用 v3，S8.reject-v2 在启动前拒绝。未支持类型/形状有诊断，不外推 dot_scaled 或其他 dtype。 |
| S8-02 | 实现 coral tile 计算方言 | 此时引入 coral.tile_mma 等确有目标语义的操作。首版可在 buffer 阶段匹配合法 tile；若前移到 tensor 阶段则补齐所需接口模型。 | S8-01 | 有 verifier 的 tile 操作 | 形状、布局、输入与累加类型、tile 状态及内存效果明确，不重复定义普通算术。 |
| S8-03 | 降低到已验证 Zvt 接口 | 核对固定 SDK/RTL 的 intrinsic/微内核与 mstatus 矩阵使能（当前接口记录0x60000000），处理装载、tile状态、累加和输出；保护 Zvt 状态活跃区间，避免 vsetvli 重置 mtype/altfmt。微内核与内联路径分别记录。 | S8-02 | 真实 Zvt 目标代码 | 实际指令与所属 launch 的轨迹对应；状态/副作用不被优化器删除、重排或被 vsetvli 重置。使能位和状态行为以固定 SDK/RTL 验证，不能套用其他版本 ISA。 |
| S8-04 | 验收矩阵执行 | 运行 S8 的 16×16×32 与 17×19×35、padding/尾部/1及4核矩阵用例。先 M/N 分块，跨核 K 归约以后另设计。 | S8-03,S7-05 | G8 Zvt 报告 | S8 数值、宽位参考、pack/transpose、实际 Zvt 指令和执行轨迹通过；padding 不改写，布局开销计入；INT8 不代表其他类型通过。 |

建议代码位置：

- **S8-01**：TritonToLinalg；矩阵合法化。
- **S8-02**：Dialect/Coral；LinalgToCoral。
- **S8-03**：CoralToLLVM；Zvt 封装。
- **S8-04**：矩阵数值/指令回归。

### S9 任务明细

出口 **G9**。可选语法按能力独立验收，重叠版本保持结果正确，性能报告记录实际周期。

新增类型不以性能优化为前置；有限浮点样例不代表完整浮点、数学库、原子或 descriptor 支持。

| ID | 任务 | 实现内容 | 技术前置 | 交付物 | 通过标准 |
| --- | --- | --- | --- | --- | --- |
| S9-01 | 建立可解释的性能基线 | 分别记录编译、启动、kernel、DMA、争用及控制周期和宿主仿真耗时。关联目标配置、源码、固件和二进制。 | S7-05 | 分项性能基线 | 报告编译、打包、仿真启动、装载、kernel 与回传的边界，按真实时间基准比较；模型周期和宿主耗时分开，不以虚构或未归一化计时宣称吞吐。 |
| S9-02 | 逐步实现重叠和双缓冲 | 先重叠不同核的搬运/计算；只有端口、buffer 不相交和生命周期有证明时，才放宽同核互斥或增加预取/双缓冲。 | S9-01 | 有证据的流水线优化 | 不覆盖仍在消费的 buffer，不超发 DMA；每次优化同时给出正确性和周期证据。 |
| S9-03 | 按需求扩展算子与类型 | G5 后按需求独立扩展类型/语法，先用 S9.fp32 与 S9.bf16 测有限加法和 BF16 读取扩宽，再补特殊值/舍入/数学函数、scan/sort、非规则访存、融合/卷积、原子及 descriptor。每项单独建用例。 | S5-03 | 逐项语法/类型支持报告（独立于性能出口） | 每个语法/类型能力分别按AOT/JIT、目标配置和精度验收，记录 validated_capabilities；通过的可选模式自动进入后续累计回归，未验证模式保持排除。有限样例不外推完整浮点/数学/原子能力，禁止宿主代算。先运行已有间接读写、排序和单 program 原子用例。GPU scope 并发与内存序须独立验收。 |

建议代码位置：

- **S9-01**：profiling；回归报告。
- **S9-02**：资源调度；生命周期；队列锁粒度。
- **S9-03**：Linalg 扩展；Coral 转换；数值测试。

## 统一验收与推进规则

1. 每个阶段都有实际可观察的出口；编译、数值、资源和异常结果分别记录。未通过本阶段验收，不为追求方言数量而扩张范围。
2. G1 验证 AOT，G3 验证标准 JIT；G5 再验证实际 RVV。每个“通过”都对应真实执行或明确标注的静态检查。
3. 首版以 INT32 及必要的 i1 mask 为主要支持范围。i64、浮点、原子、任意 gather/scatter 和完整 Torch 设备集成逐项定义与验收。
4. 部分多核或存储变化只需重新规划；影响 tile、布局或目标指令的变化需要重新生成 kernel，并更新缓存身份。
5. 记录源码、工具链/补丁、ABI、IR、ELF、控制镜像、配置和输出的来源关系。单个成功固定样例不能代替变化输入、尾部和失败用例。
6. 修改 Triton 编译器时遵守其仓库 `AGENTS.md` 与 `docs/coral-llvm.md`：修改 native/compiler 后，使用固定 Coral LLVM 24 构建目录运行 `make BUILD_DIR=... PYTHON=...`（需要更新 Python 扩展时按构建脚本同步 `python/triton/_C/libtriton.so`，勿裸跑无参 `make` 混用其他 SDK 目录），再执行相应 lit/pytest；仅 Python 修改按规则选择检查。pytest 使用 `-s --tb=short`。执行前核对仓库最新说明，IR 用例保持前端可达，优先扩展已有测试文件。
7. 核数、存储容量、DMA 并发和可见性按实际硬件能力验收；当前单通道与同核 DMA/kernel 互斥不能凭计划自行取消。
8. 不预设日历工期。每完成一个出口更新任务状态及下一阶段工作量；先把 G1 跑通，再估计后续迁移成本。

## 官方参考

- [Ascend 版 TTS 定义](https://github.com/triton-lang/triton-ascend/blob/main/third_party/ascend/include/Dialect/TritonStructured/IR/TritonStructuredDialect.td)
- [Ascend 编译链说明](https://github.com/triton-lang/triton-ascend/blob/main/docs/en/architecture_design_and_core_features.md)
- [AscendNPU-IR 架构](https://github.com/Ascend/AscendNPU-IR/blob/master/docs/source/en/introduction/architecture.md)
- [MLIR 到 LLVM](https://mlir.llvm.org/docs/TargetLLVMIR/)
- [MLIR Bufferization](https://mlir.llvm.org/docs/Bufferization/)
- [MLIR Linalg](https://mlir.llvm.org/docs/Dialects/Linalg/)

- [LLVM 整数语义](https://llvm.org/docs/LangRef.html#add-instruction)

- [RISC-V 调用及 ELF ABI](https://riscv-non-isa.github.io/riscv-elf-psabi-doc/)

- [Triton 语言接口](https://triton-lang.org/main/python-api/triton.language.html)

- [Triton 数值语义](https://triton-lang.org/main/python-api/triton-semantics.html)

- [Triton dot](https://triton-lang.org/main/python-api/generated/triton.language.dot.html)

- [Triton atomic_add](https://triton-lang.org/main/python-api/generated/triton.language.atomic_add.html)

- [Triton debug_barrier](https://triton-lang.org/main/python-api/generated/triton.language.debug_barrier.html)

- [Triton tensor descriptor](https://triton-lang.org/main/python-api/generated/triton.language.make_tensor_descriptor.html)

- [Triton inline assembly](https://triton-lang.org/main/python-api/generated/triton.language.inline_asm_elementwise.html)

- [Triton 向量加法教程](https://triton-lang.org/main/getting-started/tutorials/01-vector-add.html)

- [Triton load 与 mask](https://triton-lang.org/main/python-api/generated/triton.language.load.html)

- [Triton range](https://triton-lang.org/main/python-api/generated/triton.language.range.html)
