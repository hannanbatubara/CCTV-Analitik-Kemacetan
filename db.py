# ==================================
# PENYIMPANAN KE DATABASE (opsional)
# Aktif jika env DATABASE_URL diisi, contoh:
#   postgresql+psycopg2://user:pass@host:5432/traffic
#   sqlite:///traffic.db
# ==================================

from datetime import datetime

from sqlalchemy import (
    JSON, Column, DateTime, Float, Index, Integer, MetaData, String, Table,
    create_engine,
)

metadata = MetaData()

traffic_snapshots = Table(
    "traffic_snapshots", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("module", String(32), nullable=False),
    Column("camera_id", String(64), nullable=False),
    Column("location", String(128)),
    Column("timestamp", DateTime(timezone=True), nullable=False),
    Column("density", String(16), nullable=False),
    Column("vehicles_in_frame", Integer, nullable=False),
    Column("avg_vehicles_in_frame", Float, nullable=False),
    Column("flow_in_window", Integer, nullable=False),
    Column("total_crossed", Integer, nullable=False),
    Column("detail", JSON, nullable=False),  # rincian per kelas & arah
    Index("ix_traffic_camera_time", "camera_id", "timestamp"),
)


class Database:

    def __init__(self, url):
        # pool_pre_ping: koneksi yang diputus server dibuka ulang otomatis
        self.engine = create_engine(url, pool_pre_ping=True)
        metadata.create_all(self.engine)

    def save(self, data):
        t = data["traffic"]
        row = {
            "module": data["module"],
            "camera_id": data["camera_id"],
            "location": data.get("location"),
            "timestamp": datetime.fromisoformat(data["timestamp"]),
            "density": t["density"],
            "vehicles_in_frame": t["vehicles_in_frame"],
            "avg_vehicles_in_frame": t["avg_vehicles_in_frame"],
            "flow_in_window": t["flow_in_window"]["total"],
            "total_crossed": t["total_crossed"]["total"],
            "detail": {
                "flow_in_window": t["flow_in_window"]["detail"],
                "total_crossed": t["total_crossed"]["detail"],
            },
        }
        with self.engine.begin() as conn:
            conn.execute(traffic_snapshots.insert(), row)
