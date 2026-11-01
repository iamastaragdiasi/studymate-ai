"""Database failure handling (T15): DB errors must not crash the app."""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from database import db

IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    assert db.init_db(path) is True
    return path


def _raise_db_error(*args, **kwargs):
    raise sqlite3.OperationalError("disk I/O error")


def test_save_message_returns_true_on_success(db_path):
    assert db.save_message("user", "hello", "general", db_path=db_path) is True
    assert [m["content"] for m in db.load_messages(db_path=db_path)] == ["hello"]


def test_save_message_returns_false_when_disk_full(db_path, monkeypatch, caplog):
    """Reproduces the real T07 'database or disk is full' error without filling C:."""
    real_get_connection = db.get_connection

    def full_disk_connection(path):
        connection = real_get_connection(path)
        pages = connection.execute("PRAGMA page_count").fetchone()[0]
        connection.execute(f"PRAGMA max_page_count = {pages}")  # no room to grow
        return connection

    monkeypatch.setattr(db, "get_connection", full_disk_connection)
    private_text = "PRIVATE-NOTE-" + "x" * 200_000
    with caplog.at_level(logging.ERROR, logger=db.__name__):
        assert db.save_message("user", private_text, "general", db_path=db_path) is False

    assert "database or disk is full" in caplog.text
    assert "PRIVATE-NOTE" not in caplog.text  # content never logged
    monkeypatch.undo()
    assert db.load_messages(db_path=db_path) == []  # no partial row left behind


@pytest.mark.parametrize("role, mode", [("admin", "general"), ("user", "chat")])
def test_save_message_still_rejects_invalid_role_or_mode(db_path, role, mode):
    with pytest.raises(ValueError):
        db.save_message(role, "hi", mode, db_path=db_path)


def test_load_messages_returns_empty_list_on_error(monkeypatch):
    monkeypatch.setattr(db, "get_connection", _raise_db_error)
    assert db.load_messages() == []


def test_load_messages_returns_empty_list_for_corrupt_file(tmp_path):
    path = tmp_path / "corrupt.db"
    path.write_bytes(b"not a database " * 100)
    assert db.load_messages(db_path=str(path)) == []


def test_clear_messages_returns_true_on_success(db_path):
    db.save_message("user", "hello", "general", db_path=db_path)
    assert db.clear_messages(db_path=db_path) is True
    assert db.load_messages(db_path=db_path) == []


def test_clear_messages_returns_false_on_error(monkeypatch):
    monkeypatch.setattr(db, "get_connection", _raise_db_error)
    assert db.clear_messages() is False


def test_init_db_returns_false_when_folder_cannot_be_created(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file where the data folder should be")
    assert db.init_db(str(blocker / "studymate.db")) is False


def test_init_db_returns_false_for_corrupt_file(tmp_path):
    path = tmp_path / "corrupt.db"
    path.write_bytes(b"not a database " * 100)
    assert db.init_db(str(path)) is False


def test_created_at_is_utc(db_path):
    before = datetime.now(timezone.utc).replace(microsecond=0)
    db.save_message("user", "hello", "general", db_path=db_path)
    created = datetime.fromisoformat(db.load_messages(db_path=db_path)[0]["created_at"])
    assert created.utcoffset() == timedelta(0)
    assert before <= created <= datetime.now(timezone.utc)


def test_format_local_time_converts_utc_to_given_zone():
    assert db.format_local_time("2026-11-01 05:57:03+00:00", tz=IST) == "2026-11-01 11:27"


def test_format_local_time_handles_date_change():
    assert db.format_local_time("2026-10-31 20:00:00+00:00", tz=IST) == "2026-11-01 01:30"


@pytest.mark.parametrize("value", ["2026-11-01 11:27:03", "not a date", ""])
def test_format_local_time_returns_naive_or_invalid_values_unchanged(value):
    assert db.format_local_time(value) == value