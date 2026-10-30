"""Thin wrapper around the Ollama local HTTP API (no API key, no paid service)."""
import requests

from config import CONTEXT_WINDOW_TOKENS, MODEL_NAME, OLLAMA_URL, REQUEST_TIMEOUT_SECONDS


class ModelError(Exception):
    """Raised with a user-friendly message when the local model cannot answer."""


def check_model_status() -> tuple[bool, str]:
    """Return (is_ready, message) describing whether Ollama and the model are available."""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        response.raise_for_status()
        installed = [model.get("name", "") for model in response.json().get("models", [])]
    except requests.exceptions.ConnectionError:
        return False, "Ollama is not running. Start the Ollama app or run `ollama serve`."
    except (requests.exceptions.RequestException, ValueError) as error:
        return False, f"Could not reach Ollama: {error}"

    if MODEL_NAME not in installed and f"{MODEL_NAME}:latest" not in installed:
        return False, f"Model '{MODEL_NAME}' is not installed. Run: `ollama pull {MODEL_NAME}`"
    return True, f"Connected - using {MODEL_NAME}"


def chat_completion(messages: list[dict], temperature: float = 0.3) -> str:
    """Send chat messages to Ollama and return the reply text.

    Raises ModelError with a readable explanation for every failure case, so the
    UI can show it without crashing.
    """
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": CONTEXT_WINDOW_TOKENS},
    }
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat", json=payload, timeout=REQUEST_TIMEOUT_SECONDS
        )
    except requests.exceptions.ConnectionError as error:
        raise ModelError("Cannot connect to Ollama. Make sure it is running, then try again.") from error
    except requests.exceptions.Timeout as error:
        raise ModelError(
            f"The model took longer than {REQUEST_TIMEOUT_SECONDS}s to respond. "
            "Try a shorter question or document."
        ) from error
    except requests.exceptions.RequestException as error:
        raise ModelError(f"Request to Ollama failed: {error}") from error

    if response.status_code == 404:
        raise ModelError(f"Model '{MODEL_NAME}' was not found. Run: ollama pull {MODEL_NAME}")
    if response.status_code != 200:
        raise ModelError(f"Ollama returned an error (HTTP {response.status_code}): {response.text[:200]}")

    try:
        content = response.json()["message"]["content"].strip()
    except (ValueError, KeyError, TypeError) as error:
        raise ModelError("Received an unexpected response from Ollama.") from error

    if not content:
        raise ModelError("The model returned an empty response. Please try again.")
    return content