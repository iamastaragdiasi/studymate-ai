"""SQLite storage for chat history.

Database errors (disk full, corrupt file, unwritable folder) are caught and
logged here, so the app keeps working even when history cannot be saved.
"""

import logging
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from config import DB_PATH

logger = logging.getLogger(__name__)

VALID_ROLES = {"user", "assistant"}
VALID_MODES = {"general", "document"}

# sqlite3.Error covers disk full, locked and corrupt databases.
# OSError covers a data folder that cannot be created.
DB_ERRORS = (sqlite3.Error, OSError)

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


def _log_failure(operation: str, db_path: str, error: Exception) -> None:
    """Log a database failure. Never logs message content."""
    logger.error("%s failed for %s: %s: %s", operation, db_path, type(error).__name__, error)


def init_db(db_path: str = DB_PATH) -> bool:
    """Create the messages table if needed. Returns False if the database is unusable."""
    try:
        with closing(get_connection(db_path)) as connection:
            with connection:
                connection.execute(CREATE_MESSAGES_TABLE)
        return True
    except DB_ERRORS as error:
        _log_failure("init_db", db_path, error)
        return False


def save_message(role: str, content: str, mode: str, db_path: str = DB_PATH) -> bool:
    """Insert one message. Returns True if saved, False on a database error.

    Raises ValueError for an invalid role or mode (a coding mistake, not a disk problem).
    """
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}")
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode: {mode}")
    timestamp = datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")
    try:
        with closing(get_connection(db_path)) as connection:
            with connection:
                connection.execute(
                    "INSERT INTO messages (role, content, mode, created_at) VALUES (?, ?, ?, ?)",
                    (role, content, mode, timestamp),
                )
        return True
    except DB_ERRORS as error:
        _log_failure("save_message", db_path, error)
        return False


def load_messages(limit: int = 200, db_path: str = DB_PATH) -> list[dict]:
    """Return the most recent `limit` messages, oldest first. Returns [] on a database error."""
    try:
        with closing(get_connection(db_path)) as connection:
            rows = connection.execute(
                "SELECT id, role, content, mode, created_at FROM messages ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    except DB_ERRORS as error:
        _log_failure("load_messages", db_path, error)
        return []
    return [dict(row) for row in reversed(rows)]


def clear_messages(db_path: str = DB_PATH) -> bool:
    """Delete all saved messages. Returns False on a database error."""
    try:
        with closing(get_connection(db_path)) as connection:
            with connection:
                connection.execute("DELETE FROM messages")
        return True
    except DB_ERRORS as error:
        _log_failure("clear_messages", db_path, error)
        return False


def format_local_time(created_at: str, tz=None) -> str:
    """Convert a stored UTC timestamp to local time for display (YYYY-MM-DD HH:MM).

    Old rows without a timezone, or unreadable values, are returned unchanged.
    """
    try:
        moment = datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        return created_at
    if moment.tzinfo is None:
        return created_at
    return moment.astimezone(tz).strftime("%Y-%m-%d %H:%M")