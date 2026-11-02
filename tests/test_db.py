# python tests/test_db.py  -> uji simpan snapshot ke SQLite sementara
import os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

path = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["DATABASE_URL"] = f"sqlite:///{path}"

from output import OutputManager
from traffic import TrafficAnalyzer
from sqlalchemy import text

cam = {"id": "CAM_TEST", "name": "t", "location": "X", "lane": 1}
out = OutputManager(cam)
ta = TrafficAnalyzer()
ta.record_frame(5); ta.record_crossing("car")
data = out.generate(ta.analyze({"car": {"in": 1, "out": 0}, "motorcycle": {"in": 0, "out": 0},
                                "bus": {"in": 0, "out": 0}, "truck": {"in": 0, "out": 0}}))
out.db.save(data)
with out.db.engine.connect() as c:
    rows = c.execute(text("select module, camera_id, density, flow_in_window, total_crossed from traffic_snapshots")).all()
assert rows == [("congestion", "CAM_TEST", "LOW", 1, 1)], rows
print("OK", rows)
