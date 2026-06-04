"""
arduino.py — Persistent serial connection to the Fruit Sorter Arduino.

Provides a thread-safe, auto-reconnecting serial interface.
Supports auto-detection of the Arduino port on Linux and Windows.

Sensor: VL53L0X (láser I2C). El Arduino convierte mm → cm antes de enviar
la respuesta al comando GET_DISTANCE. El umbral de detección por defecto
es 13 cm, que corresponde al rango máximo configurado en el firmware.

CORRECCIÓN: Se añade debounce de dos niveles para eliminar falsos positivos:
  1. Hardware: comando CHECK_OBJECT:<mm> hace DEBOUNCE_READS lecturas en Arduino.
  2. Software (fallback): DEBOUNCE_CONFIRM lecturas consecutivas válidas.
"""

import sys
import time
import threading
import glob
import serial

# === CONFIGURATION ===
SERIAL_PORT = None  # Auto-detect if None; override with e.g. "/dev/ttyUSB0" or "COM5"
SERIAL_BAUD = 115200

# Timeouts
TIMEOUT_SHORT = 5       # PING, GET_DISTANCE, CHECK_OBJECT
TIMEOUT_SORT = 10       # APPLE / ORANGE (3s servo + margin)
SENSOR_POLL_INTERVAL = 0.05  # Seconds between distance polls

# === DEBOUNCE (software fallback) ===
# Número de lecturas consecutivas válidas requeridas para confirmar detección.
# Elimina falsos positivos del sensor VL53L0X por ruido o reflexiones espurias.
DEBOUNCE_CONFIRM = 3    # lecturas válidas consecutivas requeridas
DEBOUNCE_WINDOW  = 0.1  # segundos entre lecturas de debounce (software)

# === INTERNAL STATE ===
_serial_lock = threading.Lock()
_serial_conn: serial.Serial | None = None


def _auto_detect_port() -> str | None:
    """Find the first available serial port (Arduino)."""
    if sys.platform.startswith('win'):
        ports = [f'COM{i}' for i in range(1, 21)]
    elif sys.platform.startswith('linux'):
        ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.usbmodem*') + glob.glob('/dev/tty.usbserial*')
    else:
        return None

    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            return port
        except (OSError, serial.SerialException):
            continue
    return None


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


def _is_numeric(s: str) -> bool:
    """Return True if the string represents a valid float number."""
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


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
                # success=True para respuestas conocidas Y para valores numéricos
                # (GET_DISTANCE devuelve un float, no "OK")
                "success": response in ("OK", "PONG", "DETECTED", "PRESENT", "ABSENT")
                           or _is_numeric(response),
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
    """Get the current distance reading from the VL53L0X laser sensor (cm)."""
    result = send_command("GET_DISTANCE")
    try:
        return float(result["response"])
    except (ValueError, KeyError):
        return 999.0


def wait_for_fruit(threshold_cm: float = 13.0, timeout_seconds: int = 30) -> dict:
    """
    Poll the VL53L0X laser sensor until an object is detected within threshold_cm.

    Usa debounce de dos niveles para eliminar falsos positivos:
      1. Hardware: el comando CHECK_OBJECT:<mm> hace DEBOUNCE_READS lecturas
         consecutivas en el Arduino antes de responder PRESENT/ABSENT.
      2. Software (fallback): si el Arduino no soporta CHECK_OBJECT, se
         requieren DEBOUNCE_CONFIRM lecturas válidas seguidas desde Python.

    Returns:
        {"detected": True/False, "distance_cm": ..., "message": ...}
    """
    threshold_mm = int(threshold_cm * 10)
    start = time.time()

    # --- Intentar usar el comando hardware CHECK_OBJECT (más confiable) ---
    probe = send_command(f"CHECK_OBJECT:{threshold_mm}")
    use_hw_debounce = probe.get("response") in ("PRESENT", "ABSENT")

    if use_hw_debounce:
        # El firmware tiene soporte de debounce nativo
        if probe["response"] == "PRESENT":
            dist = get_distance()
            return {
                "detected": True,
                "distance_cm": dist,
                "message": "Fruit detected. Ready to classify.",
            }
        # Primera lectura fue ABSENT — esperar en bucle
        while time.time() - start < timeout_seconds:
            result = send_command(f"CHECK_OBJECT:{threshold_mm}")
            if result.get("response") == "PRESENT":
                dist = get_distance()
                return {
                    "detected": True,
                    "distance_cm": dist,
                    "message": "Fruit detected. Ready to classify.",
                }
            time.sleep(SENSOR_POLL_INTERVAL)

    else:
        # --- Fallback: debounce por software ---
        # Requiere DEBOUNCE_CONFIRM lecturas consecutivas < threshold_cm
        consecutive = 0
        last_dist   = 999.0
        while time.time() - start < timeout_seconds:
            distance = get_distance()
            if distance < threshold_cm:
                consecutive += 1
                last_dist = distance
                if consecutive >= DEBOUNCE_CONFIRM:
                    return {
                        "detected": True,
                        "distance_cm": last_dist,
                        "message": "Fruit detected. Ready to classify.",
                    }
                time.sleep(DEBOUNCE_WINDOW)
            else:
                consecutive = 0  # Resetear si hay una lectura no válida
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
