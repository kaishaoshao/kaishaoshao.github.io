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
'!' 是TableGen的[bang 运算符]标记
在TableGen的语法里，所有求值运算符都必须以!开头。llvm-tblgen解析到!时才知道接下来时一个内置运算符号调用，要做计算而不是普通标识符。

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
  // Shift Left logical(逻辑左移) -> shl
  int shl_v = !shl(1, 3); // 8
  assert !eq(shl_v, 8), errorStr;

  // Shift Right Logical (逻辑右移) -> srl
  int srl_v = !srl(8, 3); // 1
  assert !eq(srl_v, 1), errorStr;

  // !not(a)
  bit not_t = !not(true); // 0
  assert !eq(not_t, 0), errorStr;

  bit not_f = !not(false); // 1
  assert !eq(not_f, 1), errorStr;

  // 对 0 和 1的作用与对 true/false相同
  bit not_1 = !not(1); // 0
  assert !eq(not_1, 0), errorStr;

  // !empty(a)
  // 如果字符串、列表或DAG a为空， 该运算符产生1； 否则为0.
  // 如果 DAG没有参数， 则它为空；运算符本身不计入
  bit empty_string = !empty("");
  assert empty_string, errorStr;

  // size(a) (求长度)
  int size_hello = !size("Hello, World!"); // 13
  assert !eq(size_hello, 13), errorStr;

  int size_list = !size([1, 2, 3]); // 3
  assert !eq(size_list, 3), errorStr;

}

#endif // UNARYOPS
```

输出：
```bash
./llvm-project/build/bin/mlir-tblgen /tmp/unaryops.td  -I /tmp/
------------- Classes -----------------
class Op {
  string name = ?;
}
------------- Defs -----------------
def UnaryOps {
  string addOp_s = "addOp {     // Op
  string name = "add";
}
";
  int logtwo_v = 1;
  int shl_v = 8;
  int srl_v = 1;
  bit not_t = 0;
  bit not_f = 1;
  bit not_1 = 0;
  bit empty_string = 1;
  int size_hello = 13;
  int size_list = 3;
}
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

### 二元运算符

```tablegen
/// binaryops.td

#ifndef BINARYOPS
#define BINARYOPS

include "setup.td"

def BinaryOps {
  // !add(a, b, ...) // 
  int add_v = !add(10, 50, -59); // 1
  assert !eq(add_v, 1), errorStr;

  // 二元算术运算符， 形式为
  // !op(a, b)
  int sub_v = !sub(100, 99); // 1
  assert !eq(sub_v, 1), errorStr;

  int mul_v = !mul(2, 3, 4); // 24
  assert !eq(mul_v, 24), errorStr;

  int div_v = !div(100, 100);
  assert !eq(div_v, 1), errorStr;

  // 二元逻辑运算符，形式为
  // ！op(a, b)
  bit eq_v = !eq(10, 10); // true, 转换为1
  assert eq_v, errorStr;

  bit ne_v = !ne(10, 11); // 1
  assert ne_v, errorStr;

  bit gt_v = !gt(11, 10); // 1
  assert gt_v, errorStr;

  bit lt_v = !lt(10, 11); // 1
  assert lt_v, errorStr;

  bit le_v = !le(10, 11); // 1
  assert le_v, errorStr;

  // 逻辑运算符，形式为
  // ！op(a, b, ...)
  bit and_v = !and(true, true, true); // 1
  assert and_v, errorStr;

  bit or_v = !or(false, false, false, true); // 1
  assert or_v, errorStr;

  bit xor_v = !xor(true, false, false, false, false); // 1
  assert xor_v, errorStr;  
}

#endif  // BINARYOPS
```

输出
```tablegen
------------- Classes -----------------
class Op {
  string name = ?;
}
------------- Defs -----------------
def BinaryOps {
  int add_v = 1;
  int sub_v = 1;
  int mul_v = 24;
  int div_v = 1;
  bit eq_v = 1;
  bit ne_v = 1;
  bit gt_v = 1;
  bit lt_v = 1;
  bit le_v = 1;
  bit and_v = 1;
  bit or_v = 1;
  bit xor_v = 1;
}
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

### 字符串运算符
```tablegen
/// stringops.td

#ifndef STRINGOPS
#define STRINGOPS

include "setup.td"

