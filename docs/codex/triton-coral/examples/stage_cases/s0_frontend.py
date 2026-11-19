"""S0 case definitions."""

from .inputs import scalar


def add_cases(add):
    add("S0.frontend", "S0", [scalar("scalar_copy", -3)], mode="frontend")
    add("S0.bad-target", "S0", [scalar("scalar_copy", -3)], mode="frontend",
        error="NC_UNSUPPORTED_TARGET", target_override="coral-invalid")
