# Serah terima: modul kemacetan (CCTV Traffic Analytics)

Dokumen ini untuk tim yang memasang modul kemacetan di server. Modul lain (kebakaran, kecelakaan) berjalan di container masing-masing dan tidak dibahas di sini.

## 1. Apa yang dilakukan modul ini
- Membaca stream CCTV (HLS `.m3u8` atau RTSP) dari `data/cameras.json`.
- Mendeteksi kendaraan (motor, mobil, bus, truk) dengan YOLOv8s (OpenVINO), melacaknya dengan ByteTrack, dan menghitung kendaraan yang melewati garis hitung.
- Setiap 10 detik menulis satu snapshot:
  - `logs/traffic_data.json` (snapshot terbaru),
  - `logs/traffic_YYYYMMDD.jsonl` (riwayat harian),
  - tabel database `traffic_snapshots` (jika `DATABASE_URL` diisi).
- API baca-saja di port 8000: `/health`, `/traffic/latest`, `/traffic/history?limit=60&date=YYYYMMDD`.

## 2. Kebutuhan server
| Kebutuhan | Nilai |
|---|---|
| Perangkat lunak | Docker + Docker Compose v2 |
| Jaringan keluar | Akses HTTPS ke sumber stream (contoh: `restreamer3.kotabogor.go.id`) |
| Port | 8000 (API), sebaiknya hanya untuk jaringan internal |
| Image | ±2,8 GB (Python 3.12, PyTorch CPU, OpenVINO) |
| RAM worker | ±580 MB per kamera (terukur) |
| CPU worker | ±2,4 core penuh pada 3 FPS di laptop Ryzen 5 3550H (terukur) |

### Penting: kecepatan pemrosesan menentukan akurasi
Hitung manual pada klip 12,1 detik (31 kendaraan) dibanding program:

| FPS yang diproses | Hitungan program | Dibanding manual |
|---|---|---|
| 3 (batas CPU laptop) | 12 | 39% |
| 15 (semua frame) | 26 | 84% |

Detail: `docs/validasi_manual/hasil_validasi.md`. Jadi server sebaiknya mampu memproses **±15 FPS per kamera**. Dengan CPU saja, kemungkinan besar perlu GPU NVIDIA (lihat bagian 6). Sampel validasi ini kecil, jadi angkanya indikasi awal.

## 3. File yang diserahkan
Wajib:
```
*.py (worker, detector, tracker, counter, traffic, output, video_stream, db, api, config)
bytetrack_lowfps.yaml, requirements.txt, Dockerfile, docker-compose.yml, .env.example
data/cameras.json
models/best_openvino_model_v2/   (model yang dipakai, 43 MB)
```
Tidak perlu di server: `dataset/`, `archive/`, `tools/`, `tests/`, `docs/`, `models/best_openvino_model` (model lama), `data/video_cctv.mp4`.

## 4. Langkah pemasangan
```bash
cp .env.example .env          # lalu isi nilai yang diperlukan (bagian 5)
docker compose up -d --build
docker compose ps             # worker dan api harus "Up"
docker compose logs -f worker # harus muncul "CCTV Connected", "YOLO Model Loaded",
                              # lalu baris "CAM_001 | density=..." tiap 10 detik
curl http://localhost:8000/health
curl http://localhost:8000/traffic/latest
```
Mengganti model: taruh folder model baru di `models/`, ubah `MODEL_PATH` di `.env`, lalu `docker compose restart worker`. Model di-mount sebagai volume, jadi tidak perlu build ulang.

## 5. Pengaturan (`.env`)
| Variabel | Default | Server CPU | Server GPU |
|---|---|---|---|
| `DATABASE_URL` | kosong (tanpa DB) | `postgresql+psycopg2://user:pass@host:5432/db` | sama |
| `MODEL_PATH` | `models/best_openvino_model_v2` | default | `models/best_v2.pt` |
| `DEVICE` | otomatis | kosong | `0` |
| `PROCESS_FPS` | `3` | setinggi yang sanggup (ukur) | `15` |
| `TRACKER` | `bytetrack_lowfps.yaml` | lowfps jika < 10 FPS | `bytetrack.yaml` |
| `CONFIDENCE` | `0.4` | default | default |
| `LOW_THRESHOLD` / `MEDIUM_THRESHOLD` | `8` / `20` | **perlu kalibrasi** | **perlu kalibrasi** |

