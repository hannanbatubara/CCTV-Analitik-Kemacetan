"""
Ambil frame dari stream CCTV untuk dianotasi, plus pra-label dari model sekarang.

  python tools/capture_frames.py --every 30 --count 300 --prelabel

Hasil di dataset/frames_bogor/: gambar .jpg, label YOLO .txt (jika --prelabel), data.yaml.
Pra-label HANYA bantuan: periksa tiap gambar, tambahkan kendaraan yang terlewat
dan hapus kotak yang salah, jangan dipercaya mentah-mentah.
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # config.py ada di root
from config import CAMERAS_FILE, MODEL_PATH

CLASSES = ["motorcycle", "bus", "car", "truck"]  # urutan sama dengan dataset_gabungan


def capture(source, out, every, count):
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise SystemExit("Stream gagal dibuka")
    saved, last = 0, 0.0
    while saved < count:
        ok, frame = cap.read()
        if not ok:
            time.sleep(1)
            cap = cv2.VideoCapture(source)  # sambung ulang
            continue
        if time.time() - last >= every:
            name = datetime.now().strftime("bogor_%Y%m%d_%H%M%S")
            cv2.imwrite(str(out / f"{name}.jpg"), frame)
            saved, last = saved + 1, time.time()
            print(f"[{saved}/{count}] {name}", flush=True)
    cap.release()


def prelabel(out, conf):
    from ultralytics import YOLO
    model = YOLO(MODEL_PATH, task="detect")
    for img in sorted(out.glob("*.jpg")):
        r = model.predict(str(img), conf=conf, verbose=False)[0]
        lines = []
        for (x, y, w, h), c in zip(r.boxes.xywhn.tolist(), r.boxes.cls.tolist()):
            name = model.names[int(c)]
            if name in CLASSES:
                lines.append(f"{CLASSES.index(name)} {x:.6f} {y:.6f} {w:.6f} {h:.6f}")
        img.with_suffix(".txt").write_text("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=float, default=30, help="detik antar frame")
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--out", default="dataset/frames_bogor")
    ap.add_argument("--prelabel", action="store_true")
    ap.add_argument("--conf", type=float, default=0.3, help="confidence pra-label (rendah = lebih banyak kandidat)")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(exist_ok=True)
    source = json.load(open(CAMERAS_FILE, encoding="utf-8"))[0]["source"]
    capture(source, out, a.every, a.count)
    if a.prelabel:
        prelabel(out, a.conf)
    (out / "data.yaml").write_text("names:\n" + "".join(f"  {i}: {n}\n" for i, n in enumerate(CLASSES)))
    print("Selesai:", len(list(out.glob("*.jpg"))), "gambar di", out)
