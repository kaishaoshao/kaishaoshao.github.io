# 01. Triton Coral 后端骨架接入教程

更新日期：2026-11-18（Asia/Shanghai）。本教程记录**已实测验证通过**的后端骨架实现（对应 `triton-coral` 分支 `dev/triton-coral` 提交 `4f045a9d77`）。

配套文件：[实施计划](../plan.md)、[任务数据](../plan.json)、[任务表](../tasks.xlsx)、[总目录](../../README.md)。

本篇是提交 `4f045a9d77` 的骨架复盘，不能作为后续能力的验收清单。下一步按 [起步微步](../backend-skeleton.md) 推进；当前阶段白名单、必需 ABI v3 与测试协议2统一维护在 `plan.json`/`plan.md`。空函数已有 `S1.empty.frontend` 和 `S1.empty.llvm` 独立用例，新增语法须分别验证 AOT/JIT。

---

## 1. 本篇目标与验证边界

本篇完成在 `triton-coral`（Triton 3.9 + Coral LLVM 24 + nanobind 2.10.2）中**从 0 到 1 接入 In-tree `coral` 后端骨架**。

- **本篇支持什么语法**：`@triton.jit` 最小单元素 `tl.load(ptr)` / `tl.store(ptr, x)`（走通 `ASTSource → TTIR → 占位 ELF`）。
- **本篇用到什么方言**：**不新增任何自定义方言**，仅使用 Triton 前端原生 `tt`（`TritonDialect`）。
- **验证边界**：本篇验证的是 **Python 后端发现 + C++ nanobind 扩展调用 + `add_stages` 编译与缓存框架闭环**；`make_elf` 返回的是占位字节流，**不代表真实 Coral RTL 执行通过**。

### 为什么选 In-tree（同时兼容 Out-of-tree）？

1. 当前仓库本身即 `triton-coral` 定制分支，Coral（RV32IMF_Zve32x + 8 KiB ITCM / 32 KiB DTCM + Zvt）与 GPU SIMT 差异大，后续需要与顶层 CMake、`triton-opt` 及工具链联动调试。
2. In-tree 直接通过 `add_triton_library` / `add_triton_plugin` 编入 `triton-opt` 和 `libtriton.so`，避免 Out-of-tree 在 `-fvisibility=hidden` 下的符号导出和 `TRITON_EXT_ENABLED` ABI 陷阱。
3. 全部 Coral 代码收敛在 `third_party/coral/` 内，并保留 `backend/name.conf`，未来如需抽离为 `TRITON_PLUGIN_DIRS` 外置插件几乎零迁移成本。

---

## 2. 目录结构与文件实现先后顺序

### 最终骨架目录树

```text
triton-coral/
├── setup.py                              # [修改] 将 "coral" 加入内置后端列表
└── third_party/coral/
    ├── CMakeLists.txt                    # [新建] 注册 TritonCoral 插件并链接 nanobind-static
    ├── triton_coral.cc                   # [新建] nanobind C++ 扩展入口 init_triton_coral
    ├── backend/
    │   ├── name.conf                     # [新建] 后端唯一名称标识（兼容外置插件）
    │   ├── __init__.py                   # [新建] Python 包标记
    │   ├── driver.py                     # [新建] 运行时驱动 CoralDriver(DriverBase)
    │   └── compiler.py                   # [新建] 编译流水线 CoralBackend(BaseBackend)
    └── unittest/
        └── test1.py                      # [新建] 端到端骨架冒烟验证脚本
```

### 为什么必须按以下顺序编写？

Triton 构建与加载存在严格的依赖拓扑：

```text
Step 1：建立目录身份标识
   third_party/coral/backend/name.conf + __init__.py
              ↓
Step 2：C++ nanobind 扩展入口（提供 libtriton.so 所需符号）
   third_party/coral/triton_coral.cc
              ↓
Step 3：CMake 插件挂载（将 C++ 对象库接入 libtriton.so）
   third_party/coral/CMakeLists.txt
              ↓
Step 4：Python 运行时驱动（向编译器提供 GPUTarget 目标描述）
   third_party/coral/backend/driver.py
              ↓
Step 5：Python 编译器与 3 段式 add_stages 流水线
   third_party/coral/backend/compiler.py
              ↓
Step 6：顶层 setup.py 挂载 + 构建 + 软链接 + 跑 test1.py 验收
```

