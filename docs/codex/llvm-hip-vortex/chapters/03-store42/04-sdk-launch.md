# L03.4 用 SDK 提交首个 launch

用一个小型 SDK host 加载刚生成的镜像，提交一个线程并读回结果。

- **操作** 加载模块，取得 `main` handle，设置 `ndim=1`、grid/block 各 1、`args_size=8`。让读回复用 SDK 的 launch 依赖，等待完成后再检查数据。
- **测试与通过标准** 输出先是 `-1`，执行后是 `42`，进程退出 0。另用不存在的名字查找 kernel，确认错误可观察且没有提交计算。保存命令、镜像指纹和三个地址的来源。
- **实现注意** 现成的 demo/sgemm runner 绑定了自己的参数布局，`store42` 需要与本实验 8 字节布局匹配的 host。测试使用有界等待，保留 API 返回、超时或进程故障的实际记录。

## 复跑用户已提交的样例

在已按本机路径构建 LLVM 与 Vortex SDK 的 WSL 中，脚本会重建设备镜像，编译 x86 host，然后通过 SDK 启动 SimX。

```bash
cd /home/kaikai/vortex-word/llvm-project/llvm/unittests/Vortex/L03
bash ./run-sim.sh
```

`host_store42.cpp` 用 `vx_module_load_file` 加载镜像，再用 `vx_module_get_kernel` 找到 `main`。在 `vortex2.h` 的 `vx_launch_info_t` 中设置 `ndim`、`grid_dim` 和 `block_dim`。读回请求依赖 launch 的 event，等待读回完成后才比较结果。

用户提交 `ebb09fb51` 对应的原始记录和 2026-11-20 在独立目录的复跑均读回 42。样例覆盖一次单线程启动和读回。上面的哨兵、错误用例与有界等待是进一步的验收练习。

```text
>>> [Host] Loading kernel.vxbin...
>>> [Host] Enqueue launch on SimX...
>>> [Host] Read back value from SimX: 42
SUCCESS! SimX returned 42 from store42!
```

---

[上一节 · L03.3](03-link-and-package.md) · [本章目录](README.md) · [下一节 · L03.5](05-rebuild-and-check.md)
