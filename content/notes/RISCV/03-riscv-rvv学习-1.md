---
title: "riscv rvv 学习-1"
date: 2026-03-23 11:19:00
tags: ["0.0.1"]
---
## 概念： 什么是SISD与SIMD?

在进入RVV学习前，我们要先搞清楚两种最基本的CPU计算模式

* **SISD(Single Instruction Single Data，单指令单数据):** 这是传统 CPU 的经典模式。一条指令，只能处理一个数据。
* **SIMD (Single Instruction Multiple Data，单指令多数据)**：一条指令，同时处理多个数据。RVV 就属于一种高级的 SIMD 变体。

### 举例子

假设我们要吧两个数组A和B的钱4个元素相加，存到C里面

* SISD的做法（普通标量循环 + 4次加法指令）

  ```c
  // 每次循环只处理 1个元素，共循环4次
  for(int i = 0; i < N; i+=4) {
  	c[i] = a[i] + b[i];
      c[i+1] = a[i+1] + b[i+1];
      c[i+2] = a[i+2] + b[i+2];
      c[i+3] = a[i+3] + b[i+3];
  }
  for(; i < N; i++) {   // 剩余元素
      c[i] = a[i] + b[i];
  }
  
  // 直接使用编译器宏也一样
  #pragma unrool 4
  for(int i = 0; i < N; i++) {
  	c[i] = a[i] + b[i];
  }
  ```

  在绝大多数情况下，**直接使用 `#pragma unroll 4` 更安全、更简洁**，编译器会生成等效甚至更优的代码。
* SIMD做法(只需要1次加载、1次加法指令，搞定4个元素)

  ```c
  // 伪代码
  // 一次性把4个整数加载到专门的SIMD寄存器A_tmp中
  vec4 A_tmp = load4(A)
  vec4 B_tmp = load4(B)
  
   // 仅仅用1条加法指令，同时完成4组数据相加
   vec4 C_tmp = add3(A_tmp, B_tmp)
   strore4(C_tmp, C);
  ```

  ```c
  // RVV
  #include <riscv_vector.h> // 包含 RVV 的 Intrinsics 头文件
  void vector_add(const float *a, const float *b, float *c, int n) {
  size_t i;
  for (i = 0; i < n; ) {
  // 1. 正确的 vsetvli 用法：
  // 第一个参数是元素的个数，第二个参数是 SEW (e32 代表 32位)
  // 注意：在 Intrinsics 中，vsetvli 实际上被封装在特定的操作函数里，
  // 或者使用 __riscv_vsetvl_e32m1(n - i) 这种形式
  size_t vl = __riscv_vsetvl_e32m1(n - i);
  
  // 2. 加载数据：使用 __riscv_vle32_v_f32m1
  vfloat32m1_t va = __riscv_vle32_v_f32m1(&a[i], vl);
  vfloat32m1_t vb = __riscv_vle32_v_f32m1(&b[i], vl);
  
  // 3. 向量加法：使用 __riscv_vfadd_vv_f32m1
  vfloat32m1_t vc = __riscv_vfadd_vv_f32m1(va, vb, vl);
  
  // 4. 存储数据：使用 __riscv_vse32_v_f32m1
  __riscv_vse32_v_f32m1(&c[i], vc, vl);
  
  i += vl;
  }
  }
  
  int main() {
  float a[] = {1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0};
  float b[] = {9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0};
  float c[9];
  int n = 9;
  
  vector_add(a, b, c, n);
  
  printf("计算结果: ");
  for (int i = 0; i < n; i++) {
  printf("%.1f ", c[i]);
  }
  printf("\n");
  
  return 0;
  }
  
  ```

对比为代码

1. **没有“硬编码”的 4**： 你的代码里写死的是 `load4`。这意味着如果硬件换成了 8 宽度的，或者你数据只有 3 个了，这段代码就会崩溃或者出错。 RVV 使用 `vl` 寄存器。不管剩下几个，`vsetvli` 都会自动调整 `vl` 的值，让指令完美适配。
2. **指令的“正交性”**： RVV 的指令不需要像 `add4`, `add8`, `add16` 这样写一堆重名的。它是一套指令走天下。`vadd` 指令本身不包含长度信息，长度信息全在 `vl` 寄存器里。这让 CPU 设计变得异常简洁。
3. **内存指针的自动偏移**： 在 RVV 中，我们利用 `vl` 配合循环，不仅解决了尾部处理问题，还让编译器非常容易进行“自动向量化”。

## **RVV关键特性：**

1. 可配置的向量长度：RVV 支持从 128到 1024 bit甚至更长的向量寄存器长度（最大可到65536bit），具体取决于实现。这种灵活性允许开发者编写与向量长度无关的代码（Vector-Length Agnostic, VLA），从而提高代码的可移植性;

2. 动态调整向量长度：RVV 允许在运行时动态调整向量长度，这使得同一段代码可以在不同配置的硬件上高效运行，而无需重新编译;

3. 统一的指令格式，整数和浮点指令比较统一;

4. 丰富的指令集

   

## **动态向量长度（VL)**

对于ARM Neno指令（Intel AVX类似），处理的是定长的数据，如果数据的数量不是向量大小的整数倍，就会出现剩余元素的问题，这些剩余元素需要特别处理，参考ARM官方的[Coding for Neon](https://developer.arm.com/architectures/instruction-sets/simd-isas/neon/neon-programmers-guide-for-armv8-a/coding-for-neon/)，在第4节 Load and store - leftovers给了处理技巧：

- 剩余元素用cpu来算（走标量通路）
- 填充数组（Larger Arrays），即将原始数组扩展到下一个向量大小的倍数
- 重叠计算（Overlapping）
- 单个元素处理（Single Elements）

而对于 RVV：

RVV支持动态向量长度（VL)，在RVV指令集中，`vl`（Vector Length）是一个关键的控制寄存器，用于指定向量指令操作的数据元素数量，`vl`值可以根据不同的循环迭代或不同的数据集大小来动态调整，使用起来很方便。



### RVV 的 Intrinsics 官方的查询工具：

https://dzaima.github.io/intrinsics-viewer/

## 参考链接

[RISC-V RVV](https://www.cnblogs.com/sureZ-learning/p/18822194)
