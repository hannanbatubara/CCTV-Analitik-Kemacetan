"""
Alat bantu CVAT (format "YOLO 1.1") untuk frame Bogor.

  python tools/cvat_tools.py pack
      -> dataset/cvat_import.zip : pra-label dari dataset/frames_bogor/ untuk diimpor ke CVAT
  python tools/cvat_tools.py unpack EXPORT.zip OUT_DIR
      -> OUT_DIR berisi train/ dan valid/ (gambar diambil dari dataset/frames_bogor/),
         siap digabung dengan merge_datasets.py. Frame di dataset/val_frames.txt jadi valid.
"""
import shutil
import sys
import zipfile
from pathlib import Path

CLASSES = ["motorcycle", "bus", "car", "truck"]  # urutan = model & dataset_final
FRAMES = Path("dataset/frames_bogor")
VAL_LIST = Path("dataset/val_frames.txt")


def pack(out="dataset/cvat_import.zip"):
    labels = sorted(FRAMES.glob("bogor_*.txt"))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("obj.data", "classes = 4\ntrain = train.txt\nnames = obj.names\nbackup = backup/\n")
        z.writestr("obj.names", "\n".join(CLASSES) + "\n")
        z.writestr("train.txt", "".join(f"data/obj_train_data/{p.stem}.jpg\n" for p in labels))
        for p in labels:
            rows = [ln.strip() for ln in p.read_text().splitlines() if ln.strip()]
            z.writestr(f"obj_train_data/{p.name}", "\n".join(rows) + "\n")
    print(f"{out}: {len(labels)} gambar berlabel")


def unpack(export_zip, out_dir):
    val = set(VAL_LIST.read_text().split()) if VAL_LIST.exists() else set()
    out = Path(out_dir)
    stats = {"train": 0, "valid": 0}
    with zipfile.ZipFile(export_zip) as z:
        names = [n.strip() for n in z.read("obj.names").decode().splitlines() if n.strip()]
        bad = [n for n in names if n not in CLASSES]
        assert not bad, f"kelas tak dikenal di CVAT: {bad}"
        for member in z.namelist():
            p = Path(member)
            if p.suffix != ".txt" or not p.parent.name.startswith("obj_") or not p.parent.name.endswith("_data"):
                continue
            img = FRAMES / (p.stem + ".jpg")
            assert img.exists(), f"gambar tidak ada di {FRAMES}: {img.name}"
            lines = []
            for ln in z.read(member).decode().splitlines():
                q = ln.split()
                if len(q) == 5:
                    lines.append(" ".join([str(CLASSES.index(names[int(q[0])]))] + q[1:]))
            split = "valid" if p.stem in val else "train"
            (out / split / "images").mkdir(parents=True, exist_ok=True)
            (out / split / "labels").mkdir(parents=True, exist_ok=True)
            shutil.copy2(img, out / split / "images" / img.name)
            (out / split / "labels" / p.name).write_text("\n".join(lines))
            stats[split] += 1
    (out / "data.yaml").write_text("names:\n" + "".join(f"  {i}: {n}\n" for i, n in enumerate(CLASSES)))
    print("Hasil:", stats)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "pack":
        pack()
    elif cmd == "unpack" and len(sys.argv) == 4:
        unpack(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
