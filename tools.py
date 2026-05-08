"""
tools.py — Sorting tools exposed to the LLM agent (V4+ - Optimized Version).

These tools now accept a 'fruit_name' argument so the AI can explicitly
report what it identified.
"""

import arduino
import camera
import base64

# === TOOL IMPLEMENTATIONS ===

def sort_to_left(fruit_name: str = "Fruit") -> str:
    """Sort the detected fruit to the LEFT bin."""
    result = arduino.classify_as_apple()
    if result["success"]:
        return f"SUCCESS:{fruit_name}:LEFT"
    return f"ERROR:Sorting failed for {fruit_name}"


def sort_to_right(fruit_name: str = "Fruit") -> str:
    """Sort the detected fruit to the RIGHT bin."""
    result = arduino.classify_as_orange()
    if result["success"]:
        return f"SUCCESS:{fruit_name}:RIGHT"
    return f"ERROR:Sorting failed for {fruit_name}"


def discard_fruit() -> str:
    """Discard the fruit — do not sort it."""
    return "DISCARD:Unknown Item"


def get_camera_image() -> str:
    """Take a new photo from the camera."""
    image_b64 = camera.get_camera_data()
    if image_b64 is None:
        return "ERROR:Camera unavailable"
    return f"NEW_IMAGE_READY:{image_b64}"


# === API SCHEMAS (OpenAI Format) ===

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "sort_to_left",
            "description": "Sort the detected fruit to the LEFT bin (e.g., for apples).",
            "parameters": {
                "type": "object",
                "properties": {
                    "fruit_name": {
                        "type": "string",
                        "description": "The specific name of the fruit (e.g., 'Red Apple', 'Green Apple')."
                    }
                },
                "required": ["fruit_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sort_to_right",
            "description": "Sort the detected fruit to the RIGHT bin (e.g., for oranges).",
            "parameters": {
                "type": "object",
                "properties": {
                    "fruit_name": {
                        "type": "string",
                        "description": "The specific name of the fruit (e.g., 'Navel Orange', 'Tangerine')."
                    }
                },
                "required": ["fruit_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "discard_fruit",
            "description": "Discard the fruit when unknown or no fruit is visible.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_camera_image",
            "description": "Take another photo if the first one was unclear.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

# Dictionary to dispatch function calls by name
AVAILABLE_FUNCTIONS = {
    "sort_to_left": sort_to_left,
    "sort_to_right": sort_to_right,
    "discard_fruit": discard_fruit,
    "get_camera_image": get_camera_image
}
