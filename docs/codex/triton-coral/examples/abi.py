"""Reference codecs for current v2 and proposed v3; not firmware implementation."""

import struct

CAPACITY = {2: (3, 4), 3: (8, 12)}
FRAME_SIZE = {2: 68, 3: 128}


def unsigned(value, name):
    if type(value) is not int or not 0 <= value < 1 << 32:
        raise ValueError(name + " must fit an unsigned device word")
    return value


def word(value):
    if type(value) is not int or not -(1 << 31) <= value < 1 << 32:
        raise ValueError("scalar cannot be silently truncated to 32 bits")
    return value & 0xFFFFFFFF


def pack_frame(version, bindings, scalars, *, program_id, grid, core_id, done):
    if version not in CAPACITY:
        raise ValueError("unknown ABI version")
    nb, ns = CAPACITY[version]
    if len(bindings) > nb or len(scalars) > ns:
        raise ValueError("argument slots exceed ABI capacity")
    if len(program_id) != 3 or len(grid) != 3:
        raise ValueError("program_id/grid must have three axes")
    for pid, count in zip(program_id, grid):
        unsigned(pid, "program_id"); unsigned(count, "grid")
        if count == 0 or pid >= count:
            raise ValueError("zero grid is not launched; program_id must be inside grid")
    unsigned(core_id, "core_id"); unsigned(done, "done")
    if done == 0 or done % 4:
        raise ValueError("done must be a nonzero word-aligned device address")
    addresses = [unsigned(p, "binding") for p in bindings] + [0] * (nb - len(bindings))
    values = [word(v) for v in scalars] + [0] * (ns - len(scalars))
    prefix = [version, FRAME_SIZE[version], *program_id, *grid, core_id]
    words = (prefix + addresses + values + [done] if version == 2 else
             prefix + [len(bindings), len(scalars), done] + addresses + values)
    return struct.pack("<" + "I" * len(words), *words)


def unpack_frame(data):
    if len(data) < 8:
        raise ValueError("truncated ABI header")
    version, size = struct.unpack_from("<II", data)
    if version not in FRAME_SIZE or size != FRAME_SIZE[version] or len(data) != size:
        raise ValueError("unknown ABI or incorrect size")
    words = list(struct.unpack("<" + "I" * (size // 4), data))
    if version == 2:
        nb, ns, base, done = 3, 4, 9, words[16]
    else:
        nb, ns, base, done = words[9], words[10], 12, words[11]
        if nb > 8 or ns > 12:
            raise ValueError("argument counts exceed ABI capacity")
        if any(words[12 + nb:20]) or any(words[20 + ns:32]):
            raise ValueError("unused v3 slots must be zero")
    bindings = words[base:base + CAPACITY[version][0]]
    scalars = words[base + CAPACITY[version][0]:base + sum(CAPACITY[version])]
    # Reuse range/grid/completion validation; decoding does not validate target region permissions.
    pack_frame(version, bindings[:nb], scalars[:ns], program_id=words[2:5], grid=words[5:8],
               core_id=words[8], done=done)
    return {"version": version, "size": size, "program_id": words[2:5], "grid": words[5:8],
            "core_id": words[8], "done": done, "bindings": bindings[:nb], "scalars": scalars[:ns]}
