# ==================================
# VEHICLE TRACKER STATE
# Menyimpan posisi sebelumnya, voting kelas, dan membersihkan track lama.
# ==================================

from collections import Counter, deque

from config import TRACK_MAX_MISSING_FRAMES

SPEED_BASELINE_SECONDS = 1.0


class VehicleTracker:

    def __init__(self):
        self.tracks = {}  # track_id -> {"prev", "last_seen", "votes", "number"}

    def update(self, track_id, class_name, point, frame_idx, now=None, size=None):
        """
        Update state track. Mengembalikan titik posisi sebelumnya
        (None jika track baru). Jika `now` (detik video) dan `size` (tinggi kotak)
        diisi, kecepatan terakhir disimpan di speed(track_id).
        """
        t = self.tracks.get(track_id)

        if t is None:
            t = {
                "prev": None,
                "hist": deque(),  # (detik video, titik) selama ±1 detik terakhir
                "speed": None,
                "last_seen": frame_idx,
                "votes": Counter(),
                "number": None,  # diisi saat kendaraan dihitung
            }
            self.tracks[track_id] = t

        prev = t["prev"]
        t["speed"] = None
        if now is not None and size:
            # kecepatan diukur dari perpindahan selama ±1 detik, bukan antar frame:
            # getaran kotak antar frame tidak ikut terhitung, dan hasilnya sama di 3 FPS maupun 15 FPS
            hist = t["hist"]
            while hist and now - hist[0][0] > SPEED_BASELINE_SECONDS:
                hist.popleft()
            if hist and now - hist[0][0] >= SPEED_BASELINE_SECONDS / 2:
                t0, p0 = hist[0]
                dist = ((point[0] - p0[0]) ** 2 + (point[1] - p0[1]) ** 2) ** 0.5
                t["speed"] = dist / size / (now - t0)
            hist.append((now, point))
        t["prev"] = point
        t["last_seen"] = frame_idx
        t["votes"][class_name] += 1
        return prev

    def majority_class(self, track_id):
        """Kelas paling sering terdeteksi sepanjang track (lebih stabil)."""
        return self.tracks[track_id]["votes"].most_common(1)[0][0]

    def speed(self, track_id):
        """Kecepatan terakhir (panjang kendaraan per detik), None jika belum bisa dihitung."""
        return self.tracks[track_id]["speed"]

    def set_number(self, track_id, number):
        self.tracks[track_id]["number"] = number

    def label(self, track_id):
        cls = self.majority_class(track_id)
        return cls, self.tracks[track_id]["number"]

    def prune(self, frame_idx):
        """Hapus track yang sudah lama hilang. Mengembalikan daftar id yang dihapus."""
        stale = [
            tid for tid, t in self.tracks.items()
            if frame_idx - t["last_seen"] > TRACK_MAX_MISSING_FRAMES
        ]
        for tid in stale:
            del self.tracks[tid]
        return stale
