"""Frontend and verifier checks for the stage examples."""

import os
import shlex
import sys

import lit.formats

config.name = "Coral stage checks"
config.test_format = lit.formats.ShTest()
config.suffixes = [".test", ".mlir"]
config.test_source_root = os.path.dirname(__file__)
config.test_exec_root = os.path.abspath(lit_config.params.get("out", ".coral-lit"))

frontend = lit_config.params.get("frontend", "coral")
if frontend not in ("coral", "cuda"):
    lit_config.fatal("frontend must be coral or cuda")
if frontend == "cuda" or lit_config.params.get("dot") == "1":
    config.available_features.add("dot-frontend")
for name in ("TRITON_BACKENDS_IN_TREE", "PYTHONPATH"):
    if name in os.environ:
        config.environment[name] = os.environ[name]

for name, default in (("python", sys.executable), ("filecheck", "FileCheck"), ("triton_opt", "triton-opt")):
    config.substitutions.append(("%coral_" + name, shlex.quote(lit_config.params.get(name, default))))
config.substitutions.append(("%coral_frontend", frontend))
