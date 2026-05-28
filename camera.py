"""
camera.py — Persistent camera connection with continuous background capture.

Provides a thread-safe camera interface that reads frames continuously
in the background, ensuring zero buffer lag and providing live feed support.
"""

import cv2
import base64
import threading
import time
import sys

# === CONFIGURATION ===
CAMERA_INDEX = 0  # Default to first camera
MAX_IMAGE_SIZE = 384
JPEG_QUALITY = 75

# === INTERNAL STATE ===
_camera_lock = threading.Lock()
_latest_frame = None
_running = False
_thread = None

def _camera_loop():
    global _latest_frame, _running
    
    # Use DSHOW on Windows to avoid MSMF errors; fallback to default
    if sys.platform.startswith('win'):
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(CAMERA_INDEX)
    else:
        cap = cv2.VideoCapture(CAMERA_INDEX)
        
    if not cap.isOpened():
        for i in range(5):
            if i == CAMERA_INDEX: continue
            cap = cv2.VideoCapture(i)
            if cap.isOpened(): break
            
    if not cap.isOpened():
        print("❌ Error: No se pudo abrir ninguna cámara.")
        _running = False
        return

    # Buffer a 1
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    while _running:
        ret, frame = cap.read()
        if ret:
            with _camera_lock:
                _latest_frame = frame.copy()
        else:
            time.sleep(0.03) # Pequeña pausa si falla el frame
            
    cap.release()

def start_camera():
    """Start the background thread to capture frames continuously."""
    global _running, _thread
    if not _running:
        _running = True
        _thread = threading.Thread(target=_camera_loop, daemon=True)
        _thread.start()
        # Wait until we get the first frame
        for _ in range(50):
            if _latest_frame is not None:
                break
            time.sleep(0.1)

def capture_frame():
    """Return the absolute freshest frame from the background thread."""
    start_camera()
    with _camera_lock:
        if _latest_frame is None:
            return None
        return _latest_frame.copy()

def frame_to_base64(frame, max_size: int = MAX_IMAGE_SIZE) -> str:
    """Resize and encode a frame to base64 JPEG."""
    h, w = frame.shape[:2]
    scale = max_size / max(h, w)
    if scale < 1.0:
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    return base64.b64encode(buffer).decode("utf-8")

def get_camera_data() -> str | None:
    """Capture a frame and return it as a base64 JPEG string for the LLM."""
    frame = capture_frame()
    if frame is None:
        return None
    return frame_to_base64(frame)

def get_latest_frame_jpeg() -> bytes | None:
    """Get the latest frame encoded as JPEG bytes (for MJPEG streaming)."""
    frame = capture_frame()
    if frame is None:
        return None
    # Usamos una compresión estándar para el video en vivo
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
    return buffer.tobytes()

def close():
    """Release the camera connection cleanly."""
    global _running, _latest_frame
    _running = False
    _latest_frame = None
