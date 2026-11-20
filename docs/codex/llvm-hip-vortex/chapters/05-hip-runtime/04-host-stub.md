# L05.4 接通 host stub、配置和注册

以 Clang 实际生成的 host IR 确定 runtime 所需的隐式入口。

> 本节是实验提纲。通过标准用于实现后的验收。

- **操作** 从 L01 的 launch 表达式追到 `CGCUDANV.cpp`，使用所选 HIP 声明检查 host IR，提取配置 push/pop、launch、镜像/函数注册与注销的签名和时序。
- **测试与通过标准** 检查 `dim3`、`size_t`、stream 与调用签名符合已选 host ABI。用受控的模块和注册表记录验证 host kernel 标识解析到正确的设备入口，缺失标识给出明确错误。宿主构造函数触发的实际注册随 L05.5 的嵌入产物在 L05.6 复验。
- **实现注意** 用编译器实际发出的符号和参数传递为准。初版约定 legacy 默认流，避免将 per-thread 默认流静默按同一种行为处理。注册可在 main 前发生，明确首次设备初始化和注销的时机。[Clang HIP 编译流程](https://clang.llvm.org/docs/HIPSupport.html)

---

[上一节 · L05.3](03-generate-wrapper.md) · [本章目录](chapter-09-offload.md) · [下一节 · L05.5](05-offload-link.md)
