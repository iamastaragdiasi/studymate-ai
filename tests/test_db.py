import pytest

from database.db import clear_messages, init_db, load_messages, save_message


def test_messages_persist_and_clear(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    save_message("user", "What is a cell?", "general", db_path=db)
    save_message("assistant", "A cell is...", "general", db_path=db)

    init_db(db)  # simulates an app restart: table already exists, data kept
    messages = load_messages(db_path=db)
    assert [m["role"] for m in messages] == ["user", "assistant"]

    clear_messages(db)
    assert load_messages(db_path=db) == []


def test_invalid_role_rejected(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    with pytest.raises(ValueError):
        save_message("system", "x", "general", db_path=db)