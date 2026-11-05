# TableGen Basic 01

## 介绍
### 什么是介绍TableGen
TableGen是一种数据定义语言，它允许用户指定记录的名称。后端可以解析这些记录并根据需要使用它们。
TableGen 提供了模板、类层次结构、宏和预处理等额外功能，使我们能够最大限度地减少重复代码，并降低信息指定的复杂性。然而，TableGen 的实用性在社区中也存在争议。目前，它是他们的首选工具，所以我们也继续使用它。

###  术语
TableGen规范主要包含两种类型的记录： 抽象记录(称为类)和具体记录。更复杂的是，TableGen的输出中，具体记录被称为“Defs”,
我们使用`defs`关键字来定义具体记录。使用`records`来抽象记录和具体记录，
下面例子来说明这一点：
```tablegen
/// sample.td
/// class (defined using the `class` keyword) 
class ArithmeticOperator {
  string mnemonic;   // field defined with its type
}

// record （defined using the `def` keyword: creates an instance of ArithmeticOperator）
def AddOp : ArithmeticOperator {
  let mnemonic = "add";  // field initialized using `let`
}

def MulOp : ArithmeticOperator {
  let mnemonic = "mul"; // field initialized using `let`
}

```

### 模板
与C++类似，在TableGen中，模板允许我们将初始化值传递给类
```tablegen
// Base class for all Traits (shared behaviour among classes/instances)
class Trait {}

// Operator类接收两个模板参数： mnemonicString和traitltem
// 这两个变量存储在类中
// 将变量初始化为‘？’意味着当前持有一个未定义的值
class Operator<string mnemonicString = ?, Trait traitItem = ?> {
  string mnemonic = mnemonicString;
  Trait trait = traitItem;
}

// A concrete record
def ArithmeticOperatorTrait : Trait {}

// A detived class
class ArithmeticOperator<string mnemonic, Trait trait = ArithmeticOperatorTrait> 
  : Operator<mnemonic, trait>;

// Concrete records
def AddOp : ArithmeticOperator<"add">;
def MulOp : ArithmeticOperator<"mul">;

```

### 类型
```tablegen
// Using in TypeExample
class BinaryOp {}
def op : BinaryOp {}

// 我们并不真的需要 TypeExample的多个实例
// 所以把所有内容直接放在一个definition里
// 而不是先定义一个class, 再用def去实例化。
def TypeExample {
  // Bit type
  bit bitV = 1;

  // TableGen 中没有专门的布尔类型
  // 用 `bit` 来表示布尔值。不过， TableGen 提供了`true`和`false`关键字，
  // 它们会被自动转换为1和0
  bit falseV = false; // 转换为0

  // `assert` 和 `!eq` 不是不等于
  assert !eq(falseV, 0), "Expected falseV to be 0";

  bit tureV = true; // Converted 1.
  assert !eq(trueV, 1), "Expected trueV to be 1";

  bit alsoTrueV = 1; // 强制转换为bit类型。
  assert !eq(alsoTrueV, true), "Expected alsoTrueV to be true";
  assert !eq(alsoTrueV, 1), "Expected alsoTrueV to be 1";

  // int 类型
  int intV = -1;

  // 字符串类型
  string stringV = "stringVal";

  // bits 类型： 一串位
  bits<4> bitsV1 = {0, 1, 0, 1}; // 逐位设置
  bits<4> bitsV2 = 5; // 或者一次性设置
  assert !eq(bitsV1, bitsV2), "Expected bitsV1 and bitsV2 to be equal";

  // Lists of any type, like in C++。
  list<int> listV = [10, 20, 30, 40];
  list<string> stringList = ["a", "b", "c", "d"];

  // We'll cover `dag` Later.
  dag dagV = !dag(op, [10, 20], ["op1", "op2"]);

  // 可以用问号（？）指定未初始化的值
  // 下面两个定义是等价的
  string uName1;
  string uName2 = ?

  // `!`（bang）运算符不能作用于未初始化的数据，我们很快就会学到它们。
  // 下面这行不会生效：  
  // assert !eq(uName1, uName2), "Expected uName1 and uName2 to be uninitialized";
  // 取消注释会抛出如下错误：
  // error: assert condition must be of type bit, bits, or int.

}

```

