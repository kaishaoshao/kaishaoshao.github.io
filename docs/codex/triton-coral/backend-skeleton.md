# 第二课：从标量 TTIR 到单核 ELF

从已经搭好的 Coral 骨架开始。本课的目标是让 `scalar_copy` 经真实 LLVM IR 和 RV32 ELF 在 core0 上把 −37 写回。用共享 SRAM 和 v2 参数框架。完成这一课后再做 block、mask 和更多 program。开始前按[第一次运行](plan.md#第一次运行)设置环境变量。

```text
Triton 源码 → TTIR → LLVM 方言 → LLVM IR → RV32 ELF
  → AOT 镜像 → 控制 CPU 装载 → core0 执行 → 读回并比较
```

## 第一批：正式选项与空 kernel 接入编译流水线

按顺序做三个检查点。每次完成一行并保存测试结果，再改下一行。[源码目录与职责](plan.md#源码目录与职责)

| 检查点 | 入口 | 通过信号 |
| --- | --- | --- |
| S0-03 正式前端选项 | 现有 `backend/compiler.py` | 正式 Coral 选项产生 TTIR，未知架构被拒绝。 |
| S1-01a 原生转换 | `coral.passes.add_to_llvmir(pm)` | 原生库能加载，`empty_kernel` 的 TTIR 变为 LLVM 方言。 |
| S1-01a 正式编译 | `triton.compile(ASTSource(...), target=...)` | `make_llir` 导出 RV32 LLVM IR，`scalar_copy` 在 `tt.load` 处给出诊断。 |

### 第一步：S0-03 正式前端选项

这一步只改 `third_party/coral/backend/compiler.py`。在 `CoralOptions` 中，与 `debug` 对齐添加字段。Triton 生成整数加法时会读取它，设备执行阶段用 `S1.wrap` 验证 I32 回绕。

```python
  sanitize_overflow: bool = False
```

同一文件替换 `CoralBackend.supports_target`，让教程的 `coral-rv32` 和当前 driver 返回的 `rv32imf_zve32x` 都能选择 Coral。

```python
  @staticmethod
  def supports_target(target: GPUTarget) -> bool:
    return (
      target.backend == "coral"
      and target.arch in ("coral-rv32", "rv32imf_zve32x")
      and target.warp_size == 1
    )
```

用已有构建执行下面的命令。保留这个 WSL shell，下一步使用同一个 `out` 目录里的 TTIR。

```bash
cd ~/work/coral/triton-coral
set -e
export TRITON_BACKENDS_IN_TREE=1 TRITON_DEFAULT_BACKEND=coral
examples="${CORAL_TUTORIAL:-/mnt/c/Users/20327/Documents/ChatGPT/learn/kaishaoshao.github.io/docs/codex/triton-coral/examples}"
out=$(mktemp -d /tmp/coral-llir-XXXXXX)

.venv/bin/python "$examples/dump_ttir.py" --stage S1 --cumulative \
  --case S0.frontend --case S1.add --case S1.empty.frontend --case S1.copy \
  --backend-options --output "$out/frontend"

.venv/bin/python - <<'PY'
from triton.backends.compiler import GPUTarget
from triton.compiler.compiler import make_backend

for arch in ("coral-rv32", "rv32imf_zve32x"):
    target = GPUTarget("coral", arch, 1)
    assert make_backend(target).target == target

try:
    make_backend(GPUTarget("coral", "coral-invalid", 1))
except RuntimeError as error:
    assert str(error).startswith("0 compatible backends"), error
    print("PASS: rejected coral-invalid")
else:
    raise AssertionError("unsupported target was accepted")
PY
```

看到 5 份 TTIR 和 `PASS: rejected coral-invalid`，这一小步完成。

### 第二步：S1-01a 构建并单测转换库

先让转换独立通过，下一步再接入 `make_llir`。以下路径均相对于 `third_party/coral/`。

| 文件 | 改动 |
| --- | --- |
| `include/TritonCoralToLLVM/Passes.td` | 新建，声明 pass 名称和依赖方言。 |
| `include/TritonCoralToLLVM/Passes.h` | 新建，公开生成的 factory 声明。 |
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

`include/TritonCoralToLLVM/Passes.h` 内容如下。

```cpp
#ifndef TRITON_CORAL_TO_LLVM_PASSES_H
#define TRITON_CORAL_TO_LLVM_PASSES_H

#include "mlir/Pass/Pass.h"

namespace mlir::triton::coral {

#define GEN_PASS_DECL
#include "TritonCoralToLLVM/Passes.h.inc"

} // namespace mlir::triton::coral

#endif // TRITON_CORAL_TO_LLVM_PASSES_H
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
#include "TritonCoralToLLVM/Passes.h"

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

`convertFuncOpToLLVMFuncOp()` 转换函数签名并保留原函数体，`ReturnLowering` 改写 `tt.return`。`applyFullConversion()` 要求所有操作满足转换目标，所以 `tt.load` 在有对应 pattern 前会报出源位置。首批验收公开的无返回值 kernel、两个全局 `*i32` 参数和 `tt.return`。RV32 ILP32 的 data layout 和 SDK 对齐，设备指针映射到地址空间 0。[Triton 函数转换](https://github.com/triton-lang/triton/blob/main/lib/Conversion/TritonGPUToLLVM/FuncOpToLLVM.cpp) · [MLIR Dialect Conversion](https://mlir.llvm.org/docs/DialectConversion/)

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
#include "TritonCoralToLLVM/Passes.h"
#include "mlir/Pass/PassManager.h"
```

在 `init_triton_coral` 末尾、`hello()` 注册之后插入下面三行。

```cpp
  m.def_submodule("passes").def("add_to_llvmir", [](mlir::PassManager &pm) {
    pm.addPass(mlir::triton::coral::createConvertTritonCoralToLLVM());
  });
```

#### 增量编译并验证原生转换

在第一步的 WSL shell 中执行。`triton-opt` 复核产物，pass 由 Python binding 加入 `PassManager`。

```bash
sdk="$HOME/work/coral/coralnpu-compiler/out/llvm-zvt/install"
build="$PWD/build/coral-llvm24"
export PATH="$sdk/bin:$PATH"

make BUILD_DIR="$build" PYTHON="$PWD/.venv/bin/python"
install -m 755 "$build/python-module/libtriton.so" python/triton/_C/libtriton.so.new
mv -T python/triton/_C/libtriton.so.new python/triton/_C/libtriton.so
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

看到 `llvm.func @empty_kernel`、两个 `!llvm.ptr` 参数和 `llvm.return`，并通过 `EMPTYLLVM`，就可以接入编译阶段。

### 第三步：S1-01a 接入正式编译

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

#### 用标准 Triton 源程序验证编译

在同一个 WSL shell 中执行。`ASTSource` 与 `triton.compile()` 从已有 `@triton.jit` kernel 进入正式流程，缓存写到本次临时目录。

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

**预期结果**

1. `empty.ll` 的 target 为 RV32。`empty_kernel` 保留两个 `ptr` 参数和 `ret void`，通过 `EMPTYLLIR` 和 LLVM verifier。
2. 同一个编译入口处理 `scalar_copy` 时在 `tt.load` 处失败，脚本打印 `PASS: scalar_copy rejected at tt.load`。
3. `empty.o` 的头部显示 `ELF32`、`REL`、`RISC-V`，反汇编有 `ret`。这里的真实目标文件由 `llc` 生成。可装载的 ELF 和 core0 执行归后续阶段验收。

做完第三步后发 `empty.ll`、`tt.load` 诊断和反汇编。通过后在这个转换库里增加标量访存。

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

1. 在 `third_party/coral/backend/runtime/start.S` 接入 v2 参数帧。核对两条设备指针、16 字节栈对齐及完成标志地址。参与编译的 `constexpr` 不占运行参数槽位。
2. 用固定 Coral SDK 的 `clang`、`ld.lld` 和 `backend/runtime/link.ld` 生成 ELF32 小端 RISC-V ELF。先用 SDK 的 `llvm-readelf -h -l` 检查入口和 `PT_LOAD`，再交给宿主打包器。
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
