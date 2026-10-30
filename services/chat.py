"""General (non-document) study chat."""
from ai.model import chat_completion
from config import HISTORY_CONTEXT_MESSAGES

GENERAL_SYSTEM_PROMPT = (
    "You are StudyMate, a helpful study assistant for university students. "
    "Explain concepts clearly and concisely, use simple examples, and say when you "
    "are unsure instead of guessing."
)


def build_general_messages(question: str, history: list[dict]) -> list[dict]:
    """Build the message list: system prompt + recent general-chat history + new question."""
    messages = [{"role": "system", "content": GENERAL_SYSTEM_PROMPT}]
    recent = [m for m in history if m["mode"] == "general"][-HISTORY_CONTEXT_MESSAGES:]
    messages.extend({"role": m["role"], "content": m["content"]} for m in recent)
    messages.append({"role": "user", "content": question})
    return messages


def answer_general_question(question: str, history: list[dict]) -> str:
    """Return the model's answer to a general academic question."""
    return chat_completion(build_general_messages(question, history))