# 1.3 节：补齐 CoralOptions 正式选项与 TTIR 生成

## 1. 这节课做什么
- **功能目标**：让拷贝和加法通过正式 CoralOptions，并拒绝未知目标。
- **支持语法**：`scalar_copy, scalar_add 前端编译与选项校验`
- **涉及方言**：tt + arith.constant/addi
- **阶段标记**：`S0-03`（所属章节：第 1 章：验证 Triton 后端发现与 C++ 插件骨架）
- **实现注意**：教程默认补充选项。当前正式 `S1.add` 缺少 `sanitize_overflow`，先重现再修复。

## 2. 核心代码实现
```python
# third_party/coral/backend/compiler.py
@dataclass(frozen=True)
class CoralOptions:
  arch: str = "coral-rv32"
  num_warps: int = 1
  num_stages: int = 1
  debug: bool = False
  sanitize_overflow: bool = False

class CoralBackend(BaseBackend):
  @staticmethod
  def supports_target(target: GPUTarget) -> bool:
    return (
      target.backend == "coral"
      and target.arch in ("coral-rv32", "rv32imf_zve32x")
      and target.warp_size == 1
    )
```

## 3. 解释说明与注释
- **`sanitize_overflow: bool = False`**：Triton 默认前端在降低二元标量加减法时，会尝试读取 `builder.options.sanitize_overflow`。若未配置会报 `AttributeError`；若设为 True 会插入 GPU 端的溢出 trap/assert。
- **目标架构校验**：支持 `coral-rv32` 和 driver 原生架构 `rv32imf_zve32x`，拒绝非 Coral 目标。

## 4. 测试与验证代码
```bash
cd /home/compiler-1/work/coral/triton-coral
.venv/bin/python -c '
from triton.backends.compiler import GPUTarget
from triton.compiler.compiler import make_backend
b = make_backend(GPUTarget("coral", "coral-rv32", 1))
assert b.parse_options({}).sanitize_overflow is False
print("PASS: S0-03 选项校验成功")
'
```
