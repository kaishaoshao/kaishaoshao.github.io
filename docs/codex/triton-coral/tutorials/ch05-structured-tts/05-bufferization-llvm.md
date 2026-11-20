# 5.5 节：完成 Bufferization、资源检查及 LLVM 降低

## 1. 这节课做什么
- **功能目标**：完成 Bufferization、资源检查及 LLVM 降低。
- **支持语法**：`张量内存化与 LLVM 降级`
- **涉及方言**：bufferization / memref -> LLVM
- **阶段标记**：`S4-05`（所属章节：第 5 章：二维结构化访存与循环（TTS / Linalg））
- **实现注意**：临时 buffer 必须在 DTCM 容量内，并能证明释放或复用。降低后的 LLVM IR 要通过目标 verifier。

## 2. 核心代码实现
> 待实现

## 3. 解释说明与注释
> 待实现

## 4. 测试与验证代码
> 待实现
