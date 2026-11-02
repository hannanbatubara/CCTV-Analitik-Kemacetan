# ==================================
# LINE CROSSING COUNTER
# Kendaraan dihitung HANYA saat melewati garis hitung, satu kali per track.
# ==================================

from config import DEFAULT_LINE, VEHICLE_CLASSES


class LineCounter:
    """
    Arah ditentukan oleh sisi garis (dari titik 1 ke titik 2):
      "in"  = bergerak ke sisi positif (untuk garis horizontal kiri->kanan: ke bawah layar)
      "out" = bergerak ke sisi sebaliknya (ke atas layar)
    """

    def __init__(self, line=None):
        self.line = line or DEFAULT_LINE
        self.totals = {c: {"in": 0, "out": 0} for c in VEHICLE_CLASSES}
        self.counted_ids = set()

    def _pixel_line(self, width, height):
        l = self.line
        return (l["x1"] * width, l["y1"] * height, l["x2"] * width, l["y2"] * height)

    def _side(self, point, line):
        x1, y1, x2, y2 = line
        return (x2 - x1) * (point[1] - y1) - (y2 - y1) * (point[0] - x1)

    def pixel_line(self, frame_shape):
        h, w = frame_shape[:2]
        return tuple(int(v) for v in self._pixel_line(w, h))

    def update(self, track_id, cls, prev_point, point, frame_shape):
        """
        Mengembalikan "in"/"out" jika track baru saja melewati garis, selain itu None.
        """
        if prev_point is None or track_id in self.counted_ids:
            return None
        if cls not in self.totals:
            return None

        h, w = frame_shape[:2]
        line = self._pixel_line(w, h)
        s_prev = self._side(prev_point, line)
        s_now = self._side(point, line)

        if s_prev * s_now >= 0:  # tidak berpindah sisi
            return None

        direction = "in" if s_now > 0 else "out"
        self.totals[cls][direction] += 1
        self.counted_ids.add(track_id)
        return direction

    def forget(self, track_ids):
        self.counted_ids.difference_update(track_ids)

    def get_result(self):
        return self.totals
