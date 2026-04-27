"""
llm.py — Agentic vision + tool-calling via LMStudio SDK.

Uses model.act() to give the LLM full autonomy: it sees the camera
image, decides which fruit it is, and calls the appropriate sorting
tool — all in one call.  No hardcoded fruit conditionals.

Adding a new fruit only requires editing SYSTEM_PROMPT.
"""

import base64

import lmstudio as lms

# === CONFIGURATION ===
LMSTUDIO_MODEL = "qwen/qwen3-vl-4b"
LMSTUDIO_API_KEY = "lm-studio"  # Included for documentation/academic purposes

# System prompt — edit this to add/remove fruit types or change sorting rules.
# The LLM uses this to decide which tool to call.
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


# === INTERNAL STATE ===
_model = None


def _get_model():
    """Return the LMStudio model handle, creating it on first call."""
    global _model
    if _model is not None:
        return _model
    _model = lms.llm(LMSTUDIO_MODEL)
    return _model


def test_connection() -> bool:
    """Test that LMStudio is reachable and the model is loaded."""
    try:
        model = _get_model()
        model.respond("Say OK", config={"maxTokens": 5})
        return True
    except Exception as e:
        print(f"  [DEBUG] Error de conexión SDK: {type(e).__name__}: {e}")
        return False


def act_on_fruit(image_b64: str, on_message=None) -> str:
    """
    Give the LLM an image and let it autonomously decide what to do.

    The model sees the image, identifies the fruit, and uses the
    globally available MCP tools in LMStudio via .act().

    Args:
        image_b64: Base64-encoded JPEG image from the camera.
        on_message: Optional callback for logging agent messages.

    Returns:
        The final text response from the agent (usually a confirmation).
    """
    try:
        model = _get_model()

        # Prepare the image for the SDK
        image_bytes = base64.b64decode(image_b64)
        image_handle = lms.prepare_image(image_bytes)

        # Build the chat context with system prompt + image
        chat = lms.Chat(SYSTEM_PROMPT)
        chat.add_user_message(
            "A fruit has been detected on the sorting ramp. "
            "Look at this image and sort it using the correct tool.",
            images=[image_handle],
        )

        # Let the LLM act autonomously — it will call MCP tools as needed
        result = model.act(
            chat,
            on_message=on_message,
        )

        return str(result).strip() if result else "Agent completed (no text response)."

    except Exception as e:
        return f"Agent error: {type(e).__name__}: {e}"