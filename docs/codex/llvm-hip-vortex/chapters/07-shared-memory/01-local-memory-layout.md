# 11.1 为每个 block 布置共享内存

从 LMEM 和 launch 的动态共享内存字节数出发，定义静态 `__shared__` 对象与 `extern __shared__` 的布局。

> 本节为进阶实验提纲。

- **操作** 从 SDK 的 `vx_spawn2.h` 和 `vortex2.h` 阅读 local memory 地址与 launch 配置。再查 Clang 的 shared 对象发射，将静态和动态区画在同一张偏移图上。
- **测试与通过标准** 用包含两个 block 的样例核对块内共享和块间隔离。检查静态对象对齐，再让同一个 kernel 取两种动态大小并加入超容量反例。
- **实现注意** 布局须定义地址空间、对齐、动态区起点、容量和区域复用。同一动态区的多种 typed view 采用明确的别名约定。跨线程读写使用已核对的同步或独立测试协议。

[SDK 源码入口](../../tasks.md#源码导航) · [T09.1 布局设计](../../tasks.md#t091-定义-shared-memory-abi)

---

[上一节 · L06.5](../06-porting/05-reproduce.md) · [本章目录](README.md) · [下一节 · 11.2](02-block-barrier.md)
