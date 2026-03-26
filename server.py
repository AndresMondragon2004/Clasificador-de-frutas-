from fastmcp import FastMCP
import cv2
import base64
import requests
import serial
import time

# === CONFIGURATION ===
CAMERA_INDEX = 1          # 0 = built-in webcam, 1 = external USB webcam
WARMUP_FRAMES = 10        # Frames to discard so autoexposure can stabilize

# LMStudio vision API (second instance on port 1235).
# Instance 1 (port 1234): chat + MCP — the one that calls this tool.
# Instance 2 (port 1235): vision model — the one that classifies the fruit.
LMSTUDIO_URL = "http://localhost:1235/v1/chat/completions"
LMSTUDIO_MODEL = "qwen/qwen3-vl-4b"  # Vision model (VL) — the one that can see images

# Arduino serial
SERIAL_PORT = "COM8"
SERIAL_BAUD = 9600
SERIAL_TIMEOUT = 10  # seconds (3s servo movement + margin)

app = FastMCP(
    name="Fruit Classifier",
    instructions="""
    You are a fruit sorting assistant with a webcam and an Arduino-controlled
    servo mechanism. You have vision capabilities (Qwen3-VL).

    WORKFLOW for sorting fruits:
    1. Use classify_fruit to capture an image and identify the fruit.
    2. Based on your classification, use sort_fruit to activate the correct servo.
    3. Report the result to the user.

    Available tools:

    take_photo: Captures a photo from the webcam. Use it to preview the scene.
    classify_fruit: Captures a photo and classifies the fruit as 'apple' or 'orange'.
    sort_fruit: After classifying, call this with fruit="apple" or fruit="orange"
               to activate the corresponding servo on the Arduino.
    """
)


# === ARDUINO ===

def send_arduino_command(command: str) -> dict:
    """
    Sends a command to the Arduino via serial and waits for response.
    Returns a dict with status and response.
    """
    try:
        with serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=SERIAL_TIMEOUT) as ser:
            # Wait for Arduino to be ready after opening port
            # (Arduino Uno resets when serial is opened)
            time.sleep(2)

            # Send command
            ser.write(f"{command}\n".encode())

            # Read response
            response = ser.readline().decode().strip()

            return {
                "success": response == "OK" or response == "PONG",
                "response": response
            }
    except serial.SerialException as e:
        return {
            "success": False,
            "error": f"Serial error: {str(e)}"
        }


# === CAMERA ===

def get_camera():
    """Opens the webcam with fallback and warmup."""
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
    """Captures a single frame from the webcam. Returns the frame or None."""
    cap = get_camera()
    if cap is None:
        return None

    ret, frame = cap.read()
    cap.release()

    return frame if ret else None


def frame_to_base64(frame, max_size=512) -> str:
    """Resizes the frame (keeping aspect ratio) and encodes as JPEG base64."""
    h, w = frame.shape[:2]
    scale = max_size / max(h, w)
    if scale < 1.0:
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buffer).decode("utf-8")


# === MCP TOOLS ===

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
        "resolution": f"{frame.shape[1]}x{frame.shape[0]}"
    }


@app.tool
def classify_fruit() -> dict:
    """
    Capture a photo and classify the fruit in it.
    Uses the vision model loaded in LMStudio to analyze the image.
    Returns 'apple', 'orange', or an error.
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
                                    "Reply with ONLY one word: 'apple' or 'orange'. "
                                    "If you cannot identify a fruit, reply 'unknown'."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64}"
                                },
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
        fruit: The type of fruit to sort. Must be "apple" or "orange".
              - "apple": activates servo 1 (rotates left 45 degrees)
              - "orange": activates servo 2 (rotates right 45 degrees)

    The servo will hold position for 3 seconds to let the fruit pass,
    then return to neutral position.
    """
    fruit_lower = fruit.strip().lower()

    if fruit_lower not in ("apple", "orange"):
        return {
            "error": f"Invalid fruit type: '{fruit}'. Must be 'apple' or 'orange'."
        }

    # Map to Arduino command
    command = "APPLE" if fruit_lower == "apple" else "ORANGE"

    # Send command to Arduino
    result = send_arduino_command(command)

    if result["success"]:
        direction = "left (izquierda)" if fruit_lower == "apple" else "right (derecha)"
        return {
            "status": "success",
            "fruit": fruit_lower,
            "action": f"Servo rotated 45° {direction}. Fruit sorted successfully."
        }
    else:
        return {
            "status": "error",
            "fruit": fruit_lower,
            "error": result.get("error", result.get("response", "Unknown error"))
        }


if __name__ == "__main__":
    app.run(transport="streamable-http")