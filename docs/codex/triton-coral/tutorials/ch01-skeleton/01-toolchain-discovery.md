# 1.1 节：确认工具链、后端发现与 C++ 扩展

## 1. 这节课做什么
- **功能目标**：确认 LLVM 锁定信息、后端发现与 C++ 扩展。
- **支持语法**：`@triton.jit 标量拷贝（仅用于冒烟探测）`
- **涉及方言**：原生 tt 方言，C++ nanobind 插件绑定
- **阶段标记**：`S0-01`（所属章节：第 1 章：验证 Triton 后端发现与 C++ 插件骨架）
- **实现注意**：确认解释器来自当前 checkout。避免把环境中其他版本的 libtriton 当作当前构建。

## 2. 核心代码实现
```python
# third_party/coral/backend/name.conf
coral
```

```cpp
// third_party/coral/triton_coral.cc
#include <nanobind/nanobind.h>
namespace py = nanobind;

void init_triton_coral(py::module_ &m) {
  m.def("hello", []() { return "Hello from Coral backend!"; });
}
```

```python
# third_party/coral/backend/driver.py
class CoralDriver(DriverBase):
  def __init__(self):
    self.utils = CoralUtils()
  def get_current_target(self):
    return GPUTarget("coral", "rv32imf_zve32x", 1)
```

## 3. 解释说明与注释
- **In-tree 发现机制**：当设置 `TRITON_BACKENDS_IN_TREE=1` 时，Triton 扫描 `python/triton/backends/` 下的符号链接。软链接 `coral -> third_party/coral/backend` 使得 Triton 能够发现 `CoralBackend`。
- **默认后端锁定**：设置 `TRITON_DEFAULT_BACKEND=coral` 强制优先使用 Coral driver，防止未安装 CUDA 的机器错误回退到 NVIDIA driver 寻找 `cuda.h`。
- **Nanobind 模块导出**：Triton 3.9 采用 nanobind 2.10.2。C++ 扩展必须导出 `void init_triton_coral(py::module_ &m)`。

## 4. 测试与验证代码
```bash
cd /home/compiler-1/work/coral/triton-coral
TRITON_BACKENDS_IN_TREE=1 TRITON_DEFAULT_BACKEND=coral \
  .venv/bin/python third_party/coral/unittest/test1.py
```

**预期输出**：
- 后端发现列表中包含 `'coral'`
- C++ 扩展返回 `Hello from Coral backend!`
- 编译产物以 `/* Coral RISC-V Binary:` 开头，端到端骨架自检成功。
