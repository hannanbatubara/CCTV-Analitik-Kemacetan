# ==================================
# VEHICLE TRACKER STATE
# Menyimpan posisi sebelumnya, voting kelas, dan membersihkan track lama.
# ==================================

from collections import Counter

from config import TRACK_MAX_MISSING_FRAMES


class VehicleTracker:

    def __init__(self):
        self.tracks = {}  # track_id -> {"prev", "last_seen", "votes", "number"}

    def update(self, track_id, class_name, point, frame_idx):
        """
        Update state track. Mengembalikan titik posisi sebelumnya
        (None jika track baru).
        """
        t = self.tracks.get(track_id)

        if t is None:
            t = {
                "prev": None,
                "last_seen": frame_idx,
                "votes": Counter(),
                "number": None,  # diisi saat kendaraan dihitung
            }
            self.tracks[track_id] = t

        prev = t["prev"]
        t["prev"] = point
        t["last_seen"] = frame_idx
        t["votes"][class_name] += 1
        return prev

    def majority_class(self, track_id):
        """Kelas paling sering terdeteksi sepanjang track (lebih stabil)."""
        return self.tracks[track_id]["votes"].most_common(1)[0][0]

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
