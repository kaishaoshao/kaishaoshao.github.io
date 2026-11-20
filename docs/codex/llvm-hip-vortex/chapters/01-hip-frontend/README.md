# 第 1 章 读懂 HIP 前端（L01）

从 `store42` 和一个 device helper 出发，观察 Clang 怎样处理 HIP 属性、调用限制和设备 IR。完成后，你能指出哪一步已经有 Clang 实现，哪一步需要接到 Vortex 的入口与执行链。先在 WSL 准备三节共用的工具和输入。[准备实验](#准备实验)

## 本章目录

- [L01.1 宏展开与属性 AST](01-attributes.md)
- [L01.2 调用侧限制与启动表达式](02-sema-launch.md)
- [L01.3 设备 IR 与后续接口](03-device-ir.md)

## 准备实验

在 **WSL Ubuntu-22.04 的 Bash** 中执行。文档仓库路径按本机位置设置；其他机器修改 VORTEX_DOCS_ROOT 即可。

```bash
export VORTEX_WORD_ROOT=/home/kaikai/vortex-word
export VORTEX_DOCS_ROOT=/mnt/c/Users/20327/Documents/ChatGPT/learn/kaishaoshao.github.io/docs/codex/llvm-hip-vortex
export HIP_TUTORIAL_CLANG="$VORTEX_WORD_ROOT/build/llvm/bin/clang++"
"$HIP_TUTORIAL_CLANG" --version
mkdir -p "$VORTEX_WORD_ROOT/artifacts/tutorial/l01"
export L01_OUT="$(mktemp -d "$VORTEX_WORD_ROOT/artifacts/tutorial/l01/manual-XXXXXX")"
cp "$VORTEX_DOCS_ROOT/examples/l01/"*.hip "$L01_OUT/"
printf '本次输出：%s\n' "$L01_OUT"
```

当前优先使用你构建的 LLVM 23。需要参考对照时，将 HIP_TUTORIAL_CLANG 显式改为 `/home/kaikai/vortex-word/tools/llvm-vortex/bin/clang++`，并使用新的输出目录，分别记录版本。不要因目录名含 llvm 就假定它是新编译器。

可以先运行汇总检查，再回到三节小课逐条理解命令。

```bash
python3 "$VORTEX_DOCS_ROOT/examples/run_l01.py" \
  --clang "$HIP_TUTORIAL_CLANG" \
  --output-root "$VORTEX_WORD_ROOT/artifacts/tutorial/l01"
```

检查脚本保存输入副本、SHA-256、完整命令、stdout/stderr、IR 和 report.json；每次创建独立目录。它检查七项前端观察（包括版本），两个反例应由编译器拒绝；只有诊断内容也匹配才算该反例通过。脚本通过不证明任何设备执行能力。

## 完成这一章

| 检查 | 应观察到什么 | 尚未证明什么 |
|---|---|---|
| 预处理、属性 AST | 宏展开、CUDAGlobalAttr/CUDADeviceAttr | Vortex kernel ABI |
| 两种非法调用 | 对应函数的调用侧诊断 | 完整 HIP/C++ 语义覆盖 |
| 启动 AST | CUDAKernelCallExpr、配置函数 | host runtime 已实现 |
| 设备 IR | RISC-V triple/DataLayout、函数和 store | 正式 driver、镜像与 SimX 执行 |

保存本次输出，并使用 [证据模板](../../evidence-template.md) 写下你的解释。run_l01.py 的 PASS 是观察检查通过；整个课程交付还包含阅读与回答，不能自动完成 T00/T07/T08 整组。

2026-11-19 记录中，新 Clang 23.1.4 与参考 Clang 20.1.8 的七项前端观察均通过。[历史证据](../../plan.md#03-已核对的教学实验与证据边界)

---

[全书目录](../../tutorial.md) · [下一章](../02-vortex-codegen/README.md)
