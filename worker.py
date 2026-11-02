# ==================================
# CCTV TRAFFIC ANALYTICS WORKER
#   python worker.py            -> headless (server)
#   python worker.py --show     -> tampilkan jendela (ESC untuk keluar)
# ==================================

import argparse
import json
import signal
import time

import cv2

from config import CAMERAS_FILE, DEFAULT_LINE, PROCESS_FPS, SAVE_INTERVAL, VEHICLE_CLASSES
from counter import LineCounter
from detector import Detector
from output import OutputManager
from tracker import VehicleTracker
from traffic import TrafficAnalyzer
from video_stream import VideoStream

CLASS_COLORS = {  # BGR
    "car": (0, 200, 0),
    "motorcycle": (255, 0, 0),
    "bus": (0, 255, 255),
    "truck": (0, 140, 255),
}
WINDOW_NAME = "CCTV TRAFFIC ANALYTICS"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--show", action="store_true", help="tampilkan jendela video")
    p.add_argument("--camera", type=int, default=0, help="index kamera di cameras.json")
    p.add_argument("--source", help="override sumber video (mis. video_cctv.mp4)")
    p.add_argument("--loop", action="store_true", help="ulangi video file saat selesai")
    p.add_argument("--record", help="simpan video beranotasi ke file .mp4 (mis. rekaman.mp4)")
    p.add_argument("--duration", type=float, help="berhenti otomatis setelah sekian detik")
    return p.parse_args()


def draw_box_and_label(frame, box, label, color):
    x1, y1, x2, y2 = box
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    font, scale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
    (tw, th), _ = cv2.getTextSize(label, font, scale, thick)
    ly1 = max(0, y1 - th - 10)
    cv2.rectangle(frame, (x1, ly1), (x1 + tw + 10, y1), color, -1)
    cv2.putText(frame, label, (x1 + 5, y1 - 5), font, scale, (255, 255, 255), thick, cv2.LINE_AA)


def draw_overlay(frame, camera_name, traffic_result, line):
    t = traffic_result
    cv2.line(frame, (line[0], line[1]), (line[2], line[3]), (0, 0, 255), 3)
    cv2.putText(frame, f"Camera: {camera_name}", (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(frame, f"Density: {t['density']} | In frame: {t['vehicles_in_frame']} "
                       f"| Flow/{t['window_seconds']}s: {t['flow_in_window']['total']}",
                (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)
    per_class = "  ".join(
        f"{c}: {sum(v.values())}" for c, v in t["total_crossed"]["detail"].items()
    )
    cv2.putText(frame, f"Crossed {t['total_crossed']['total']} | {per_class}", (20, 105),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)


def main():
    args = parse_args()

    with open(CAMERAS_FILE, "r", encoding="utf-8") as f:
        camera = json.load(f)[args.camera]

    source = args.source or camera["source"]
    line_cfg = camera.get("line", DEFAULT_LINE)

    print("==============================")
    print(" CCTV TRAFFIC SERVER START ")
    print("==============================")
    print("Camera :", camera["name"])
    print("Source :", source)

    stream = VideoStream(source, loop=args.loop)
    detector = Detector()
    tracker = VehicleTracker()
    counter = LineCounter(line_cfg)
    traffic = TrafficAnalyzer()
    output = OutputManager(camera)

    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    if args.show:
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    draw = args.show or args.record
    writer = None

    last_save = time.time()
    frame_idx = 0
    final_data = None

    start = time.time()
    while running and not stream.ended:
        if args.duration and time.time() - start >= args.duration:
            break
        frame = stream.read()
        if frame is None:
            continue
        frame_idx += 1
        annotated = frame.copy() if draw else None

        result = detector.detect(frame)
        in_frame = 0

        if result.boxes.id is not None:
            boxes = result.boxes.xyxy.cpu().numpy()
            ids = result.boxes.id.cpu().numpy()
            classes = result.boxes.cls.cpu().numpy()

            for box, track_id, cls in zip(boxes, ids, classes):
                class_name = detector.names[int(cls)]
                if class_name not in VEHICLE_CLASSES:
                    continue

                in_frame += 1
                track_id = int(track_id)
                x1, y1, x2, y2 = map(int, box)
                point = ((x1 + x2) / 2, y2)  # tengah-bawah box ~ posisi di jalan

                prev = tracker.update(track_id, class_name, point, frame_idx)
                voted_cls, _ = tracker.label(track_id)

                if counter.update(track_id, voted_cls, prev, point, frame.shape):
                    traffic.record_crossing(voted_cls)
                    c = counter.totals[voted_cls]
                    tracker.set_number(track_id, c["in"] + c["out"])

                if draw:
                    _, number = tracker.label(track_id)
                    text = voted_cls.upper() + (f" #{number}" if number else "")
                    draw_box_and_label(
                        annotated, (x1, y1, x2, y2), text,
                        CLASS_COLORS.get(voted_cls, (255, 255, 255)),
                    )

        counter.forget(tracker.prune(frame_idx))
        traffic.record_frame(in_frame)

        now = time.time()
        if now - last_save >= SAVE_INTERVAL:
            final_data = output.generate(traffic.analyze(counter.get_result()))
            output.save_json(final_data)
            output.display(final_data)
            last_save = now

        if draw:
            traffic_result = traffic.analyze(counter.get_result())
            draw_overlay(annotated, camera["name"], traffic_result,
                         counter.pixel_line(frame.shape))
            if annotated.shape[1] > 1280:
                r = 1280 / annotated.shape[1]
                annotated = cv2.resize(annotated, (1280, int(annotated.shape[0] * r)))
            if args.record:
                if writer is None:
                    h, w = annotated.shape[:2]
                    writer = cv2.VideoWriter(args.record, cv2.VideoWriter_fourcc(*"mp4v"), PROCESS_FPS, (w, h))
                    written = 0
                # frame diulang jika pemrosesan lebih lambat dari PROCESS_FPS, supaya video tetap berjalan seperti waktu nyata
                while written < (time.time() - start) * PROCESS_FPS:
                    writer.write(annotated)
                    written += 1
            if args.show:
                cv2.imshow(WINDOW_NAME, annotated)
                if cv2.waitKey(1) == 27:
                    break

    print("Stopping CCTV Worker...")
    # simpan snapshot terakhir
    final_data = output.generate(traffic.analyze(counter.get_result()))
    output.save_json(final_data)
    output.display(final_data)

    stream.release()
    if writer is not None:
        writer.release()
    if args.show:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
