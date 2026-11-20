# 1.3 节：验证已接入的 CoralOptions 与 TTIR

## 1. 这节课做什么

**S0-03**。使用 compiler-1 上已实现的正式前端选项生成 TTIR，验证两个有效目标与目标拒绝路径。

## 2. 核心代码实现

`third_party/coral/backend/compiler.py` 中的 `CoralOptions` 和目标匹配如下。其余已有方法保留。该实现已在 compiler-1 工作树验证，当前提交 `4f045a9d77` 还未记录这两处改动。

```python
@dataclass(frozen=True)
class CoralOptions:
  arch: str = "coral-rv32"
  num_warps: int = 1
  num_stages: int = 1
  debug: bool = False
  sanitize_overflow: bool = False
```

```python
  @staticmethod
  def supports_target(target: GPUTarget) -> bool:
    return (
      target.backend == "coral"
      and target.arch in ("coral-rv32", "rv32imf_zve32x")
      and target.warp_size == 1
    )
```

## 3. 解释说明与注释

`parse_options()` 按 dataclass 字段筛选调用方选项，返回 `CoralOptions`。Triton 前端生成整数加法时读取 `sanitize_overflow`，此处关闭溢出插桩。`add_stages()` 注册 `ttir`、`llir`、`elf` 三阶段。已有 `make_ttir()` 创建 PassManager，跑 inliner，并从 module 文本取符号名到 metadata。`make_llir()` 当前返回输入的文本，下一节才开始替换。

## 4. 测试与验证代码

```bash
cd /home/compiler-1/work/coral/triton-coral
export TRITON_BACKENDS_IN_TREE=1 TRITON_DEFAULT_BACKEND=coral
examples=/home/compiler-1/learn/kaishaoshao.github.io/docs/codex/triton-coral/examples
out=$(mktemp -d /tmp/coral-s0-XXXXXX)

.venv/bin/python "$examples/dump_ttir.py" --stage S1 --cumulative \
  --case S0.frontend --case S1.empty.frontend --case S1.copy --case S1.add \
  --backend-options --output "$out"

.venv/bin/python - <<'PY'
from triton.backends.compiler import GPUTarget
from triton.compiler.compiler import make_backend

for arch in ("coral-rv32", "rv32imf_zve32x"):
    target = GPUTarget("coral", arch, 1)
    assert make_backend(target).target == target

for target in (GPUTarget("coral", "coral-invalid", 1),
               GPUTarget("coral", "coral-rv32", 32)):
    try:
        make_backend(target)
    except RuntimeError as error:
        assert "0 compatible backends" in str(error), error
    else:
        raise AssertionError(target)

print("PASS: 2 legal Coral targets accepted, bad arch and warp_size rejected")
PY
```

2026-11-20 实测生成 5 份 TTIR，正负目标检查通过。继续 [2.1 节的空 kernel 转换](../ch02-scalar-single-core/01-empty-kernel-pass.md)。