---

## 3. Triton 底层发现与注册机制

### 3.1 C++ 侧链路（CMake + nanobind + `main.cc`）

1. `setup.py` 将内置后端列表拼为 `-DTRITON_CODEGEN_BACKENDS=nvidia;amd;coral` 传入 CMake。
2. 顶层 `CMakeLists.txt` 遍历 `TRITON_CODEGEN_BACKENDS`，依次执行 `add_subdirectory(third_party/${CODEGEN_BACKEND})`。
3. 后端自己的 `CMakeLists.txt` 调用 `add_triton_plugin(TritonCoral ...)`，把对象库追加到全局 `TRITON_PLUGINS` 属性中，最终统一链接进 `libtriton.so`。
4. 顶层 `CMakeLists.txt` 生成 `-DTRITON_BACKENDS_TUPLE=(nvidia,amd,coral,proton)`；`python/src/main.cc` 将其自动展开为：
   ```cpp
   void init_triton_coral(nanobind::module_ &m);
   ...
   {
     auto sub = m.def_submodule("coral");
     init_triton_coral(sub);
   }
   ```
5. **为什么链接 `nanobind-static` 而不是 `pybind11`？**
   当前 Triton 主线已全面迁移至 **nanobind 2.10.2**（体积更小、支持 Stable ABI）。顶层 `CMakeLists.txt` 通过 `nanobind_build_library(nanobind-static)` 构建统一静态库，所有后端必须链接 `nanobind-static` 且入口参数必须为 `nanobind::module_ &`（带下划线、左值引用）。

### 3.2 Python 侧链路（`backends/__init__.py` + `runtime/driver.py`）

1. **后端扫描（`python/triton/backends/__init__.py`）**：
   - 默认路径：读取 `entry_points().select(group="triton.backends")`（由 `pip install -e .` 写入）；
   - In-tree 快速路径：设置 `TRITON_BACKENDS_IN_TREE=1` 时，直接扫描 `python/triton/backends/` 下的子目录或软链接（`python/triton/backends/coral -> third_party/coral/backend`）。
2. **唯一具体子类校验**：`_find_concrete_subclasses()` 要求 `compiler.py` 中有且仅有 1 个 `BaseBackend` 非抽象子类，`driver.py` 中有且仅有 1 个 `DriverBase` 非抽象子类。
3. **活动驱动选择（`python/triton/runtime/driver.py`）**：
   - 若设置 `TRITON_DEFAULT_BACKEND=coral`，直接选用 `coral`；
   - 未设置时要求所有 `is_active() == True` 的驱动数量恰好为 1，否则报错或误回退到 NVIDIA 驱动。

---

## 4. 逐步骤完整代码、注释与作用说明

### Step 1：建立目录身份（`name.conf` + `__init__.py`）

**`third_party/coral/backend/name.conf`**
- **作用**：声明后端唯一名称 `coral`。纯 In-tree 模式下不强制，但保留一行 `coral` 即可同时兼容 `TRITON_PLUGIN_DIRS` 外置插件模式。
```text
coral
```

**`third_party/coral/backend/__init__.py`**
- **作用**：Python 包标记，使 `importlib.import_module("triton.backends.coral.compiler")` 合法。
```python
# Triton Coral backend Python package marker.
```

---

### Step 2：编写最小 C++ nanobind 扩展入口（`triton_coral.cc`）

- **作用**：导出 `init_triton_coral`，使 Python 可通过 `from triton._C.libtriton import coral` 访问 C++ 模块。

```cpp
//------------------------------------------------------------------------------
// Coral 后端 C++ nanobind 扩展入口
// 对应 python/src/main.cc 中由 TRITON_BACKENDS_TUPLE 自动展开的声明与调用：
//   void init_triton_coral(nanobind::module_ &m);
//------------------------------------------------------------------------------
#include <nanobind/nanobind.h>

namespace py = nanobind;

void init_triton_coral(py::module_ &m) {
  m.doc() = "Python bindings to the Coral Triton backend";

  // 最小冒烟接口：验证 CMake 编译、libtriton.so 链接与 Python 导入闭环
  m.def("hello", []() {
    return "Hello from Coral backend!";
  });
}
```

