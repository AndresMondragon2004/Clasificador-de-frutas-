"""
tools.py — Sorting tools exposed to the LLM agent.

These are the tools the model can call via .act() to physically sort
fruits. Tools are named by physical direction (left/right), NOT by
fruit name — the LLM decides which tool to call based on its system
prompt.  Adding a new fruit only requires editing the prompt.
"""

import arduino
import camera
import lmstudio as lms
import base64


def sort_to_left() -> str:
    """Sort the detected fruit to the LEFT bin by activating the left servo."""
    result = arduino.classify_as_apple()
    if result["success"]:
        return "Done. The fruit has been sorted to the LEFT bin."
    return f"Error sorting to left: {result.get('error', result.get('response', 'unknown'))}"


def sort_to_right() -> str:
    """Sort the detected fruit to the RIGHT bin by activating the right servo."""
    result = arduino.classify_as_orange()
    if result["success"]:
        return "Done. The fruit has been sorted to the RIGHT bin."
    return f"Error sorting to right: {result.get('error', result.get('response', 'unknown'))}"


def discard_fruit() -> str:
    """Discard the fruit — do not sort it. Use when the fruit is unknown or unrecognizable."""
    return "Fruit discarded. No servo was activated."


def get_camera_image() -> str:
    """
    Take a new photo from the camera. Use this if the previous image was
    unclear or you need another look at the fruit before deciding.
    Returns a base64-encoded JPEG image.
    """
    image_b64 = camera.get_camera_data()
    if image_b64 is None:
        return "Error: Camera is not available."
    return f"Here is the new photo (base64 JPEG): {image_b64}"


# List of all tools available to the agent
ALL_TOOLS = [sort_to_left, sort_to_right, discard_fruit, get_camera_image]
