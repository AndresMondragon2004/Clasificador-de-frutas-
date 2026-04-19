"""
llm.py — Vision classification via LMStudio API.

Uses direct HTTP requests to the LMStudio OpenAI-compatible API for
image classification. No litellm dependency needed.

The LLM is used ONLY for vision (classifying images), not for
orchestrating tools.
"""

import requests

# === CONFIGURATION ===
LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
LMSTUDIO_MODEL = "qwen3-vl-4b"

# Classification settings
MIN_VOTES = 1       # Minimum matching answers to confirm a fruit
MAX_ATTEMPTS = 3    # Maximum photos per detection event


def test_connection() -> bool:
    """Test that LMStudio is reachable and responding."""
    try:
        response = requests.post(
            LMSTUDIO_URL,
            json={
                "model": LMSTUDIO_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": "Say OK",
                    }
                ],
                "max_tokens": 5,
            },
            timeout=10,
        )
        return response.status_code == 200
    except Exception:
        return False


def classify_image(image_b64: str) -> str | None:
    """
    Send one base64 image to LMStudio and return the classification.

    Returns:
        'apple', 'orange', or 'unknown'. Returns None on connection error.
    """
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
                                    "You are a fruit classification system for a sorting machine. "
                                    "Look at this image carefully and identify the fruit.\n\n"
                                    "Rules:\n"
                                    "- If you see an apple (any color: red, green, yellow), respond: apple\n"
                                    "- If you see an orange (round citrus fruit), respond: orange\n"
                                    "- If you see no fruit, or the image is unclear, respond: unknown\n\n"
                                    "Reply with ONLY one word: apple, orange, or unknown.\n"
                                    "No punctuation, no explanation, no extra text."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_b64}"
                                },
                            },
                        ],
                    }
                ],
                "temperature": 0,
                "max_tokens": 10,
            },
            timeout=15,
        )
        if response.status_code == 200:
            raw = (
                response.json()["choices"][0]["message"]["content"]
                .strip()
                .lower()
            )
            # Extract keyword even if the model adds extra text
            for keyword in ("apple", "orange"):
                if keyword in raw:
                    return keyword
            return "unknown"
        return None
    except Exception:
        return None