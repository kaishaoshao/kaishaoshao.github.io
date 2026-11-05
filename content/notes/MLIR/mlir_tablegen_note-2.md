# TableGen Basic 02

## MLIR TableGen(.td)编写核心注意事项
编`.td`文件绝不是“简单配置”， 它的本质是在用DSL驱动C++代码生成，编写是需要格外注意一下8个维度的原则与陷阱

### 语法与依赖关系：“成对效应”
TableGen负责生成`.h.inc` 和 `.cpp.inc`，但它不会自动帮你管理c++的#include。
* .td include必须C++ .h include保持同步： 你在.td中每include 一个带有Interface/Trait的文件，对应的C++
包装头文件中必须include对应的C++头文件，否则会报“类型未定义”或找不到基类。
```c
// ToyOps.td
include "mlir/Interfaces/SideEffectInterfaces.h" // .td中引入
```
```cpp
// ToyOps.h 中必须配对引入
#include "mlir/Interfaces/SideEffectInterfaces.h"
```
避免循环include：保持清晰的层次关系：XxxDialect.td->XxxTypes.td->XxxOps.td->XxxPasses.td. 最后用一个总的Xxx.td统一include， 交给CMake的add_mlir_dialect.

### 操作数（Operands）与 属性（Attributes）
* 划清Oprand与Attribute的界限
    * Operand(操作数， ins AnyType:$x): 运行时SSA（mlir::Value）, 随数据流动传递 
    * Attribute(属性， ins I32Attr:$attr): 编译期常量/静态元数据，保存在Operation的属性字典中。
    * 陷阱： 常量折叠时，常量的值在生成的constant Op里是Attribute，而后续计算Op接收的是该constant产生SSA Result(Operand).

* 多可变参数陷阱（极其常见）：如果一个Op中包含超过一个Variadic<...> 或 Optional<...>, TableGen无法单凭参数个数知道每个段占多长，必须添加Trait:
```c
// 错误示范：编译生成代码是会抛出断言错误
def BadOp ： ToyOp<"bad"> {
    let arguments = (ins Variadic<AnyType>:$a, Variadic<AnyType>:$b);
}

// 正确写法：声明AttrSizedOperandSegments
def GoodOp : ToyOp<"good", [AttrSizedOperandSegments]> {
    let arguments = (ins Variadic<AnyType>:$a, Variadic<AnyType>:$b);
}

```
如果是多返回值可变，需添加AttrSizeResultSegments.

### AssemblyFormat(自定义打印与解析语法)
assemblyFormat可以让你摆脱繁琐冗长Generic格式（"toy.add"(%a, %b): ...）, 但它是语法错误高发区：
* 永远不要遗漏 attr-dict: MLIR允许任意Pass跨Dialect向Op附加临时属性(如优化标记、 位置调试信息等)。
如果你的format丢掉了attr-dict, 这些属性在打印时会被丢弃，导致解析再重构时信息丢失：
```tablegen
// 必须加上 attr-dict
let assemblyFormat = "$lhs `,` $rhs attr-dict `:` type($result)";
```
* 类型歧义与显式类型指定：所有无法完全其它地方推导出的Result 或Operand类型， 必须再format中显示输出， 否则Parser会无法推导类型报错：
    * 常见组合：$inputs attr-dict: functional-type($inputs, results)
    * 或者： $lhs, $rhs attr-dict: type($lhs) -> type($result)
* 条件组与锚点（Anchor ^）规则： 对于Optional 或 UnitAttr, 使用（...）?条件输出时，括号内必须有且仅有一个元素被打上锚点^:
```tablegen
// reset是Optional<I1>, 用reset^作为显示整个括号内容的判定条件
let assemblyFormat = "(`rest` $reset^) ? $input attr-dict `:` type($input)";
```

### Verifier(校验机制)的设计哲学
* 分清TableGen Constraint 与 C++ verify()的职责：
    * 静态约束走TableGen: 
    * 跨参数逻辑走hasVerifier = 1: 比如要求 lhs.getType() = rhs.getType(), 或者属性数组长度与输入操作数个数匹配，必须再C++中手写LoagicalReuslt verify()。
    * 禁止再verify()中修改IR：Verifier的唯一职责是检查合法性。绝对不要再Verifier里面调用builder创建新Op或修改现有Op的operand,这会破坏编译器不变式并引发难以察觉的UB。
    * 错误诊断必须附带位置信息：永远使用Op自带的报错工具：
