# 7.1 节：参数化核数及有效核掩码

## 1. 这节课做什么
- **功能目标**：参数化核数及有效核掩码。
- **支持语法**：`多核配置参数与 Core Mask (1, 3, 15)`
- **涉及方言**：TargetSpec 多核拓扑描述
- **阶段标记**：`S6-01`（所属章节：第 7 章：多维 Grid 与多核调度（coral_rt））
- **实现注意**：物理容量来自实际 TargetSpec。运行掩码选择可用核的子集。

## 2. 核心代码实现
现有 RTL 在 `coralnpu` 的 `experiments/multicore/Cluster.scala` 与 `die/Die.scala`。PicoRV32 控制核管理四个私有 ITCM/DTCM 地址窗。固件已有如下核选择函数。[RTL 核簇](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/Cluster.scala) · [控制固件](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/die/firmware/runtime.c)

```c
void coral_start_mask(unsigned mask) {
  memory_fence();
  for(unsigned core=0;core<CORAL_COUNT;++core)if(mask&(1u<<core)) {
    write32(coral_address(core,CLUSTER_CSR_ADDRESS),1);
    write32(coral_address(core,CLUSTER_CSR_ADDRESS),0);
  }
}
```

## 3. 解释说明与注释
现有 `nc_submit()` 校验四核掩码、非空 grid 和选中核数能否覆盖在剩余的逻辑 program 区间。启动时以 `program_id + rank` 分配逻辑索引，以位序得到物理 `core_id`。Triton 端的拓扑能力声明与通用三维 grid 调度仍由本章完成。[队列校验](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/die/firmware/queue.c) · [启动调用方](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/die/firmware/queued_demo.c)

## 4. 测试与验证代码
用 [7.3 节](03-bounded-queue-isolation.md) 的宿主队列测试复查非法 mask 与 program 范围，再结合设备侧 [23 项多核 RVV 运行记录](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/docs/profiling_verification.md) 查看空分片和非均匀分片。Triton 端需再复跑 `S6.grid.*`。