### 多态
TableGen类面向对象编程OOP特性偏离的地方，一个类允许你生成一个定义，而多类允许你生成多个定义。
比如在需要为不同架构生成定义的时候。
```tablegen
// 使用一个空的指令类
class Instruction{}

// multiclass 会接收一条指令，然后由它创建出多个record
multiclass InstructionM { 
  // 我们希望为每条指令生成两种不同的变体
  def _amd : Instruction{}
  def _intel: Instruction{}
}


// 可以使用defm来调用一个multiclass
defm ADD : InstructionM;
// tablegen会按预期生成新的record
// 但recored的名字会加上变量作为前缀
// 因此不会生成名为_amd 和 _intel的record
// 而是生成
// ADD_amd 和 ADD_intel

defm MUL : InstructionM;
// 同样生曾 MUL_amd 和 MUL_intel
```
生成
```bash
./llvm-project/build/bin/mlir-tblgen /tmp/multi.td 
------------- Classes -----------------
class Instruction {
}
------------- Defs -----------------
def ADD_amd {   // Instruction
}
def ADD_intel { // Instruction
}
def MUL_amd {   // Instruction
}
def MUL_intel { // Instruction
}
```
复杂的例子
```tablegen
// 定义一个指令类，包含4位操作码(opcode)和汇编名称(asm name)
class InstructionWithOpcode {
  bits<4> opcode;
  string asm;
}

// 定义一个multiclass，用于为每条之林生成两个变体
// 这两个变体使用指定的操作码和汇编名称
multiclass InstructionWithOpcodeM<bits<4> OpcodeA, bits<4> OpcodeB, string Asm> {
  def _amd : InstructionWithOpcode {
    bits<4> opcode = OpcodeA;
    string asm = Asm;
  }

  def _intel : InstructionWithOpcode {
    bits<4> opcode = OpcodeB;
    string asm = Asm;
  }
}

// 调用该multiclass，生成带有不同
// 操作码和汇编名臣的record
defm ADD : InstructionWithOpcodeM<0b0000, 0b0001, "add">;
// 这个将生成两条record
// ADD_amd, 操作码为0b0000, 汇编名为"add"
// ADD_intel, 操作码为0b0001, 汇编名为"mul"

defm SUB : InstructionWithOpcodeM<0b0010, 0b0011, "sub">;

```

### 预处理
```tablegen
/// prepeocessor.td

#ifndef PERPROCESSOR_TD
#define PERPROCESSOR_TD

// 只有当你的include路径设置正确时，这才能正常工作
include "mlir/IR/BuiltinAttributes.td"

class C {

}
// 预处理也可以使用#else

#endif // PERPROCESSOR_TD

```

### 举例说明
```tablegen
#ifndef SETUP
#define SETUP

class Op {
  string name;
}

def addOp : Op { let name = "add"; }
def mulOp : Op { let name = "mul"; }
def divOp : Op { let name = "div"; }

// defvar 用于定义一个全局变量
// 我们只是用它充当错误信息的占位符
defvar errorStr = "error";

#endif // SETUP
```
输出
```bash 
------------- Classes -----------------
class Op {
  string name = ?;
}
------------- Defs -----------------
def addOp {     // Op
  string name = "add";
}
def divOp {     // Op
  string name = "div";
}
def mulOp {     // Op
  string name = "mul";
}
```

### 一元运算符
```tablegen
#ifndef UNARYOPS
#define UNARYOPS

// 注意与c++不同， include前面没有#号
include "setup.td"

def UnaryOps {
  // !repr(value)
  // 将value 表示字符串
  // 该值的字符串格式在不同TableGen版本之间可能会变化
  // 所以不要依赖它完全精确
  // 仅供调试目的使用
  string addOp_s = !repr(addOp);
  // " addOp {
  // string name = "add";
  // }
  // ";

  // Base 2 log
  int logtwo_v = !logtwo(2); // 1
  assert !eq(logtwo_v, 1), errorStr;

  // 在64位整数上执行逻辑移位
  // 如果count &#3C; count > 6, 则结果未定义。
  // 移位函数的命名约定有点奇怪
  // Shift L

}

#endif // UNARYOPS
```


