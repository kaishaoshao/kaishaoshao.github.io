# 8.1 节：定义存储区域、权限、owner 及容量

## 1. 这节课做什么
- **功能目标**：定义存储区域、权限、owner 及容量。
- **支持语法**：`HBF, 3D DRAM, SRAM, DTCM 存储建模`
- **涉及方言**：coral_mem 资源模型
- **阶段标记**：`S7-01`（所属章节：第 8 章：分层存储架构与显式 DMA（coral_mem））
- **实现注意**：HBF 对计算平面只读，3D DRAM 承担存储，DTCM 归对应核。地址窗口与物理容量分别记录。

## 2. 核心代码实现
已有 RTL 在 `coralnpu@f9ab975c`。地址许可由 `Storage.scala::StorageMap` 和 `TieredMemoryFabric` 实现，CPU 配置常量与设备入口在 `firmware/platform.h`。下面是当前实现使用的系统地址窗口。[存储 RTL](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/die/Storage.scala) · [固件地址定义](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/die/firmware/platform.h)

| 区域 | 地址 | 已有行为 |
| --- | --- | --- |
| 共享 SRAM | `[0x20000000, 0x20004000)` | CPU、核簇和 DMA 共享，末 16B 保留给日志。 |
| 核 `i` ITCM/DTCM | `0x40000000 + i * 0x100000` 下的 `+0x00000` 与 `+0x10000` | 8 KiB ITCM、32 KiB DTCM，owner 是核 `i`。 |
| 3D DRAM | `[0x60000000, 0x70000000)` | 256 MiB 读写地址窗口，承担数据存储。 |
| HBF | `[0x80000000, 0xc0000000)` | 1 GiB 地址窗口，计算平面只读，DMA 目的端会拒绝。 |

## 3. 解释说明与注释
这两个外存窗口由 RTL 分流。Verilator 使用 `storage_model.h` 的稀疏功能模型响应访问。地址窗口、物理容量和测量带宽是三个独立参数。本分支的 3D DRAM 只存储，算术在 Coral RVV/Zvt 核执行。Triton 的 region/owner 表示需要按这个契约建模。[原型设计与边界](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/docs/hbf_3ddram.md)

## 4. 测试与验证代码
使用固定 SDK 构建并运行现有模型。下列命令复跑该仓库的功能验证。

```bash
cd /home/compiler-1/work/coral/coralnpu
sdk=/home/compiler-1/work/coral/coralnpu-compiler/out/llvm-zvt/install
export PATH="$sdk/bin:$PATH"
python3 experiments/multicore/tools/ncoral.py storage --build --test \
  --clang "$sdk/bin/clang" --lld "$sdk/bin/ld.lld" --jobs 12
```

2026-11-20 使用匹配历史 SHA256 的仿真器复跑 `smoke_storage_fabric`，25 项通过。2026-11-17 的整机报告还记录了 10 项 HBF/DRAM top 和 9 项旧 SRAM top 兼容用例通过。[版本化报告](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/docs/hbf_3ddram_validation.json)
