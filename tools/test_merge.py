# python tools/test_merge.py -> uji penggabungan dua dataset tiruan dengan urutan kelas berbeda
import tempfile
from pathlib import Path

import yaml

from merge_datasets import merge


def make(root, name, names, labels):
    d = root / name
    for split, rows in labels.items():
        (d / split / "images").mkdir(parents=True)
        (d / split / "labels").mkdir(parents=True)
        for i, row in enumerate(rows):
            (d / split / "images" / f"{i}.jpg").write_bytes(b"x")
            (d / split / "labels" / f"{i}.txt").write_text(row)
    (d / "data.yaml").write_text(yaml.safe_dump({"names": names}))
    return d


root = Path(tempfile.mkdtemp())
a = make(root, "A", ["Car", "Truck", "Bike", "person"], {"train": ["0 .5 .5 .1 .1\n1 .2 .2 .1 .1\n2 .3 .3 .1 .1"], "valid": ["3 .5 .5 .1 .1"]})
b = make(root, "B", {0: "motorcycle", 1: "bus", 2: "car"}, {"train": ["0 .5 .5 .1 .1\n2 .6 .6 .1 .1"]})
stats, unmapped = merge(root / "out", [a, b])

assert stats["car"] == 2 and stats["truck"] == 1 and stats["motorcycle"] == 1, stats
assert set(unmapped) == {"A:Bike", "A:person"}, unmapped  # Bike ambigu -> harus dipetakan manual
lbl = (root / "out/labels/train/A_0.txt").read_text().split("\n")
assert lbl == ["2 .5 .5 .1 .1", "3 .2 .2 .1 .1"], lbl  # Car->2, Truck->3, Bike dibuang
assert (root / "out/labels/val/A_0.txt").read_text() == ""  # gambar tanpa kendaraan = latar
stats, _ = merge(root / "out2", [a], {"bike": "motorcycle"})
assert stats["motorcycle"] == 1, stats
stats, _ = merge(root / "out3", [a, b], limit=1)
assert stats["gambar_train"] + stats["gambar_val"] == 2, stats  # 1 gambar per dataset
c = make(root, "C", ["x", "y"], {"train": ["0 .5 .5 .1 .1\n1 .2 .2 .1 .1"]})  # nama di yaml salah
stats, un = merge(root / "out4", [c], idmaps={"C": {0: "bus", 1: "motorcycle"}})
assert stats["bus"] == 1 and stats["motorcycle"] == 1 and not un, (stats, un)
print("OK", dict(stats))