def StringOps {
  // strconcat(str1, str2, ...)字符串连接
  string str_c = !strconcat("Hello, ", "World!"); // "Hello, World!"
  assert !eq(str_c, "Hello, World!"), errorStr;

  // !subst(target, repl, value)
  // 在value 中吧 target替换为repl
  string str_s = !subst("World", "Universe", "Hello World World!");
  assert !eq(str_s, "Hello Universe Universe!"), errorStr;

  // !tolower(a) 转小写
  string str_t = !tolower("Hello World"); // "hello world"
  assert !eq(str_t, "hello world"), errorStr;

  // ！toupper(a) 转大写
  string str_u = !toupper("Hello World");
  assert !eq(str_u, "HELLO WORLD"), errorStr;

  // !find(string1, string2[, start])
  // 在string1 中查找 string2, 返回起始下标； 可选参数start指定从哪个下标开始查找
  // 找不到返回-1
  int index1 = !find("Hello World", "World"); // 6
  assert !eq(index1, 6), errorStr;

  int index2 = !find("Hello World", "World", 6); // 6
  assert !eq(index2, 6), errorStr;

  int index3 = !find("Hello World", "World", 7); // -1
  assert !eq(index3, -1), errorStr;
}

#endif // STRINGOPS
```
输出
```tablegen
------------- Classes -----------------
class Op {
  string name = ?;
}
------------- Defs -----------------
def StringOps {
  string str_c = "Hello, World!";
  string str_s = "Hello Universe Universe!";
  string str_t = "hello world";
  string str_u = "HELLO WORLD";
  int index1 = 6;
  int index2 = 6;
  int index3 = -1;
}
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