```cpp
// 正确：自动附带该Op的源码位置
return emitOpError("type mismatch between lhs and rhs");
```  

### Builders(构造函数)设计
* 牢记默认生成Builder参数排布规则：MLIR生成的默认build函数签名顺序一般为： OpBuilder &builder, OperationState &state, Type resultType..., Value operand..., Attribute attr... 先传所有的Result Type，再传Operand, 最后传Attribute.
* 推导类型优先用Trait, 而非手写Builder：很多人为了避免每次手动传入返回类型，再let builders = [...]里面写大量的C++字符串。更好、更优雅的做法是使用MLIR的Interface:
    * 输入与输出同类型： 直接打上SameOperandsAndResultType.
    * 根据输入推导输出： 使用InferTypeOpInterface. MLIR会自动为你生成无需传入Result Type的精简Builder.

### C++逻辑与TableGen的代码分离
在.td中，你可以通过let extraClassDeclaration = [{ ... }]插入C++声明与内联实现
警告： 切忌在.td的[{ ... }] 里编写大量复杂C++实现
* 原因：
    1. .td文件里的C++代码没有任何clangd补全、语法检查或重命名重构支持
    2. 哪怕缺了一个分号，报错也会指向自动生成的.h.inc第几千行，难以排查
* 最佳实践：
```tablegen
// .td中只写声明
let extraClassDeclaration = [{

}]
```
```cpp
// .cpp 中写实现，享受完整的C++ IDE高亮与编译诊断
int64_t ConstantOp::getBitWidth() {
    return getResult().getType().getIntOrFloatBitWidth();
}
```
* 在extraClassDeclaration中仅写函数签名声明。
* 将函数体实现全部写在对应的.cpp（如ToyOps.cpp）中。


### Trait与Interface的“契约机制”
* 理解Trait的承诺：
    * 标记了Pure（或NoMemoryEffect），就向MLIR保证此Op没有读写全局内存、没有外部副作用。一旦撒谎（例如在Pure Op内部修改全局静态变量或指针内容），Canonicalize、CSE和DCE会错误地将有用的计算消除，导致静默计算错误。
* Interface必须实现接口方法： 如果给Op加上了CallOpInterface或FunctionOpInterface等Interface,TableGen会在生成代码是强制继承某个Interface C++类。你必须在extraCLassDeclaration中实现该接口声明所有非默认方法，否则编译期会直接包“试图实例化抽象类”的C++错误。

### 调试TableGen的“杀手锏”技巧
遇到玄学编译器错误时，不要对着.td瞎猜， 掌握以下调试手段：
1. 直接翻阅生成物（.h.inc 和 .cpp.inc）:
    * 它们通常存放在build/include/your_dialect/目录下。
    * 查看TableGen到底生成什么样参数签名的build(...)、parse(...)或print(...)。看一眼生成的代码， 90%的接口传参报错都能迎刃而解。
2. 单独编译IncGen Target, 加速迭代循环： 
    * 每次改完.td， 不要跑全局ninja.
    * 单独编译对应target(如ninja MLIRToyIncGen或自定义的ninja header). 这只需要0.5秒即可完成语法校验，无需等待漫长的c++链接。
3. 善用mlir-tblgen命令行单独跑生成的测试： 如果TableGen自身报错崩溃，可以直接在终端调用mlir-tblgen调试定位：
```bash
mlir-tblgen -gen-op-decls ToyOps.td -I /path/to/llvm/mlir/include
```

### 总结
```
结构先理清，成对写头档；     （.td与.h include对应）
多变参数段，Trait莫遗忘；     (多Variadic必加AttrSizeOperandSegments)
格式留字典，类型推到畅；      (assemblyFormat必带attr-dict, 类型无歧义)
校验纯逻辑，切忌改IR样；      (verify()只查不改)
逻辑留实现，表格放声明；      (.td留声明，复杂逻辑进.cpp)
报错莫抓瞎，打开.inc细看详。  (查阅生成代码时最快调试手段)
```

