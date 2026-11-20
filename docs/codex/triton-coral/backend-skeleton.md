# 第二课：从标量 TTIR 到单核 ELF

从已经搭好的 Coral 骨架开始。本课的目标是让 `scalar_copy` 经真实 LLVM IR 和 RV32 ELF 在 core0 上把 −37 写回。用共享 SRAM 和 v2 参数框架。完成这一课后再做 block、mask 和更多 program。开始前按[第一次运行](plan.md#第一次运行)设置环境变量。

```text
Triton 源码 → TTIR → LLVM 方言 → LLVM IR → RV32 ELF
  → AOT 镜像 → 控制 CPU 装载 → core0 执行 → 读回并比较
```

## 第一批：正式选项与空函数 lowering

把 **S0-03 和 S1-01a** 一起做。目标是让正式 Coral 选项生成 TTIR，再把其中的空函数交给你新注册的转换 pass。最后检查生成的 LLVM 方言，并用含访存的合法 TTIR 验证转换确实拒绝越出当前范围的输入。

### 1. 补齐正式前端选项

在 Triton checkout 的 `third_party/coral/backend/compiler.py` 中，给现有 `CoralOptions` 加一个字段，与 `debug` 对齐。

```python
  sanitize_overflow: bool = False
```

Triton 的整数 `+` 会读取这个字段。固定骨架提交 `4f045a9d77` 的正式选项会在 `S1.add` 缺这个字段。关闭此处的溢出插桩后，设备执行阶段用 `S1.wrap` 验证 I32 回绕。

同一文件替换现有的 `supports_target`。教程的 `coral-rv32` 和当前 driver 返回的 `rv32imf_zve32x` 都要能选择 Coral。

```python
  @staticmethod
  def supports_target(target: GPUTarget) -> bool:
    return (
      target.backend == "coral"
      and target.arch in ("coral-rv32", "rv32imf_zve32x")
      and target.warp_size == 1
    )
```

### 2. 编写两个转换 pattern

新建 `third_party/coral/lib/Conversion/MinimalTritonToLLVM.cpp`。当前只接受单块、无结果的公开空函数。`TypeConverter` 把 Triton 全局 `*i32` 参数映射为这一步约定的 LLVM 默认地址空间指针，适用于首版平坦的 RV32 地址模型。LLVM 指针的位宽后续由目标 data layout 决定。

```cpp
// MinimalTritonToLLVM.cpp
#include "mlir/Dialect/LLVMIR/LLVMDialect.h"
#include "mlir/IR/BuiltinOps.h"
#include "mlir/Pass/Pass.h"
#include "mlir/Transforms/DialectConversion.h"
#include "triton/Dialect/Triton/IR/Dialect.h"
#include "llvm/ADT/STLExtras.h"

namespace {
using namespace mlir;
namespace tt = mlir::triton;

struct EmptyFuncLowering : OpConversionPattern<tt::FuncOp> {
  using OpConversionPattern::OpConversionPattern;

  LogicalResult matchAndRewrite(tt::FuncOp op, OpAdaptor,
                                ConversionPatternRewriter &rewriter) const override {
    if (!op.isPublic() || !llvm::hasSingleElement(op.getBody()) ||
        !op.getResultTypes().empty())
      return rewriter.notifyMatchFailure(op, "expected a public void function with one block");

    Block &body = op.getBody().front();
    if (!llvm::hasSingleElement(body) || !isa<tt::ReturnOp>(body.front()))
      return rewriter.notifyMatchFailure(op, "expected a body containing only tt.return");

    SmallVector<Type> params;
    if (failed(getTypeConverter()->convertTypes(op.getArgumentTypes(), params)))
      return rewriter.notifyMatchFailure(op, "expected global pointers to i32");

    auto type = LLVM::LLVMFunctionType::get(
        LLVM::LLVMVoidType::get(rewriter.getContext()), params);
    auto lowered = LLVM::LLVMFuncOp::create(rewriter, op.getLoc(), op.getSymName(), type);
    rewriter.inlineRegionBefore(op.getBody(), lowered.getBody(), lowered.getBody().end());
    if (failed(rewriter.convertRegionTypes(&lowered.getBody(), *getTypeConverter())))
      return rewriter.notifyMatchFailure(op, "could not convert entry arguments");
    rewriter.eraseOp(op);
    return success();
  }
};

struct VoidReturnLowering : OpConversionPattern<tt::ReturnOp> {
  using OpConversionPattern::OpConversionPattern;

  LogicalResult matchAndRewrite(tt::ReturnOp op, OpAdaptor adaptor,
                                ConversionPatternRewriter &rewriter) const override {
    if (!adaptor.getOperands().empty())
      return rewriter.notifyMatchFailure(op, "expected a void return");
    rewriter.replaceOpWithNewOp<LLVM::ReturnOp>(op, ValueRange{});
    return success();
  }
};

struct MinimalTritonToLLVM : PassWrapper<MinimalTritonToLLVM, OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(MinimalTritonToLLVM)

  StringRef getArgument() const override { return "convert-coral-minimal-triton-to-llvm"; }
  StringRef getDescription() const override { return "Lower empty Coral kernels to LLVM dialect"; }

  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<LLVM::LLVMDialect>();
  }

  void runOnOperation() override {
    MLIRContext *context = &getContext();
    TypeConverter converter;
    converter.addConversion([context](tt::PointerType ptr) -> Type {
      if (ptr.getAddressSpace() != tt::PtrAddrSpace::Global || !ptr.getPointeeType().isInteger(32))
        return {};
      return LLVM::LLVMPointerType::get(context);
    });

    RewritePatternSet patterns(context);
    patterns.add<EmptyFuncLowering, VoidReturnLowering>(converter, context);

    ConversionTarget target(*context);
    target.addLegalOp<ModuleOp>();
    target.addLegalDialect<LLVM::LLVMDialect>();
    target.addIllegalDialect<tt::TritonDialect>();
    if (failed(applyFullConversion(getOperation(), target, std::move(patterns))))
      signalPassFailure();
  }
};
} // namespace

namespace mlir::triton::coral {
void registerMinimalTritonToLLVMPass() {
  PassRegistration<MinimalTritonToLLVM>{};
}
} // namespace mlir::triton::coral
```

`tt.func` pattern 移动原有 region 并转换入口 block 参数，`tt.return` pattern 生成 `llvm.return`。函数定义和入口参数类型要同时转换。用真实 `S1.copy` 做负例，可以发现漏写 body 检查或把非法操作当成已转换的问题。

### 3. 接入 CMake 和 triton-opt

在 `third_party/coral/CMakeLists.txt` 中，放在现有 Python 插件的 `if(...)` 块之前。

```cmake
add_triton_library(CoralMinimalTritonToLLVM
  lib/Conversion/MinimalTritonToLLVM.cpp
  DEPENDS TritonTableGen
  LINK_LIBS PUBLIC TritonIR MLIRLLVMDialect MLIRPass MLIRTransforms
)
```

`bin/CMakeLists.txt` 已通过全局 `TRITON_LIBS` 收集 `add_triton_library` 的库。在 `add_executable(triton-opt triton-opt.cpp)` 后，给包含 Coral 的构建开启注册。

```cmake
if(TARGET CoralMinimalTritonToLLVM)
  target_compile_definitions(triton-opt PRIVATE TRITON_ENABLE_CORAL_LOWERING)
endif()
```

在 `bin/triton-opt.cpp` 中的 `main` 前加声明，并在 `main` 内 `registerTritonDialects(registry);` 之后调用。声明和调用使用同一个宏。

```cpp
// File scope, before main.
#ifdef TRITON_ENABLE_CORAL_LOWERING
namespace mlir::triton::coral {
void registerMinimalTritonToLLVMPass();
}
#endif
```

```cpp
  // Inside main, after registerTritonDialects(registry).
#ifdef TRITON_ENABLE_CORAL_LOWERING
  mlir::triton::coral::registerMinimalTritonToLLVMPass();
#endif
```

### 4. 用源码验证正例和负例

在 WSL 的 Triton checkout 根目录执行。下面给出本机样例目录的默认值，也可以沿用[第一次运行](plan.md#第一次运行)中设置的 `CORAL_TUTORIAL`。本机的构建目录是 `build/coral-llvm24`。

```bash
cd ~/work/coral/triton-coral
export TRITON_BACKENDS_IN_TREE=1 TRITON_DEFAULT_BACKEND=coral
CORAL_TUTORIAL="${CORAL_TUTORIAL:-/mnt/c/Users/20327/Documents/ChatGPT/learn/kaishaoshao.github.io/docs/codex/triton-coral/examples}"
sdk="$HOME/work/coral/coralnpu-compiler/out/llvm-zvt/install"
bin="$PWD/build/coral-llvm24/bin"
out=$(mktemp -d /tmp/coral-first-lowering-XXXXXX)

PATH="$sdk/bin:$PATH" make triton-opt BUILD_DIR="$PWD/build/coral-llvm24" \
  PYTHON="$PWD/.venv/bin/python"

.venv/bin/python "$CORAL_TUTORIAL/dump_ttir.py" --stage S1 --cumulative \
  --case S0.frontend --case S1.add --case S1.empty.frontend --case S1.copy \
  --backend-options --output "$out"

"$bin/triton-opt" --convert-coral-minimal-triton-to-llvm \
  "$out/S1.empty.frontend.0.ttir" -o "$out/empty.llvm.mlir"
"$sdk/bin/FileCheck" "$CORAL_TUTORIAL/ir_checks.txt" --check-prefix=EMPTYLLVM \
  --input-file="$out/empty.llvm.mlir"

if "$bin/triton-opt" --convert-coral-minimal-triton-to-llvm \
    "$out/S1.copy.0.ttir" -o "$out/copy.llvm.mlir" 2>"$out/copy.err"; then
  echo "FAIL: the empty-function pass accepted load/store" >&2
  false
fi
grep -F "failed to legalize operation" "$out/copy.err"
```

目标负例走真实的 backend 选择入口。

```bash
.venv/bin/python - <<'PY'
from triton.backends.compiler import GPUTarget
from triton.compiler.compiler import make_backend

for arch in ("coral-rv32", "rv32imf_zve32x"):
    assert make_backend(GPUTarget("coral", arch, 1)).target.arch == arch

try:
    make_backend(GPUTarget("coral", "coral-invalid", 1))
except RuntimeError as error:
    assert str(error).startswith("0 compatible backends")
    print("PASS: rejected coral-invalid")
else:
    raise AssertionError("coral-invalid was accepted")
PY
```

**交付证据**是正式选项生成的 5 份 TTIR、通过 `EMPTYLLVM` 的 `empty.llvm.mlir`、拷贝被拒绝的诊断，以及 `PASS: rejected coral-invalid`。到这里即可交这一批。`S1.empty.llvm` 的适配器模式留到适配器接通后复跑。

## 第二批：标量访存、整数加法与 LLVM IR 导出

先用 `S1.copy` 处理无 mask 的 `tt.load/store`。只有运行接口保证 4 字节对齐时才给转换后的访存标注 4 字节对齐。再用 `S1.add` 转换 `arith.constant/addi`，通过标准 MLIR 转换导出 LLVM IR。正式 lowering 检查点是 `make_llir` 产生的文本。

| 在哪看 | 看什么 |
| --- | --- |
| `scalar_copy` 的 LLVM 方言 | 从输入指针加载 I32，向输出指针写回，同源函数签名一致。 |
| `scalar_add` 的 LLVM IR | 用实际 RV32 target triple、data layout 和 LLVM verifier，结果包含数据依赖的 I32 加法。 |
| `S1.wrap` | `INT32_MAX + 1` 应得到 `INT32_MIN`。没有确凿证明时保留模运算，避免加上 `nsw` 或 `nuw`。 |
| 转换负例 | 把超出本课白名单的 block/mask 提交给实际 pass，检查明确诊断。 |

**完成信号**  编译产物随输入源码改变，拷贝和加法各自通过 verifier。更复杂的张量、mask 和循环按 S2/S4 的用例逐项加入。

## 第三批：链接、装载和 core0 执行

1. 用 v2 参数帧接入入口包装。核对两条设备指针、16 字节栈对齐及完成标志地址。参与编译的 `constexpr` 不占运行参数槽位。
2. 用固定 Coral SDK 的 `clang` 和 `ld.lld` 生成 ELF32 小端 RISC-V ELF。先用 SDK 的 `llvm-readelf -h -l` 检查入口和 `PT_LOAD`，再交给宿主打包器。
3. 由控制 CPU 装载并启动 core0。保存每次调用的完成身份，确认本次写回可见后读取结果。再用不同 ELF 和输入重复运行，验证取指及完成状态更新。

链接布局、ITCM 预取填充、`p_vaddr/p_paddr`、BSS 和 loader 负例见 [S1 任务明细](plan.md#s1-任务明细)。

## 运行 G1 验收

把 `CORAL_ADAPTER` 设为实际适配器脚本的绝对路径。从单个拷贝开始，再跑累计用例。

```bash
: "${CORAL_ADAPTER:?先设置真实适配器的绝对路径}"
"$CORAL_PYTHON" "$CORAL_TUTORIAL/run_stage.py" --stage S1 --case S1.copy \
  --adapter "$CORAL_ADAPTER" --output "$CORAL_TEST_OUT/device"
"$CORAL_PYTHON" "$CORAL_TUTORIAL/run_stage.py" --stage S1 --cumulative \
  --adapter "$CORAL_ADAPTER" --output "$CORAL_TEST_OUT/regression"
```

**完成信号**  `S1.copy` 读回值为 −37，常量变化、回绕、换代码和坏 ABI 都由对应测试验收。报告里能沿 TTIR、LLVM、ELF、镜像和真实执行记录追到同一次运行。G1 通过后进入 [S2 的 mask 与向量加法](plan.md#s2-blockmask-与选择)。