---

### Step 3：接入 CMake 插件构建（`third_party/coral/CMakeLists.txt`）

- **作用**：将 `triton_coral.cc` 注册为 Triton 插件对象库并链接 `nanobind-static`。

```cmake
if(TRITON_BUILD_PYTHON_MODULE)
  # 创建 OBJECT library 并自动加入全局 TRITON_PLUGINS，由 libtriton.so 链接
  add_triton_plugin(TritonCoral ${CMAKE_CURRENT_SOURCE_DIR}/triton_coral.cc)

  # 链接 Python 头文件与顶层统一构建的 nanobind-static（勿混用 pybind11）
  target_link_libraries(TritonCoral PRIVATE Python3::Module nanobind-static)
endif()
```

---

### Step 4：编写最小运行时驱动（`third_party/coral/backend/driver.py`）

- **作用**：向 Triton 运行时提供设备检测、`GPUTarget` 目标描述、类型映射与基准测试接口。

```python
#------------------------------------------------------------------------------
# Triton Coral 运行时驱动骨架
# 要求：有且仅有 1 个继承自 DriverBase 的非抽象具体子类
#------------------------------------------------------------------------------
from __future__ import annotations

import os
from triton.backends.compiler import GPUTarget
from triton.backends.driver import DriverBase


class CoralDriver(DriverBase):

    def __init__(self):
        super().__init__()

    @classmethod
    def is_active(cls) -> bool:
        # 骨架调试阶段返回 True；S3-01 必须替换为真实仿真桥/硬件可用性检测
        return os.environ.get("TRITON_DEFAULT_BACKEND", "") == "coral" or True

    def get_current_target(self) -> GPUTarget:
        # Coral NPU 为 32 位 RISC-V（RV32IMF_Zve32x）；非 SIMT GPU，故 warp_size=1
        return GPUTarget("coral", arch="rv32imf_zve32x", warp_size=1)

    def map_python_to_cpp_type(self, ty: str) -> str:
        # 将 Triton 类型签名（如 '*fp32', 'i32'）映射为 C 启动器参数类型
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
        # 机器可能未安装 torch，安全降级返回 cpu 或 None
        try:
            import torch
            return torch.device("cpu")
        except Exception:
            return None

    def get_benchmarker(self):
        # 骨架占位；S3-01 替换为真实执行计时
        def _benchmark(kernel_call, *, quantiles=None, **kwargs):
            return [0.0] * (len(quantiles) if quantiles else 1)

        return _benchmark
```

---

### Step 5：编写编译器核心与 3 段式 `add_stages`（`third_party/coral/backend/compiler.py`）

- **作用**：实现 `CoralOptions`（选项与缓存哈希）和 `CoralBackend(BaseBackend)`（`ttir → llir → elf` 编译流水线）。
- **`add_stages` 三条铁律**：
  1. 字典按插入顺序执行，前一步输出传给下一步；
  2. 必须写入 `metadata["name"]` 和 `metadata["num_warps"]`，否则 Triton 缓存写盘会报错；
  3. **最后一个 stage（`elf`）必须返回 `bytes`**，中间 stage 返回 MLIR Module 或 `str`。

