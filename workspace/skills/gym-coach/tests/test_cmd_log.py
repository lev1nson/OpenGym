import argparse
import sqlite3
import pytest
import gym_coach
from gym_coach import cmd_log, connect


def test_cmd_log_status_is_completed(tmp_db):
    # Act: log a session (cmd_log calls connect() and ensure_schema() internally)
    args = argparse.Namespace(
        date="2026-03-01",
        day="Push",
        text="bench press 70x6 @8",
    )
    cmd_log(args)

    # Assert: status = 'completed'
    conn = connect()
    row = conn.execute(
        "SELECT status, completed_at FROM workout_sessions ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row["status"] == "completed"
    assert row["completed_at"] is not None
