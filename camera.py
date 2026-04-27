"""
camera.py — Persistent camera connection with warmup and optimization.

Provides a thread-safe camera interface that keeps the connection open
for fast successive captures.
"""

import cv2
import base64
import threading

# === CONFIGURATION ===
CAMERA_INDEX = 1  # Try 0 first on Linux; override if needed
WARMUP_FRAMES = 3
MAX_IMAGE_SIZE = 512
JPEG_QUALITY = 85

# === INTERNAL STATE ===
_camera_lock = threading.Lock()
_camera_conn: cv2.VideoCapture | None = None


def _get_camera() -> cv2.VideoCapture | None:
    """Return the persistent camera, creating it on first call."""
    global _camera_conn
    if _camera_conn is not None and _camera_conn.isOpened():
        return _camera_conn

    # Try the configured index first, then scan others
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        for i in range(5):
            if i == CAMERA_INDEX:
                continue
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                break

    if not cap.isOpened():
        return None

    # Warmup: discard initial dark/unstable frames
    for _ in range(WARMUP_FRAMES):
        cap.read()

    _camera_conn = cap
    return _camera_conn


def capture_frame():
    """Capture a single frame. Returns the raw OpenCV frame or None."""
    global _camera_conn
    with _camera_lock:
        cap = _get_camera()
        if cap is None:
            return None
        ret, frame = cap.read()
        if not ret:
            # Camera may have disconnected — reset for next call
            try:
                cap.release()
            except Exception:
                pass
            _camera_conn = None
            return None
        return frame


def frame_to_base64(frame, max_size: int = MAX_IMAGE_SIZE) -> str:
    """Resize and encode a frame to base64 JPEG."""
    h, w = frame.shape[:2]
    scale = max_size / max(h, w)
    if scale < 1.0:
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    return base64.b64encode(buffer).decode("utf-8")


def get_camera_data() -> str | None:
    """Capture a frame and return it as a base64 JPEG string."""
    frame = capture_frame()
    if frame is None:
        return None
    return frame_to_base64(frame)


def close():
    """Release the camera connection cleanly."""
    global _camera_conn
    with _camera_lock:
        if _camera_conn and _camera_conn.isOpened():
            _camera_conn.release()
        _camera_conn = None