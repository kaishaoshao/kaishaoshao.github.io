# Triton Coral 后端骨架与起步指南（按极小步推进）

更新日期：2026-11-18（Asia/Shanghai）。本文件在固定路径持续维护，变更记录见 Git 历史。

配套文件：[实施计划](plan.md)、[任务数据](plan.json)、[任务表](tasks.xlsx)、[目录与维护说明](../README.md)。

本文保留骨架复盘与起步微步；阶段白名单、ABI和验收以 `plan.json` 及同步的 `plan.md` 为准。当前测试协议为2：主机自检、前端、LLVM方言检查和设备执行分别记录，不能用骨架占位产物验收执行。

---

## 0. 你现在在哪里 & 下一步做什么（总览）

为了避免一次铺开太多概念，我们把起步阶段拆成 **两段、12 个极小步骤**，每一步都明确写出：**支持什么 Triton 语法、是否新增方言、明确不支持什么、要改哪个文件、如何独立验收**。

| 阶段 | 小步编号 | 这一小步做什么 | 支持的 Triton 语法 | 方言策略 | 当前状态 |
| --- | --- | --- | --- | --- | --- |
| **第一段：后端骨架** | Step 1～Step 8 | 接入 `third_party/coral` 注册骨架、nanobind 扩展、Driver 与 3 段式 `add_stages` 壳子 | 单元素 `tl.load(ptr)` / `tl.store(ptr, x)`（仅到 TTIR + 占位 ELF） | **不新增方言**，仅用 Triton 原生 `tt` | **已完成（`4f045a9d77`）** |
| **第二段：S0-03（下一步第 1 小步）** | **Micro-Step 1** | 补全 `CoralOptions`（`sanitize_overflow=False` 等）+ 固化标量拷贝与加一用例 | 新增单元素标量 `x + 1`（`*i32` 指针，无 `tl.arange`） | **不新增方言**，仅用原生 `tt` + `arith` | **⬅ 紧接着先做这一步** |
| **第二段：S1-01a（下一步第 2 小步）** | **Micro-Step 2** | 搭 `MinimalTritonToLLVM` Pass 架子，只转空函数与指针参数 | `empty_kernel(X, Y)`；指针类型在 `ASTSource.signature` 中声明 | **不新增自定义方言**，复用标准 `LLVM` 方言 | 待开始 |
| **第二段：S1-01b（下一步第 3 小步）** | **Micro-Step 3** | 在 Pass 中加入标量 `i32` 无掩码访存转换 | `x = tl.load(in_ptr); tl.store(out_ptr, x)` | **不新增自定义方言**，复用标准 `LLVM` 方言 | 待开始 |
| **第二段：S1-01c（下一步第 4 小步）** | **Micro-Step 4** | 接入标准 `ArithToLLVM` + RV32 Triple/DataLayout + LLVM Verifier | `x + 1` 等标量 `i32` 算术，拒绝 `tl.arange` | **不新增自定义方言**，复用标准 `arith`/`cf`/`LLVM` | 待开始 |

> **关键原则**：整个 G1（S0～S1）**零自定义方言**，不碰 TTS、Linalg、RVV、DMA 或多核。每次只完成一个小步，写完代码后发出来逐行核对并跑通本步验收，再进入下一小步。

---

## 第一段：后端骨架接入（Step 1 ～ Step 8 逐文件复盘）

骨架的目标只有一件事：**让 Triton 能发现 `coral` 后端、调通 C++ 扩展、走完 `ASTSource → TTIR → 占位 ELF` 的编译缓存框架**。

### Step 1：建立目录身份（`name.conf` + `__init__.py`）

- **做什么**：创建 `third_party/coral/backend/` 并放入身份标识文件。
- **支持语法 / 方言**：无（纯目录结构准备）。
- **为什么先做它**：`setup.py` 和 Python 导入器必须先识别该目录是名为 `coral` 的包。

**`third_party/coral/backend/name.conf`**（纯 In-tree 不强制，但写一行 `coral` 即可同时兼容 `TRITON_PLUGIN_DIRS` 外置插件模式）：
```text
coral
```

**`third_party/coral/backend/__init__.py`**（Python 包标记，让 `importlib.import_module("triton.backends.coral.compiler")` 合法）：
```python
# Triton Coral backend Python package marker.
```

---

### Step 2：写最小 C++ nanobind 扩展入口（`triton_coral.cc`）

