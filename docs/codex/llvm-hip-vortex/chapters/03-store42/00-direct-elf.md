# L03.0 直接用 SimX 运行 ELF

运行一个有 `_start` 的 RV64 ELF，确认新 Clang 生成的 `store42` 在 SimX 上计算正确。

## 先运行现有镜像

在 WSL 中使用已构建的 SimX 命令行程序。以下命令读取已保留的本机镜像，并在新的运行目录生成仿真日志。

```bash
root=/home/kaikai/vortex-word
simx="$root/vortex/build64/sim/simx/simx"
out="$root/artifacts/tutorial/l03/direct-elf-rpgekj_l"

run=$(mktemp -d "$root/artifacts/tutorial/l03/elf-check-XXXXXX")
(
  cd "$run" || exit 1
  "$simx" "$out/store42.elf"
  printf 'exit=%d\n' "$?"
  "$simx" "$out/wrong-expected.elf"
  printf 'exit=%d\n' "$?"
)
```

2026-11-19 的记录与 2026-11-20 的复跑一致。第一个进程退出 `0`，第二个退出 `1`。两份镜像使用同一个 `store42.o`，检查程序分别期望读到 42 和 43。第二次运行用于确认检查程序能识别错误结果。

## ELF 如何启动

```text
store42.hip → 新 Clang → store42.o
                             ↓ 链接 check_store42.S 对应的设备对象
SimX → ELF e_entry → _start → store42(out) → 检查内存 → 退出码
```

- **操作** 打开实验目录中的 `check_store42.S`。它建立栈，把已初始化为 `-1` 的输出地址放到 `a0`，调用 `store42`，比对输出后将状态写到 `VX_MEM_IO_EXIT_CODE` 并结束执行。目录内的 `*.command.json` 保存编译和链接的参数，`*-simx.log` 保存两次运行结果。
- **测试与通过标准** 用 `llvm-readelf -h -l -s` 找到 `ET_EXEC`、入口地址、装载段和 `_start`。比对上面的两种退出码。SimX 命令行按 ELF 的装载段和入口执行，默认单线程配置适合这节的检查。
- **实现注意** `store42.o` 需要先链接成 ELF。直接启动时，`_start` 已经把输出地址作为函数参数准备好，设备代码可以直接调用 `store42`。随后用 SDK 启动时，`a0` 收到的是参数区地址，由 wrapper 解包。[SDK 启动契约](../../compiler-sim-contract.md#l03-walkthrough)

---

[上一节 · L02.5](../02-vortex-codegen/05-device-object.md) · [本章目录](README.md) · [下一节 · L03.1](01-device-buffer.md)
