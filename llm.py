"""
llm.py — Agentic vision + tool-calling via direct HTTP requests (V4).

This version eliminates the LMStudio SDK in favor of 'requests'.
It implements a manual agent loop to handle tool_calls from the model
following the OpenAI API standard.

The LLM sees the image, decides which tool to call, and Python 
executes it and feeds the result back to the model if necessary.
"""

import json
import base64
import requests
import tools

# === CONFIGURATION ===
# Default LMStudio local server URL
API_URL = "http://127.0.0.1:1234/v1/chat/completions"
LMSTUDIO_MODEL = "qwen/qwen3-vl-4b"
LMSTUDIO_API_KEY = "lm-studio"  # Required for V4 as per instructions

# System prompt — The "brain" of the agent.
SYSTEM_PROMPT = (
    "You are an autonomous fruit sorting machine controller. "
    "You receive images from a camera mounted above a sorting ramp. "
    "Your job is to identify the fruit and call the correct sorting tool.\n\n"
    "CURRENT SORTING RULES:\n"
    "- Apples (any color: red, green, yellow) → sort to LEFT  (call sort_to_left)\n"
    "- Oranges (round citrus fruit)           → sort to RIGHT (call sort_to_right)\n"
    "- Unknown / unclear / no fruit visible    → discard       (call discard_fruit)\n\n"
    "INSTRUCTIONS:\n"
    "1. Look at the image carefully.\n"
    "2. Identify the fruit.\n"
    "3. Call EXACTLY ONE sorting tool.\n"
    "4. If the image is unclear, call get_camera_image for another photo.\n"
    "5. Do NOT explain your reasoning — just call the tool.\n"
    "6. ALWAYS call a tool. Never respond with only text."
)


def test_connection() -> bool:
    """Test that the LMStudio server is reachable and accepting requests."""
    try:
        headers = {"Authorization": f"Bearer {LMSTUDIO_API_KEY}"}
        payload = {
            "model": LMSTUDIO_MODEL,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5
        }
        response = requests.post(API_URL, headers=headers, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"  [DEBUG] Error de conexión HTTP: {e}")
        return False


def act_on_fruit(image_b64: str, on_message=None) -> str:
    """
    Agent loop: Sends image to LLM, executes tools, and repeats if needed.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LMSTUDIO_API_KEY}"
    }

    # Initial history with system prompt and user image
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "text", 
                    "text": "A fruit has been detected. Look at this image and sort it."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}"
                    }
                }
            ]
        }
    ]

    max_turns = 5  # Prevent infinite loops
    
    for turn in range(max_turns):
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
            assistant_message = res_json["choices"][0]["message"]
            
            # 1. Add assistant's thought/call to history
            messages.append(assistant_message)
            
            # Log assistant message if callback provided
            if on_message and assistant_message.get("content"):
                on_message(type('obj', (object,), {"role": "assistant", "content": assistant_message["content"]}))

            # 2. Check for tool calls
            tool_calls = assistant_message.get("tool_calls")
            
            if not tool_calls:
                # If no tool calls, the model just spoke. Return the text.
                return assistant_message.get("content", "Agent finished without tools.")

            # 3. Execute tool calls
            for tool_call in tool_calls:
                func_name = tool_call["function"]["name"]
                call_id = tool_call["id"]
                
                if on_message:
                    on_message(type('obj', (object,), {"role": "tool", "content": func_name}))
                
                # Run the actual Python function
                if func_name in tools.AVAILABLE_FUNCTIONS:
                    result = tools.AVAILABLE_FUNCTIONS[func_name]()
                else:
                    result = f"Error: Tool {func_name} not found."

                # Add tool result to history
                messages.append({
                    "role": "tool",
                    "content": result,
                    "tool_call_id": call_id
                })
                
                # If it's a sorting tool (terminal action), we can stop here
                if func_name in ["sort_to_left", "sort_to_right", "discard_fruit"]:
                    return result

            # If we reached here, a non-terminal tool was called (e.g., get_camera_image)
            # The loop continues and sends the updated history back to the model.
            
        except Exception as e:
            return f"Agent error (turn {turn}): {type(e).__name__}: {e}"

    return "Agent reached maximum turns without a terminal action."
