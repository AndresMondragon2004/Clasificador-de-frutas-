from fastmcp import FastMCP
import cv2
import base64
import requests
import serial
import time
import threading
from collections import Counter
from datetime import datetime

# === CONFIGURATION ===
CAMERA_INDEX   = 1
WARMUP_FRAMES  = 3

LMSTUDIO_URL   = "http://localhost:1235/v1/chat/completions"
LMSTUDIO_MODEL = "qwen/qwen3-vl-4b"

SERIAL_PORT    = "COM5"
SERIAL_BAUD    = 115200

# Timeouts
SERIAL_TIMEOUT_SHORT = 5    # For PING / fast commands
SERIAL_TIMEOUT_FRUIT = 35   # For WAIT_FRUIT (30s Arduino + 5s margin)
SERIAL_TIMEOUT_SORT  = 10   # For APPLE / ORANGE (3s servo + margin)

# Classification settings
MIN_VOTES     = 1   # Minimum matching answers needed to confirm a fruit
MAX_ATTEMPTS  = 3   # Maximum photos taken per detection event

# Timing
STABILIZATION_DELAY = 0.4   # Seconds to wait after sensor detection before photo
PHOTO_INTERVAL      = 0.0   # Seconds between consecutive photo attempts

app = FastMCP(
    name="Fruit Classifier",
    instructions="""
    Sistema de clasificación de frutas con cámara, sensor ultrasónico y servo Arduino.

    INICIO: Cuando el usuario diga iniciar/start → llama start_sorting_loop().
    MONITOREO: Después llama get_loop_status() cada 3-5 segundos automáticamente.
    NARRACIÓN: Traduce new_events a lenguaje natural en español. No muestres JSON.
    PARADA: Cuando el usuario diga detener/stop → llama stop_sorting_loop().

    NUNCA preguntes si deseas continuar. Solo sigue llamando get_loop_status().
    """,
)

# ── Loop state ────────────────────────────────────────────────────────────────

_loop_running = False
_loop_thread: threading.Thread | None = None
_loop_stats: dict = {"cycles": 0, "sorted": Counter(), "last_error": None}
_log_list: list = []           # All log messages (append-only)
_log_lock = threading.Lock()   # Protect _log_list access
_last_seen_index: int = 0      # Cursor for get_loop_status