- **做什么**：导出 `init_triton_coral`，让 Python 能通过 `from triton._C.libtriton import coral` 调用 C++。
- **支持语法 / 方言**：不涉及任何 MLIR 方言。
- **关键原理**：顶层 `python/src/main.cc` 会根据 `TRITON_BACKENDS_TUPLE` 宏自动展开：
  ```cpp
  void init_triton_coral(nanobind::module_ &m);
  ```
  当前 `triton-coral` 已全面迁移到 **nanobind 2.10.2**，参数**必须是 `nanobind::module_ &`**（带下划线、左值引用），绝不能写成旧版 `pybind11::module &&`。

**`third_party/coral/triton_coral.cc`**：
```cpp
#include <nanobind/nanobind.h>

namespace py = nanobind;

// 函数名和参数签名必须与 python/src/main.cc 的 DECLARE_BACKEND(coral) 完全一致
void init_triton_coral(py::module_ &m) {
  m.doc() = "Python bindings to the Coral Triton backend";

  // 最小冒烟函数：确认 C++ 编译、链接进 libtriton.so、Python 导入全链路正常
  m.def("hello", []() {
    return "Hello from Coral backend!";
  });
}
```

---

### Step 3：接入 CMake 插件构建（`third_party/coral/CMakeLists.txt`）

- **做什么**：把 `triton_coral.cc` 注册为 Triton 插件对象库并链接 `nanobind-static`。
- **关键原理**：
  - 顶层 `CMakeLists.txt` 遍历 `TRITON_CODEGEN_BACKENDS` 执行 `add_subdirectory(third_party/coral)`；
  - `add_triton_plugin(TritonCoral ...)` 会把目标加入全局属性 `TRITON_PLUGINS`，由 `libtriton.so` 自动链接；
  - 所有后端统一链接顶层构建好的 `nanobind-static`，避免多插件重复内联绑定运行时。

**`third_party/coral/CMakeLists.txt`**：
```cmake
if(TRITON_BUILD_PYTHON_MODULE)
  add_triton_plugin(TritonCoral ${CMAKE_CURRENT_SOURCE_DIR}/triton_coral.cc)
  target_link_libraries(TritonCoral PRIVATE Python3::Module nanobind-static)
endif()
```

---

### Step 4：写最小运行时驱动（`third_party/coral/backend/driver.py`）

- **做什么**：告诉 Triton 当前设备的目标架构（`GPUTarget`）以及基础类型映射。
- **规则约束**：`python/triton/backends/__init__.py` 强制要求本文件**有且仅有 1 个**继承自 `DriverBase` 的具体（非抽象）子类。
- **关键细节**：
  - `warp_size=1`：Coral 是单核标量/向量 NPU，没有 GPU 32/64 线程束概念；
  - `is_active()` 在骨架阶段先返回 `True`（并配合 `TRITON_DEFAULT_BACKEND=coral`），到 S3-01 再改为真实硬件/仿真器可用性检查；
  - `get_benchmarker()` 返回 `0.0` 仅作骨架占位，S3-01 必须替换为真实计时。

**`third_party/coral/backend/driver.py`**：
```python
from __future__ import annotations

import os
from triton.backends.compiler import GPUTarget
from triton.backends.driver import DriverBase


class CoralDriver(DriverBase):

    def __init__(self):
        super().__init__()

    @classmethod
    def is_active(cls) -> bool:
        # 骨架调试阶段返回 True；S3-01 必须替换为真实设备/仿真桥检测
        return os.environ.get("TRITON_DEFAULT_BACKEND", "") == "coral" or True

    def get_current_target(self) -> GPUTarget:
        # Coral NPU 基础 ISA 为 32 位 RISC-V，无 GPU warp 概念故 warp_size=1
        return GPUTarget("coral", arch="rv32imf_zve32x", warp_size=1)

    def map_python_to_cpp_type(self, ty: str) -> str:
        # 将 Triton 参数签名映射为 C 启动器形参类型
        mapping = {
            "i1": "bool", "i8": "int8_t", "i16": "int16_t", "i32": "int32_t", "i64": "int64_t",
            "u1": "bool", "u8": "uint8_t", "u16": "uint16_t", "u32": "uint32_t", "u64": "uint64_t",
            "fp16": "uint16_t", "bf16": "uint16_t", "fp32": "float", "fp64": "double",
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
        # 骨架占位；S3-01 替换为真实计时
        def _benchmark(kernel_call, *, quantiles=None, **kwargs):
            return [0.0] * (len(quantiles) if quantiles else 1)

        return _benchmark
```

