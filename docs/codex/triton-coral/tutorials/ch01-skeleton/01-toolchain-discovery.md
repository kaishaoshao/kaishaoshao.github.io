# 1.1 节：从零接入 Triton Coral 后端骨架

源码基线为 `triton-coral` 的 `dev/triton-coral@4f045a9d77`，工具链锁定由 `d63968303d` 引入。本节按 `605e951159184e75660cdcba4b8f07c74829ae86` 的骨架教程顺序逐文件复盘。代码块中的后端模块和测试来自实际提交。[实施计划](../../plan.md) · [章节目录](../README.md)

## 1. 这节课做什么

让 Triton 发现 Coral、从 Python 调到 C++ `hello()`，并让 `compile(ASTSource(...))` 完成三阶段编译及缓存。验收用例的源程序只有 `tl.load(ptr)` 和 `tl.store(ptr, x)`，前端产生原生 `tt` 方言。`llir` 阶段仍保存 TTIR 文本，`elf` 阶段保存占位字节，设备执行不在本节验收范围内。

当前选择 in-tree。Coral 的源码与 Triton 在同一仓库，构建时由顶层 CMake 加入 `libtriton.so`，Python 也从同一 checkout 加载后端。`backend/name.conf` 保留名称标识，供以后适配 `TRITON_PLUGIN_DIRS`。外置构建需要单独验证。

## 2. 文件布局与接入顺序

```text
triton-coral/
├── setup.py
├── python/triton/backends/coral          # 开发环境的软链接
└── third_party/coral/
    ├── triton_coral.cc
    ├── CMakeLists.txt
    ├── backend/
    │   ├── name.conf
    │   ├── __init__.py
    │   ├── driver.py
    │   └── compiler.py
    └── unittest/
        └── test1.py
```

| 顺序 | 操作 | 怎么判断接好了 |
| --- | --- | --- |
| 1 | 建立 `backend/name.conf` 和 `__init__.py` | 包路径及后端名都是 `coral`。 |
| 2 | 写 `triton_coral.cc` | 提供 `init_triton_coral(nanobind::module_ &)`。 |
| 3 | 写后端 `CMakeLists.txt` | `TritonCoral` 进入 `libtriton.so` 的链接。 |
| 4 | 写 `backend/driver.py` | 提供一个可实例化的 `CoralDriver` 和 `GPUTarget`。 |
| 5 | 写 `backend/compiler.py` | 提供一个可实例化的 `CoralBackend`，按顺序注册三个 stage。 |
| 6 | 修改 `setup.py`，核对 Python 软链接 | Python 能发现 compiler 和 driver。 |
| 7 | 用固定 LLVM 24 配置构建并导入 | `libtriton.coral.hello()` 返回字符串。 |
| 8 | 运行 `unittest/test1.py` | 临时缓存中出现 TTIR、`llir`、`elf` 和元数据。 |

## 3. 两条注册链怎样汇合

### C++ 链接与绑定

`setup.py` 把内置后端名写入 `TRITON_CODEGEN_BACKENDS`。顶层 `CMakeLists.txt` 按名称执行 `add_subdirectory(third_party/coral)`。该目录的 `add_triton_plugin` 把对象库目标加入 `TRITON_PLUGINS`。顶层的 `triton` 共享库链接这个目标，产物为 `libtriton.so`。

顶层也把后端名组成 `TRITON_BACKENDS_TUPLE`。`python/src/main.cc` 中的 `DECLARE_BACKEND(coral)` 声明 `init_triton_coral`，`INIT_BACKEND(coral)` 建立 Python 子模块再调用该函数。展开效果为下面两行。

```cpp
auto sub = m.def_submodule("coral");
init_triton_coral(sub);
```

这就是 `from triton._C.libtriton import coral` 的来源。当前仓库固定 nanobind 2.10.2，入口签名使用 `nanobind::module_ &`。骨架的 `TritonCoral` 是 Python 扩展对象库，后续转换 pass 库的构建另见 [2.1 节](../ch02-scalar-single-core/01-empty-kernel-pass.md)。

### Python 发现与目标选择

