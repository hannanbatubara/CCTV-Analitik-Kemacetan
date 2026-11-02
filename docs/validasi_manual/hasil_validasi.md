# Validasi hitungan kendaraan: manual vs program

Klip: `clip_hitung.mp4` (CCTV Depan Balaikota Bogor, 15 FPS), **detik 0 sampai 12,1**.
Garis hitung: y = 0,4 dari tinggi frame. Kendaraan dihitung sekali saat melewati garis, dari arah mana pun.
Model: `best_openvino_model_v2` (hasil fine-tune), confidence 0,4.

## Hitungan manual (acuan)
| Motor | Mobil | Bus/truk | Total |
|---|---|---|---|
| 21 | 10 | 0 | 31 |

## Hasil program pada klip yang sama
| Konfigurasi | FPS diproses | Motor | Mobil | Total | Total / manual |
|---|---|---|---|---|---|
| Model lama, tracker lowfps | 3 | 1 | 9 | 10 | 32% |
| Model baru, tracker lowfps | 3 | 3 | 9 | 12 | 39% |
| Model baru, tracker default | 5 | 2 | 9 | 11 | 35% |
| **Model baru, tracker default** | **15 (semua frame)** | **17** | **9** | **26** | **84%** |

## Kesimpulan
- Hitungan program sangat bergantung pada **FPS yang diproses**, bukan hanya pada modelnya.
  Pada 3 FPS (batas CPU laptop, ±330 ms per frame) tracking sering putus sehingga kendaraan yang bergerak cepat
  (terutama motor) tidak terhitung. Pada 15 FPS hasilnya 26 dari 31 (motor 17 dari 21, mobil 9 dari 10).
- Karena itu angka hitungan yang dihasilkan di laptop ini (sekitar 3 FPS) **under-count** dan tidak boleh dianggap akurasi akhir.
- Server untuk produksi perlu memproses mendekati FPS stream (idealnya GPU), dengan `PROCESS_FPS=15` dan `TRACKER=bytetrack.yaml`.

## Batasan validasi ini
- Sampel kecil: satu klip, 12,1 detik, 31 kendaraan. Perlu sampel lebih panjang dan di waktu lain untuk kesimpulan yang kuat.
- Hitungan dibandingkan sebagai total per kelas, bukan dicocokkan kendaraan per kendaraan. Kemungkinan ada hitungan ganda
  yang menutupi kendaraan yang terlewat di 26 itu.
- Hanya satu pencacah manual.
