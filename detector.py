# ==================================
# YOLO DETECTOR MODULE
# ==================================

from ultralytics import YOLO

from config import CONFIDENCE, DEVICE, IOU, MODEL_PATH, TRACKER


class Detector:

    def __init__(self):
        self.model = YOLO(MODEL_PATH, task="detect")
        self.names = self.model.names
        print("YOLO Model Loaded")

    def detect(self, frame):
        result = self.model.track(
            frame,
            persist=True,
            conf=CONFIDENCE,
            iou=IOU,
            tracker=TRACKER,
            verbose=False,
            **({"device": DEVICE} if DEVICE else {}),
        )
        return result[0]
