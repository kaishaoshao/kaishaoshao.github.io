# 7.3 节：接通有界队列、核内隔离及回收

## 1. 这节课做什么
- **功能目标**：接通有界队列、核内隔离及回收。
- **支持语法**：`长 Grid 任务队列与每核参数隔离`
- **涉及方言**：控制固件调度协议
- **阶段标记**：`S6-03`（所属章节：第 7 章：多维 Grid 与多核调度（coral_rt））
- **实现注意**：每核参数、scratch、ELF 身份和提交序号独立。等待完成后才回收。

## 2. 核心代码实现
控制核队列的任务描述符来自 `experiments/multicore/die/firmware/queue.h`。当前实现使用 32 个队列项和 64 个事件槽。[完整头文件](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/die/firmware/queue.h) · [完整实现](https://github.com/Learn-Compiler/coralnpu/blob/f9ab975c/experiments/multicore/die/firmware/queue.c)

```c
typedef struct {
  uint32_t kind, core_mask, wait[2], signal;
  uint32_t src, dst, bytes;
  uint32_t kernel_id, program_id, grid, args[4];
} NcTask;
```

入口是 `nc_event_reserve()`、`nc_submit()`、`nc_pump()`、`nc_event_release()`。控制核使用 `NcBackend.start/poll` 分派 DMA 或启动核。

## 3. 解释说明与注释
每个任务最多两个前驱事件。描述符使用带 generation 的 token，旧 token 和仍被引用的事件有各自的错误返回。扫描就绪任务时检查 `cores_busy` 和 `dma_busy`，等待中的任务不会阻止可独立启动的后续任务，完成记录按 FIFO 回收。COPY 的资源掩码根据两端地址推导。前驱错误传播成 `NC_DEPENDENCY`。共享地址依赖由提交方声明。

## 4. 测试与验证代码
在 compiler-1 独立跑同一份宿主队列测试。

```bash
cd /home/compiler-1/work/coral/coralnpu
d=experiments/multicore/die
out=$(mktemp -d /tmp/coral-queue-XXXXXX)
gcc -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined -g \
  -c "$d/firmware/queue.c" -o "$out/queue.o"
g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -g \
  "$d/queue_test.cc" "$out/queue.o" -o "$out/queue-test"
"$out/queue-test"
```

2026-11-20 复跑通过，覆盖依赖顺序、环形队列回绕、generation、资源互斥、重叠、失败传播、死锁和容量。四核队列与独立 DMA 的 RTL 用例见 [8.3 节](../ch08-tiered-memory/03-dma-ordering-visibility.md)。
