"""
arduino.py — Persistent serial connection to the Fruit Sorter Arduino.

Provides a thread-safe, auto-reconnecting serial interface.
Supports auto-detection of the Arduino port on Linux and Windows.
"""

import time
import threading
import glob
import serial

# === CONFIGURATION ===
SERIAL_PORT = "COM5"  # Auto-detect if None; override with e.g. "/dev/ttyUSB0" or "COM5"
SERIAL_BAUD = 115200

# Timeouts
TIMEOUT_SHORT = 5       # PING, GET_DISTANCE
TIMEOUT_SORT = 10       # APPLE / ORANGE (3s servo + margin)
SENSOR_POLL_INTERVAL = 0.3  # Seconds between distance polls

# === INTERNAL STATE ===
_serial_lock = threading.Lock()
_serial_conn: serial.Serial | None = None

def _get_serial() -> serial.Serial:
    """Return the persistent serial connection, creating it on first call."""
    global _serial_conn
    if _serial_conn is not None and _serial_conn.is_open:
        return _serial_conn

    port = SERIAL_PORT or _auto_detect_port()
    if port is None:
        raise serial.SerialException(
            "No Arduino found. Set arduino.SERIAL_PORT manually."
        )

    _serial_conn = serial.Serial(port, SERIAL_BAUD, timeout=TIMEOUT_SHORT)
    time.sleep(2)  # Wait for Arduino reset on first connection

    # Drain the initial "READY" message
    while _serial_conn.in_waiting:
        _serial_conn.readline()

    return _serial_conn


def send_command(command: str, timeout: float = TIMEOUT_SHORT) -> dict:
    """Send a command to the Arduino and return the response (thread-safe)."""
    global _serial_conn
    with _serial_lock:
        try:
            ser = _get_serial()
            ser.timeout = timeout
            ser.reset_input_buffer()
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
            return {"success": False, "error": f"Serial error: {e}"}


def ping() -> dict:
    """Test the connection to the Arduino."""
    return send_command("PING")


def get_distance() -> float:
    """Get the current distance reading from the ultrasonic sensor (cm)."""
    result = send_command("GET_DISTANCE")
    try:
        return float(result["response"])
    except (ValueError, KeyError):
        return 999.0


def wait_for_fruit(threshold_cm: float = 20.0, timeout_seconds: int = 30) -> dict:
    """
    Poll the ultrasonic sensor until an object is detected within threshold_cm.

    Returns:
        {"detected": True/False, "distance_cm": ..., "message": ...}
    """
    start = time.time()
    while time.time() - start < timeout_seconds:
        distance = get_distance()
        if distance < threshold_cm:
            return {
                "detected": True,
                "distance_cm": distance,
                "message": "Fruit detected. Ready to classify.",
            }
        time.sleep(SENSOR_POLL_INTERVAL)

    return {
        "detected": False,
        "distance_cm": 999.0,
        "message": "Timeout: no fruit detected.",
    }


def classify_as_apple() -> dict:
    """Activate the servo to sort as apple."""
    return send_command("APPLE", timeout=TIMEOUT_SORT)


def classify_as_orange() -> dict:
    """Activate the servo to sort as orange."""
    return send_command("ORANGE", timeout=TIMEOUT_SORT)


def close():
    """Close the serial connection cleanly."""
    global _serial_conn
    with _serial_lock:
        if _serial_conn and _serial_conn.is_open:
            _serial_conn.close()
        _serial_conn = None