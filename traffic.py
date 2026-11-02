# ==================================
# TRAFFIC ANALYTICS MODULE
# Density = rata-rata kendaraan di frame dalam jendela waktu terakhir.
# Flow    = jumlah kendaraan yang melewati garis dalam jendela waktu yang sama.
# Status  = LANCAR / RAMAI / MACET dari jumlah kendaraan DAN kecepatannya:
#           banyak kendaraan yang bergerak = RAMAI, banyak kendaraan yang merayap = MACET.
# ==================================

import statistics
import time
from collections import deque

from config import (
    DENSITY_WINDOW_SECONDS,
    FREE_FLOW_SPEED,
    JAM_SPEED_RATIO,
    LOW_THRESHOLD,
    MEDIUM_THRESHOLD,
    VEHICLE_CLASSES,
)


class TrafficAnalyzer:

    def __init__(self, window_seconds=DENSITY_WINDOW_SECONDS):
        self.window = window_seconds
        self._frames = deque()     # (timestamp, jumlah kendaraan di frame)
        self._crossings = deque()  # (timestamp, kelas)
        self._speeds = deque()     # (timestamp, kecepatan satu kendaraan)

    def record_frame(self, vehicles_in_frame, speeds=(), now=None):
        now = now if now is not None else time.time()
        self._frames.append((now, vehicles_in_frame))
        self._speeds.extend((now, s) for s in speeds)

    def record_crossing(self, cls, now=None):
        self._crossings.append((now if now is not None else time.time(), cls))

    def _prune(self, now):
        limit = now - self.window
        while self._frames and self._frames[0][0] < limit:
            self._frames.popleft()
        while self._crossings and self._crossings[0][0] < limit:
            self._crossings.popleft()
        while self._speeds and self._speeds[0][0] < limit:
            self._speeds.popleft()

    @staticmethod
    def classify(avg_in_frame):
        if avg_in_frame < LOW_THRESHOLD:
            return "LOW"
        if avg_in_frame < MEDIUM_THRESHOLD:
            return "MEDIUM"
        return "HIGH"

    @staticmethod
    def status(avg_in_frame, speed_ratio):
        if avg_in_frame >= LOW_THRESHOLD and speed_ratio is not None and speed_ratio < JAM_SPEED_RATIO:
            return "MACET"
        if avg_in_frame >= MEDIUM_THRESHOLD:
            return "RAMAI"
        return "LANCAR"

    def analyze(self, line_totals, now=None):
        now = now if now is not None else time.time()
        self._prune(now)

        counts = [n for _, n in self._frames]
        avg = round(sum(counts) / len(counts), 1) if counts else 0.0
        current = counts[-1] if counts else 0

        flow_detail = {c: 0 for c in VEHICLE_CLASSES}
        for _, cls in self._crossings:
            flow_detail[cls] = flow_detail.get(cls, 0) + 1

        total_crossed = sum(v["in"] + v["out"] for v in line_totals.values())

        # median: tidak terpengaruh beberapa track yang meloncat karena salah sambung
        speed = round(statistics.median(s for _, s in self._speeds), 2) if self._speeds else None
        ratio = round(speed / FREE_FLOW_SPEED, 2) if speed is not None else None

        return {
            "status": self.status(avg, ratio),
            "speed": speed,
            "speed_ratio": ratio,
            "density": self.classify(avg),
            "window_seconds": self.window,
            "vehicles_in_frame": current,
            "avg_vehicles_in_frame": avg,
            "flow_in_window": {
                "total": sum(flow_detail.values()),
                "detail": flow_detail,
            },
            "total_crossed": {
                "total": total_crossed,
                "detail": line_totals,
            },
        }
