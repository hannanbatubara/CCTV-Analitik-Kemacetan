import threading
import time
from collections import deque

import cv2

from config import PROCESS_FPS, RECONNECT_DELAY

LIVE_PREFIXES = ("http://", "https://", "rtsp://", "rtmp://")
DEFAULT_STREAM_FPS = 15


class VideoStream:
    """
    Sumber video.
    - Live (m3u8/rtsp): thread pembaca men-decode semua frame, tetapi hanya
      mengambil 1 dari setiap N frame (N dari PROCESS_FPS) dan memasukkannya ke
      antrean berurutan. Jarak waktu antar frame yang diproses jadi konstan
      (penting untuk tracking), walau HLS mengirim frame secara berkelompok.
      Jika inferensi lebih lambat dari antrean, frame terlama dibuang.
    - File: dibaca berurutan; `ended` menjadi True di akhir file (kecuali loop=True).
    """

    def __init__(self, source, loop=False):
        self.source = source
        self.loop = loop
        self.is_live = str(source).lower().startswith(LIVE_PREFIXES)
        self.ended = False

        self.cap = None
        self.time = 0.0  # waktu video (detik) dari frame terakhir yang dikembalikan read()
        self._fps = DEFAULT_STREAM_FPS
        self._queue = deque(maxlen=4)
        self._cond = threading.Condition()
        self._running = True
        self.stride = 1

        self._connect()

        if self.is_live:
            self._thread = threading.Thread(target=self._reader, daemon=True)
            self._thread.start()

    def _connect(self):
        if self.cap is not None:
            self.cap.release()
        self.cap = cv2.VideoCapture(self.source)
        ok = self.cap.isOpened()
        print("CCTV Connected" if ok else "CCTV Failed")
        if ok:
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            fps = fps if fps and 1 < fps <= 120 else DEFAULT_STREAM_FPS
            self._fps = fps
            self.stride = max(1, round(fps / PROCESS_FPS))
        return ok

    def _reader(self):
        i = 0
        while self._running:
            # grab() hanya men-decode; retrieve() (konversi BGR) hanya untuk
            # frame yang benar-benar diproses -> hemat CPU untuk inferensi.
            if not (self.cap.isOpened() and self.cap.grab()):
                print("Stream lost. Reconnecting...")
                time.sleep(RECONNECT_DELAY)
                self._connect()
                continue
            i += 1
            if i % self.stride:
                continue
            ret, frame = self.cap.retrieve()
            if ret:
                with self._cond:
                    self._queue.append((i / self._fps, frame))
                    self._cond.notify()

    def read(self):
        """Mengembalikan frame berikutnya, atau None jika belum ada / video selesai."""
        if self.is_live:
            with self._cond:
                if not self._queue:
                    self._cond.wait(timeout=2.0)
                if not self._queue:
                    return None
                self.time, frame = self._queue.popleft()
                return frame

        ret, frame = self.cap.read()
        if ret:
            self.time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            return frame
        if self.loop:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        else:
            self.ended = True
        return None

    def release(self):
        self._running = False
        if self.is_live and self._thread.is_alive():
            self._thread.join(timeout=5)
        if self.cap is not None:
            self.cap.release()