---

### Step 5 & Step 6：写编译器选项、后端壳子与 3 段式 `add_stages`（`third_party/coral/backend/compiler.py`）

- **做什么**：实现 `CoralOptions`（选项与缓存哈希）和 `CoralBackend(BaseBackend)`（3 段式编译流水线 `ttir → llir → elf`）。
- **骨架阶段支持的语法**：仅单元素 `tl.load(ptr)` 与 `tl.store(ptr, x)`（在补全 `CoralOptions` 之前不支持 `x + 1`）。
- **骨架阶段用到的方言**：**不新增方言**，仅使用 Triton 前端生成的 `tt`（`TritonDialect`）。
- **`add_stages` 三条铁律**：
  1. 字典按插入顺序执行，前一步输出传给下一步；
  2. 必须写入 `metadata["name"]` 和 `metadata["num_warps"]`，否则 Triton 缓存写盘报错；
  3. **最后一个 stage（`elf`）必须返回 `bytes`**，中间 stage 返回 MLIR Module 或 `str`。

**`third_party/coral/backend/compiler.py`（骨架基线版）**：
```python
import hashlib
import re
from dataclasses import dataclass
from typing import Dict
from types import ModuleType

from triton.backends.compiler import BaseBackend, GPUTarget, Language
from triton._C.libtriton import ir, passes, llvm, coral


@dataclass(frozen=True)
class CoralOptions:
    """不可变编译选项；hash() 用于 Triton 磁盘缓存键。"""
    arch: str = "coral-rv32"
    num_warps: int = 1
    num_stages: int = 1
    debug: bool = False

    def hash(self) -> str:
        key = "_".join([f"{k}-{v}" for k, v in self.__dict__.items()])
        return hashlib.sha256(key.encode("utf-8")).hexdigest()


class CoralBackend(BaseBackend):

    @staticmethod
    def supports_target(target: GPUTarget) -> bool:
        return target.backend == "coral"

    def __init__(self, target: GPUTarget) -> None:
        super().__init__(target)
        # 声明最终产物扩展名为 elf（对应 add_stages 最后一项）
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
        # 骨架与 S1 阶段均无自定义方言，留空即可
        pass

    def pack_metadata(self, metadata):
        return (
            metadata.num_warps,
            getattr(metadata, "num_ctas", 1),
            getattr(metadata, "shared", 0),
        )

    def get_codegen_implementation(self, options):
        return {}

    def get_module_map(self) -> Dict[str, ModuleType]:
        return {}

    @staticmethod
    def make_ttir(mod, metadata, options):
        """阶段 1：运行通用内联并从 TTIR 提取真实函数名。"""
        pm = ir.pass_manager(mod.context)
        pm.enable_debug()
        passes.common.add_inliner(pm)
        pm.run(mod, "coral_make_ttir")

        mod_str = str(mod)
        names = re.findall(r"tt\.func\s+(?:public\s+)?@([a-zA-Z_][a-zA-Z0-9_]*)", mod_str)
        metadata["name"] = names[0] if names else "coral_kernel"
        metadata["num_warps"] = options.num_warps
        return mod

    @staticmethod
    def make_llir(src, metadata, options):
        """阶段 2：骨架阶段先透传字符串；S1-01 替换为真实 TTIR->RV32 LLVM IR。"""
        return str(src)

    @staticmethod
    def make_elf(src, metadata, options):
        """阶段 3：必须返回 bytes；骨架阶段返回占位字节（不代表真实执行）。"""
        return f"/* Coral RISC-V Binary: {metadata.get('name', 'kernel')} */\n".encode("utf-8")

    def add_stages(self, stages: dict, options: CoralOptions, language: Language) -> None:
        stages["ttir"] = lambda src, metadata: self.make_ttir(src, metadata, options)
        stages["llir"] = lambda src, metadata: self.make_llir(src, metadata, options)
        stages["elf"]  = lambda src, metadata: self.make_elf(src, metadata, options)
```

---

### Step 7：顶层挂载 `setup.py`、建立软链接并构建

1. 修改 `triton-coral/setup.py` 第 400 行左右：
   ```python
   backends = [*BackendInstaller.copy(["nvidia", "amd", "coral"]), *BackendInstaller.copy_externals()]
   ```
