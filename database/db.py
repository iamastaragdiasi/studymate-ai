"""SQLite chat history (stored locally in data/studymate.db, never committed)."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime

from config import DB_PATH

VALID_ROLES = {"user", "assistant"}
VALID_MODES = {"general", "document"}

CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    mode       TEXT NOT NULL CHECK (mode IN ('general', 'document')),
    created_at TEXT NOT NULL
)
"""


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Open a connection, creating the data folder if needed."""
    folder = os.path.dirname(db_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: str = DB_PATH) -> None:
    """Create the messages table if it does not exist."""
    with closing(get_connection(db_path)) as connection:
        with connection:
            connection.execute(CREATE_MESSAGES_TABLE)


def save_message(role: str, content: str, mode: str, db_path: str = DB_PATH) -> None:
    """Insert one message. Raises ValueError for an invalid role or mode."""
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}")
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode: {mode}")
    timestamp = datetime.now().isoformat(sep=" ", timespec="seconds")
    with closing(get_connection(db_path)) as connection:
        with connection:
            connection.execute(
                "INSERT INTO messages (role, content, mode, created_at) VALUES (?, ?, ?, ?)",
                (role, content, mode, timestamp),
            )


def load_messages(limit: int = 200, db_path: str = DB_PATH) -> list[dict]:
    """Return the most recent `limit` messages, oldest first."""
    with closing(get_connection(db_path)) as connection:
        rows = connection.execute(
            "SELECT id, role, content, mode, created_at FROM messages ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def clear_messages(db_path: str = DB_PATH) -> None:
    """Delete all saved messages."""
    with closing(get_connection(db_path)) as connection:
        with connection:
            connection.execute("DELETE FROM messages")