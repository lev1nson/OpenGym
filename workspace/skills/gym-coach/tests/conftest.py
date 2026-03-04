import pytest
import gym_coach


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    db = tmp_path / "test.sqlite"
    monkeypatch.setattr(gym_coach, "DB_PATH", str(db))
    return db
