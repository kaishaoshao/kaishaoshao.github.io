# 2.7 节：启动 core0 并关联每次加载与完成

## 1. 这节课做什么
- **功能目标**：启动 core0 并关联每次加载与完成。
- **支持语法**：`硬件/仿真器加载运行`
- **涉及方言**：设备执行状态
- **阶段标记**：`S1-05`（所属章节：第 2 章：标量语法降级与单核 AOT 执行闭环）
- **实现注意**：缓存、取指可见性和完成标志按调用刷新。超时后先确认停止，再复用设备内存。

## 2. 核心代码实现
现有设备侧实现放在 `coralnpu` 的 `experiments/multicore/die/firmware/runtime.c`。它已经能由真实 PicoRV32 控制核装入预编译 ITCM 镜像、写入口 PC、启动核组并等待完成。以下是完整的镜像加载函数。[固件源码](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/die/firmware/runtime.c)

```c
void coral_load(const uint32_t *image,unsigned words,uint32_t entry) {
  for(unsigned core=0;core<CORAL_COUNT;++core) {
    write32(coral_address(core,CLUSTER_CSR_ADDRESS),3); // Reset + clock gate.
    for(unsigned i=0;i<words;++i)
      write32(coral_address(core,4*i),image[i]);
    write32(coral_address(core,CLUSTER_CSR_ADDRESS+4),entry);
  }
  memory_fence();
}
```

## 3. 解释说明与注释
`queued_demo.c::start()` 为目标核先清零共享 done，写帧，再调用 `coral_start_mask()`。完成侧检查对应核的 done 和 WFI，并检测 trap、fault 或超时。Triton 接入时可以沿用这个启动顺序。当前设备演示的输入是固件已经嵌入的镜像，支持任意 Triton ELF 及单核连续换镜像属于本节后续验收。[启动和等待调用方](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/die/firmware/queued_demo.c)

## 4. 测试与验证代码
在已构建的设备模型上复跑预编译加法。

```bash
cd /home/compiler-1/work/coral/coralnpu
python3 experiments/multicore/tools/ncoral.py run \
  --elements 37 --rounds 2 --run-timeout 120
```

建模分支已有的记录是四核两轮依赖加法，checksum 为 11507，8 次核启动。Triton core0 回归要另用 `S1.copy` 和 `S1.reload`，关联本次生成的 ELF、回读数据和运行记录。[原始运行证据](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/docs/model_validation.md)
