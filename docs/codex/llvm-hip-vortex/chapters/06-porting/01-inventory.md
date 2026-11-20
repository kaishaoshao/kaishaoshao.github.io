# L06.1 盘点已有源码依赖

先读源码和 Makefile，用一张短表说明程序需要哪些接口、启动形状和验证行为。

> 本节是实验提纲。通过标准用于实现后的验收。

- **操作** 记录 SDK commit、`main.cpp/common.h`、输入种子、CPU 参考算法、浮点容差和现有构建路径。
- **测试与通过标准** 从源码逐项核对 `hipGetDevice`、`hipGetDeviceProperties`、`hipGetErrorString`、内存与同步 API。确认 kernel 使用 1D 索引、加法和边界判断，原程序根据 `maxThreadsPerBlock` 选择 block。
- **实现注意** 区分 host 的 C++ 标准库和设备依赖。本用例需要设备属性查询，共享内存、原子和 event 可留给使用这些能力的程序。

---

[上一节 · L05.6](../05-hip-runtime/06-hip-end-to-end.md) · [本章目录](README.md) · [下一节 · L06.2](02-first-build.md)