设置 `TRITON_BACKENDS_IN_TREE=1` 时，`python/triton/backends/__init__.py` 扫描 `python/triton/backends/`，分别导入 `coral.compiler` 与 `coral.driver`。每个文件必须各提供一个对应基类的非抽象子类。默认发现路径由安装产生的 `triton.backends` entry points 提供。

`TRITON_DEFAULT_BACKEND=coral` 在 `python/triton/runtime/driver.py` 选择已发现且 active 的 Coral driver。`get_current_target()` 返回目标后，`compile()` 通过各编译器的 `supports_target()` 找到唯一匹配项。显式传入 target 的 AOT 可以直接选择编译器。

## 4. 八步接入与实际代码

### Step 1 建立名称与 Python 包

`third_party/coral/backend/name.conf` 的全部内容。

```text
coral
```

`third_party/coral/backend/__init__.py` 是包标记。这个提交中它只有注释。

```python
###-----------------------------------------------------------------------------
## C++插件实现
###-----------------------------------------------------------------------------
```

### Step 2 写 C++ binding

`third_party/coral/triton_coral.cc` 完整文件如下。`hello()` 用来检查绑定是否被正确调用。

```cpp
///-----------------------------------------------------------------------------
// C++插件实现
///-----------------------------------------------------------------------------
#include <nanobind/nanobind.h>

namespace py = nanobind;

void init_triton_coral(py::module_ &m) {
  m.doc() = "Python bindings to the Coral Triton backend";

  // 示例导出接口（后续在此注册 Coral 特有的 Dialect、Passes、LLVM Target 设置等）
  m.def("hello", []() {
    return "Hello from Coral backend!";
  });
}
```

### Step 3 将 binding 接入构建

`third_party/coral/CMakeLists.txt` 完整文件如下。`Python3::Module` 和顶层生成的 `nanobind-static` 提供绑定所需依赖。

```cmake
if(TRITON_BUILD_PYTHON_MODULE)
  add_triton_plugin(TritonCoral ${CMAKE_CURRENT_SOURCE_DIR}/triton_coral.cc)
  target_link_libraries(TritonCoral PRIVATE Python3::Module nanobind-static)
endif()
```

### Step 4 写 Python driver

`third_party/coral/backend/driver.py` 完整文件如下。

```python
###-----------------------------------------------------------------------------
## Triton运行时驱动
###-----------------------------------------------------------------------------
from __future__ import annotations
import os
from triton.backends.compiler import GPUTarget
from triton.backends.driver import DriverBase


class CoralDriver(DriverBase):

    def __init__(self):
        super().__init__()

    @classmethod
    def is_active(cls) -> bool:
        # 当检测到Coral 仿真器或硬件运行时返回True，或通过 TRITON_DEFAULT_BACKEND=coral 显式指定
        return os.environ.get("TRITON_DEFAULT_BACKEND", "") == "coral" or True

    def get_current_target(self) -> GPUTarget:
        # Coral NPU是 32-bit RISCV(RV32IMF_Zve32x)
        return GPUTarget("coral", arch="rv32imf_zve32x", warp_size=1)

    def map_python_to_cpp_type(self, ty: str) -> str:
        mapping = {
            "i1": "bool",
            "i8": "int8_t",
            "i16": "int16_t",
            "i32": "int32_t",
            "i64": "int64_t",
            "u1": "bool",
            "u8": "uint8_t",
            "u16": "uint16_t",
            "u32": "uint32_t",
            "u64": "uint64_t",
            "fp16": "uint16_t",
            "bf16": "uint16_t",
            "fp32": "float",
            "fp64": "double",
        }
        if ty.startswith("*"):
            return "void*"
        return mapping.get(ty, "void*")

    def get_active_torch_device(self):
        try:
            import torch
            return torch.device("cpu")
        except Exception:
            return None

    def get_benchmarker(self):
        def _benchmark(kernel_call, *, quantiles=None, **kwargs):
            return [0.0] * (len(quantiles) if quantiles else 1)

        return _benchmark
```

