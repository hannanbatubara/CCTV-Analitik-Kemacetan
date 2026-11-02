# CCTV Analitik Kemacetan

Modul **kemacetan** untuk analitik CCTV lalu lintas: mendeteksi dan melacak kendaraan dari stream CCTV,
menghitung kendaraan yang melewati garis hitung, dan menentukan tingkat kepadatan (LOW / MEDIUM / HIGH).
Kamera uji: **Depan Kantor Balaikota Bogor** (stream HLS publik Pemkot Bogor).

Modul ini satu dari tiga modul (kemacetan, kebakaran, kecelakaan) yang masing-masing berjalan di container
sendiri di server. Repo ini hanya berisi modul kemacetan.

---

## Daftar isi
1. [Cara kerja](#1-cara-kerja)
2. [Struktur folder](#2-struktur-folder)
3. [Menjalankan](#3-menjalankan)
4. [Konfigurasi](#4-konfigurasi)
5. [Output: JSON, API, database](#5-output-json-api-database)
6. [Model](#6-model)
7. [Riwayat percobaan](#7-riwayat-percobaan)
8. [Hasil validasi](#8-hasil-validasi)
9. [Sumber data dan lisensi](#9-sumber-data-dan-lisensi)

---

## 1. Cara kerja

```
Stream CCTV (HLS/RTSP)
   │  video_stream.py   ambil 1 dari tiap N frame (PROCESS_FPS), antrean berurutan
   ▼
Deteksi + tracking
   │  detector.py       YOLOv8s (OpenVINO) + ByteTrack
   ▼
State per kendaraan
   │  tracker.py        posisi sebelumnya, voting kelas, bersihkan track lama
   ▼
Hitung lewat garis
   │  counter.py        dihitung sekali per kendaraan saat melintasi garis, arah in/out
   ▼
Analisis kepadatan
   │  traffic.py        density dari rata-rata kendaraan di frame dalam 60 detik terakhir
   ▼
Output
      output.py / db.py / api.py   JSON tiap 10 detik, riwayat .jsonl, database, REST API
```

Metrik yang dihasilkan:

| Metrik | Arti |
|---|---|
| `vehicles_in_frame` | Jumlah kendaraan yang terlihat di frame saat ini |
| `avg_vehicles_in_frame` | Rata-rata kendaraan di frame selama jendela waktu (default 60 detik) |
| `density` | LOW / MEDIUM / HIGH berdasarkan `avg_vehicles_in_frame` dan dua batas di `config.py` |
| `flow_in_window` | Kendaraan yang melewati garis dalam jendela waktu terakhir, per kelas |
| `total_crossed` | Total kendaraan yang melewati garis sejak worker berjalan, per kelas dan arah (`in` = ke bawah layar, `out` = ke atas) |

Kelas kendaraan: `motorcycle`, `bus`, `car`, `truck` (angkot dihitung sebagai `car`).

---

## 2. Struktur folder

```
worker.py            program utama (loop stream -> deteksi -> hitung -> output)
config.py            semua pengaturan, bisa dioverride lewat environment variable
video_stream.py      pembaca stream (thread, frame berurutan, reconnect otomatis)
detector.py          YOLO + tracker
tracker.py           state track: posisi, voting kelas, pembersihan
counter.py           penghitung lewat garis
traffic.py           density dan flow per jendela waktu
output.py            JSON terbaru + riwayat .jsonl + database (opsional)
db.py                penyimpanan ke database (SQLAlchemy)
api.py               REST API (FastAPI)
bytetrack_lowfps.yaml  pengaturan ByteTrack untuk FPS pemrosesan rendah

Dockerfile, docker-compose.yml, requirements.txt, .env.example

data/cameras.json    daftar kamera: id, nama, lokasi, sumber stream, posisi garis hitung
models/best_openvino_model_v2/   model yang dipakai (YOLOv8s hasil fine-tune, OpenVINO, 640 px)

tools/
  merge_datasets.py      gabung dataset YOLO ke 4 kelas (peta nama/ID kelas, batas jumlah gambar)
  capture_frames.py      ambil frame dari stream + pra-label otomatis untuk anotasi
  cvat_tools.py          impor/ekspor pra-label ke CVAT (format YOLO 1.1)
  calibrate_density.py   hitung batas LOW/MEDIUM/HIGH dari log
  train_colab.ipynb      notebook training (fine-tune) di Google Colab
  test_merge.py          tes merge_datasets.py
tests/test_db.py         tes penyimpanan database

```

Tidak disertakan di repo: dataset, log, video uji, dan model lama (terlalu besar atau hanya untuk pengembangan).

---

## 3. Menjalankan

Semua perintah dijalankan dari folder utama (tempat `worker.py`).

### Lokal (Python 3.12/3.13)
```bash
pip install -r requirements.txt
python worker.py                       # headless, sumber dari data/cameras.json
python worker.py --show                # dengan jendela video (ESC untuk keluar)
python worker.py --source video.mp4    # uji dengan file video
python worker.py --camera 1            # pakai kamera ke-2 di cameras.json
uvicorn api:app --port 8000            # API
```

### Docker
```bash
docker compose up -d --build           # worker + API (http://localhost:8000/traffic/latest)
docker compose logs -f worker
docker compose down
```
`data/`, `models/`, dan `logs/` di-mount dari host, jadi kamera, garis hitung, dan model bisa diganti tanpa build ulang
(`docker compose restart worker`). Pengaturan server diisi di file `.env` (contoh di `.env.example`).

### Tes
```bash
python tools/test_merge.py
python tests/test_db.py
```

---

## 4. Konfigurasi

Semua nilai di `config.py` bisa dioverride lewat environment variable dengan nama yang sama (di Docker: file `.env`).

| Variabel | Default | Keterangan |
|---|---|---|
| `MODEL_PATH` | `models/best_openvino_model_v2` | Folder OpenVINO (server CPU) atau file `.pt` (server GPU) |
| `DEVICE` | otomatis | `0` untuk GPU NVIDIA, `cpu` untuk CPU |
| `CONFIDENCE` | `0.4` | Ambang keyakinan deteksi |
| `IOU` | `0.5` | Ambang NMS |
| `TRACKER` | `bytetrack_lowfps.yaml` | Pakai `bytetrack.yaml` di server cepat (>= 10 FPS) |
| `PROCESS_FPS` | `3` | Frame yang dianalisis per detik video. **Sangat menentukan akurasi**, lihat bagian 8 |
| `DENSITY_WINDOW_SECONDS` | `60` | Panjang jendela waktu untuk density dan flow |
| `LOW_THRESHOLD` / `MEDIUM_THRESHOLD` | `8` / `20` | Batas density (rata-rata kendaraan di frame). Perlu dikalibrasi per kamera |
| `SAVE_INTERVAL` | `10` | Detik antar snapshot |
| `DATABASE_URL` | kosong | Contoh `postgresql+psycopg2://user:pass@host:5432/db`. Kosong = tanpa database |
| `CAMERAS_FILE` | `data/cameras.json` | Daftar kamera |

Garis hitung per kamera diatur di `data/cameras.json` dengan koordinat relatif 0..1 (tidak bergantung resolusi):
```json
"line": {"x1": 0.0, "y1": 0.4, "x2": 1.0, "y2": 0.4}
```

---

## 5. Output: JSON, API, database

Setiap `SAVE_INTERVAL` detik:
- `logs/traffic_data.json`: snapshot terbaru (ditulis atomic, tidak pernah terbaca setengah jadi),
- `logs/traffic_YYYYMMDD.jsonl`: riwayat harian, satu baris per snapshot,
- tabel `traffic_snapshots` di database, jika `DATABASE_URL` diisi (tabel dibuat otomatis).

Contoh snapshot:
```json
{
  "module": "congestion",
  "camera_id": "CAM_001",
  "camera_name": "Depan Kantor Balaikota Bogor",
  "location": "BALAIKOTA_BOGOR",
  "lane": 2,
  "timestamp": "2026-10-29T08:49:10+07:00",
  "traffic": {
    "density": "MEDIUM",
    "window_seconds": 60,
    "vehicles_in_frame": 9,
    "avg_vehicles_in_frame": 11.2,
    "flow_in_window": {"total": 7, "detail": {"motorcycle": 3, "car": 4, "bus": 0, "truck": 0}},
    "total_crossed": {"total": 7, "detail": {"motorcycle": {"in": 2, "out": 1}, "car": {"in": 4, "out": 0},
                                              "bus": {"in": 0, "out": 0}, "truck": {"in": 0, "out": 0}}}
  }
}
```

API (baca saja):

| Endpoint | Isi |
|---|---|
| `GET /health` | `{"status": "ok"}` |
| `GET /traffic/latest` | Snapshot terbaru |
| `GET /traffic/history?limit=60&date=YYYYMMDD` | Snapshot terakhir dari log harian |

Kolom tabel database: `module`, `camera_id`, `location`, `timestamp`, `density`, `vehicles_in_frame`,
`avg_vehicles_in_frame`, `flow_in_window`, `total_crossed`, dan `detail` (JSON rincian per kelas dan arah).
Jika database gagal, worker tetap berjalan dan data tetap tersimpan di `.jsonl`.

---

## 6. Model

`models/best_openvino_model_v2` adalah YOLOv8s yang di-fine-tune dari model awal proyek dengan dataset gabungan
(lihat 7.5). Ekspor OpenVINO, input 640 x 640, kelas `0 motorcycle, 1 bus, 2 car, 3 truck`.

| Model | Precision | Recall | mAP50 | mAP50-95 |
|---|---|---|---|---|
| Model awal (validasi gabungan 102 gambar) | 0,771 | 0,692 | 0,845 | 0,678 |
| **Model v2 (validasi yang sama)** | **0,906** | **0,861** | **0,911** | **0,751** |

Training ulang: dari bobot model awal, 60 epoch, batch 16, 640 px, Google Colab (GPU T4), notebook `tools/train_colab.ipynb`.
Loss validasi turun sampai akhir (1,02 -> 0,77), tanpa tanda overfitting.

---

## 7. Riwayat percobaan

Catatan semua percobaan selama pengembangan, termasuk yang tidak dipakai, beserta alasannya.

### 7.1 Analisis kode awal
Masalah yang ditemukan di versi awal (kode awal disimpan di luar repo):

| Masalah | Akibat | Perbaikan |
|---|---|---|
| Hitungan kumulatif tidak pernah di-reset, lalu dibandingkan dengan batas density | Density naik ke MEDIUM/HIGH hanya karena program berjalan lama | Density dari rata-rata kendaraan di frame per jendela 60 detik |
| Garis hitung di config tidak dipakai; setiap ID baru dihitung | ID tracking yang pecah dihitung ganda, kendaraan parkir ikut terhitung | Hitung hanya saat melintasi garis, sekali per track, dengan arah |
| Pengaturan tersebar dan tidak konsisten (model, confidence, kamera) | Nilai di config tidak berpengaruh | Satu `config.py`, bisa dioverride env var |
| JSON dicetak tiap frame, `cv2.imshow` wajib | Lambat, tidak bisa jalan di server | Mode headless, log ringkas tiap 10 detik |
| Satu file log per 10 detik | ±8.600 file per hari | Satu file `.jsonl` per hari |
| Nomor label kendaraan diberikan ke setiap track baru | Nomor melompat (#23 -> #40) dan tidak sama dengan hitungan | Nomor diberikan saat kendaraan dihitung |

### 7.2 Pembacaan stream
- Stream HLS Balaikota 1920 x 1080 ternyata datang **berkelompok**: satu segmen dibaca sangat cepat (±480 frame/detik), lalu jeda ±2,8 detik.
- Cara awal (ambil frame terbaru) membuang hampir semua frame dalam satu kelompok, sehingga jarak waktu antar frame yang diproses bisa beberapa detik dan tracking putus.
- Solusi: ambil 1 dari setiap N frame (`PROCESS_FPS`) ke antrean berurutan.

| | Sebelum | Sesudah |
|---|---|---|
| Track terbentuk / track panjang (2 menit) | 208 / 41 | 119 / 93 |
| Median perjalanan track (posisi y relatif) | 0,21 -> 0,24 | 0,14 -> 0,64 |

### 7.3 Kalibrasi garis, tracker, dan confidence
Semua diuji pada klip stream Bogor 80 detik yang sama.

**Posisi garis.** Dari 93 track panjang, garis di y = 0,4 dilintasi 65 track (70%), di area tempat kendaraan cukup besar untuk dideteksi andal. Dipilih y = 0,4.

**Tracker** (jumlah kendaraan lewat garis):

| Konfigurasi | Lewat garis | Track dibuat |
|---|---|---|
| 7,5 FPS, ByteTrack default (pembanding) | 82 | 261 |
| **3 FPS, `bytetrack_lowfps.yaml` (dipakai)** | **73** | 124 |
| 3 FPS, ByteTrack default | 48 | 146 |
| 3 FPS, ByteTrack ketat | 60 | 114 |
| 5 FPS, ByteTrack default | 62 | 195 |

**Confidence** (3 FPS, tracker lowfps): 0,5 -> 73; **0,4 -> 77 (dipakai)**; 0,3 -> 80. Menurunkan confidence menambah kendaraan terdeteksi tanpa menambah track yang pecah.

Catatan: angka-angka ini dibandingkan antar konfigurasi, bukan dengan hitungan manual. Validasi manual (bagian 8) kemudian menunjukkan semua konfigurasi 3 FPS masih jauh di bawah jumlah sebenarnya.

### 7.4 Kecepatan inferensi (laptop Ryzen 5 3550H, 4 core)

| Percobaan | Hasil | Keputusan |
|---|---|---|
| OpenVINO FP32 di CPU | ±330-400 ms per frame (±2,5 FPS) | Dipakai |
| OpenVINO di GPU (iGPU Vega dan GTX 1050 lewat OpenVINO) | 570-640 ms per frame, lebih lambat | Tidak dipakai |
| Kuantisasi INT8 (NNCF, kalibrasi 300 frame Bogor) | 283 ms vs 387 ms, hitungan setara (82 vs 77) | Tidak dipakai: hanya relevan untuk laptop, server ditargetkan GPU |
| Ukuran input 640 / 800 / 960 | 17,5 / 17,8 / 13,1 deteksi per frame | Tetap 640 (800 tidak membantu walau model awal dilatih di 800) |
| GTX 1050 dengan PyTorch CUDA | Tidak diuji (PyTorch terpasang versi CPU) | Pekerjaan lanjutan |

### 7.5 Data dan training ulang

**Evaluasi model awal.** YOLOv8s, dilatih di dataset Roboflow "Traffic", berhenti di epoch 86 dari 200: precision 0,77, recall 0,55, mAP50 0,68.
Di stream Bogor: kendaraan dekat terdeteksi baik, tetapi kendaraan jauh banyak terlewat, bus kota sering terbaca truk,
**angkot hijau terbaca truk**, dan **tanaman di median terdeteksi sebagai motor** di posisi yang sama hampir di setiap frame.

**Model alternatif yang diuji.** Model 5 kelas lain (mAP50 0,94 di validasinya sendiri) hanya mendeteksi 11,8 kendaraan per frame di Bogor
dibanding 17,5 untuk model awal, jadi tidak dipakai. Skor tinggi di dataset sendiri tidak menjamin bagus di kamera lain.

**Dataset yang dipertimbangkan:**

| Dataset | Keputusan | Alasan |
|---|---|---|
| Traffic (Roboflow `iitp-w6lkv/traffic-er4bf`), CCTV Indonesia | **Dipakai penuh** (1.430 / 87 / 72 gambar) | `Bike` dipetakan ke motor, `Other` dilewati |
| vehicle-det (Roboflow `vehicledet/vehicle-det`) | **Dipakai 1.000 dari 19.422 gambar** | Urutan nama kelas di `data.yaml` **salah**; dipetakan per ID setelah dicek visual (0 bus, 1 car, 2 truck, 3 dan 4 motor). Dibatasi karena isinya foto umum, bukan CCTV |
| Frame Bogor (diambil sendiri) | **Dipakai** (85 train, 15 validasi) | Lihat di bawah |
| cctv (Roboflow `baemsu`) | Tidak | Hanya 8 gambar |
| vehicle-detection (Roboflow `shivin`) | Tidak | Kelas `LARGE_VEHICLE` (bus atau truk) dan roda tiga tidak cocok dengan 4 kelas |
| Vehicle_Detection (satu kelas "Vehicle") | Tidak | Tidak membedakan jenis kendaraan |
| InaTRC (Mendeley) | Tidak | Kelas "non-truk" mencampur mobil dan bus |
| UA-DETRAC, BMD-45 | Tidak | Tanpa kelas motor / lisensi dan unduhan belum jelas |

**Frame Bogor.** 100 frame diambil dari stream (29 Oktober 2026, 11:33-12:01) dengan `tools/capture_frames.py`,
lalu diberi pra-label oleh model awal. Perbaikan otomatis yang dicek visual:
- 136 kotak motor palsu pada tanaman median dihapus (87 gambar). Satu kotak berulang lain ternyata ojek yang benar-benar parkir, jadi dipertahankan.
- 16 kotak truk berwarna hijau (angkot) diubah ke `car` berdasarkan warna.

Koreksi manual penuh (Roboflow, lalu CVAT) direncanakan tetapi tidak dilakukan; Roboflow membutuhkan paket berbayar untuk sebagian fitur.
Jadi label frame Bogor masih sebagian besar berasal dari model awal.

**Dataset akhir** (`tools/merge_datasets.py`): 2.515 gambar latih, 102 validasi, 72 uji.
Objek: motor 8.797, mobil 7.365, truk 1.738, bus 912.

**Training** di Colab menghasilkan model v2 (bagian 6).

---

## 8. Hasil validasi

### 8.1 Model awal vs v2 di klip Bogor independen (tidak ikut training), 3 FPS

| | Model awal | Model v2 |
|---|---|---|
| Deteksi per frame | 12,5 | 15,1 |
| Kendaraan lewat garis (80 detik) | 77 | 87 |
| Motor / mobil / truk | 28 / 45 / 4 | 38 / 45 / 4 |

Pada 100 frame Bogor (ikut training, jadi bukan bukti generalisasi): kotak palsu di tanaman 52 -> 0 frame, angkot terbaca truk 14 -> 0.

### 8.2 Hitung manual vs program
Klip yang sama, detik 0 sampai 12,1, dihitung manual oleh satu orang:

| | FPS diproses | Motor | Mobil | Total | Dibanding manual |
|---|---|---|---|---|---|
| **Manual** | - | 21 | 10 | 31 | 100% |
| Model awal | 3 | 1 | 9 | 10 | 32% |
| Model v2 | 3 | 3 | 9 | 12 | 39% |
| Model v2 | 5 | 2 | 9 | 11 | 35% |
| **Model v2** | **15** | **17** | **9** | **26** | **84%** |

**Temuan utama: akurasi hitungan ditentukan oleh FPS pemrosesan.** Pada 3 FPS (batas CPU laptop) motor yang bergerak cepat
berpindah terlalu jauh antar frame sehingga tracking putus. Pada 15 FPS hasilnya mendekati hitungan manual.
Server produksi perlu memproses ±15 FPS per kamera (`PROCESS_FPS=15`, `TRACKER=bytetrack.yaml`), kemungkinan dengan GPU.

### 8.3 Docker
Diuji di Docker Desktop (Windows): image ±2,8 GB, worker ±580 MB RAM dan ±2,4 core pada 3 FPS. Worker membaca stream,
memuat model v2 dari volume, menulis snapshot ke `logs/`, dan API menjawab.

---

## 9. Sumber data dan lisensi

### Dataset yang dipakai untuk training model v2
| Dataset | Tautan | Lisensi | Pemakaian |
|---|---|---|---|
| Traffic (CCTV Indonesia), versi 1 | [universe.roboflow.com/iitp-w6lkv/traffic-er4bf/dataset/1](https://universe.roboflow.com/iitp-w6lkv/traffic-er4bf/dataset/1) | CC BY 4.0 | Semua gambar; `Bike` -> motor, `Other` dilewati |
| vehicle-det, versi 1 | [universe.roboflow.com/vehicledet/vehicle-det/dataset/1](https://universe.roboflow.com/vehicledet/vehicle-det/dataset/1) | CC BY 4.0 | 1.000 dari 19.422 gambar, kelas dipetakan per ID |
| Frame CCTV Balaikota Bogor | [app.roboflow.com/hannan-azhari-batubara/cctv-newak/1](https://app.roboflow.com/hannan-azhari-batubara/cctv-newak/1) (privat) | Privat | 100 frame, diambil dari stream sendiri |

### Dataset yang dipertimbangkan tetapi tidak dipakai
| Dataset | Tautan | Alasan |
|---|---|---|
| cctv (baemsu), versi 1 | [universe.roboflow.com/baemsu/cctv-39zes/dataset/1](https://universe.roboflow.com/baemsu/cctv-39zes/dataset/1) | Hanya 8 gambar |
| vehicle-detection (Shivin), versi 4 | [universe.roboflow.com/shivin/vehicle-detection-pvvca/dataset/4](https://universe.roboflow.com/shivin/vehicle-detection-pvvca/dataset/4) | Kelas tidak cocok dengan 4 kelas |
| Vehicle_Detection_YOLOv8 (farzad), versi 3 | [universe.roboflow.com/farzad/vehicle_detection_yolov8/dataset/3](https://universe.roboflow.com/farzad/vehicle_detection_yolov8/dataset/3) | Hanya satu kelas "Vehicle" |
| InaTRC (jalan tol Indonesia) | [data.mendeley.com/datasets/kddgphck3b/1](https://data.mendeley.com/datasets/kddgphck3b/1) | Mobil dan bus dalam satu kelas |
| UA-DETRAC (makalah) | [arxiv.org/abs/1511.04136](https://arxiv.org/abs/1511.04136) | Tidak ada kelas motor |
| BMD-45 (makalah) | [alphaxiv.org/abs/2604.24419](https://www.alphaxiv.org/abs/2604.24419) | Lisensi dan unduhan belum jelas |

### Lainnya
- Stream CCTV: Pemerintah Kota Bogor (restreamer publik).
- Model dan library deteksi: [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics), lisensi AGPL-3.0.
  Bobot model di repo ini turunan dari YOLOv8 dan mengikuti lisensi tersebut.