### 列表运算符
```tablegen
#ifndef LISTOPS
#define LISTOPS

include "setup.td"

def ListOps {
  // 列表及其相关操作
  list<int> lst_1 = [10, 20];
  list<int> lst_2 = [30, 40];

  // !listconcat(list1, list2, ...) 允许传入任意数量的列表进行拼接
  list<int> lst_c = !listconcat(lst_1, lst_2); // [10, 20, 30, 40]
  assert !eq(!repr(lst_c), "[10, 20, 30, 40]"), errorStr;

  // !listremove(list1, list2) 从list1中移除包含在list2中的所有元素
  list<int> lst_r = !listremove(lst_c, lst_2); // [10, 20]
  assert !eq(!repr(lst_r), "[10, 20]"), errorStr;

  // !head(list) 获取列表的第0个元素（头部元素）
  int h = !head(lst_c); // 10
  assert !eq(h, 10), errorStr;

  // !tail(list) 移除列表的头部元素，返回剩余部分
  list<int> t = !tail(lst_c); // [20, 30, 40]
  assert !eq(!repr(t), "[20, 30, 40]"), errorStr;

  // “Splat”表示通过多次复制某个值来填充更大的结构
  // 在这里，数值1被重复2次以生成列表[1, 1, 1].
  list<int> lst_s= !listsplat(1, 3); // [1, 1, 1]
  assert !eq(!repr(lst_s), "[1, 1, 1]"), errorStr;

  // !foreach(var, sequence, expr) - 遍历列表中每个元素对其执行表达式求值
  list<int> foreach_v = !foreach(px, [1, 2, 3], !mul(px, 2)); // [2, 4, 6]
  assert !eq(!repr(foreach_v), "[2, 4, 6]"), errorStr;

  // range([start,] end [, step]) - 生成一个数字列表[start, end), 即左闭有开区间]
  list<int> r1 = !range(4); // 等价于 ！range(0, 4, 1) == [0, 1, 2, 3]
  assert !eq(!repr(r1), "[0, 1, 2, 3]"), errorStr;

  list<int> r2 = !range(1, 4); // !range(1, 4, 1) == [1, 2, 3]
  assert !eq(!repr(r2), "[1, 2, 3]"), errorStr;

  list<int> r3 = !range(0, 4, 2); // [0, 2]
  assert !eq(!repr(r3), "[0, 2]"), errorStr;

  list<int> r4 = !range(4, 1, -2); // [4, 2]
  assert !eq(!repr(r4), "[4, 2]"), errorStr;

  list<int> r5 = !range(0, 4, -1); // 步长方向相反，生成空列表[]
  assert !eq(!repr(r5), "[]"), errorStr;

  list<int> r6 = !range(4, 0, 1); // 起点大于终点且步长为正，生成空列表[]
  assert !eq(!repr(r6), "[]"), errorStr;

  // !foldl(init, list, acc, var, expr)
  // 注意：它是从左向右折叠(fold-left), 因此foldl而不仅仅是fold
  int sum_v = !foldl(0, [1, 1, 1, 1], total, rec, !add(total, rec)); // 4
  assert !eq(sum_v, 4), errorStr;
  
  string op_string = !foldl("", [addOp, mulOp, divOp], str,
  op, !strconcat(str, ", ", op.name)); // ", add, mul, div"
  assert !eq(op_string, ", add, mul, div"), errorStr;

  // !filter(var, list, predicate) - 过滤列表
  // var 用于再predicate(谓词条件)中引用当前的列表项
  list<int> filteredList = !filter(x, [1, 2, 3, 4, 5, 6], !eq(x, 3)); // [3]
  assert !eq(!repr(filteredList), "[3]"), errorStr;

  list<Op> filteredRecList = !filter(op, [addOp, mulOp, divOp], !eq(op.name, "add")); // [addOp]
  assert !eq(filteredRecList[0], addOp), errorStr;

  // 检查列表是否为空
  assert !empty([]<int>), errorStr;
  assert !empty(r5), errorStr;
  assert !empty(r6), errorStr;

  // ！range(list) 等价于 !range(0, !size(list)), 生成对应列表长度的索引序列
  list<int> charIndices = !range(["a", "b", "c"]); // [0, 1, 2]
  assert !eq(!repr(charIndices), "[0, 1, 2]"), errorStr;
}
#endif // LISTOPS
```
输出
```bash
------------- Classes -----------------
class Op {
  string name = ?;
}
------------- Defs -----------------
def ListOps {
  list<int> lst_1 = [10, 20];
  list<int> lst_2 = [30, 40];
  list<int> lst_c = [10, 20, 30, 40];
  list<int> lst_r = [10, 20];
  int h = 10;
  list<int> t = [20, 30, 40];
  list<int> lst_s = [1, 1, 1];
  list<int> foreach_v = [2, 4, 6];
  list<int> r1 = [0, 1, 2, 3];
  list<int> r2 = [1, 2, 3];
  list<int> r3 = [0, 2];
  list<int> r4 = [4, 2];
  list<int> r5 = [];
  list<int> r6 = [];
  int sum_v = 4;
  string op_string = ", add, mul, div";
  list<int> filteredList = [3];
  list<Op> filteredRecList = [addOp];
  list<int> charIndices = [0, 1, 2];
}
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

### !subst记录
```tablegen
// 定义三个测试记录(record): R1\R2\R3
class C {

}
def R1 : C {

}
def R2 : C {

}

def R3 : C {

}

// !subst(target, repl, value)
// 如果value是一个记录名称， 该运算符会检查value的，记录名称是否与target的记录名称匹配
// - 如果记录名称匹配，运算符返回repl记录
// - 如果记录名称不匹配，运算符直接返回原value记录。
def R4 : C {
  // 现在使用！subst将一个记录替换为另一个记录
  // 如果value是R1, 它会将其替换为R2.
  C reuslt = !subst(R1, R2, R1); // == 将R1中的R1替换为R2 -> 得到R2

  // 如果value是R3，则不会发生替换，因为R3 != R1.
  C no_substitution = !subst(R1, R2, R3); // == 将R3 中的R1替换为R2 -> 得到R3.
  // 因为R3中找不到R1

}
```

### DAG OP
TableGen 中的一个 DAG 单元（称为节点）由一个运算符和零个或多个参数组成。参数也可以是 DAG 节点，因此我们可以创建节点层次结构
```tablegen
/// dagops.td
#ifndef DAGOP
#define DAGOP

include "setup.td"

def DagOps {
  // !dag(operator, args, argNames) - 创建一个DAG(有向无环图节点)
  dag binOp1 = !dag(addOp, [10, 20], ["op1", "op2"]); // 创建结构为:(addOp 10:Sop1, 20:$op2)
  assert !eq(!repr(binOp1), "(addOp 10:$op1, 20:$op2)"), errorStr;
}

#endif // DAGOP
```
输出
```bash 

```