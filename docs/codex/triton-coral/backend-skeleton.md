# 第二课：从标量 TTIR 到单核 ELF

从已经搭好的 Coral 骨架开始。本课的目标是让 `scalar_copy` 经真实 LLVM IR 和 RV32 ELF 在 core0 上把 −37 写回。用共享 SRAM 和 v2 参数框架。完成这一课后再做 block、mask 和更多 program。开始前按[第一次运行](plan.md#第一次运行)设置环境变量。

```text
Triton 源码 → TTIR → LLVM 方言 → LLVM IR → RV32 ELF
  → AOT 镜像 → 控制 CPU 装载 → core0 执行 → 读回并比较
```

## 第一批：正式选项与空函数 lowering

把 **S0-03 和 S1-01a** 一起做。目标是让正式 Coral 选项生成 TTIR，再用现有 Coral 扩展调用 MLIR 的标准函数转换。最后检查生成的 LLVM 方言，并用含访存的合法 TTIR 验证转换确实拒绝越出当前范围的输入。

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

### 2. 需要修改的文件（仅 1 个现有 C++ 文件）

修改 Triton checkout 中的 `third_party/coral/triton_coral.cc`。保留现有 `hello()`，增加一个 Python binding，在该入口调用 MLIR 自带的 `FuncToLLVM`。以下是修改后的完整文件。前面的 S0-03 仍按两处 Python 修改完成。

```cpp
// triton_coral.cc
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include "mlir/Conversion/Passes.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/Dialect/LLVMIR/LLVMDialect.h"
#include "mlir/IR/Builders.h"
#include "mlir/IR/BuiltinOps.h"
#include "mlir/Pass/PassManager.h"
#include "triton/Dialect/Triton/IR/Dialect.h"
#include "llvm/ADT/STLExtras.h"
#include "llvm/Support/raw_ostream.h"

namespace py = nanobind;

void init_triton_coral(py::module_ &m) {
  m.doc() = "Python bindings to the Coral Triton backend";
  m.def("hello", []() { return "Hello from Coral backend!"; });

  m.def("lower_empty_kernel", [](mlir::ModuleOp source) -> std::string {
    using namespace mlir;
    namespace tt = mlir::triton;

    if (!llvm::hasSingleElement(*source.getBody()))
      throw py::value_error("expected one top-level tt.func");

    auto kernel = dyn_cast<tt::FuncOp>(source.getBody()->front());
    if (!kernel || !kernel.isPublic() || !kernel.getResultTypes().empty() ||
        !llvm::hasSingleElement(kernel.getBody()))
      throw py::value_error("expected a public void tt.func with one block");

    Block &body = kernel.getBody().front();
    if (!llvm::hasSingleElement(body) || !isa<tt::ReturnOp>(body.front()) ||
        body.front().getNumOperands() != 0)
      throw py::value_error("expected a kernel body containing only tt.return");

    MLIRContext *ctx = source.getContext();
    ctx->loadDialect<func::FuncDialect, LLVM::LLVMDialect>();
    SmallVector<Type> arguments;
    for (Type type : kernel.getArgumentTypes()) {
      auto ptr = dyn_cast<tt::PointerType>(type);
      if (!ptr || ptr.getAddressSpace() != tt::PtrAddrSpace::Global ||
          !ptr.getPointeeType().isInteger(32))
        throw py::value_error("expected a global pointer to i32");
      arguments.push_back(LLVM::LLVMPointerType::get(ctx));
    }

    OwningOpRef<ModuleOp> bridge(ModuleOp::create(source.getLoc()));
    OpBuilder builder(ctx);
    builder.setInsertionPointToStart(bridge->getBody());
    auto function = func::FuncOp::create(
        builder, kernel.getLoc(), kernel.getSymName(),
        builder.getFunctionType(arguments, {}));
    builder.setInsertionPointToStart(function.addEntryBlock());
    func::ReturnOp::create(builder, body.front().getLoc());

    PassManager pm(ctx);
    pm.addPass(createConvertFuncToLLVMPass());
    if (failed(pm.run(*bridge)))
      throw py::value_error("FuncToLLVM failed");

    std::string text;
    llvm::raw_string_ostream stream(text);
    bridge->print(stream);
    return text;
  });
}
```

**原理分析**

- 先读取真实的 Triton 模块，检查只有一个公开、无结果的空函数，然后根据它的函数名、参数和返回建立标准 `func.func`。使用类型化 MLIR API，函数名和参数数量都来自输入。
- 这一课把 Triton 全局 `*i32` 参数映射到平坦地址模型的 `!llvm.ptr`。指针位宽后续由 RV32 data layout 决定。
- 调用标准 `createConvertFuncToLLVMPass()` 完成 `func.func → llvm.func` 和 `func.return → llvm.return`。当前 SDK 已把这套转换链接进 `libtriton.so`。
- 入口先检查整个空函数契约。真实 `S1.copy` 含 load/store，会在构造中间 IR 前明确报错。接通标量访存和算术后再扩大入口范围。

### 3. 编译与验证命令

在 WSL 增量编译并同步 Python 加载的扩展。本机的构建目录是 `build/coral-llvm24`。

```bash
cd ~/work/coral/triton-coral
export TRITON_BACKENDS_IN_TREE=1 TRITON_DEFAULT_BACKEND=coral
sdk="$HOME/work/coral/coralnpu-compiler/out/llvm-zvt/install"
build="$PWD/build/coral-llvm24"
export PATH="$sdk/bin:$PATH"

make BUILD_DIR="$build" PYTHON="$PWD/.venv/bin/python"
install -m 755 "$build/python-module/libtriton.so" python/triton/_C/libtriton.so.new
mv -T python/triton/_C/libtriton.so.new python/triton/_C/libtriton.so
```

下面的验证在临时输出目录写 TTIR。先完成前面的 S0-03，再用正式选项生成用例。Python 脚本可以直接执行。

```bash
set -e
examples="${CORAL_TUTORIAL:-/mnt/c/Users/20327/Documents/ChatGPT/learn/kaishaoshao.github.io/docs/codex/triton-coral/examples}"
out=$(mktemp -d /tmp/coral-first-lowering-XXXXXX)

.venv/bin/python "$examples/dump_ttir.py" --stage S1 --cumulative \
  --case S0.frontend --case S1.add --case S1.empty.frontend --case S1.copy \
  --backend-options --output "$out"

.venv/bin/python - "$out" <<'PY'
import sys
from pathlib import Path

from triton._C.libtriton import coral, ir
from triton.backends.compiler import GPUTarget
from triton.compiler.compiler import make_backend

out = Path(sys.argv[1])

for arch in ("coral-rv32", "rv32imf_zve32x"):
    assert make_backend(GPUTarget("coral", arch, 1)).target.arch == arch

try:
    make_backend(GPUTarget("coral", "coral-invalid", 1))
except RuntimeError as error:
    assert str(error).startswith("0 compatible backends"), error
    print("PASS: rejected coral-invalid")
else:
    raise AssertionError("unsupported Coral arch was accepted")

def lower(filename):
    context = ir.context()
    ir.load_dialects(context)
    module = ir.parse_mlir_module(str(out / filename), context)
    assert module.verify()
    return coral.lower_empty_kernel(module)

(out / "empty.llvm.mlir").write_text(lower("S1.empty.frontend.0.ttir"))
try:
    lower("S1.copy.0.ttir")
except ValueError as error:
    assert "expected a kernel body containing only tt.return" in str(error), error
    print("PASS: load/store rejected by the empty-kernel entry")
else:
    raise AssertionError("load/store kernel was accepted")
PY

"$build/bin/triton-opt" "$out/empty.llvm.mlir" -o /dev/null
"$sdk/bin/FileCheck" "$examples/ir_checks.txt" --check-prefix=EMPTYLLVM \
  --input-file="$out/empty.llvm.mlir"
cat "$out/empty.llvm.mlir"
```

**预期结果**

1. 正式前端生成 5 份 TTIR，非法架构被拒绝。
2. `empty.llvm.mlir` 有 `llvm.func @empty_kernel`、两个 `!llvm.ptr` 参数及 `llvm.return`，通过 verifier 和 `EMPTYLLVM`。
3. `S1.copy` 产生合法 TTIR，进入空函数转换时失败。验证脚本打印 `PASS: load/store rejected by the empty-kernel entry`。

交付这一批时发出空函数输出和负例诊断。接通适配器后，再用已有 `S1.empty.llvm` 用例保存真实检查点。

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