`get_current_target()` 给出 `rv32imf_zve32x`，骨架用 `warp_size=1` 作为目标参数。`is_active()` 的 `or True` 让骨架可显式选择，Torch CPU 与 benchmark 零值都是占位。`map_python_to_cpp_type()` 的 `void*` 是宿主启动器的类型映射，设备帧仍遵守 [RV32 v2 ABI](02-abi-contract.md)。

### Step 5 写 Python 编译器

`third_party/coral/backend/compiler.py` 完整文件如下，来自 `4f045a9d77`。在 compiler-1 的后续本地版本中，`CoralOptions` 和 `supports_target()` 已按 [1.3 节](03-frontend-options.md) 扩展。已有这两处改动时保留它们。

```python
###-----------------------------------------------------------------------------
## Triton编译器核心
## 规范定义了定义了完整的add_stages流水线
## (TTIR优化->LLIR->ELF bytes二进制 以及元数据提取)
###-----------------------------------------------------------------------------
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict
from types import ModuleType

from triton.backends.compiler import BaseBackend, GPUTarget, Language
from triton._C.libtriton import ir, passes, llvm, coral

@dataclass(frozen=True)
class CoralOptions:
  arch: str = "coral-rv32"
  num_warps: int = 1
  num_stages: int = 1
  debug: bool = False

  def hash(self):
    key = "_".join([f"{k}-{v}" for k, v in self.__dict__.items()])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class CoralBackend(BaseBackend):

  @staticmethod
  def supports_target(target: GPUTarget) -> bool:
    return target.backend == "coral"

  def __init__(self, target: GPUTarget) -> None:
    super().__init__(target)
    # 声明最终二进制文件的后缀名
    self.binary_ext = "elf"

  def hash(self) -> str:
    return f"{self.target}"

  def parse_options(self, options: dict) -> CoralOptions:
    opts = {
      k: options[k]
      for k in CoralOptions.__dataclass_fields__.keys()
      if k in options and options[k] is not None
    }
    return CoralOptions(**opts)


  def load_dialects(self, context) -> None:
    # 后续加载Coral专有Dialect（tts, linalg）等
    pass

  def pack_metadata(self, metadata):
    return (metadata.num_warps, getattr(metadata, "num_ctas", 1), getattr(metadata, "shared", 0))

  def get_codegen_implementation(self, options):
    return {}

  def get_module_map(self) -> Dict[str, ModuleType]:
    return {}

  # =========================================================================
  # Stage 流水线处理函数
  # =========================================================================
  @staticmethod
  def make_ttir(mod, metadata, options):
    """阶段1: TTIR优化(内联 + 规范化) """
    pm = ir.pass_manager(mod.context)
    pm.enable_debug()
    passes.common.add_inliner(pm)
    pm.run(mod, "coral_make_ttir")

    # 提取kernel 函数名并记录到metadata(Triton缓存机制要求)
    mod_str = str(mod)
    names = re.findall(r"tt\.func\s+(?:public\s+)?@([a-zA-Z_][a-zA-Z0-9_]*)", mod_str)
    if names:
      metadata["name"] = names[0]
    else:
      metadata["name"] = "coral_kernel"

    metadata["num_warps"] = options.num_warps
    return mod

  @staticmethod
  def make_llir(src, metadata, options):
    '''阶段2: 降级到LLVM IR'''
    return str(src)


  @staticmethod
  def make_elf(src, metadata, options):
    '''阶段3: 最终二进制生成(铁律： 必须返回bytes类型)'''
    # 第一阶段先返回占位虚拟字节六，确保编译和缓存系统完整闭环
    dummy_elf = f"/* Coral RISC-V Binary: { metadata.get('name', 'kernel')} */\n".encode("utf-8")
    return dummy_elf


  def add_stages(self, stages: dict, options: CoralOptions, language: Language) -> None:
    # 按照顺序注册流水线
    stages["ttir"] = lambda src, metadata: self.make_ttir(src, metadata, options)
    stages["llir"] = lambda src, metadata: self.make_llir(src, metadata, options)
    stages["elf"]  = lambda src, metadata: self.make_elf(src, metadata, options)
```

