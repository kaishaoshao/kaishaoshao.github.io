# 4.2 从设备对象链接独立 ELF

把 L03.0 运行过的镜像再链接一遍，弄清设备函数体、启动代码和 ELF 入口各起什么作用。

## 准备输入

以下命令使用上节已保留的设备对象 `store42.o`，以及设备侧检查入口 `check_store42.S`。可在复现成功后把对象换成 L02.5 新生成的文件，再核对 `store42` 的实际符号。汇编入口的 `.insn` 用于结束本次独立执行。

## 链接与检查

```bash
root=/home/kaikai/vortex-word
llvm_bin="$root/build/llvm/bin"
inputs="$root/artifacts/tutorial/l03/direct-elf-rpgekj_l"
out=$(mktemp -d "$root/artifacts/tutorial/l03/relink-XXXXXX")

"$llvm_bin/clang" --target=riscv64-unknown-elf -march=rv64imfd -mabi=lp64d \
  -I"$root/vortex/build64/sw" -DEXPECTED_STORE=42 \
  -c "$inputs/check_store42.S" -o "$out/entry.o"
"$llvm_bin/ld.lld" -m elf64lriscv --no-relax -Ttext=0x80000000 --entry=_start \
  "$out/entry.o" "$inputs/store42.o" -o "$out/store42.elf"
"$llvm_bin/llvm-readelf" -h -l -s "$out/store42.elf"

(
  cd "$out" || exit 1
  "$root/vortex/build64/sim/simx/simx" "$out/store42.elf"
)
```

- **通过标准** ELF 为 RV64 的 `ET_EXEC`，入口地址与符号 `_start` 一致并落在可执行装载段。SimX 运行该镜像后退出 0。
- **实现注意** 入口汇编先建立栈，再依照 RV64 调用约定把输出指针放到 `a0`。直接把 ELF 入口设成 `store42` 会绕过这些准备。这节的链接地址用于已固定的独立实验，SDK 启动采用自己的链接脚本和入口设置。[SDK 启动接口](../../compiler-sim-contract.md#两个-pc-与真实启动路径)

2026-11-20 用本节命令重新链接，分别以 42 和 43 作为期望值，SimX 退出码为 0 和 1。工具输出保存在 `/home/kaikai/vortex-word/artifacts/tutorial/l03/chapter-04-check-sa_bth7t/`。

---

[上一节 · L03.0](00-direct-elf.md) · [本章目录](README.md) · [下一节 · 4.3](00-diagnose-standalone.md)
