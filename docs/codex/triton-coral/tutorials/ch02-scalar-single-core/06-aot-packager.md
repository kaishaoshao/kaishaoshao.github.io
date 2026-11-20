# 2.6 节：从加载段打包 AOT 镜像与装载清单

## 1. 这节课做什么
- **功能目标**：从加载段打包 AOT 镜像与装载清单。
- **支持语法**：`镜像提取与段信息 manifest`
- **涉及方言**：主机打包格式
- **阶段标记**：`S1-04`（所属章节：第 2 章：标量语法降级与单核 AOT 执行闭环）
- **实现注意**：先确定使用 p_vaddr 还是 p_paddr，保留段权限和可追溯的哈希。

## 2. 核心代码实现
设备侧已有 `build_firmware.py::build()` 将 `coral.elf`、`complex.elf` 或 `zvt.elf` 以 `llvm-objcopy -O binary` 提取为自举镜像。它校验 ELF magic、镜像非空、4 字节对齐、大小不超过 8 KiB、入口对齐且落在镜像内，再用小端 32 位字生成 `*_image.h`。控制 CPU 固件编译时嵌入这些头文件。[打包源码](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/tools/die/build_firmware.py)

## 3. 解释说明与注释
固件报告包含构建配方、源文件和产物哈希，`validate_rvv_firmware()` 复用前逐一核对。现有单段自举输入可以作为参考。接入通用 Triton AOT 加载清单时，仍需按 `PT_LOAD` 逐段检查文件范围、目标地址、BSS、权限和重叠。在独立 IREE 路径已有仿真器 ELF loader 可参考其装载接口。[IREE 仿真装载源码](https://github.com/Learn-Compiler/coralnpu-compiler/blob/5c68026/runtime/sim/simulator_elf_loader.c)

## 4. 测试与验证代码
已有产物可按下列命令核对。

```bash
cd /home/compiler-1/work/coral/coralnpu
firmware=experiments/multicore/tools/die/logs/firmware
test -s "$firmware/zvt_image.h"
wc -c "$firmware/zvt.bin"
grep -E 'ZVT_IMAGE_WORDS|ZVT_IMAGE_ENTRY' "$firmware/zvt_image.h"
```

`*_IMAGE_WORDS * 4` 应等于 bin 字节数，入口在镜像内。下一节从控制核实际加载这两个参数。
