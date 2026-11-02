# ==================================
# API untuk dashboard / konsumen data
#   uvicorn api:app --host 0.0.0.0 --port 8000
# ==================================

import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from config import LATEST_FILE, LOGS_DIR

BASE = Path(__file__).resolve().parent
app = FastAPI(title="CCTV Traffic Analytics API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/traffic/latest")
def latest():
    path = BASE / LATEST_FILE
    if not path.exists():
        raise HTTPException(404, "Belum ada data. Jalankan worker.py dulu.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/traffic/history")
def history(limit: int = Query(60, ge=1, le=1000), date: str | None = None):
    """Snapshot terakhir dari log harian. `date` format YYYYMMDD (default hari ini)."""
    date = date or datetime.now().strftime("%Y%m%d")
    if not (date.isdigit() and len(date) == 8):
        raise HTTPException(400, "Format date harus YYYYMMDD")
    path = BASE / LOGS_DIR / f"traffic_{date}.jsonl"
    if not path.exists():
        raise HTTPException(404, f"Tidak ada log untuk {date}")
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(l) for l in lines]
