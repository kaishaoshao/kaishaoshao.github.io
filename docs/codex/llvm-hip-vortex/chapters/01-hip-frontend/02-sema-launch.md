# L01.2 调用侧限制与启动表达式

用两个非法调用和一个合法 launch，分开观察语义诊断与 `<<<>>>` 的 AST。

准备好 `HIP_TUTORIAL_CLANG` 与 `L01_OUT` 再继续。[实验环境](README.md#准备实验)

先检查 [illegal-host-call.hip](../../examples/l01/illegal-host-call.hip)。host 函数直接调用仅 device 可用的函数，下面的编译命令**预期非零退出并给出 device_only 的调用侧诊断**：

```bash
"$HIP_TUTORIAL_CLANG" -x hip --offload-host-only -nogpuinc -nogpulib \
  -fsyntax-only "$L01_OUT/illegal-host-call.hip" \
  > "$L01_OUT/host-to-device.stdout.txt" 2> "$L01_OUT/host-to-device.stderr.txt"
cat "$L01_OUT/host-to-device.stderr.txt"
```

反方向使用设备语义检查：[illegal-device-call.hip](../../examples/l01/illegal-device-call.hip) 中，kernel 调用 host_only，下面也预期被拒绝。host-only 成功不能代替这一项。

```bash
"$HIP_TUTORIAL_CLANG" -cc1 -triple riscv64-unknown-elf \
  -target-cpu generic-rv64 -target-feature +m -target-feature +f -target-feature +d \
  -target-abi lp64d -x hip -fcuda-is-device -fsyntax-only \
  "$L01_OUT/illegal-device-call.hip" \
  > "$L01_OUT/device-to-host.stdout.txt" 2> "$L01_OUT/device-to-host.stderr.txt"
cat "$L01_OUT/device-to-host.stderr.txt"
```

最后观察 [launch-ast.hip](../../examples/l01/launch-ast.hip)：

```bash
"$HIP_TUTORIAL_CLANG" -x hip --offload-host-only -nogpuinc -nogpulib \
  -fsyntax-only -Xclang -ast-dump "$L01_OUT/launch-ast.hip" \
  > "$L01_OUT/launch.ast.txt"
rg 'CUDAKernelCallExpr|__hipPushCallConfiguration' "$L01_OUT/launch.ast.txt"
```

预期命令成功，AST 中有 CUDAKernelCallExpr 和配置函数引用。该夹具里的 dim3 与 __hipPushCallConfiguration 声明只为 AST 实验服务；没有实现函数，也没有冻结正式 HIP ABI，不能链接成可运行应用。

自己做：在 AST 中分别指出 grid/block、普通 kernel 参数、隐式配置调用。源码入口为 `clang/lib/Sema/SemaCUDA.cpp`，先追调用侧判定与执行配置，再在 L05 阅读 host stub。不要为通过反例而删除函数属性。

---

[上一节 · L01.1](01-attributes.md) · [本章目录](README.md) · [下一节 · L01.3](03-device-ir.md)
