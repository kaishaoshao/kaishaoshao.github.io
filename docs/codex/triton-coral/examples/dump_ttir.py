"""Frontend-only validation using the pinned Triton ASTSource API; no device launch."""

import argparse
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

from suite import cases


def make_ttir(item, tutorial_dot_contract=False):
    from triton.backends import backends
    from triton.backends.compiler import GPUTarget
    from triton.compiler.compiler import ASTSource
    from triton._C.libtriton import ir

    kernels = importlib.import_module("kernels")
    function = getattr(kernels, item["kernel"])
    signature = {}
    for name in function.arg_names:
        if name in item["buffers"]:
            dtype = item["buffers"][name]["dtype"]
            signature[name] = {"i32": "*i32", "i8": "*i8", "f32": "*fp32", "bf16": "*bf16"}[dtype]
        elif name in item["scalars"]:
            signature[name] = "i32"
        else:
            signature[name] = "constexpr"
    # These options describe only language-to-TTIR checks. They do not enable ISA features.
    options = SimpleNamespace(arch="coral-rv32", backend_name="coral", debug=False, num_ctas=1,
                              sanitize_overflow=False, default_dot_input_precision="ieee",
                              allowed_dot_input_precisions=("ieee",), max_num_imprecise_acc_default=0,
                              deprecated_fp8_dot_operand_dtypes=(), supported_fp8_dtypes=())
    context = ir.context()
    ir.load_dialects(context)
    target = GPUTarget("coral", "coral-rv32", 1)
    backend = backends["coral"].compiler(target)
    backend.load_dialects(context)
    codegen = backend.get_codegen_implementation(options)
    if tutorial_dot_contract:
        import triton.language as tl

        def minimum_shape(lhs, rhs):
            if lhs.scalar != tl.int8 or rhs.scalar != tl.int8:
                raise ValueError("tutorial dot contract is INT8 only")
            return (16, 16, 32)

        codegen["min_dot_size"] = minimum_shape
    source = ASTSource(function, signature, constexprs=item["constants"])
    module = source.make_ir(target, options, codegen, backend.get_module_map(), context)
    if module.verify() is False:
        raise ValueError("TTIR verifier failed: " + item["kernel"])
    return str(module)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=[f"S{i}" for i in range(10)], required=True)
    parser.add_argument("--cumulative", action="store_true")
    parser.add_argument("--tutorial-dot-contract", action="store_true",
                        help="proposed INT8 16x16x32 frontend bound, not implemented backend/hardware support")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    selected = [c for c in cases() if (int(c["stage"][1:]) <= int(args.stage[1:]) if args.cumulative
                                     else c["stage"] == args.stage)]
    args.output.mkdir(parents=True, exist_ok=True)
    seen, inventory = set(), []
    for case in selected:
        if case["error"]:
            continue
        for index, item in enumerate(case["steps"]):
            key = json.dumps([item["kernel"], {n: b["dtype"] for n, b in item["buffers"].items()},
                              item["constants"]], sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            text = make_ttir(item, args.tutorial_dot_contract)
            filename = f"{case['id']}.{index}.ttir"
            (args.output / filename).write_text(text, encoding="utf-8")
            inventory.append({"case": case["id"], "kernel": item["kernel"], "file": filename})
    metadata = {"scope": "frontend-only", "dot_contract": "tutorial-proposal" if args.tutorial_dot_contract else "backend",
                "specializations": inventory}
    (args.output / "frontend.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"FRONTEND ONLY: {len(inventory)} TTIR specializations verified; no ELF or Coral execution tested.")


if __name__ == "__main__":
    main()