调用关系是 `ASTSource.make_ir() → make_ttir() → make_llir() → make_elf()`。`make_ttir()` 调用 inliner，并填入 `metadata["name"]` 和 `metadata["num_warps"]`。输入与返回的类型如下，缓存文件后缀来自 `add_stages()` 的键。

| stage | 本版返回值 | 缓存中看到什么 |
| --- | --- | --- |
| `ttir` | MLIR module | `add_kernel.ttir`，含 `tt.func` 和实际访存。 |
| `llir` | `str(src)` | `add_kernel.llir`，内容仍为 TTIR。 |
| `elf` | `bytes` | `add_kernel.elf`，内容以 `/* Coral RISC-V Binary:` 开头。 |

### Step 6 注册 setup.py 并核对软链接

在 `setup.py` 中，`backends = ...` 的实际改动如下。

```python
backends = [*BackendInstaller.copy(["nvidia", "amd", "coral"]), *BackendInstaller.copy_externals()]
```

开发安装会更新后端软链接。使用既有 CMake 构建时，在 Triton 仓库根目录核对该链接。只有路径确实空缺时才手动创建。

```bash
link=python/triton/backends/coral
if [ ! -e "$link" ] && [ ! -L "$link" ]; then
  ln -s ../../../third_party/coral/backend "$link"
fi
test "$(readlink -f "$link")" = "$PWD/third_party/coral/backend"
```

### Step 7 用固定 SDK 构建并确认加载路径

LLVM 基础提交为 `6cce5bca3b901ec32e250fb43e88eb0fe511af93`。SDK 版本为 `24.0.0git`，启用 assertions，RTTI 关闭，目标包含 X86、RISCV、NVPTX、AMDGPU。锁文件为 Triton 仓库的 `cmake/llvm-info.json`，初次配置见同仓库的 `docs/coral-llvm.md`。

compiler-1 使用已配置的脚本。只有首次构建或修改 native/CMake 后需要重编。

```bash
bash /home/compiler-1/work/coral/build-triton-llvm24-python.sh
```

在 WSL 可复用已配置的 `build/coral-llvm24`。

```bash
cd /home/kaikai/work/coral/triton-coral
sdk="$HOME/work/coral/coralnpu-compiler/out/llvm-zvt/install"
build="$PWD/build/coral-llvm24"
export PATH="$sdk/bin:$PATH"
make BUILD_DIR="$build" PYTHON="$PWD/.venv/bin/python"
install -m 755 "$build/python-module/libtriton.so" python/triton/_C/libtriton.so.new
mv -T python/triton/_C/libtriton.so.new python/triton/_C/libtriton.so
```

### Step 8 跑已有冒烟测试并检查编译产物

`third_party/coral/unittest/test1.py` 完整文件如下。

```python
import os
os.environ.setdefault("TRITON_DEFAULT_BACKEND", "coral")

import triton
from triton.backends import backends
print('1. 注册的后端列表:', list(backends.keys()))

from triton._C.libtriton import coral
print('2. C++ 接口调用:', coral.hello())

import triton.language as tl
from triton.compiler import ASTSource, compile

@triton.jit
def add_kernel(x_ptr, y_ptr, BLOCK: tl.constexpr):
    x = tl.load(x_ptr)
    tl.store(y_ptr, x)

src = ASTSource(
    fn=add_kernel,
    signature={"x_ptr": "*fp32", "y_ptr": "*fp32"},
    constexprs={"BLOCK": 64},
)

compiled = compile(src, target=triton.runtime.driver.active.get_current_target())
print('3. 端到端编译成功! Kernel 名称:', compiled.name)
print('4. 生成的二进制 payload:', compiled.asm['elf'][:40])
```

历史用例沿用名字 `add_kernel`，函数体实际拷贝一个 `fp32` 元素。`BLOCK=64` 是未使用的编译时参数。这次测试使用显式 target 的 AOT 编译入口。

在当前 Triton checkout 根目录运行。临时缓存确保本次执行真正经过编译阶段。compiler-1 用 `/home/compiler-1/work/coral/triton-coral` 作为根目录，WSL 用 `/home/kaikai/work/coral/triton-coral`。

