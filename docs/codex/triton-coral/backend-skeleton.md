# 第二课：从标量 TTIR 到单核 ELF

从已经搭好的 Coral 骨架开始。本课的目标是让 `scalar_copy` 经真实 LLVM IR 和 RV32 ELF 在 core0 上把 −37 写回。用共享 SRAM 和 v2 参数框架。完成这一课后再做 block、mask 和更多 program。开始前按[第一次运行](plan.md#第一次运行)设置环境变量。

```text
Triton 源码 → TTIR → LLVM 方言 → LLVM IR → RV32 ELF
  → AOT 镜像 → 控制 CPU 装载 → core0 执行 → 读回并比较
```

## 第一批：正式选项与空 kernel 接入编译流水线

**S0-03 → S1-01a**。用现有的 `empty_kernel(X, Y)` 从 `triton.compile()` 走到 `make_llir()`，生成可交给 RV32 工具链的 LLVM IR。本次支持公开的无返回值函数、全局 `*i32` 参数和 `tt.return`。用同一个编译入口检查 `scalar_copy` 的 `tt.load` 会被拒绝。

### 1. 需要修改的文件

以下路径以 Triton checkout 为起点。先完成 Python 中的 S0-03 两处修改，再按顺序接通 pass、构建、binding 和 stage。

| 文件 | 修改位置 |
| --- | --- |
| `third_party/coral/backend/compiler.py` | 在 `CoralOptions` 加字段，替换 `supports_target`，最后替换已有 `make_llir`。 |
| `third_party/coral/include/TritonCoralToLLVM.h` | 新增 pass factory 声明。 |
| `third_party/coral/lib/TritonCoralToLLVM.cpp` | 新增正式转换库的实现。后续标量访存和算术在这条流水线上扩展。 |
| `third_party/coral/CMakeLists.txt` | 在已有 Python build 条件中声明转换库和它的链接依赖。 |
| `third_party/coral/triton_coral.cc` | 保留 `hello()`，让 `coral.passes` 公开 pass factory。 |

### 2. 补齐正式前端选项

在 `backend/compiler.py` 的 `CoralOptions` 中，与 `debug` 对齐增加一个字段。Triton 生成整数加法时读取它。设备执行阶段用 `S1.wrap` 验证 I32 回绕。

```python
  sanitize_overflow: bool = False
```

同一文件中替换 `CoralBackend.supports_target`，让教程的 `coral-rv32` 和当前 driver 返回的 `rv32imf_zve32x` 都能选择 Coral。

```python
  @staticmethod
  def supports_target(target: GPUTarget) -> bool:
    return (
      target.backend == "coral"
      and target.arch in ("coral-rv32", "rv32imf_zve32x")
      and target.warp_size == 1
    )
```

### 3. 在原始 TTIR module 上实现转换 pass

新建 `include/TritonCoralToLLVM.h`，内容如下。

```cpp
#ifndef TRITON_CORAL_TO_LLVM_H
#define TRITON_CORAL_TO_LLVM_H

#include "mlir/Pass/Pass.h"
#include <memory>

namespace mlir::triton::coral {

std::unique_ptr<mlir::Pass> createConvertTritonCoralToLLVMPass();

} // namespace mlir::triton::coral

#endif // TRITON_CORAL_TO_LLVM_H
```

新建 `lib/TritonCoralToLLVM.cpp`。函数签名和入口参数复用 Triton GPU lowering 同样调用的 MLIR helper。

```cpp
#include "TritonCoralToLLVM.h"

#include "mlir/Conversion/FuncToLLVM/ConvertFuncToLLVM.h"
#include "mlir/Conversion/LLVMCommon/ConversionTarget.h"
#include "mlir/Conversion/LLVMCommon/LoweringOptions.h"
#include "mlir/Conversion/LLVMCommon/TypeConverter.h"
#include "mlir/Dialect/LLVMIR/LLVMDialect.h"
#include "mlir/IR/BuiltinOps.h"
#include "triton/Dialect/Triton/IR/Dialect.h"
#include "llvm/IR/DataLayout.h"

using namespace mlir;
namespace tt = mlir::triton;

namespace {

// This matches the locked Coral SDK for riscv32-unknown-elf, ILP32.
constexpr llvm::StringLiteral coralTriple = "riscv32-unknown-unknown-elf";
constexpr llvm::StringLiteral coralDataLayout = "e-m:e-p:32:32-i64:64-n32-S128";

struct FuncLowering : OpConversionPattern<tt::FuncOp> {
  using OpConversionPattern::OpConversionPattern;

  LogicalResult
  matchAndRewrite(tt::FuncOp op, OpAdaptor,
                  ConversionPatternRewriter &rewriter) const override {
    if (!op.isPublic() || op.isExternal() || !op.getResultTypes().empty())
      return rewriter.notifyMatchFailure(op, "expected a public void kernel");

    const auto &converter = *getTypeConverter<LLVMTypeConverter>();
    auto function = convertFuncOpToLLVMFuncOp(op, rewriter, converter);
    if (failed(function))
      return failure();

    rewriter.eraseOp(op);
    return success();
  }
};

struct ReturnLowering : OpConversionPattern<tt::ReturnOp> {
  using OpConversionPattern::OpConversionPattern;

  LogicalResult
  matchAndRewrite(tt::ReturnOp op, OpAdaptor adaptor,
                  ConversionPatternRewriter &rewriter) const override {
    if (!adaptor.getOperands().empty())
      return rewriter.notifyMatchFailure(op, "expected a void return");

    rewriter.replaceOpWithNewOp<LLVM::ReturnOp>(op, ValueRange{});
    return success();
  }
};

struct ConvertTritonCoralToLLVM
    : PassWrapper<ConvertTritonCoralToLLVM, OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(ConvertTritonCoralToLLVM)

  StringRef getArgument() const override {
    return "convert-triton-coral-to-llvm";
  }

  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<LLVM::LLVMDialect>();
  }

  void runOnOperation() override {
    MLIRContext &context = getContext();
    ModuleOp module = getOperation();
    LowerToLLVMOptions options(&context);
    options.dataLayout = llvm::DataLayout(coralDataLayout);
    LLVMTypeConverter converter(&context, options);
    converter.addConversion([](tt::PointerType type) -> std::optional<Type> {
      if (type.getAddressSpace() != tt::PtrAddrSpace::Global ||
          !type.getPointeeType().isInteger(32))
        return std::nullopt;
      return LLVM::LLVMPointerType::get(type.getContext());
    });

    LLVMConversionTarget target(context);
    target.addLegalOp<ModuleOp>();
    target.addIllegalDialect<tt::TritonDialect>();
    RewritePatternSet patterns(&context);
    patterns.add<FuncLowering, ReturnLowering>(converter, &context);

    if (failed(applyFullConversion(module, target, std::move(patterns)))) {
      signalPassFailure();
      return;
    }

    StringAttr triple = StringAttr::get(&context, coralTriple);
    StringAttr layout = StringAttr::get(&context, coralDataLayout);
    module->setAttr(LLVM::LLVMDialect::getTargetTripleAttrName(), triple);
    module->setAttr(LLVM::LLVMDialect::getDataLayoutAttrName(), layout);
  }
};

} // namespace

std::unique_ptr<mlir::Pass> tt::coral::createConvertTritonCoralToLLVMPass() {
  return std::make_unique<ConvertTritonCoralToLLVM>();
}
```

`convertFuncOpToLLVMFuncOp()` 按类型转换器重建签名并转移原函数的 region。原有函数体留在 module 中，`tt.return` 由单独的 pattern 改写。若还有 `tt.load` 等非法操作，`applyFullConversion()` 报出源位置并让 pass 失败。RV32 的全局设备指针在这个阶段用地址空间 0，data layout 指定 32 位指针和 16 字节栈对齐。[MLIR Dialect Conversion](https://mlir.llvm.org/docs/DialectConversion/) · [Triton 的函数转换](https://github.com/triton-lang/triton/blob/main/lib/Conversion/TritonGPUToLLVM/FuncOpToLLVM.cpp)

### 4. 接入已有构建和 Python binding

用下面的内容替换 `third_party/coral/CMakeLists.txt`。声明为 Triton 转换库后，pass 沿用仓库的 `-fno-exceptions -fno-rtti` 编译选项，和当前的 LLVM SDK 一致。Python 插件仍使用 nanobind。

```cmake
if(TRITON_BUILD_PYTHON_MODULE)
  add_triton_library(TritonCoralToLLVM
    lib/TritonCoralToLLVM.cpp
    LINK_LIBS
      TritonIR
      MLIRFuncToLLVM
      MLIRLLVMCommonConversion
      MLIRLLVMDialect
      MLIRTransforms
  )
  target_include_directories(TritonCoralToLLVM PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
  )

  add_triton_plugin(TritonCoral
    ${CMAKE_CURRENT_SOURCE_DIR}/triton_coral.cc
    LINK_LIBS TritonCoralToLLVM
  )
  target_link_libraries(TritonCoral PRIVATE Python3::Module nanobind-static)
endif()
```

在 `triton_coral.cc` 的 include 区增加下面两行。

```cpp
#include "TritonCoralToLLVM.h"
#include "mlir/Pass/PassManager.h"
```

在 `init_triton_coral` 的 `hello()` 注册后插入下面三行。这个 binding 把 C++ pass 加到调用方提供的 `PassManager`。

```cpp
  m.def_submodule("passes").def("add_to_llvmir", [](mlir::PassManager &pm) {
    pm.addPass(mlir::triton::coral::createConvertTritonCoralToLLVMPass());
  });
```

### 5. 替换已有的 make_llir

在 `backend/compiler.py` 替换同名方法。现有 `add_stages()` 已注册 `llir`，保留它。这里先通过 pass 将 TTIR 改写为 LLVM 方言，再复用 Triton 的 `llvm.to_module()` 导出 LLVM IR 文本。RV32 机器码验证使用同一 SDK 的 `llc`。

```python
  @staticmethod
  def make_llir(src, metadata, options):
    pm = ir.pass_manager(src.context)
    pm.enable_debug()
    coral.passes.add_to_llvmir(pm)
    pm.run(src, "coral_make_llir")

    context = llvm.context()
    return str(llvm.to_module(src, context))
```

### 6. 增量编译

在 WSL 使用已经配置好的 `build/coral-llvm24`。

```bash
cd ~/work/coral/triton-coral
set -e
export TRITON_BACKENDS_IN_TREE=1 TRITON_DEFAULT_BACKEND=coral
sdk="$HOME/work/coral/coralnpu-compiler/out/llvm-zvt/install"
build="$PWD/build/coral-llvm24"
export PATH="$sdk/bin:$PATH"

make BUILD_DIR="$build" PYTHON="$PWD/.venv/bin/python"
install -m 755 "$build/python-module/libtriton.so" python/triton/_C/libtriton.so.new
mv -T python/triton/_C/libtriton.so.new python/triton/_C/libtriton.so
```

### 7. 验证脚本

用现有 `@triton.jit` kernel、`ASTSource` 和正式的 `triton.compile()`。单独复跑同一个 pass 保存 LLVM 方言，便于对照两个 IR 层次。各步骤使用同一个临时输出目录，编译缓存也写到其中。

```bash
set -e
examples="${CORAL_TUTORIAL:-/mnt/c/Users/20327/Documents/ChatGPT/learn/kaishaoshao.github.io/docs/codex/triton-coral/examples}"
out=$(mktemp -d /tmp/coral-llir-XXXXXX)
export TRITON_CACHE_DIR="$out/cache" TRITON_STORE_BINARY_ONLY=0

.venv/bin/python "$examples/dump_ttir.py" --stage S1 --cumulative \
  --case S0.frontend --case S1.add --case S1.empty.frontend --case S1.copy \
  --backend-options --output "$out/frontend"

if ! PYTHONPATH="$examples${PYTHONPATH:+:$PYTHONPATH}" \
  .venv/bin/python - "$out" 2>"$out/diagnostics.log" <<'PY'
import sys
from pathlib import Path

import triton
from kernels.s1_scalar import empty_kernel, scalar_copy
from triton._C.libtriton import coral, ir
from triton.backends.compiler import GPUTarget
from triton.compiler.compiler import ASTSource, make_backend

out = Path(sys.argv[1])
target = GPUTarget("coral", "coral-rv32", 1)
signature = {"X": "*i32", "Y": "*i32"}
assert make_backend(GPUTarget("coral", "rv32imf_zve32x", 1)).target.warp_size == 1
try:
    make_backend(GPUTarget("coral", "coral-invalid", 1))
except RuntimeError as error:
    assert str(error).startswith("0 compatible backends"), error
    print("PASS: rejected coral-invalid")
else:
    raise AssertionError("unsupported Coral arch was accepted")

compiled = triton.compile(ASTSource(empty_kernel, signature), target=target)
assert compiled.metadata.name == "empty_kernel"
(out / "empty.ll").write_text(compiled.asm["llir"])
ttir = out / "empty.ttir"
ttir.write_text(compiled.asm["ttir"])

context = ir.context()
ir.load_dialects(context)
module = ir.parse_mlir_module(str(ttir), context)
pm = ir.pass_manager(context)
coral.passes.add_to_llvmir(pm)
pm.run(module, "check_coral_llvm_dialect")
assert module.verify()
(out / "empty.llvm.mlir").write_text(str(module))

try:
    triton.compile(ASTSource(scalar_copy, signature), target=target)
except RuntimeError as error:
    assert "PassManager::run failed" in str(error), error
else:
    raise AssertionError("tt.load was accepted before its lowering was added")
PY
then
  cat "$out/diagnostics.log" >&2
  exit 1
fi

"$build/bin/triton-opt" "$out/empty.llvm.mlir" -o /dev/null
"$sdk/bin/FileCheck" "$examples/ir_checks.txt" --check-prefix=EMPTYLLVM \
  --input-file="$out/empty.llvm.mlir"
"$sdk/bin/opt" -passes=verify -disable-output "$out/empty.ll"
"$sdk/bin/FileCheck" "$examples/ir_checks.txt" --check-prefix=EMPTYLLIR \
  --input-file="$out/empty.ll"
"$sdk/bin/FileCheck" "$examples/ir_checks.txt" --check-prefix=CORALUNSUPPORTED \
  --input-file="$out/diagnostics.log"
printf '%s\n' "PASS: scalar_copy rejected at tt.load"

"$sdk/bin/llc" -filetype=obj -mattr=+m,+f -target-abi=ilp32 \
  "$out/empty.ll" -o "$out/empty.o"
"$sdk/bin/llvm-readelf" -h "$out/empty.o"
"$sdk/bin/llvm-objdump" -d "$out/empty.o"
printf 'Artifacts: %s\n' "$out"
```

**预期结果**

1. 正式选项生成 5 份 TTIR，非法架构打印 `PASS: rejected coral-invalid`。
2. `empty.llvm.mlir` 包含 `llvm.func @empty_kernel` 和 `llvm.return`。`empty.ll` 的 target 为 RV32，包含两个 `ptr` 参数和 `ret void`，通过 `opt -passes=verify`。
3. 真正的 `triton.compile(scalar_copy)` 在 `make_llir` 失败。日志包含 `failed to legalize operation 'tt.load'`，脚本打印 `PASS: scalar_copy rejected at tt.load`。
4. `empty.o` 的 ELF 头显示 `ELF32`、`REL`、`RISC-V`，反汇编的 `empty_kernel` 有 `ret`。现有 `make_elf` 的占位字节会随完整调用写进临时缓存，这里验证的目标文件是 `llc` 生成的 `empty.o`。可装载的 ELF 和 core0 执行归第三批验收。

做完后发 `empty.ll`、`tt.load` 诊断和反汇编。通过后继续下一批。

## 第二批：标量访存与整数加法

先在同一个 Coral conversion pass 中用 `S1.copy` 处理无 mask 的 `tt.load/store`。只有运行接口保证 4 字节对齐时才给转换后的访存标注 4 字节对齐。再用 `S1.add` 转换 `arith.constant/addi`，复用第一批接好的 LLVM IR 导出。正式 lowering 检查点是 `make_llir` 产生的文本。

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
