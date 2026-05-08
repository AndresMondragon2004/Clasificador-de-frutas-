"""
llm.py — Agentic vision + tool-calling via direct HTTP requests (V4+).

Optimized version:
- Handles tool arguments (fruit_name).
- Replaces images in context instead of appending to save tokens/speed.
- Native OpenAI tool-calling loop.
"""

import json
import base64
import requests
import tools
import camera

# === CONFIGURATION ===
API_URL = "http://127.0.0.1:1234/v1/chat/completions"
LMSTUDIO_MODEL = "qwen/qwen3-vl-4b"
LMSTUDIO_API_KEY = "lm-studio"

SYSTEM_PROMPT = (
    "You are an autonomous fruit sorting machine controller. "
    "Identify the fruit and call the correct tool with the fruit's name.\n\n"
    "RULES:\n"
    "- Apples (any color) -> sort_to_left(fruit_name='Specific Apple Type')\n"
    "- Oranges (any)      -> sort_to_right(fruit_name='Specific Orange Type')\n"
    "- Unknown/None       -> discard_fruit()\n\n"
    "INSTRUCTIONS:\n"
    "1. Identify the specific variety if possible (e.g. 'Red Gala Apple').\n"
    "2. Call the tool with the fruit_name argument.\n"
    "3. No reasoning, just the tool call."
)


def test_connection() -> bool:
    try:
        headers = {"Authorization": f"Bearer {LMSTUDIO_API_KEY}"}
        payload = {
            "model": LMSTUDIO_MODEL,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5
        }
        response = requests.post(API_URL, headers=headers, json=payload, timeout=5)
        return response.status_code == 200
    except:
        return False


def act_on_fruit(image_b64: str, on_message=None) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LMSTUDIO_API_KEY}"
    }

    # Content structure for vision models
    user_content = [
        {"type": "text", "text": "Sort this fruit."},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
    ]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content}
    ]

    for _ in range(5):
        try:
            payload = {
                "model": LMSTUDIO_MODEL,
                "messages": messages,
                "tools": tools.TOOLS_SCHEMA,
                "tool_choice": "auto"
            }

            response = requests.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()
            
            res_json = response.json()
            msg = res_json["choices"][0]["message"]
            messages.append(msg)
            
            if on_message and msg.get("content"):
                on_message("assistant", msg["content"])

            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                return msg.get("content", "Process finished.")

            for tool_call in tool_calls:
                func_name = tool_call["function"]["name"]
                args = json.loads(tool_call["function"].get("arguments", "{}"))
                
                if on_message:
                    # Provide the function name and args for logging
                    on_message("tool", f"{func_name}({args})")
                
                if func_name == "get_camera_image":
                    new_img = camera.get_camera_data()
                    if new_img:
                        # OPTIMIZATION: Replace the image in the original message
                        messages[1]["content"][1]["image_url"]["url"] = f"data:image/jpeg;base64,{new_img}"
                        result = "NEW_IMAGE_READY"
                    else:
                        result = "ERROR:Capture failed"
                elif func_name in tools.AVAILABLE_FUNCTIONS:
                    # Call with unpacked arguments if they exist
                    result = tools.AVAILABLE_FUNCTIONS[func_name](**args)
                else:
                    result = f"ERROR:Unknown tool {func_name}"

                messages.append({
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tool_call["id"]
                })
                
                # If result starts with SUCCESS or DISCARD, it's a terminal action
                if result.startswith("SUCCESS") or result.startswith("DISCARD"):
                    return result

        except Exception as e:
            return f"ERROR:Agent failure: {e}"

    return "ERROR:Max turns reached"
