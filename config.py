"""Central configuration for StudyMate AI.

Values that may differ between machines can be overridden with environment variables.
"""
import os

# --- Model / Ollama ---
OLLAMA_URL = os.getenv("STUDYMATE_OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("STUDYMATE_MODEL", "gemma3:1b")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("STUDYMATE_TIMEOUT", "180"))
CONTEXT_WINDOW_TOKENS = 4096  # num_ctx sent to Ollama; keeps RAM usage modest

# --- PDF handling ---
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MIN_EXTRACTED_CHARS = 30  # less than this = treat as "no readable text"

# --- Chunking / retrieval ---
CHUNK_SIZE_WORDS = 200
CHUNK_OVERLAP_WORDS = 40
TOP_K_CHUNKS = 3

# --- Summarization ---
SUMMARY_SINGLE_PASS_CHARS = 6000   # documents up to this length are summarized in one call
SUMMARY_SECTION_CHARS = 5000       # longer documents are split into sections of this size
SUMMARY_MAX_SECTIONS = 6           # cap to keep summary time reasonable on a laptop

# --- Chat history ---
HISTORY_CONTEXT_MESSAGES = 6       # recent messages sent to the model in general chat
DB_PATH = os.getenv("STUDYMATE_DB", os.path.join("data", "studymate.db"))