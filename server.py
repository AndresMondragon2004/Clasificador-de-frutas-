from fastmcp import FastMCP
import cv2
import base64
import requests
import serial
import time

# === CONFIGURATION ===
CAMERA_INDEX   = 1
WARMUP_FRAMES  = 10

LMSTUDIO_URL   = "http://localhost:1235/v1/chat/completions"
LMSTUDIO_MODEL = "qwen/qwen3-vl-4b"

SERIAL_PORT    = "COM8"
SERIAL_BAUD    = 9600

# Timeouts
SERIAL_TIMEOUT_SHORT = 5    # For PING / fast commands
SERIAL_TIMEOUT_FRUIT = 35   # For WAIT_FRUIT (30s Arduino + 5s margin)
SERIAL_TIMEOUT_SORT  = 10   # For APPLE / ORANGE (3s servo + margin)

app = FastMCP(
    name="Fruit Classifier",
    instructions="""
    You are a fruit sorting assistant with a webcam and an Arduino-controlled
    servo mechanism. You have vision capabilities (Qwen3-VL).

    AUTOMATIC WORKFLOW when the user asks to classify:
    1. Call wait_for_fruit — blocks until the sensor detects a fruit.
    2. Call classify_fruit — takes a photo and classifies it.
    3. Call sort_fruit(fruit=...) — activates the corresponding servo.
    4. Report the result to the user.
    5. Return to step 1 if the user wants to continue in continuous mode.

    Available tools:
      take_photo      — captures a photo for preview.
      wait_for_fruit  — waits for ultrasonic sensor detection (blocking).
      classify_fruit  — takes a photo and classifies the fruit ('apple' or 'orange').
      sort_fruit      — activates the servo based on the classification.
    """
)


# ── Arduino ──────────────────────────────────────────────────────────────────

def send_arduino_command(command: str, timeout: float) -> dict:
    """Sends a command to the Arduino and waits for a response."""
    try:
        with serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=timeout) as ser:
            time.sleep(2)  # Wait for Uno reset on port open
            ser.write(f"{command}\n".encode())
            response = ser.readline().decode().strip()
            return {
                "success": response in ("OK", "PONG", "DETECTED"),
                "response": response,
            }
    except serial.SerialException as e:
        return {"success": False, "error": f"Serial error: {str(e)}"}


# ── Camera ───────────────────────────────────────────────────────────────────

def get_camera():
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
    for _ in range(WARMUP_FRAMES):
        cap.read()
    return cap


def capture_frame():
    cap = get_camera()
    if cap is None:
        return None
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None


def frame_to_base64(frame, max_size=512) -> str:
    h, w = frame.shape[:2]
    scale = max_size / max(h, w)
    if scale < 1.0:
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buffer).decode("utf-8")


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
                         Must match WAIT_TIMEOUT_MS on the Arduino.

    Returns:
        detected=True when a fruit is ready, or error/timeout.
    """
    py_timeout = timeout_seconds + 5  # Python timeout = Arduino timeout + margin

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

    b64 = frame_to_base64(frame)

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
                                    "What fruit is in this image? "
                                    "Reply with ONLY one word. "
                                    "Your answer must be exactly one of these: apple, orange, unknown. "
                                    "No punctuation, no explanation."
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
            timeout=60,
        )

        if response.status_code != 200:
            return {
                "error": f"LMStudio returned {response.status_code}",
                "details": response.text[:500],
            }

        result = response.json()["choices"][0]["message"]["content"].strip().lower()
        return {"classification": result}

    except requests.exceptions.ConnectionError:
        return {
            "error": (
                "Cannot connect to LMStudio. "
                "Make sure the local server is running at " + LMSTUDIO_URL
            )
        }
    except Exception as e:
        return {"error": f"Classification failed: {str(e)}"}


@app.tool
def sort_fruit(fruit: str) -> dict:
    """
    Activate the Arduino servo to sort a classified fruit.

    Args:
        fruit: The type of fruit to sort. Must be 'apple' or 'orange'.
               - 'apple':  activates servo 1 (rotates left 45 degrees)
               - 'orange': activates servo 2 (rotates right 45 degrees)

    The servo will hold position for 3 seconds to let the fruit pass,
    then return to neutral position.
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


if __name__ == "__main__":
    app.run(transport="streamable-http")