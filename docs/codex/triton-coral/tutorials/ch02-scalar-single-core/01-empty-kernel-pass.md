# 2.1 节：空 kernel 的 LLVM 降级与编译接入

## 1. 这节课做什么

**S1-01a**。把已能生成 TTIR 的 `empty_kernel(X, Y)` 接到现有的 `CoralBackend.make_llir()`。函数签名、两个全局 `*i32` 参数和空返回走 `tt.func / tt.return → LLVM 方言 → RV32 LLVM IR`。做完后，`scalar_copy` 会在 `tt.load` 处报未合法化，2.2 节再实现访存。

先完成 [1.3 节的正式前端选项](../ch01-skeleton/03-frontend-options.md)。compiler-1 已有空的 `include/TritonCoralToLLVM/TritonCoralToLLVM.h` 和 `lib/TritonCoralToLLVM/TritonCoralToLLVM.cpp`，下面把代码写入这两个文件，再接通生成、构建和 binding。

## 2. 核心代码实现

### A. 构建原生转换库

先让转换独立通过，下一步再接入 `make_llir`。以下路径均相对于 `third_party/coral/`。

| 文件 | 改动 |
| --- | --- |
| `include/TritonCoralToLLVM/Passes.td` | 新建，声明 pass 名称和依赖方言。 |
| `include/TritonCoralToLLVM/TritonCoralToLLVM.h` | 新建，公开生成的 factory 声明。 |
| `include/TritonCoralToLLVM/CMakeLists.txt` | 新建，在 build 目录生成 `Passes.h.inc`。 |
| `lib/TritonCoralToLLVM/TritonCoralToLLVM.cpp` | 新建，负责类型转换、改写和合法性检查。 |
| `lib/TritonCoralToLLVM/CMakeLists.txt` | 新建，编译该转换库并声明依赖。 |
| `CMakeLists.txt`、`triton_coral.cc` | 修改现有文件，接通组件构建和 binding。 |

#### 声明和生成 pass

`include/TritonCoralToLLVM/Passes.td` 内容如下。

```tablegen
include "mlir/Pass/PassBase.td"

def ConvertTritonCoralToLLVM
    : Pass<"convert-triton-coral-to-llvm", "mlir::ModuleOp"> {
  let summary = "Convert scalar Coral TTIR to the LLVM dialect";
  let dependentDialects = ["mlir::LLVM::LLVMDialect"];
}
```

`include/TritonCoralToLLVM/TritonCoralToLLVM.h` 内容如下。

```cpp
#ifndef TRITON_CORAL_TO_LLVM_H
#define TRITON_CORAL_TO_LLVM_H

#include "mlir/Pass/Pass.h"

namespace mlir::triton::coral {

#define GEN_PASS_DECL
#include "TritonCoralToLLVM/Passes.h.inc"

} // namespace mlir::triton::coral

#endif // TRITON_CORAL_TO_LLVM_H
```

`include/TritonCoralToLLVM/CMakeLists.txt` 内容如下。

```cmake
set(LLVM_TARGET_DEFINITIONS Passes.td)
mlir_tablegen(Passes.h.inc -gen-pass-decls --name TritonCoralToLLVM)
add_public_tablegen_target(TritonCoralConversionPassIncGen)
```

#### 实现转换

把下面的代码放进 `lib/TritonCoralToLLVM/TritonCoralToLLVM.cpp`。

```cpp
#include "TritonCoralToLLVM/TritonCoralToLLVM.h"

#include "mlir/Conversion/FuncToLLVM/ConvertFuncToLLVM.h"
#include "mlir/Conversion/LLVMCommon/ConversionTarget.h"
#include "mlir/Conversion/LLVMCommon/LoweringOptions.h"
#include "mlir/Conversion/LLVMCommon/TypeConverter.h"
#include "mlir/Dialect/LLVMIR/LLVMDialect.h"
#include "mlir/IR/BuiltinOps.h"
#include "triton/Dialect/Triton/IR/Dialect.h"
#include "llvm/IR/DataLayout.h"

#include <optional>
#include <utility>

namespace mlir::triton::coral {

#define GEN_PASS_DEF_CONVERTTRITONCORALTOLLVM
#include "TritonCoralToLLVM/Passes.h.inc"

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
    : impl::ConvertTritonCoralToLLVMBase<ConvertTritonCoralToLLVM> {
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

} // namespace mlir::triton::coral
```

