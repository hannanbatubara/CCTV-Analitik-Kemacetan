"""
Gabung beberapa dataset format YOLO (struktur Roboflow) ke 4 kelas model ini.

  python tools/merge_datasets.py OUT_DIR DATASET1 DATASET2 ... [--map nama=kelas ...] [--limit N] [--idmap NAMA=0:bus,...]

Tiap DATASET berisi data.yaml dan folder train/valid(val)/test dengan images/ & labels/.
Nama kelas dipetakan lewat SYNONYMS; nama yang tidak dikenal DILEWATI dan dilaporkan
(tambahkan lewat --map, mis. --map bike=motorcycle).
"""
import argparse
import random
import shutil
from collections import Counter
from pathlib import Path

import yaml

TARGET = ["motorcycle", "bus", "car", "truck"]  # urutan ID = model saat ini

SYNONYMS = {
    "motorcycle": "motorcycle", "motorbike": "motorcycle", "motor": "motorcycle",
    "bus": "bus",
    "car": "car", "sedan": "car", "suv": "car", "van": "car", "mpv": "car",
    "minibus": "car", "pickup": "car", "pick-up": "car", "jeep": "car", "taxi": "car",
    "truck": "truck", "lorry": "truck", "trailer": "truck",
}
SPLITS = {"train": "train", "valid": "val", "val": "val", "test": "test"}
IMG_EXT = {".jpg", ".jpeg", ".png"}


def class_names(ds):
    names = yaml.safe_load((ds / "data.yaml").read_text(encoding="utf-8"))["names"]
    return dict(enumerate(names)) if isinstance(names, list) else {int(k): v for k, v in names.items()}


def merge(out, datasets, extra_map=None, limit=None, idmaps=None):
    syn = {**SYNONYMS, **(extra_map or {})}
    stats, unmapped = Counter(), Counter()

    for ds in map(Path, datasets):
        names = class_names(ds)
        new_id = {i: TARGET.index(syn[n.lower()]) for i, n in names.items() if n.lower() in syn}
        if idmaps and ds.name in idmaps:  # data.yaml salah urutan -> pakai ID asli
            new_id = {i: TARGET.index(c) for i, c in idmaps[ds.name].items()}
            names = {i: n for i, n in names.items() if i not in new_id}
        for i, n in names.items():
            if i not in new_id:
                unmapped[f"{ds.name}:{n}"] += 1

        items = []  # (split, split_dir, img)
        for split_dir in ds.iterdir():
            split = SPLITS.get(split_dir.name)
            if split and (split_dir / "images").is_dir():
                items += [(split, split_dir, i) for i in sorted((split_dir / "images").iterdir())
                          if i.suffix.lower() in IMG_EXT]
        if limit and len(items) > limit:  # ambil acak (tetap proporsional antar split)
            items = random.Random(0).sample(items, limit)

        for split, split_dir, img in items:
            (out / "images" / split).mkdir(parents=True, exist_ok=True)
            (out / "labels" / split).mkdir(parents=True, exist_ok=True)
            lbl = split_dir / "labels" / (img.stem + ".txt")
            lines = []
            if lbl.exists():
                for ln in lbl.read_text().splitlines():
                    p = ln.split()
                    if len(p) == 5 and int(p[0]) in new_id:  # hanya bounding box
                        lines.append(" ".join([str(new_id[int(p[0])])] + p[1:]))
                        stats[TARGET[new_id[int(p[0])]]] += 1
            name = f"{ds.name}_{img.stem}".replace(" ", "_")
            shutil.copy2(img, out / "images" / split / (name + img.suffix))
            (out / "labels" / split / (name + ".txt")).write_text("\n".join(lines))
            stats[f"gambar_{split}"] += 1

    (out / "data.yaml").write_text(yaml.safe_dump({
        "train": "images/train", "val": "images/val",
        "test": "images/test", "names": dict(enumerate(TARGET)),
    }), encoding="utf-8")
    return stats, unmapped


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("datasets", nargs="+")
    ap.add_argument("--limit", type=int, help="maks. gambar per dataset (acak)")
    ap.add_argument("--idmap", nargs="*", default=[],
                    help="NAMA_FOLDER=0:bus,1:car,... (abaikan nama di data.yaml)")
    ap.add_argument("--map", nargs="*", default=[], help="nama=kelas")
    a = ap.parse_args()
    extra = dict(m.split("=") for m in a.map)
    idmaps = {}
    for m in a.idmap:
        name, spec = m.split("=")
        idmaps[name] = {int(k): v for k, v in (p.split(":") for p in spec.split(","))}
    stats, unmapped = merge(Path(a.out), a.datasets, extra, a.limit, idmaps)
    print("Hasil:", dict(stats))
    if unmapped:
        print("DILEWATI (kelas tak dikenal, objeknya jadi tak berlabel!):", list(unmapped))
