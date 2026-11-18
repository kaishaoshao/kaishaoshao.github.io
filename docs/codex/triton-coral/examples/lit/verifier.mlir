// RUN: %coral_triton_opt %s --split-input-file --verify-diagnostics

// Expected LLVM dialect contract for the empty-kernel micro-step.
llvm.func @empty_kernel(%x: !llvm.ptr, %y: !llvm.ptr) {
  llvm.return
}

// -----

// A valid Triton program cannot produce this mismatched return signature.
// expected-note @+1 {{when returning from function}}
llvm.func @wrong_return(%x: i32) {
  // expected-error @+1 {{expected no operands}}
  llvm.return %x : i32
}
