# L02.4 实现第一条专用指令 TMC

让汇编器和反汇编器正确处理 `vx_tmc rs1`，并验证开关确实控制这条指令。

- **操作** 对照参考 TableGen 和 SimX decode，先算 `opcode=0x0b`、`funct3/funct7/rd/rs2=0` 与 `rs1`。在 RISCV 的扩展指令定义中接入 `xvortex` 谓词。
- **测试与通过标准** 在 `llvm/test/MC/RISCV` 写四类检查。启用 feature 时，`vx_tmc a0` 和 `vx_tmc a1` 分别编码为 `0b 00 05 00` 和 `0b 80 05 00`。生成对象再反汇编，寄存器对应一致。关闭 feature 时，新汇编器应报告扩展缺失。多余操作数或立即数应报告操作数错误。
- **实现注意** 在 `HasVendorXVortex` 的定义中，核对 `AssemblerPredicate` 的条件是否引用实际 feature，再确认指令使用了它。对照同文件的 `HasCheriot`。TMC 改变活跃 mask，其副作用在后续 IR lowering 也要保留。
- **参考结果** 本机参考 `llvm-mc` 已核对这两条编码及反汇编，同时观察到旧工具在 `-mattr=-xvortex` 下仍接受 `vx_tmc`。旧工具用于校对编码，禁用测试按新实现的约定验收。[参考指令定义](https://github.com/vortexgpgpu/llvm/blob/f44a6bb2af4c62847585305bbdc760fbe0e3645f/llvm/lib/Target/RISCV/RISCVInstrInfoVX.td) · [编码实验](../../architecture.md#66-编码长什么样)

## 当前分支的指令定义

`vx_tmc` 用 `rs1` 中的值更新活跃线程掩码。以 `a0`（x10）为例，按 R 型字段拼出 `0000000 00000 01010 000 00000 0001011`，得到字值 `0x0005000b`。

提交 `0d3d3fcd2` 里的 `RISCVInstrInfoXVortex.td` 使用独立的解码命名空间。

```tablegen
let hasSideEffects = 1, mayLoad = 0, mayStore = 0 in {
let Predicates = [HasVendorXVortex], DecoderNamespace = "XVortex" in {
def VX_TMC : RVInstR<0b0000000, 0b000, OPC_CUSTOM_0, (outs), (ins GPR:$rs1), "vx_tmc", "$rs1"> {
  let rd = 0;
  let rs2 = 0;
}
}
}
```

在 `RISCVDisassembler.cpp` 中用相同 feature 掩码选中解码表。

```cpp
static constexpr FeatureBitset XVortexGroup = {RISCV::FeatureVendorXVortex};
{DecoderTableXVortex32, XVortexGroup, "Vortex simt extensions"},
```

这里摘录了 feature 位与解码表条目。先对齐 MC 结果，再验证指令执行时的语义。

---

[上一节 · L02.3](03-cpu-and-features.md) · [本章目录](chapter-03-cpu-and-tmc.md) · [下一节 · L02.5](05-device-object.md)