```bash
set -e
sdk="$HOME/work/coral/coralnpu-compiler/out/llvm-zvt/install"
"$sdk/bin/llvm-config" --version
"$sdk/bin/llvm-config" --targets-built
export TRITON_BACKENDS_IN_TREE=1 TRITON_DEFAULT_BACKEND=coral
export TRITON_CACHE_DIR="$(mktemp -d /tmp/coral-skeleton-XXXXXX)"
export TRITON_STORE_BINARY_ONLY=0

.venv/bin/python - "$PWD" <<'PY'
import sys
from pathlib import Path

import triton
from triton._C import libtriton
from triton.backends import backends
from triton.backends.compiler import GPUTarget

root = Path(sys.argv[1]).resolve()
assert Path(triton.__file__).resolve() == root / "python/triton/__init__.py"
assert Path(libtriton.__file__).resolve() == root / "python/triton/_C/libtriton.so"
assert "coral" in backends
assert triton.runtime.driver.active.get_current_target() == GPUTarget(
    "coral", "rv32imf_zve32x", 1
)
assert libtriton.coral.hello() == "Hello from Coral backend!"
print("PASS: checkout, native binding and Coral target")
PY

.venv/bin/python third_party/coral/unittest/test1.py

.venv/bin/python - "$TRITON_CACHE_DIR" <<'PY'
import json
import sys
from pathlib import Path

cache = Path(sys.argv[1])
ttir, = cache.rglob("add_kernel.ttir")
llir = ttir.with_suffix(".llir")
elf = ttir.with_suffix(".elf")
metadata = json.loads(ttir.with_suffix(".json").read_text())
text = ttir.read_text()
assert "tt.func public @add_kernel" in text
assert "tt.load" in text and "tt.store" in text
assert llir.read_text() == text
assert elf.read_bytes() == b"/* Coral RISC-V Binary: add_kernel */\n"
assert metadata["name"] == "add_kernel" and metadata["num_warps"] == 1
print(f"PASS: TTIR, passthrough llir, placeholder elf and metadata in {ttir.parent}")
PY
```

预期后端列表包含 `coral`，顺序随扫描结果变化。C++ 返回 `Hello from Coral backend!`，测试打印 `add_kernel` 和占位字节。命令输出两条 `PASS`，分别验证扩展加载和缓存中的各阶段产物。2026-11-20 在 WSL 和 compiler-1 使用已有构建复跑通过。

## 5. 排错与后续

| 现象 | 先查哪里 | 处理 |
| --- | --- | --- |
| C++ `hello()` 可调，列表却没有 `coral` | Python 包发现。 | 检查软链接与 `TRITON_BACKENDS_IN_TREE=1`。默认发现模式则检查安装的 entry point。 |
| 后端列表有 `coral`，但 `libtriton.coral` 不存在 | C++ 构建和 Python 加载路径。 | 核对 `TRITON_CODEGEN_BACKENDS` 含 `coral`，确认重编后同步了正确的 `libtriton.so`。 |
| `module_` 编译错误，或 `init_triton_coral` 符号缺失 | C++ 入口声明与链接。 | 检查 `nanobind::module_ &` 的签名和 `nanobind-static`，确认 `triton_coral.cc` 在插件目标内。 |
| 初始化 NVIDIA 或触发 CUDA 头文件报错 | 默认 driver 选择。 | 设置 `TRITON_DEFAULT_BACKEND=coral` 并确认其 `is_active()` 返回真。 |
| `Found 0 concrete subclasses` 或 `Found >1` | `compiler.py` 或 `driver.py` 模块发现。 | 核对两边各只有一个可实例化的对应子类。 |
| 没有缓存 `name` 或末级产物读回失败 | stage 与元数据。 | 检查 `make_ttir()` 的 metadata、`binary_ext`、末级名称及 `bytes` 返回类型。 |

骨架接入完成后，先核对 [1.2 节的参数 ABI](02-abi-contract.md)，再按 [1.3 节](03-frontend-options.md) 验证正式语法选项。空 kernel 的真正 LLVM IR 转换从 [2.1 节](../ch02-scalar-single-core/01-empty-kernel-pass.md) 开始。