2. 使用固定 Coral LLVM 24 构建脚本重编 `libtriton.so`（遵循 `triton-coral/docs/coral-llvm.md`）：
   ```bash
   bash /home/compiler-1/work/coral/build-triton-llvm24-python.sh
   ```
3. 确保 In-tree 软链接存在（若未重跑 `pip install -e .` 刷新 `entry_points`，则必须有软链接并开启 `TRITON_BACKENDS_IN_TREE=1`）：
   ```bash
   ln -sfn /home/compiler-1/work/coral/triton-coral/third_party/coral/backend \
           /home/compiler-1/work/coral/triton-coral/python/triton/backends/coral
   ```

---

### Step 8：骨架冒烟测试（`third_party/coral/unittest/test1.py`）

- **做什么**：验证后端列表发现 `coral`、C++ `coral.hello()` 可调、以及 `ASTSource → compile()` 跑通。
- **验证命令**：
  ```bash
  TRITON_BACKENDS_IN_TREE=1 TRITON_DEFAULT_BACKEND=coral \
    /home/compiler-1/work/coral/triton-coral/.venv/bin/python \
    /home/compiler-1/work/coral/triton-coral/third_party/coral/unittest/test1.py
  ```
- **通过标准**：输出 `['nvidia', 'amd', 'coral']`、`Hello from Coral backend!`、真实函数名 `add_kernel` 与非空 `bytes`。

#### 骨架阶段常见报错速查

| 现象 | 原因 | 解决 |
| :--- | :--- | :--- |
| `backends` 里没有 `coral`，但 `coral.hello()` 成功 | 缺 `python/triton/backends/coral` 软链接，或未设 `TRITON_BACKENDS_IN_TREE=1` | 建软链接并加 `TRITON_BACKENDS_IN_TREE=1` |
| `driver.c:1:10: fatal error: cuda.h: No such file or directory` | `coral` 未激活，Triton 回退去初始化 NVIDIA 驱动 | 设置 `TRITON_DEFAULT_BACKEND=coral` |
| `triton_coral.cc` 编译报 `module_` 不存在或符号未定义 | 混用了 `pybind11` 和 `nanobind` | 统一用 `<nanobind/nanobind.h>`、`py::module_ &` 与 `nanobind-static` |

---

## 第二段：接下来怎么做（拆成 4 个极小步，每次只写一点）

骨架（Step 1～8）已经完成。接下来进入 [plan.md](plan.md) 的 **S0-03 + S1-01**，拆成 **4 个极小步**，你每次只实现其中一小步、写完后让我帮你核对和跑测试！

---

### 下一步 · Micro-Step 1（对应 S0-03）：补齐 `CoralOptions`，让 `copy` 和 `add1` 都产出真实 TTIR

- **这一小步的目标**：不写任何 C++，只改 `compiler.py` 的 `CoralOptions`，让我们 S1 的两个真实源程序都能顺利通过 Triton 前端生成 TTIR，并看清 TTIR 长什么样。
- **支持什么 Triton 语法**：
  1. 单元素 INT32 拷贝：`x = tl.load(in_ptr); tl.store(out_ptr, x)`（参数 `*i32`）
  2. 单元素 INT32 加一：`x = tl.load(in_ptr); tl.store(out_ptr, x + 1)`（参数 `*i32`）
- **加入了什么方言**：**不加任何新方言**（纯 Triton 前端原生 `tt` + MLIR 标准 `arith`）。
- **明确不支持什么语法**：`tl.arange`、`tensor<Nxi32>`、`mask`/`other`、`tl.program_id`、浮点 `fp32`。
- **为什么要改 `CoralOptions`**：实测 `x + 1` 时，Triton 前端 `semantic.py` 会读取 `options.sanitize_overflow`；缺少它直接报 `AttributeError`。同时补齐其他前端可能读取的只读属性，并把 `sanitize_overflow` 设为 `False`（避免在裸机 S1 插入 GPU `tt.assert`）。

**你只需修改 `third_party/coral/backend/compiler.py` 中的 `CoralOptions`**（并在 `make_ttir` 加一行 `passes.common.add_canonicalizer(pm)`）：
```python
@dataclass(frozen=True)
class CoralOptions:
    arch: str = "rv32im"
    backend_name: str = "coral"
    num_warps: int = 1
    num_ctas: int = 1
    num_stages: int = 1
    debug: bool = False
    sanitize_overflow: bool = False               # 必须：x + 1 时前端语义层会读取
    enable_fp_fusion: bool = True
    supported_fp8_dtypes: Tuple[str, ...] = ()
    deprecated_fp8_dot_operand_dtypes: Tuple[str, ...] = ()
    default_dot_input_precision: str = "ieee"
    allowed_dot_input_precisions: Tuple[str, ...] = ("ieee",)
    max_num_imprecise_acc_default: int = 0
```

