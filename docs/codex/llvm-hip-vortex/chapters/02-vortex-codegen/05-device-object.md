# L02.5 生成第一个设备对象

把同一个 `store42` 从 IR 生成 RV64 可重定位对象，拿到 L03 的链接输入。

- **操作** 先用下方通用 RV64 命令建立对照。下面沿用 L01 的 `VORTEX_DOCS_ROOT`。接通 L02.2～L02.4 后，再用你的 Vortex 设备配置生成 `.ll/.o`，保存实际编译参数。

  ```bash
  cd /home/kaikai/vortex-word
  l02_out=$(mktemp -d)
  build/llvm/bin/clang++ -cc1 -triple riscv64-unknown-elf -target-cpu generic-rv64 \
    -target-feature +m -target-feature +f -target-feature +d \
    -target-abi lp64d -x hip -fcuda-is-device -emit-obj -O0 \
    "$VORTEX_DOCS_ROOT/examples/l01/attributes.hip" -o "$l02_out/store42.o"
  build/llvm/bin/llvm-readelf -h -s -A "$l02_out/store42.o"
  build/llvm/bin/llvm-objdump -d "$l02_out/store42.o"
  ```

- **测试与通过标准** 通用对照和新设备对象的 ELF 头都应显示小端 ELF64、RISC-V、`ET_REL` 与 double-float ABI，符号及反汇编能找到 `store42` 和写入 42 的代码。新路径另外在 IR 检查逻辑标记和有效 CPU/features。
- **实现注意** IR 属性未必会以同名符号留在对象里。在生成对象前保存 IR，方便 L03 接入 wrapper。固化公共 offload 命令在 L05.5 完成。

## Vortex 设备对象示例

在已构建三个 L02 改动的环境中，使用 `llvm/unittests/Vortex/L03/store42.hip` 生成设备 IR 和对象。以下是该目录 `build-00.sh` 的前两个步骤，可在独立目录观察。

```bash
root=/home/kaikai/vortex-word
llvm_bin="$root/build/llvm/bin"
source="$root/llvm-project/llvm/unittests/Vortex/L03/store42.hip"
out=$(mktemp -d)
"$llvm_bin/clang" -cc1 -triple riscv64-unknown-elf -target-cpu vortex \
  -target-abi lp64d -x hip -fcuda-is-device -emit-llvm -O2 "$source" -o "$out/store42.ll"
"$llvm_bin/llc" -mtriple=riscv64 -mcpu=vortex -filetype=obj "$out/store42.ll" -o "$out/store42.o"
"$llvm_bin/llvm-objdump" -d "$out/store42.o"
```

用户实验记录中的设备函数为 `_Z7store42Pi`，用 `li a1, 0x2a` 和 `sw a1, 0(a0)` 存入 42，最后 `ret`。同时检查 IR 中的实际属性和对象的 ISA 标记。

---

[上一节 · L02.4](04-tmc-mc.md) · [本章目录](chapter-03-cpu-and-tmc.md) · [下一节 · L03.0](../03-store42/00-direct-elf.md)
