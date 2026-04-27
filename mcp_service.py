"""
mcp_service.py — Optional MCP server exposing fruit sorter tools.

This is a COMPLEMENTARY component to service.py. It exposes the
same hardware functions as MCP tools for use with external MCP clients
(e.g., Claude Desktop, LMStudio with MCP support).

service.py does NOT require this file to run — it drives hardware
directly. Use this only if you want to connect an MCP client.

Usage:
    python mcp_service.py
"""

import arduino
import camera
from fastmcp import FastMCP

app = FastMCP(
    name="Fruit Classifier Machine Control",
    instructions="""
    Tools for controlling a fruit sorting machine with Arduino and camera.
    Available tools:

    - ping_machine: Test Arduino connection
    - get_distance: Read ultrasonic sensor distance
    - wait_for_fruit: Block until a fruit is detected
    - capture_photo: Capture a photo from the camera
    - sort_to_left: Sort fruit to the left bin
    - sort_to_right: Sort fruit to the right bin
    """,
)


@app.tool()
def ping_machine() -> dict:
    """Test the connection to the Arduino."""
    return arduino.ping()


@app.tool()
def get_distance() -> dict:
    """Get the current ultrasonic sensor distance reading in cm."""
    return {"distance_cm": arduino.get_distance()}


@app.tool()
def wait_for_fruit(threshold_cm: float = 20.0, timeout_seconds: int = 30) -> dict:
    """
    Block until a fruit is detected within the given threshold.

    Args:
        threshold_cm: Detection distance threshold (default: 20.0 cm)
        timeout_seconds: Maximum seconds to wait (default: 30)
    """
    return arduino.wait_for_fruit(
        threshold_cm=threshold_cm,
        timeout_seconds=timeout_seconds,
    )


@app.tool()
def capture_photo() -> dict:
    """Capture a photo from the camera and return it as base64 JPEG."""
    image_b64 = camera.get_camera_data()
    if image_b64 is None:
        return {"error": "Camera not available."}
    return {"image_b64": image_b64}


@app.tool()
def sort_to_left() -> dict:
    """Sort the current fruit to the LEFT bin (activates left servo)."""
    return arduino.classify_as_apple()


@app.tool()
def sort_to_right() -> dict:
    """Sort the current fruit to the RIGHT bin (activates right servo)."""
    return arduino.classify_as_orange()


if __name__ == "__main__":
    app.run(transport="sse", port=8000)