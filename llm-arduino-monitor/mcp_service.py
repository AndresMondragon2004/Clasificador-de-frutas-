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
import llm
from fastmcp import FastMCP

app = FastMCP(
    name="Fruit Classifier Machine Control",
    instructions="""
    Tools for controlling a fruit sorting machine with Arduino, camera,
    and vision classification. Available tools:

    - ping_machine: Test Arduino connection
    - get_distance: Read ultrasonic sensor distance
    - wait_for_fruit: Block until a fruit is detected
    - classify_fruit: Capture photo and classify the fruit
    - sort_apple: Activate servo – sort as apple
    - sort_orange: Activate servo – sort as orange
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
def classify_fruit() -> dict:
    """Capture a photo and classify the fruit using the vision model."""
    image_b64 = camera.get_camera_data()
    if image_b64 is None:
        return {"error": "Camera not available."}

    label = llm.classify_image(image_b64)
    if label is None:
        return {"error": f"Cannot connect to LMStudio at {llm.LMSTUDIO_URL}"}

    return {"classification": label if label in ("apple", "orange") else "unknown"}


@app.tool()
def sort_apple() -> dict:
    """Activate the servo to sort the current fruit as an apple."""
    return arduino.classify_as_apple()


@app.tool()
def sort_orange() -> dict:
    """Activate the servo to sort the current fruit as an orange."""
    return arduino.classify_as_orange()


if __name__ == "__main__":
    app.run(transport="streamable-http")