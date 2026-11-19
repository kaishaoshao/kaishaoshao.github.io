"""S6 case definitions."""

from .inputs import SENTINEL, buffer, step


def add_cases(add):
    for cores in (1, 3, 15):
        for nx, ny in ((1, 1), (5, 13)):
            out = [x + 100 * y + 10000 * nx + 1000000 * ny for y in range(ny) for x in range(nx)]
            add(f"S6.grid.{nx}x{ny}.mask{cores}", "S6", [step("grid_ids",
                {"Y": buffer("i32", [SENTINEL] * (nx * ny))}, grid=[nx, ny, 1], expected={"Y": out})],
                cores=cores, features=("schedule",))
    nx, ny, nz = 3, 5, 5
    out = [x + 10 * y + 100 * z + 1000 * nz for z in range(nz) for y in range(ny) for x in range(nx)]
    add("S6.grid.3d", "S6", [step("grid_ids_3d", {"Y": buffer("i32", [SENTINEL] * len(out))},
        grid=[nx, ny, nz], expected={"Y": out})], cores=15, features=("schedule",))