#### 接到 Coral 构建与绑定

`lib/TritonCoralToLLVM/CMakeLists.txt` 内容如下。`add_triton_library` 会按仓库的编译器库选项编译 pass，和当前 LLVM SDK 一样关闭 RTTI 和异常。

```cmake
add_triton_library(TritonCoralToLLVM
  TritonCoralToLLVM.cpp

  DEPENDS
    TritonCoralConversionPassIncGen

  LINK_LIBS
    TritonIR
    MLIRFuncToLLVM
    MLIRLLVMCommonConversion
    MLIRLLVMDialect
    MLIRTransforms
)
```

`third_party/coral/CMakeLists.txt` 整体替换为下面的内容。公开头与生成头分别来自源码和构建目录。

```cmake
if(TRITON_BUILD_PYTHON_MODULE)
  include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)
  include_directories(${CMAKE_CURRENT_BINARY_DIR}/include)
  add_subdirectory(include/TritonCoralToLLVM)
  add_subdirectory(lib/TritonCoralToLLVM)

  add_triton_plugin(TritonCoral
    ${CMAKE_CURRENT_SOURCE_DIR}/triton_coral.cc

    DEPENDS
      TritonCoralConversionPassIncGen

    LINK_LIBS
      TritonCoralToLLVM
  )
  target_link_libraries(TritonCoral PRIVATE Python3::Module nanobind-static)
endif()
```

在 `triton_coral.cc` 的 include 区添加下面两行。

```cpp
#include "TritonCoralToLLVM/TritonCoralToLLVM.h"
#include "mlir/Pass/PassManager.h"
```

在 `init_triton_coral` 末尾、`hello()` 注册之后插入下面三行。

```cpp
  m.def_submodule("passes").def("add_to_llvmir", [](mlir::PassManager &pm) {
    pm.addPass(mlir::triton::coral::createConvertTritonCoralToLLVM());
  });
```

### B. 接入 make_llir

先完成第 4 节的 **A. 验证原生转换**。看到正确的 LLVM 方言后，再回来改 Python。

只替换 `backend/compiler.py` 的 `make_llir`。现有 `add_stages()` 已注册 `llir`。编译阶段通过 pass 得到 LLVM 方言，再由 `llvm.to_module()` 导出 LLVM IR 文本。这一步复用第二步的构建。

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

## 3. 解释说明与注释