def _log(msg: str):
    """Append a timestamped message to the log list (thread-safe)."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    with _log_lock:
        _log_list.append(formatted)


# ── Arduino (persistent connection) ──────────────────────────────────────────

_serial_lock = threading.Lock()
_serial_conn: serial.Serial | None = None


def _get_serial() -> serial.Serial:
    """Return the persistent serial connection, creating it on first call."""
    global _serial_conn
    if _serial_conn is not None and _serial_conn.is_open:
        return _serial_conn

    _serial_conn = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=SERIAL_TIMEOUT_SHORT)
    time.sleep(2)  # Wait for Uno reset on first connection only

    # Drain the initial "READY" message (and any other startup noise)
    while _serial_conn.in_waiting:
        _serial_conn.readline()

    return _serial_conn


def send_arduino_command(command: str, timeout: float) -> dict:
    """Sends a command to the Arduino over the persistent connection."""
    with _serial_lock:
        try:
            ser = _get_serial()
            ser.timeout = timeout          # Adjust read timeout per command
            ser.reset_input_buffer()       # Clear any stale data
            ser.write(f"{command}\n".encode())
            response = ser.readline().decode().strip()
            return {
                "success": response in ("OK", "PONG", "DETECTED"),
                "response": response,
            }
        except serial.SerialException as e:
            # Connection lost — close so next call reconnects
            try:
                if _serial_conn:
                    _serial_conn.close()
            except Exception:
                pass
            _serial_conn = None
            return {"success": False, "error": f"Serial error: {str(e)}"}


# ── Camera (persistent connection) ───────────────────────────────────────────

_camera_lock = threading.Lock()
_camera_conn: cv2.VideoCapture | None = None


def _get_camera() -> cv2.VideoCapture | None:
    """Return the persistent camera connection, creating it on first call."""
    global _camera_conn
    if _camera_conn is not None and _camera_conn.isOpened():
        return _camera_conn

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

    # Warmup only on first open
    for _ in range(WARMUP_FRAMES):
        cap.read()

    _camera_conn = cap
    return _camera_conn


def capture_frame():
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


def frame_to_base64(frame, max_size=512) -> str:
    h, w = frame.shape[:2]
    scale = max_size / max(h, w)
    if scale < 1.0:
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buffer).decode("utf-8")


# ── Vision helper ─────────────────────────────────────────────────────────────

def _query_vision(b64: str) -> str | None:
    """
    Sends one base64 image to LMStudio and returns the classification.
    Returns 'apple', 'orange', or 'unknown'. Returns None on connection error.
    """
    try:
        response = requests.post(
            LMSTUDIO_URL,
            json={
                "model": LMSTUDIO_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "You are a fruit classification system for a sorting machine. "
                                    "Look at this image carefully and identify the fruit.\n\n"
                                    "Rules:\n"
                                    "- If you see an apple (any color: red, green, yellow), respond: apple\n"
                                    "- If you see an orange (round citrus fruit), respond: orange\n"
                                    "- If you see no fruit, or the image is unclear, respond: unknown\n\n"
                                    "Reply with ONLY one word: apple, orange, or unknown.\n"
                                    "No punctuation, no explanation, no extra text."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                            },
                        ],
                    }
                ],
                "temperature": 0,
                "max_tokens": 10,
            },
            timeout=15,
        )
        if response.status_code == 200:
            raw = response.json()["choices"][0]["message"]["content"].strip().lower()
            # Extract keyword even if model adds extra text
            for keyword in ("apple", "orange"):
                if keyword in raw:
                    return keyword
            return "unknown"
        return None
    except Exception:
        return None


def classify_with_retries(min_votes: int = MIN_VOTES, max_attempts: int = MAX_ATTEMPTS) -> dict:
    """
    Takes up to `max_attempts` photos. Stops early once any label reaches
    `min_votes` consistent answers. Returns the winning label or 'unknown'.
    """
    votes: Counter = Counter()
    errors = 0

    for attempt in range(1, max_attempts + 1):
        frame = capture_frame()
        if frame is None:
            errors += 1
            if attempt < max_attempts:
                time.sleep(PHOTO_INTERVAL)
            continue

        label = _query_vision(frame_to_base64(frame))
        if label is None:
            errors += 1
            if attempt < max_attempts:
                time.sleep(PHOTO_INTERVAL)
            continue

        # Normalize: accept only valid labels
        if label not in ("apple", "orange"):
            label = "unknown"

        votes[label] += 1

        # Early exit: enough votes for a confirmed answer
        if votes[label] >= min_votes:
            return {
                "classification": label,
                "votes": dict(votes),
                "attempts": attempt,
                "confirmed": label != "unknown",
            }

        # Small delay between photos for different angles/frames
        if attempt < max_attempts:
            time.sleep(PHOTO_INTERVAL)

    # All attempts exhausted — pick the most common answer
    if not votes:
        return {
            "classification": "unknown",
            "votes": {},
            "attempts": max_attempts,
            "confirmed": False,
            "error": "Camera or LMStudio unavailable during all attempts.",
        }

    best_label, best_count = votes.most_common(1)[0]
    return {
        "classification": best_label,
        "votes": dict(votes),
        "attempts": max_attempts,
        "confirmed": best_label != "unknown" and best_count >= min_votes,
    }


# ── MCP Tools ────────────────────────────────────────────────────────────────

@app.tool
def take_photo() -> dict:
    """
    Capture a photo from the webcam.
    Returns the base64-encoded JPEG image for preview.
    """
    frame = capture_frame()
    if frame is None:
        return {"error": "Webcam not available."}
    return {
        "image_base64": frame_to_base64(frame),
        "format": "jpeg",
        "resolution": f"{frame.shape[1]}x{frame.shape[0]}",
    }


@app.tool
def wait_for_fruit(timeout_seconds: int = 30) -> dict:
    """
    Blocks until the ultrasonic sensor detects a fruit
    at the classification position.

    Args:
        timeout_seconds: Maximum seconds to wait (default 30).

    Returns:
        detected=True when a fruit is ready, or error/timeout.
    """
    py_timeout = timeout_seconds + 5

    result = send_arduino_command("WAIT_FRUIT", timeout=py_timeout)

    if result.get("response") == "DETECTED":
        return {"detected": True, "message": "Fruit detected. Ready to classify."}

    if result.get("response") == "TIMEOUT":
        return {"detected": False, "message": "Timeout: no fruit detected."}

    return {
        "detected": False,
        "error": result.get("error", result.get("response", "Unknown error")),
    }


@app.tool
def classify_fruit() -> dict:
    """
    Capture a photo and classify the fruit in it.
    Uses the vision model loaded in LMStudio to analyze the image.
    Returns 'apple', 'orange', or 'unknown'.
    """
    frame = capture_frame()
    if frame is None:
        return {"error": "Webcam not available."}

    label = _query_vision(frame_to_base64(frame))
    if label is None:
        return {"error": f"Cannot connect to LMStudio at {LMSTUDIO_URL}"}

    return {"classification": label if label in ("apple", "orange") else "unknown"}


@app.tool
def sort_fruit(fruit: str) -> dict:
    """
    Activate the Arduino servo to sort a classified fruit.

    Args:
        fruit: The type of fruit to sort. Must be 'apple' or 'orange'.
               - 'apple':  activates servo 1 (rotates left 45 degrees)
               - 'orange': activates servo 2 (rotates right 45 degrees)
    """
    fruit_lower = fruit.strip().lower()

    if fruit_lower not in ("apple", "orange"):
        return {
            "error": f"Invalid fruit type: '{fruit}'. Must be 'apple' or 'orange'."
        }

    command = "APPLE" if fruit_lower == "apple" else "ORANGE"
    result = send_arduino_command(command, timeout=SERIAL_TIMEOUT_SORT)

    if result["success"]:
        direction = "left" if fruit_lower == "apple" else "right"
        return {
            "status": "success",
            "fruit": fruit_lower,
            "action": f"Servo rotated 45° {direction}. Fruit sorted successfully.",
        }

    return {
        "status": "error",
        "fruit": fruit_lower,
        "error": result.get("error", result.get("response", "Unknown error")),
    }


# ── Background sorting loop ─────────────────────────────────────────────────

def _sorting_loop_worker(sensor_timeout: int, min_votes: int, max_attempts: int):
    """Background thread: runs the sorting pipeline indefinitely."""
    global _loop_running, _loop_stats, _last_seen_index

    _loop_stats = {"cycles": 0, "sorted": Counter(), "last_error": None}
    with _log_lock:
        _log_list.clear()
    _last_seen_index = 0

    _log("🟢 Sistema de clasificación iniciado.")

    while _loop_running:
        _loop_stats["cycles"] += 1
        cycle = _loop_stats["cycles"]

        # ── Step 1: Wait for sensor ───────────────────────────────────────
        _log(f"🔍 Ciclo {cycle}: Esperando fruta en el sensor...")
        py_timeout = sensor_timeout + 5
        sensor_result = send_arduino_command("WAIT_FRUIT", timeout=py_timeout)
        response = sensor_result.get("response", "")

        if not _loop_running:
            break

        if response == "DETECTED":
            _log(f"📦 Ciclo {cycle}: ¡Fruta detectada! Estabilizando ({STABILIZATION_DELAY}s)...")
            time.sleep(STABILIZATION_DELAY)
        elif response == "TIMEOUT":
            _log(f"⏳ Ciclo {cycle}: No hay fruta — reintentando.")
            continue
        elif sensor_result.get("error"):
            err = sensor_result["error"]
            _loop_stats["last_error"] = err
            _log(f"⚠️ Ciclo {cycle}: Error serial — {err}. Reintentando en 3s.")
            time.sleep(3)
            continue
        else:
            _log(f"⚠️ Ciclo {cycle}: Respuesta inesperada '{response}'. Reintentando.")
            time.sleep(1)
            continue

        # ── Step 2: Classify with validation ─────────────────────────────
        _log(f"📷 Ciclo {cycle}: Analizando fruta (máx {max_attempts} fotos, necesito {min_votes} votos)...")
        result = classify_with_retries(min_votes=min_votes, max_attempts=max_attempts)
        label = result["classification"]
        confirmed = result["confirmed"]
        votes = result.get("votes", {})
        attempts = result.get("attempts", 0)

        if not _loop_running:
            break

        if not confirmed or label == "unknown":
            _log(
                f"🚫 Ciclo {cycle}: No es una fruta reconocida después de "
                f"{attempts} foto(s). Votos: {votes}. Descartando."
            )
            continue

        emoji = "🍎" if label == "apple" else "🍊"
        nombre = "manzana" if label == "apple" else "naranja"
        _log(f"{emoji} Ciclo {cycle}: ¡Detecté una {nombre}! ({votes}, {attempts} foto(s))")

        # ── Step 3: Sort ──────────────────────────────────────────────────
        direction = "izquierda" if label == "apple" else "derecha"
        _log(f"🤖 Ciclo {cycle}: Girando servo hacia la {direction}...")
        command = "APPLE" if label == "apple" else "ORANGE"
        sort_result = send_arduino_command(command, timeout=SERIAL_TIMEOUT_SORT)

        if sort_result["success"]:
            _loop_stats["sorted"][label] += 1
            total = sum(_loop_stats["sorted"].values())
            _log(
                f"🎉 Ciclo {cycle}: ¡Clasificada exitosamente! "
                f"Fruta #{total} — Total: {dict(_loop_stats['sorted'])}"
            )
        elif sort_result.get("error"):
            err = sort_result["error"]
            _loop_stats["last_error"] = err
            _log(f"⚠️ Ciclo {cycle}: Error al clasificar — {err}")

    _log("🔴 Sistema de clasificación detenido.")
    _loop_running = False


@app.tool
def start_sorting_loop(
    sensor_timeout: int = 30,
    min_votes: int = MIN_VOTES,
    max_attempts: int = MAX_ATTEMPTS,
) -> dict:
    """
    INICIAR EL SISTEMA AUTOMÁTICO DE CLASIFICACIÓN DE FRUTAS.

    Lanza el pipeline en segundo plano y retorna inmediatamente.
    DESPUÉS de llamar esto, llama get_loop_status() cada 5 segundos
    para obtener las actualizaciones y narrarlas al usuario.

    Args:
        sensor_timeout: Segundos de espera por ciclo del sensor (default 30).
        min_votes:      Clasificaciones mínimas iguales para confirmar (default 2).
        max_attempts:   Máximo de fotos por detección (default 4).
    """
    global _loop_running, _loop_thread

    if _loop_running and _loop_thread and _loop_thread.is_alive():
        return {"status": "already_running", "message": "El sistema ya está activo."}

    _loop_running = True
    _loop_thread = threading.Thread(
        target=_sorting_loop_worker,
        args=(sensor_timeout, min_votes, max_attempts),
        daemon=True,
        name="FruitSortingLoop",
    )
    _loop_thread.start()

    return {
        "status": "started",
        "message": (
            "Sistema iniciado. Llama get_loop_status() cada 5 segundos "
            "para ver las actualizaciones y narrarlas al usuario."
        ),
    }


@app.tool
def stop_sorting_loop() -> dict:
    """
    DETENER EL SISTEMA AUTOMÁTICO DE CLASIFICACIÓN.

    Envía la señal de parada. El loop terminará después del ciclo actual.
    """
    global _loop_running

    if not _loop_running:
        return {"status": "not_running", "message": "No hay un sistema activo."}

    _loop_running = False
    return {
        "status": "stopping",
        "message": "Señal de parada enviada. El sistema se detendrá al terminar el ciclo actual.",
        "stats": {
            "cycles_completed": _loop_stats.get("cycles", 0),
            "sorted": dict(_loop_stats.get("sorted", {})),
        },
    }


@app.tool
def get_loop_status() -> dict:
    """
    Obtener las NUEVAS actualizaciones del sistema de clasificación.

    Devuelve solo los eventos que ocurrieron desde la última vez que
    llamaste esta función. Debes llamarla cada ~5 segundos mientras
    el sistema esté corriendo, y narrar los eventos nuevos al usuario.

    Si "new_events" está vacío, no hay nada nuevo — vuelve a llamar
    en unos segundos sin decirle nada al usuario.
    """
    global _loop_running, _loop_thread, _last_seen_index

    is_alive = _loop_thread is not None and _loop_thread.is_alive()

    with _log_lock:
        new_events = _log_list[_last_seen_index:]
        _last_seen_index = len(_log_list)

    return {
        "running": _loop_running and is_alive,
        "cycles_completed": _loop_stats.get("cycles", 0),
        "sorted": dict(_loop_stats.get("sorted", {})),
        "last_error": _loop_stats.get("last_error"),
        "new_events": new_events,
    }


if __name__ == "__main__":
    app.run(transport="streamable-http")