**本小步验收标准**：编写脚本编译 `copy_i32_kernel` 和 `add1_i32_kernel`，打印 `compiled.asm["ttir"]`，能看到精确的标量 TTIR：
```mlir
// copy_i32_kernel 预期 TTIR
module {
  tt.func public @copy_i32_kernel(%in_ptr: !tt.ptr<i32>, %out_ptr: !tt.ptr<i32>) {
    %x = tt.load %in_ptr : !tt.ptr<i32>
    tt.store %out_ptr, %x : !tt.ptr<i32>
    tt.return
  }
}

// add1_i32_kernel 预期 TTIR（多出 arith.constant 和 arith.addi）
module {
  tt.func public @add1_i32_kernel(%in_ptr: !tt.ptr<i32>, %out_ptr: !tt.ptr<i32>) {
    %c1_i32 = arith.constant 1 : i32
    %x = tt.load %in_ptr : !tt.ptr<i32>
    %y = arith.addi %x, %c1_i32 : i32
    tt.store %out_ptr, %y : !tt.ptr<i32>
    tt.return
  }
}
```
> 完成 Micro-Step 1 后发给我确认，我们再做 Micro-Step 2！

---

### 下一步 · Micro-Step 2（对应 S1-01a）：搭 `MinimalTritonToLLVM` Pass 架子（只支持空函数与指针参数）

- **这一小步的目标**：把 C++ MLIR Pass 的 TableGen、CMake、`triton-opt` 注册和 `triton_coral.cc` 绑定打通，**只转换最简单的空函数**，先不写 load/store/arith！
- **支持什么 Triton / MLIR 语法**：
  - 类型：`!tt.ptr<i32>`（标量指针）$\to$ `!llvm.ptr`（**显式拒绝** `!tt.ptr<tensor<...>>`）
  - Op：`tt.func` $\to$ `llvm.func`（外链接，保留真实函数名）；`tt.return` $\to$ `llvm.return`
- **加入了什么方言**：**不新增自定义方言**，仅依赖 MLIR 标准 `LLVM` 方言（`mlir::LLVM::LLVMDialect`）和已有 `TritonDialect`。
- **明确不支持什么语法**：`tt.load`、`tt.store`、`arith.*`、`tl.arange`（出现即报错）。
- **需要改动/新建的文件**：
  1. `third_party/coral/include/CMakeLists.txt` + `include/MinimalTritonToLLVM/{CMakeLists.txt, Passes.td, Passes.h}`
  2. `third_party/coral/lib/CMakeLists.txt` + `lib/Conversion/CMakeLists.txt` + `lib/Conversion/MinimalTritonToLLVM/{CMakeLists.txt, MinimalTritonToLLVM.cpp}`
  3. `third_party/coral/CMakeLists.txt`（加 `add_subdirectory(include)`、`add_subdirectory(lib)` 与 `LINK_LIBS CoralMinimalTritonToLLVM`）
  4. `bin/RegisterTritonDialects.h`（注册 `registerCoralMinimalTritonToLLVMPasses()`）
- **本小步验收标准**：
  使用已有真实源码 [empty_kernel](examples/kernels.py)，不把 `p: *i32` 当成 Python 类型注解：

  ```python
  @triton.jit
  def empty_kernel(X, Y):
      pass
  # ASTSource.signature = {"X": "*i32", "Y": "*i32"}
  ```

  沿用 plan.md 中的 `CORAL_PYTHON`、`CORAL_TUTORIAL`、`CORAL_TEST_OUT` 环境变量，先生成并验证源 TTIR：

  ```bash
  "$CORAL_PYTHON" "$CORAL_TUTORIAL/dump_ttir.py" --stage S1 --case S1.empty.frontend --output "$CORAL_TEST_OUT/empty"
  ```

  完成并注册本微步的 pass、构建 `triton-opt` 后，对上一步生成的文件运行：
  ```bash
  triton-opt --convert-coral-minimal-triton-to-llvm "$CORAL_TEST_OUT/empty/S1.empty.frontend.0.ttir"
  ```
  输出应有 `llvm.func @empty_kernel(%arg0: !llvm.ptr, %arg1: !llvm.ptr) { llvm.return }`，并通过实际 MLIR verifier。接通真实 pass 适配器后，运行 `run_stage.py --stage S1 --case S1.empty.llvm --adapter "$CORAL_ADAPTER" --output "$CORAL_TEST_OUT/empty-lowered"`，mode=ir 只要求真实 TTIR、LLVM方言 checkpoint 和 verifier，不要求 load/store、ELF 或启动设备。该微步不计作 G1 执行通过。

