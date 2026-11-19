"""S7 case definitions."""

from .inputs import vector


def add_cases(add):
    for cores in (1, 15):
        add(f"S7.tiers.mask{cores}", "S7", [vector(257, 16, region="hbf")], cores=cores,
            features=("schedule", "dma"), storage_path=["hbf", "dram", "dtcm", "dram"], buffer_policy="single")
    for suffix, error in (("hbf-write", "NC_READ_ONLY"), ("owner", "NC_OWNER"), ("dma-mid", "NC_DMA_ERROR")):
        transfer = vector(37, 16, region="hbf")
        fault = None
        if suffix == "hbf-write":
            transfer["buffers"]["Y"]["region"] = "hbf"
        elif suffix == "owner":
            transfer["buffers"]["Y"].update(region="dtcm", owner=3)
        else:
            fault = {"engine": "dma", "after_bytes": 16}
        add("S7." + suffix, "S7", [transfer], error=error,
            fault=fault, features=("dma",), storage_path=["hbf", "dram", "dtcm", "dram"])
