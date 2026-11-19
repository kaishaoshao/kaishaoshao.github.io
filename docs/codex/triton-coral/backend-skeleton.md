# 第二课：从标量 TTIR 到单核 ELF

从已经搭好的 Coral 骨架开始。本课的目标是让 `scalar_copy` 经真实 LLVM IR 和 RV32 ELF 在 core0 上把 −37 写回。用共享 SRAM 和 v2 参数框架。完成这一课后再做 block、mask 和更多 program。开始前按[第一次运行](plan.md#第一次运行)设置环境变量。

```text
Triton 源码 → TTIR → LLVM 方言 → LLVM IR → RV32 ELF
  → AOT 镜像 → 控制 CPU 装载 → core0 执行 → 读回并比较
```

## 1. 用正式选项生成 TTIR

先用默认教程选项观察 `scalar_add`，然后用实际 `CoralBackend.parse_options` 再生成一次。

```bash
"$CORAL_PYTHON" "$CORAL_TUTORIAL/dump_ttir.py" --stage S1 --case S1.add \
  --output "$CORAL_TEST_OUT/add-tutorial"
"$CORAL_PYTHON" "$CORAL_TUTORIAL/dump_ttir.py" --stage S1 --case S1.add --backend-options \
  --output "$CORAL_TEST_OUT/add-backend"
```

在 `4f045a9d77`，第一条可以看到 `tt.load → arith.addi → tt.store`，第二条会因为 `CoralOptions` 缺少 `sanitize_overflow` 报错。先修改 `third_party/coral/backend/compiler.py` 的选项定义，使标量 I32 前端能读取所需字段。首版以 32 位模运算验证溢出回绕。未知 Coral 架构还需在实际目标入口拒绝，并通过 `S0.bad-target`。

**完成信号**  拷贝与加法都能用正式选项生成合法 TTIR，输出 `frontend.json` 的 `options` 为 `backend`。这是 S0-03 的源码检查点。

## 2. 先转换空函数

在 [s1_scalar.py](examples/kernels/s1_scalar.py) 找到 `empty_kernel`。`ASTSource.signature` 把 X、Y 声明为 `*i32`。先把 `tt.func`、`tt.return` 和这类标量指针签名转换为 `llvm.func`、`llvm.return` 和 `!llvm.ptr`。

```bash
"$CORAL_PYTHON" "$CORAL_TUTORIAL/dump_ttir.py" --stage S1 --case S1.empty.frontend \
  --output "$CORAL_TEST_OUT/empty"
"$CORAL_FILECHECK" "$CORAL_TUTORIAL/ir_checks.txt" --check-prefix=EMPTY \
  --input-file="$CORAL_TEST_OUT/empty/S1.empty.frontend.0.ttir"
```

实现并注册最小转换 pass 后，把同一个 `.ttir` 交给 `triton-opt`。建议将 pass 源文件接入 `third_party/coral/lib/Conversion`，在 native 工具注册中暴露选项。下面以拟议的选项名为例，先用 `--help` 核对你注册的实际名字。

```bash
"$CORAL_TRITON_OPT" --convert-coral-minimal-triton-to-llvm \
  "$CORAL_TEST_OUT/empty/S1.empty.frontend.0.ttir" -o "$CORAL_TEST_OUT/empty.llvm.mlir"
"$CORAL_FILECHECK" "$CORAL_TUTORIAL/ir_checks.txt" --check-prefix=EMPTYLLVM \
  --input-file="$CORAL_TEST_OUT/empty.llvm.mlir"
```

**完成信号**  verifier 接受 `llvm.func @empty_kernel`，参数是两个 `!llvm.ptr`，函数体有 `llvm.return`。接通转换适配器后运行 `S1.empty.llvm` 保存真实检查点。

## 3. 增加标量访存和加法

先用 `S1.copy` 处理无 mask 的 `tt.load/store`。只有运行接口保证 4 字节对齐时才给转换后的访存标注 4 字节对齐。再用 `S1.add` 转换 `arith.constant/addi`，通过标准 MLIR 转换导出 LLVM IR。正式 lowering 检查点是 `make_llir` 产生的文本。

| 在哪看 | 看什么 |
| --- | --- |
| `scalar_copy` 的 LLVM 方言 | 从输入指针加载 I32，向输出指针写回，同源函数签名一致。 |
| `scalar_add` 的 LLVM IR | 用实际 RV32 target triple、data layout 和 LLVM verifier，结果包含数据依赖的 I32 加法。 |
| `S1.wrap` | `INT32_MAX + 1` 应得到 `INT32_MIN`。没有确凿证明时保留模运算，避免加上 `nsw` 或 `nuw`。 |
| 转换负例 | 把超出本课白名单的 block/mask 提交给实际 pass，检查明确诊断。 |

**完成信号**  编译产物随输入源码改变，拷贝和加法各自通过 verifier。更复杂的张量、mask 和循环按 S2/S4 的用例逐项加入。

## 4. 链接并让 core0 执行

1. 用 v2 参数帧接入入口包装。核对两条设备指针、16 字节栈对齐及完成标志地址。参与编译的 `constexpr` 不占运行参数槽位。
2. 用固定 Coral SDK 的 `clang` 和 `ld.lld` 生成 ELF32 小端 RISC-V ELF。先用 SDK 的 `llvm-readelf -h -l` 检查入口和 `PT_LOAD`，再交给宿主打包器。
3. 由控制 CPU 装载并启动 core0。保存每次调用的完成身份，确认本次写回可见后读取结果。再用不同 ELF 和输入重复运行，验证取指及完成状态更新。

链接布局、ITCM 预取填充、`p_vaddr/p_paddr`、BSS 和 loader 负例见 [S1 任务明细](plan.md#s1-任务明细)。

## 5. 运行 G1 验收

把 `CORAL_ADAPTER` 设为实际适配器脚本的绝对路径。从单个拷贝开始，再跑累计用例。

```bash
: "${CORAL_ADAPTER:?先设置真实适配器的绝对路径}"
"$CORAL_PYTHON" "$CORAL_TUTORIAL/run_stage.py" --stage S1 --case S1.copy \
  --adapter "$CORAL_ADAPTER" --output "$CORAL_TEST_OUT/device"
"$CORAL_PYTHON" "$CORAL_TUTORIAL/run_stage.py" --stage S1 --cumulative \
  --adapter "$CORAL_ADAPTER" --output "$CORAL_TEST_OUT/regression"
```

**完成信号**  `S1.copy` 读回值为 −37，常量变化、回绕、换代码和坏 ABI 都由对应测试验收。报告里能沿 TTIR、LLVM、ELF、镜像和真实执行记录追到同一次运行。G1 通过后进入 [S2 的 mask 与向量加法](plan.md#s2-blockmask-与选择)。
