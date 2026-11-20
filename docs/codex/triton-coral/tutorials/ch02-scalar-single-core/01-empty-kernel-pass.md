# 2.1 节：空 Kernel LLVM 降级 Pass 与流水线接入

## 1. 这节课做什么
- **功能目标**：在 make_llir 转换函数签名、指针和空返回，导出 RV32 LLVM IR。
- **支持语法**：`def empty_kernel(X, Y): pass`
- **涉及方言**：tt.func / tt.return -> llvm.func / llvm.return
- **阶段标记**：`S1-01a`（所属章节：第 2 章：标量语法降级与单核 AOT 执行闭环）
- **实现注意**：用 triton.compile 验证正式流水线。S1.copy 应在 tt.load 报未合法化。

## 2. 核心代码实现
```cpp
// third_party/coral/include/TritonCoralToLLVM/TritonCoralToLLVM.h
#ifndef TRITON_CORAL_TO_LLVM_H
#define TRITON_CORAL_TO_LLVM_H
#include "mlir/Pass/Pass.h"
#include <memory>
namespace mlir::triton::coral {
std::unique_ptr<mlir::Pass> createConvertTritonCoralToLLVMPass();
}
#endif
```

```cpp
// third_party/coral/lib/TritonCoralToLLVM/TritonCoralToLLVM.cpp
#include "TritonCoralToLLVM/TritonCoralToLLVM.h"
#include "mlir/Conversion/FuncToLLVM/ConvertFuncToLLVM.h"
#include "mlir/Conversion/LLVMCommon/ConversionTarget.h"
#include "mlir/Conversion/LLVMCommon/TypeConverter.h"
#include "mlir/Dialect/LLVMIR/LLVMDialect.h"
#include "triton/Dialect/Triton/IR/Dialect.h"

using namespace mlir;
namespace tt = mlir::triton;

struct FuncLowering : OpConversionPattern<tt::FuncOp> {
  using OpConversionPattern::OpConversionPattern;
  LogicalResult matchAndRewrite(tt::FuncOp op, OpAdaptor, ConversionPatternRewriter &rewriter) const override {
    if (!op.isPublic() || op.isExternal() || !op.getResultTypes().empty()) return failure();
    const auto &converter = *getTypeConverter<LLVMTypeConverter>();
    auto function = convertFuncOpToLLVMFuncOp(op, rewriter, converter);
    if (failed(function)) return failure();
    rewriter.eraseOp(op);
    return success();
  }
};

struct ReturnLowering : OpConversionPattern<tt::ReturnOp> {
  using OpConversionPattern::OpConversionPattern;
  LogicalResult matchAndRewrite(tt::ReturnOp op, OpAdaptor adaptor, ConversionPatternRewriter &rewriter) const override {
    if (!adaptor.getOperands().empty()) return failure();
    rewriter.replaceOpWithNewOp<LLVM::ReturnOp>(op, ValueRange{});
    return success();
  }
};
```

## 3. 解释说明与注释
- **Dialect Conversion 机制**：利用 MLIR `applyFullConversion`，将 `tt::TritonDialect` 标记为非法方言。
- **负例拦截保证**：此时任何包含 `tt.load` 的 kernel 会因为没有合法化规则而直接报错中断，保证流水线安全。

## 4. 测试与验证代码
```bash
cd /home/compiler-1/work/coral/triton-coral
.venv/bin/python -c '
import triton
from kernels.s1_scalar import empty_kernel
from triton.backends.compiler import GPUTarget
from triton.compiler.compiler import ASTSource

target = GPUTarget("coral", "coral-rv32", 1)
compiled = triton.compile(ASTSource(empty_kernel, {"X": "*i32", "Y": "*i32"}), target=target)
assert "empty_kernel" in compiled.asm["llir"]
print("PASS: 2.1 节 empty_kernel 成功导出 LLVM IR！")
'
```