---

### 下一步 · Micro-Step 3（对应 S1-01b）：加入标量 `i32` 访存（跑通 `copy_i32_kernel`）

- **这一小步的目标**：在 Micro-Step 2 的 Pass 中仅增加 2 个 Pattern：`ScalarLoadOpConversion` 与 `ScalarStoreOpConversion`。
- **支持什么 Triton / MLIR 语法**：
  - `x = tl.load(in_ptr)` $\Rightarrow$ `tt.load %ptr : !tt.ptr<i32>` $\to$ `llvm.load %ptr {alignment = 4 : i64} : !llvm.ptr -> i32`
  - `tl.store(out_ptr, x)` $\Rightarrow$ `tt.store %ptr, %x : !tt.ptr<i32>` $\to$ `llvm.store %x, %ptr {alignment = 4 : i64} : i32, !llvm.ptr`
- **加入了什么方言**：**不新增方言**。
- **明确不支持什么语法**：
  - 带 `mask` 或 `other` 的 load/store（明确 `notifyMatchFailure` 拒绝，留到 S2-02）；
  - 非 `i32` 类型或 `tensor` 类型访存（明确拒绝）。
- **本小步验收标准**：`triton-opt --convert-coral-minimal-triton-to-llvm` 对 `copy_i32_kernel` 产出合法的 `llvm.load` / `llvm.store` MLIR。

---

### 下一步 · Micro-Step 4（对应 S1-01c）：接入整数算术 + RV32 Triple/DataLayout + LLVM Verifier（跑通 `add1_i32_kernel`）

- **这一小步的目标**：把 `arith` / `cf` 接入标准 MLIR 转换，加上 RV32 32 位指针 DataLayout 与 Triple，并通过 `triton_coral.cc` 接到 `compiler.py` 的 `make_llir`。
- **支持什么 Triton / MLIR 语法**：
  - 标量 INT32 整数算术（`+`, `-`, `*`, 位运算等），对应 `arith.constant`, `arith.addi`, `arith.subi`, `arith.muli` 等 $\to$ 复用 MLIR 标准 `arith::populateArithToLLVMConversionPatterns` 与 `cf::populateControlFlowToLLVMConversionPatterns`；
  - 模块级写入实测自固定 Coral SDK 的 RV32 契约：
    - `target datalayout = "e-m:e-p:32:32-i64:64-n32-S128"`
    - `target triple = "riscv32-unknown-unknown-elf"`
  - 注意遵守 [plan.md](plan.md) D03：INT32 加法按 32 位模运算，**不凭猜测添加 `nsw`/`nuw`**。
- **加入了什么方言**：**仍不新增自定义方言**（仅复用 MLIR 标准 `arith` / `cf` / `LLVM`）。
- **明确不支持什么语法**：`tl.arange(0, BLOCK)`、`tensor<Nxi32>`、浮点、原子操作（测试必须断言这些语法报错而不是静默忽略）。
- **本小步验收标准**：
  - Python 运行 `copy_i32_kernel` 和 `add1_i32_kernel`，`compiled.asm["llir"]` 通过 `llvm::verifyModule`，输出带 RV32 triple/datalayout 的真实 LLVM IR；
  - `copy_i32_kernel` 不含 `add i32`，`add1_i32_kernel` 含 `add i32`（证明 IR 随源程序变化，非固定模板）；
  - 含 `tl.arange` 的 kernel 明确抛出编译错误。

---

> **建议节奏**：现在就只做 **Micro-Step 1（S0-03）**——只需改 `compiler.py` 的 `CoralOptions` 并跑通 `copy_i32_kernel` 与 `add1_i32_kernel` 打印 TTIR。写完后告诉我，我来帮你检查代码和输出，确认无误后再进入 Micro-Step 2！