```python
#------------------------------------------------------------------------------
# Triton Coral 编译器骨架
# 要求：有且仅有 1 个继承自 BaseBackend 的非抽象具体子类
#------------------------------------------------------------------------------
import hashlib
import re
from dataclasses import dataclass
from typing import Dict
from types import ModuleType

from triton.backends.compiler import BaseBackend, GPUTarget, Language
from triton._C.libtriton import ir, passes, llvm, coral


@dataclass(frozen=True)
class CoralOptions:
    """不可变编译选项；hash() 作为 Triton 磁盘缓存键的一部分。"""
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
        # 骨架阶段不引入自定义 Dialect
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
        """阶段 1：运行通用内联，并从 TTIR 提取真实函数名写入 metadata。"""
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
        """阶段 2：骨架阶段先透传文本；后续 S1-01 替换为真实 TTIR->RV32 LLVM IR。"""
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

### Step 6：挂载 `setup.py`、构建、建立软链接并运行冒烟测试

1. **修改 `triton-coral/setup.py`**（第 400 行左右）：
   ```python
   backends = [*BackendInstaller.copy(["nvidia", "amd", "coral"]), *BackendInstaller.copy_externals()]
   ```
   `BackendInstaller.copy` 会自动校验 `backend/{compiler.py, driver.py}` 存在、向 CMake 传入 `TRITON_CODEGEN_BACKENDS`、并在 `pip install -e .` 时创建软链接和 `entry_points`。

2. **使用固定 Coral LLVM 24 构建脚本重编 `libtriton.so`**：
   ```bash
   bash /home/compiler-1/work/coral/build-triton-llvm24-python.sh
   ```

3. **确保 In-tree 软链接存在**（如果只重编替换了 `libtriton.so` 而未重跑 `pip install -e .`）：
   ```bash
   ln -sfn /home/compiler-1/work/coral/triton-coral/third_party/coral/backend \
           /home/compiler-1/work/coral/triton-coral/python/triton/backends/coral
   ```

4. **编写并运行 `third_party/coral/unittest/test1.py`**：
   ```python
   import os
   os.environ.setdefault("TRITON_DEFAULT_BACKEND", "coral")

   import triton
   from triton.backends import backends
   print("1. 注册的后端列表:", list(backends.keys()))

   from triton._C.libtriton import coral
   print("2. C++ 接口调用:", coral.hello())

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
   print("3. 端到端编译成功! Kernel 名称:", compiled.name)
   print("4. 生成的二进制 payload:", compiled.asm["elf"][:40])
   ```

5. **运行与实测结果**：
   ```bash
   PYTHONPATH=/home/compiler-1/work/coral/triton-coral/python \
   TRITON_BACKENDS_IN_TREE=1 TRITON_DEFAULT_BACKEND=coral \
     python3 /home/compiler-1/work/coral/triton-coral/third_party/coral/unittest/test1.py
   ```
   实测输出：
   ```text
   1. 注册的后端列表: ['nvidia', 'amd', 'coral']
   2. C++ 接口调用: Hello from Coral backend!
   3. 端到端编译成功! Kernel 名称: add_kernel
   4. 生成的二进制 payload: b'/* Coral RISC-V Binary: add_kernel */\n'
   ```

---

## 5. 实测踩坑速查表

| 现象 / 报错 | 根因 | 解决方法 |
| :--- | :--- | :--- |
| `coral.hello()` 成功，但 `backends` 列表只有 `['amd', 'nvidia']` | 缺少 `python/triton/backends/coral` 软链接，或未重跑 `pip install -e .` 刷新 `entry_points` | 建立软链接并设置 `TRITON_BACKENDS_IN_TREE=1` |
| `third_party/nvidia/backend/driver.c:1:10: fatal error: cuda.h: No such file or directory` | `coral` 未被激活，Triton 回退去初始化 NVIDIA 驱动并用 `gcc` 编译 `driver.c` | 设置 `TRITON_DEFAULT_BACKEND=coral` 并确认 `coral` 在 `backends` 中 |
| 编译 `triton_coral.cc` 报 `module_` 不存在或链接找不到 `init_triton_coral` | 混用了旧版 `pybind11` 和当前仓库的 `nanobind` | 统一使用 `#include <nanobind/nanobind.h>`、`py::module_ &` 与 `nanobind-static` |
| `compile()` 收尾或缓存报错 | `add_stages` 最后一个 stage 返回的不是 `bytes`，或未写入 `metadata["name"]` | 保证末 stage 返回 `bytes` 且在 `make_ttir` 中填充 `metadata["name"]` |

---

> 后续教程（`02-...` 起）将在你亲手完成并实测通过对应小步代码后再逐篇整理沉淀到本目录中。下一步进度与语法白名单见 [实施计划](../plan.md)。

