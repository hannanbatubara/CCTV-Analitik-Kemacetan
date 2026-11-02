import json
import os
from datetime import datetime
from pathlib import Path

from config import LATEST_FILE, LOGS_DIR

DATABASE_URL = os.environ.get("DATABASE_URL")


class OutputManager:

    def __init__(self, camera):
        self.camera = camera
        self.base_dir = Path(__file__).resolve().parent
        self.logs_dir = self.base_dir / LOGS_DIR
        self.logs_dir.mkdir(exist_ok=True)
        self.latest_path = self.base_dir / LATEST_FILE

        self.db = None
        if DATABASE_URL:
            from db import Database
            self.db = Database(DATABASE_URL)

    def generate(self, traffic_data):
        return {
            "module": "congestion",
            "camera_id": self.camera["id"],
            "camera_name": self.camera.get("name"),
            "location": self.camera.get("location"),
            "lane": self.camera.get("lane"),
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "traffic": traffic_data,
        }

    def save_json(self, data):
        # 1. JSON terbaru (atomic: tidak pernah terbaca setengah jadi oleh API/dashboard)
        tmp = self.latest_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp, self.latest_path)

        # 2. Riwayat: satu baris JSON per snapshot, satu file per hari
        history = self.logs_dir / f"traffic_{datetime.now():%Y%m%d}.jsonl"
        with open(history, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")

    def display(self, data):
        t = data["traffic"]
        print(
            f"[{data['timestamp']}] {data['camera_id']} | "
            f"status={t['status']} (kecepatan {'-' if t['speed_ratio'] is None else t['speed_ratio']}x normal) | "
            f"density={t['density']} | in_frame={t['vehicles_in_frame']} "
            f"(avg {t['avg_vehicles_in_frame']}) | "
            f"flow/{t['window_seconds']}s={t['flow_in_window']['total']} | "
            f"total_crossed={t['total_crossed']['total']}",
            flush=True,
        )
