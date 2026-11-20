# 1.1 节：确认工具链、后端发现与 C++ 扩展

## 1. 这节课做什么

**S0-01**。复跑已经实现的 Coral 后端骨架，核对 LLVM 版本、Python 发现的后端、C++ binding 和真实编译入口。源码基线为 `triton-coral» 的 `dev/triton-coral@4f045a9d77`，工具链锁定来自 `d63968303d`。

## 2. 核心代码实现

| 源码 | 现有实现 |
| --- | --- |
| `cmake/llvm-info.json`、`docs/coral-llvm.md` | LLVM `24.0.0git` 和基础提交 `6cce5bca3b90`，固定 Coral compiler 提交、Zvt 补丁哈希和目标列表。 |
| `setup.py` | `BackendInstaller.copy(["nvidia", "amd", "coral"])` 纳入 Coral，开发安装将它链接到 `python/triton/backends/coral`。 |
| `third_party/coral/backend/name.conf` | 内容为 `coral`。 |
| `third_party/coral/CMakeLists.txt` | 用 `add_triton_plugin` 创建 `TritonCoral`，链接 Python 与 nanobind。 |
| `third_party/coral/triton_coral.cc` | `init_triton_coral` 将 `hello()` 暴露为 `triton._C.libtriton.coral.hello()`。 |
| `third_party/coral/backend/driver.py` | 提供目标查询和类型映射。 |
| `third_party/coral/unittest/test1.py` | 用真实 `@triton.jit` 源码和 `ASTSource` 验证 Python 到编译产物缓存。 |

`third_party/coral/CMakeLists.txt` 的现有内容。

```cmake
if(TRITON_BUILD_PYTHON_MODULE)
  add_triton_plugin(TritonCoral ${CMAKE_CURRENT_SOURCE_DIR}/triton_coral.cc)
  target_link_libraries(TritonCoral PRIVATE Python3::Module nanobind-static)
endif()
```

`third_party/coral/triton_coral.cc` 的导出入口。

```cpp
#include <nanobind/nanobind.h>

namespace py = nanobind;

void init_triton_coral(py::module_ &m) {
  m.doc() = "Python bindings to the Coral Triton backend";
  m.def("hello", []() {
    return "Hello from Coral backend!";
  });
}
```

## 3. 解释说明与注释

`test1.py` 里的函数名为 `add_kernel`，函数体实际是 `tl.load(x_ptr)` 后 `tl.store(y_ptr, x)`。测试通过 `CoralDriver.get_current_target()` 得到 `GPUTarget("coral", "rv32imf_zve32x", 1)`，再用 `compile(ASTSource(...), target=...)` 选择 Coral 编译器。该 driver 当前的 `is_active()` 恒真，benchmark 返回占位零值。实际设备发现、装载、启动和计时对应 [4.1 节](../ch04-jit-runtime/01-driver-dispatch.md)。

`make_elf()` 当前返回以 `/* Coral RISC-V Binary:` 开头的占位字节。冒烟测试验收后端发现、绑定、编译入口和产物缓存。

## 4. 测试与验证代码

在 compiler-1 使用已有构建。

```bash
cd /home/compiler-1/work/coral/triton-coral
export TRITON_BACKENDS_IN_TREE=1 TRITON_DEFAULT_BACKEND=coral
export TRITON_CACHE_DIR="$(mktemp -d /tmp/coral-smoke-XXXXXX)"
sdk=/home/compiler-1/work/coral/coralnpu-compiler/out/llvm-zvt/install
"$sdk/bin/llvm-config" --version
.venv/bin/python third_party/coral/unittest/test1.py
```

2026-11-20 实测为 `24.0.0git`，后端列表含 `coral`，C++ 返回 `Hello from Coral backend!`，缓存产物以 `b'/* Coral RISC-V Binary: add_kernel */` 开头。继续 [1.2 节的参数 ABI](02-abi-contract.md)。
