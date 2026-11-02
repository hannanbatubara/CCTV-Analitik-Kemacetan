# ==================================
# CCTV TRAFFIC ANALYTICS CONFIG
# Nilai default di bawah bisa dioverride lewat environment variable
# bernama sama (di Docker: file .env). Pengaturan per kamera ada di
# data/cameras.json.
# ==================================

import os


def _env(name, default):
    """Baca env var, dikonversi ke tipe default; kosong/tidak ada -> default."""
    v = os.environ.get(name)
    return default if v in (None, "") else type(default)(v)


# Daftar kamera
CAMERAS_FILE = _env("CAMERAS_FILE", "data/cameras.json")

# YOLO model: folder OpenVINO (server CPU) atau file .pt (server GPU)
MODEL_PATH = _env("MODEL_PATH", "models/best_openvino_model_v3")  # sebelumnya: v2 (lemah di malam hari), model awal: best_openvino_model
DEVICE = _env("DEVICE", "")   # "" = otomatis; GPU NVIDIA: "0"; CPU: "cpu"
CONFIDENCE = _env("CONFIDENCE", 0.4)
IOU = _env("IOU", 0.5)
# bytetrack_lowfps.yaml untuk hardware ~3 FPS; di server cepat (>=10 FPS)
# pakai bytetrack.yaml
TRACKER = _env("TRACKER", "bytetrack_lowfps.yaml")

# Kelas kendaraan yang dihitung (harus sama dengan nama kelas di model)
VEHICLE_CLASSES = ["motorcycle", "car", "bus", "truck"]

# Garis hitung (koordinat RELATIF 0..1 terhadap lebar/tinggi frame,
# jadi tidak tergantung resolusi). Bisa dioverride per kamera di cameras.json
# dengan key "line".
DEFAULT_LINE = {"x1": 0.0, "y1": 0.4, "x2": 1.0, "y2": 0.4}

# Track yang tidak terlihat selama N frame dianggap hilang (dibersihkan dari memori)
TRACK_MAX_MISSING_FRAMES = _env("TRACK_MAX_MISSING_FRAMES", 90)

# Kepadatan lalu lintas dihitung dari rata-rata jumlah kendaraan
# yang terlihat di frame selama jendela waktu terakhir.
DENSITY_WINDOW_SECONDS = _env("DENSITY_WINDOW_SECONDS", 60)
LOW_THRESHOLD = _env("LOW_THRESHOLD", 8)        # rata-rata di frame < 8  -> LOW
MEDIUM_THRESHOLD = _env("MEDIUM_THRESHOLD", 20)  # < 20 -> MEDIUM, selebihnya HIGH
# CATATAN: threshold perlu dikalibrasi ulang di server (kamera & lokasi nyata).

# Status kemacetan (LANCAR / RAMAI / MACET) memakai kecepatan, bukan hanya jumlah.
# Kecepatan = perpindahan titik bawah kotak / tinggi kotak per detik ("panjang kendaraan per detik"),
# jadi kendaraan dekat dan jauh sebanding walau ukurannya di layar berbeda.
FREE_FLOW_SPEED = _env("FREE_FLOW_SPEED", 1.0)   # kecepatan normal saat jalan lengang (kalibrasi: tools/calibrate_density.py)
JAM_SPEED_RATIO = _env("JAM_SPEED_RATIO", 0.3)  # ramai + kecepatan < 30% normal -> MACET

# Penyimpanan
SAVE_INTERVAL = _env("SAVE_INTERVAL", 10)       # detik
LATEST_FILE = "logs/traffic_data.json"
LOGS_DIR = "logs"        # satu file JSONL per hari: traffic_YYYYMMDD.jsonl
# Database: lihat env DATABASE_URL di output.py / db.py

# Stream
# Frame yang dianalisis per detik video. 3 = laptop CPU lemah;
# di server GPU naikkan ke FPS stream (mis. 15).
PROCESS_FPS = _env("PROCESS_FPS", 3)
RECONNECT_DELAY = _env("RECONNECT_DELAY", 2)    # detik
