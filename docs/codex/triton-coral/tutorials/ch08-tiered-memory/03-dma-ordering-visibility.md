# 8.3 节：把 copy、launch、wait 和回写串成有序计划

## 1. 这节课做什么
- **功能目标**：把 copy、launch、wait 和回写串成有序计划。
- **支持语法**：`coral_mem.copy, wait, version 依赖图`
- **涉及方言**：DMA 计划方言
- **阶段标记**：`S7-03`（所属章节：第 8 章：分层存储架构与显式 DMA（coral_mem））
- **实现注意**：消费者等待生产者可见完成。每次搬入和回写都要关联实际 buffer 版本。

## 2. 核心代码实现
现有 `Dma.scala` 是独立 AXI 主设备。PicoRV32 通过 `0x50000100` 寄存器提交源、目标、长度与 tag。控制固件的 `queued_demo.c` 已把 COPY 和 KERNEL 串成任务图，依赖使用上一章的队列 API。[DMA RTL](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/die/Dma.scala) · [固件提交与轮询](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/die/firmware/queued_demo.c)

```text
HBF A/B → 3D DRAM A/B → 核私有 DTCM
                              ↓ 两路输入就绪
                         Coral kernel
                              ↓ kernel done
输出 DTCM → 3D DRAM → 共享 SRAM（测试读回）
```

## 3. 解释说明与注释
DMA 校验地址和长度至少 4 字节对齐、范围合法且不重叠。最后一个写响应成功后发布完成。固件同时核对 `DONE_TAG` 与搬运进度，再让依赖开始。满四核的分层用例提交 28 个任务，包含 24 次 DMA。最后的 SRAM 搬运供测试台读回。Triton 端的 copy/launch/wait lowering 仍需要对接这套 C 接口。

## 4. 测试与验证代码
复查 [8.1 节](01-region-resource-model.md) 的 `storage --build --test`。旧 SRAM 路线可在相应仿真器与固件已构建时用以下入口跑队列、DMA 与 Zvt 回归。

```bash
cd /home/compiler-1/work/coral/coralnpu
python3 experiments/multicore/tools/ncoral.py pipeline --zvt --test --jobs 2
```

历史报告覆盖尾部、空分片、背压、无效地址、拒绝重叠以及忙时 START 拒绝和活动描述符快照。[DMA 与队列验证记录](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/docs/dma_events_zvt.md)