- `convertFuncOpToLLVMFuncOp()` 使用类型转换器转换函数签名，将原函数体转移到 `llvm.func`。`ReturnLowering` 只转换没有值的 `tt.return`。上下文中的其他操作仍由各自的 pattern 处理。[Triton 函数转换](https://github.com/triton-lang/triton/blob/main/lib/Conversion/TritonGPUToLLVM/FuncOpToLLVM.cpp)
- `applyFullConversion()` 检查完整 module。合法的 TTIR 如果出现当前阶段未支持的操作，pass 会失败并报告源位置。[MLIR Dialect Conversion](https://mlir.llvm.org/docs/DialectConversion/)
- `add_triton_library` 沿用 LLVM SDK 的编译设置关闭 RTTI 和异常。`triton_coral.cc` 只暴露添加 pass 的接口。TableGen 负责生成 factory 声明和 pass 基类，生成头位于构建目录。[MLIR Pass Infrastructure](https://mlir.llvm.org/docs/PassManagement/#declarative-pass-specification)
- 全局设备指针暂时映射到地址空间 0。模块上的 RV32 triple 和 ILP32 data layout 决定指针位宽与 ABI，后续链接与运行入口继续使用同一目标设置。

## 4. 测试与验证代码

### A. 验证原生转换

在 compiler-1 用已配置的 LLVM 24 构建目录。下面的 shell 变量也会用于下一段测试。编译前可按 [1.1 节](../ch01-skeleton/01-toolchain-discovery.md) 确认当前 Python 能加载后端。

```bash
set -e
cd /home/compiler-1/work/coral/triton-coral
export TRITON_BACKENDS_IN_TREE=1 TRITON_DEFAULT_BACKEND=coral
sdk=/home/compiler-1/work/coral/coralnpu-compiler/out/llvm-zvt/install
validation=/home/compiler-1/work/coral/coralnpu-compiler/out/llvm-zvt/triton-main-validation
build="$validation/build"
examples="${CORAL_TUTORIAL:-/home/compiler-1/learn/kaishaoshao.github.io/docs/codex/triton-coral/examples}"
out=$(mktemp -d /tmp/coral-empty-kernel-XXXXXX)
export PATH="/home/compiler-1/work/riscv-llvm-musl-toolchain/.bootstrap/bin:$sdk/bin:$PATH"

make BUILD_DIR="$build" PYTHON="$PWD/.venv/bin/python"
install -m 755 "$validation/python-module/libtriton.so" python/triton/_C/libtriton.so.new
mv -T python/triton/_C/libtriton.so.new python/triton/_C/libtriton.so

.venv/bin/python "$examples/dump_ttir.py" --stage S1 --case S1.empty.frontend \
  --backend-options --output "$out/frontend"
```

```bash
.venv/bin/python - "$out" <<'PY'
import sys
from pathlib import Path

from triton._C.libtriton import coral, ir

out = Path(sys.argv[1])
context = ir.context()
ir.load_dialects(context)
ttir = out / "frontend/S1.empty.frontend.0.ttir"
module = ir.parse_mlir_module(str(ttir), context)
pm = ir.pass_manager(context)
coral.passes.add_to_llvmir(pm)
pm.run(module, "check_coral_llvm_dialect")
assert module.verify()
(out / "empty.llvm.mlir").write_text(str(module), encoding="utf-8")
PY

"$build/bin/triton-opt" "$out/empty.llvm.mlir" -o /dev/null
"$sdk/bin/FileCheck" "$examples/ir_checks.txt" --check-prefix=EMPTYLLVM \
  --input-file="$out/empty.llvm.mlir"
cat "$out/empty.llvm.mlir"
```

看到 `llvm.func @empty_kernel`、两个 `!llvm.ptr` 参数和 `llvm.return`，并通过 `EMPTYLLVM` 后，回到第 2 节的 **B. 接入 make_llir**。这一步只改 Python，继续用已经构建的扩展。

### B. 验证 Triton 编译入口

在同一个 shell 中执行。用已有的两个 `@triton.jit` 函数验证空 kernel 成功和标量访存失败。缓存写到临时目录。

```bash
export TRITON_CACHE_DIR="$out/cache" TRITON_STORE_BINARY_ONLY=0

if ! PYTHONPATH="$examples${PYTHONPATH:+:$PYTHONPATH}" \
  .venv/bin/python - "$out" 2>"$out/diagnostics.log" <<'PY'
import sys
from pathlib import Path

import triton
from kernels.s1_scalar import empty_kernel, scalar_copy
from triton.backends.compiler import GPUTarget
from triton.compiler.compiler import ASTSource

out = Path(sys.argv[1])
target = GPUTarget("coral", "coral-rv32", 1)
signature = {"X": "*i32", "Y": "*i32"}
compiled = triton.compile(ASTSource(empty_kernel, signature), target=target)
assert compiled.metadata.name == "empty_kernel"
(out / "empty.ll").write_text(compiled.asm["llir"])
(out / "empty.ttir").write_text(compiled.asm["ttir"])

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

**通过标准**

1. `empty.ll` 有 RV32 target、两个 `ptr` 参数和 `ret void`，通过 `EMPTYLLIR` 和 `opt -passes=verify`。
2. `scalar_copy` 在 `tt.load` 处失败，脚本打印 `PASS: scalar_copy rejected at tt.load`。
3. `empty.o` 是 `llc` 生成的 RISC-V ELF32 可重定位目标文件，反汇编中的 `empty_kernel` 有 `ret`。静态链接和设备执行留在后面的章节。

完成后保留 `empty.llvm.mlir`、`empty.ll` 和 `diagnostics.log`，再进入 [2.2 节的无掩码标量访存](02-scalar-load-store.md)。
