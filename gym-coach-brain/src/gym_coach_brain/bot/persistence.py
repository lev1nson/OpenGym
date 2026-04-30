"""Persistent state storage using SQLite."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any

from loguru import logger

from gym_coach_brain.bot.state import UserState, UserStateStore


class SQLiteUserStateStore(UserStateStore):
    """Thread-safe SQLite-backed user state store with JSON serialization."""

    def __init__(self, db_path: str | Path = "bot_state.db") -> None:
        """
        Initialize the SQLite state store.

        Args:
            db_path: Path to the SQLite database file. Defaults to 'bot_state.db'.
        """
        self.db_path = Path(db_path)
        self._lock = Lock()
        self._cache: dict[str, UserState] = {}
        self._init_database()

    def _init_database(self) -> None:
        """Create the user_states table if it doesn't exist."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_states (
                        user_id TEXT PRIMARY KEY,
                        state_json TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Create index on updated_at for potential cleanup queries
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_user_states_updated_at
                    ON user_states(updated_at)
                """)
                conn.commit()
                logger.info("SQLite user state store initialized at {}", self.db_path)
            except sqlite3.Error as e:
                logger.error("Failed to initialize user state database: {}", e)
                raise
            finally:
                conn.close()

    def get(self, user_id: str) -> UserState:
        """
        Get or create user state for the given user_id.

        First checks in-memory cache, then database, then creates new state.

        Args:
            user_id: Normalized user identifier.

        Returns:
            UserState instance for the user.
        """
        # Check cache first
        if user_id in self._cache:
            return self._cache[user_id]

        # Load from database
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute(
                    "SELECT state_json FROM user_states WHERE user_id = ?",
                    (user_id,)
                )
                row = cursor.fetchone()

                if row:
                    # Deserialize from JSON
                    try:
                        state_data = json.loads(row[0])
                        state = UserState.from_dict(state_data)
                        self._cache[user_id] = state
                        logger.debug("Loaded state for user {} from database", user_id)
                        return state
                    except (json.JSONDecodeError, TypeError, ValueError) as e:
                        logger.error("Failed to deserialize state for user {}: {}", user_id, e)
                        # Fall through to create new state

                # Create new state if not found or deserialization failed
                state = UserState()
                self._cache[user_id] = state
                self._save_state(conn, user_id, state)
                logger.debug("Created new state for user {}", user_id)
                return state

            except sqlite3.Error as e:
                logger.error("Database error while getting state for user {}: {}", user_id, e)
                # Return cached state or new state on database error
                if user_id in self._cache:
                    return self._cache[user_id]
                state = UserState()
                self._cache[user_id] = state
                return state
            finally:
                conn.close()

    def save(self, user_id: str, state: UserState) -> None:
        """
        Explicitly save user state to database.

        This is called automatically by get(), but can be called manually
        to ensure state is persisted after modifications.

        Args:
            user_id: Normalized user identifier.
            state: UserState instance to save.
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                self._save_state(conn, user_id, state)
                self._cache[user_id] = state
                logger.debug("Saved state for user {}", user_id)
            except sqlite3.Error as e:
                logger.error("Failed to save state for user {}: {}", user_id, e)
            finally:
                conn.close()

    def _save_state(self, conn: sqlite3.Connection, user_id: str, state: UserState) -> None:
        """
        Internal method to save state within an existing connection.

        Args:
            conn: Active SQLite connection.
            user_id: Normalized user identifier.
            state: UserState instance to save.
        """
        state_json = json.dumps(state.to_dict(), ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO user_states (user_id, state_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, state_json)
        )
        conn.commit()

    def delete(self, user_id: str) -> None:
        """
        Delete user state from database and cache.

        Args:
            user_id: Normalized user identifier.
        """
        with self._lock:
            # Remove from cache
            self._cache.pop(user_id, None)

            # Remove from database
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
                conn.commit()
                logger.debug("Deleted state for user {}", user_id)
            except sqlite3.Error as e:
                logger.error("Failed to delete state for user {}: {}", user_id, e)
            finally:
                conn.close()

    def cleanup_stale_states(self, days: int = 30) -> int:
        """
        Remove states that haven't been updated in the specified number of days.

        Args:
            days: Number of days of inactivity before state is considered stale.

        Returns:
            Number of states deleted.
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute(
                    """
                    DELETE FROM user_states
                    WHERE updated_at < datetime('now', '-' || ? || ' days')
                    """,
                    (days,)
                )
                deleted_count = cursor.rowcount
                conn.commit()
                logger.info("Cleaned up {} stale user states (older than {} days)", deleted_count, days)
                return deleted_count
            except sqlite3.Error as e:
                logger.error("Failed to cleanup stale states: {}", e)
                return 0
            finally:
                conn.close()

    def export_all_states(self) -> dict[str, dict[str, Any]]:
        """
        Export all user states as a dictionary for backup purposes.

        Returns:
            Dictionary mapping user_id to state data.
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                cursor = conn.execute("SELECT user_id, state_json FROM user_states")
                states = {}
                for row in cursor:
                    user_id, state_json = row
                    try:
                        states[user_id] = json.loads(state_json)
                    except json.JSONDecodeError as e:
                        logger.error("Failed to parse state for user {}: {}", user_id, e)
                logger.info("Exported {} user states", len(states))
                return states
            except sqlite3.Error as e:
                logger.error("Failed to export states: {}", e)
                return {}
            finally:
                conn.close()

    def import_states(self, states: dict[str, dict[str, Any]]) -> int:
        """
        Import user states from a dictionary (for restore from backup).

        Args:
            states: Dictionary mapping user_id to state data.

        Returns:
            Number of states successfully imported.
        """
        imported_count = 0
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                for user_id, state_data in states.items():
                    try:
                        state = UserState.from_dict(state_data)
                        self._save_state(conn, user_id, state)
                        imported_count += 1
                    except (TypeError, ValueError) as e:
                        logger.error("Failed to import state for user {}: {}", user_id, e)
                logger.info("Imported {} user states", imported_count)
                return imported_count
            except sqlite3.Error as e:
                logger.error("Failed to import states: {}", e)
                return imported_count
            finally:
                conn.close()

# Made with Bob