Cara mengukur kemampuan server CPU: jalankan worker, lihat `docker stats`. Kalau CPU worker selalu penuh, `PROCESS_FPS` terlalu tinggi dan frame akan dibuang.

## 6. Server GPU (belum diuji)
Dockerfile sekarang memasang PyTorch **versi CPU** dan menjalankan OpenVINO. Untuk GPU NVIDIA perlu:
1. NVIDIA Container Toolkit di server.
2. Ganti baris PyTorch di Dockerfile ke versi CUDA (atau pakai base image PyTorch CUDA).
3. Tambahkan reservasi GPU di service `worker` pada `docker-compose.yml`:
   ```yaml
   deploy:
     resources:
       reservations:
         devices: [{driver: nvidia, count: 1, capabilities: [gpu]}]
   ```
4. Bobot PyTorch model baru: unduh `cctv/runs/v2/weights/best.pt` dari Google Drive, simpan sebagai `models/best_v2.pt`. **`models/best.pt` adalah model lama.**

Jalur ini belum pernah dijalankan; uji dulu di server.

## 7. Database
- Tabel `traffic_snapshots` dibuat otomatis saat worker pertama kali jalan.
- Kolom: `id`, `module` (`congestion`), `camera_id`, `location`, `timestamp` (dengan zona waktu), `density`, `vehicles_in_frame`, `avg_vehicles_in_frame`, `flow_in_window`, `total_crossed`, `detail` (JSON per kelas dan arah). Ada indeks `(camera_id, timestamp)`.
- Jika database tidak bisa dihubungi, worker **tetap berjalan** dan mencetak `DB gagal menyimpan: ...`. Snapshot itu tidak dikirim ulang, tetapi tetap ada di `logs/*.jsonl`.
- Diuji dengan SQLite. **Belum diuji dengan PostgreSQL sungguhan.**
- Kalau tim backend sudah punya skema sendiri, sesuaikan `db.py`.

## 8. Format JSON
```json
{
  "module": "congestion",
  "camera_id": "CAM_001",
  "camera_name": "Depan Kantor Balaikota Bogor",
  "location": "BALAIKOTA_BOGOR",
  "lane": 2,
  "timestamp": "2026-10-31T22:32:40+07:00",
  "traffic": {
    "density": "LOW",
    "window_seconds": 60,
    "vehicles_in_frame": 1,
    "avg_vehicles_in_frame": 0.8,
    "flow_in_window": {"total": 0, "detail": {"motorcycle": 0, "car": 0, "bus": 0, "truck": 0}},
    "total_crossed": {"total": 0, "detail": {"motorcycle": {"in": 0, "out": 0}, "car": {"in": 0, "out": 0},
                                             "bus": {"in": 0, "out": 0}, "truck": {"in": 0, "out": 0}}}
  }
}
```
- `density`: LOW/MEDIUM/HIGH dari rata-rata kendaraan di layar selama 60 detik terakhir.
- `flow_in_window`: kendaraan yang melewati garis dalam 60 detik terakhir.
- `total_crossed`: total kendaraan yang melewati garis sejak worker dinyalakan (kembali ke 0 saat restart). `in` = bergerak ke bawah layar, `out` = ke atas.

## 9. Kalibrasi per kamera (wajib di server)
- **Garis hitung**: `line` di `data/cameras.json` (koordinat relatif 0–1). Saat ini y = 0,4 untuk kamera Balaikota.
- **Threshold density**: dari log minimal satu hari (jam sepi dan sibuk), ambil persentil ke-33 dan ke-80 dari `avg_vehicles_in_frame`.
- **`PROCESS_FPS`**: sesuaikan dengan kemampuan server (bagian 5).
- Kamera lain: tambahkan entri di `cameras.json` dan jalankan worker dengan `--camera N` (satu worker per kamera).

## 10. Keterbatasan yang diketahui
- Validasi akurasi baru satu klip 12,1 detik dengan satu pencacah manual.
- Model lemah untuk kendaraan yang sangat jauh, dan kelas bus belum teruji di klip validasi.
- Data latih frame Bogor belum dikoreksi manual sepenuhnya.
- API tanpa autentikasi; jangan dibuka ke internet.
- Docker Compose membangun dua image (worker dan api) dari Dockerfile yang sama; layer-nya dipakai bersama sehingga tidak menggandakan ruang disk.
