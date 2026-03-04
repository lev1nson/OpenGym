#!/usr/bin/env python3

"""Gym Coach onboarding (CLI)

Purpose: collect minimal profile + equipment list for Max and store into gym_coach.sqlite.

This is a pragmatic script you can run once, then re-run anytime to update.
It writes ONLY to SQLite (no reliance on LLM memory).

Usage:
  python3 skills/gym-coach/onboard.py

Optional non-interactive usage (all fields optional):
  python3 skills/gym-coach/onboard.py \
    --goal "strength+hypertrophy" \
    --priority "aesthetics+strength" \
    --days-per-week 3 \
    --session-min 60 \
    --periodization alt_week_heavy_light \
    --equipment "dumbbells to 30kg, bench, cable" \
    --injuries "none"
"""

import argparse
import datetime as dt
import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "gym_coach.sqlite")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    # Import schema text from gym_coach.py without executing code paths
    from gym_coach import SCHEMA_SQL  # type: ignore

    conn.executescript(SCHEMA_SQL)

    # Ensure profile row exists
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    conn.execute("INSERT OR IGNORE INTO user_profile(id, updated_at) VALUES(1, ?)", (now,))

    # Ensure equipment table exists (added here for onboarding)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS equipment (
          name TEXT PRIMARY KEY,
          qty INTEGER,
          notes TEXT
        );
        """
    )


def prompt(msg: str, default: str | None = None) -> str:
    if default:
        msg = f"{msg} [{default}]"
    msg = msg + ": "
    val = input(msg).strip()
    return val if val else (default or "")


def upsert_profile(conn: sqlite3.Connection, fields: dict) -> None:
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    sets = []
    vals = []
    for k, v in fields.items():
        sets.append(f"{k}=?")
        vals.append(v)
    if not sets:
        return
    sql = f"UPDATE user_profile SET {', '.join(sets)}, updated_at=? WHERE id=1"
    conn.execute(sql, (*vals, now))


def set_equipment_bulk(conn: sqlite3.Connection, equipment_text: str) -> None:
    # Very simple: split by comma/newline; store raw names.
    items = [x.strip() for x in equipment_text.replace("\n", ",").split(",") if x.strip()]
    if not items:
        return
    conn.execute("DELETE FROM equipment")
    for it in items:
        conn.execute("INSERT INTO equipment(name, qty, notes) VALUES(?, NULL, NULL)", (it,))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gym_coach_onboard")
    p.add_argument("--goal")
    p.add_argument("--priority")
    p.add_argument("--periodization")
    p.add_argument("--days-per-week", type=int)
    p.add_argument("--session-min", type=int)
    p.add_argument("--equipment", help="Comma-separated list")
    p.add_argument("--injuries")
    p.add_argument("--experience")
    return p


def main() -> None:
    args = build_parser().parse_args()

    conn = connect()
    with conn:
        ensure_schema(conn)

        # Extend user_profile with extra columns if missing (MVP migration-lite)
        # SQLite: add columns if not exist
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(user_profile)").fetchall()}
        for col, ctype in [
            ("days_per_week", "INTEGER"),
            ("session_minutes", "INTEGER"),
            ("injuries", "TEXT"),
            ("experience", "TEXT"),
        ]:
            if col not in cols:
                conn.execute(f"ALTER TABLE user_profile ADD COLUMN {col} {ctype}")

        non_interactive = any(
            getattr(args, k.replace("-", "_"), None) is not None
            for k in [
                "goal",
                "priority",
                "periodization",
                "days_per_week",
                "session_min",
                "equipment",
                "injuries",
                "experience",
            ]
        )

        fields = {}
        if non_interactive:
            if args.goal is not None:
                fields["goal"] = args.goal
            if args.priority is not None:
                fields["priority"] = args.priority
            if args.periodization is not None:
                fields["periodization"] = args.periodization
            if args.days_per_week is not None:
                fields["days_per_week"] = args.days_per_week
            if args.session_min is not None:
                fields["session_minutes"] = args.session_min
            if args.injuries is not None:
                fields["injuries"] = args.injuries
            if args.experience is not None:
                fields["experience"] = args.experience

            upsert_profile(conn, fields)
            if args.equipment:
                set_equipment_bulk(conn, args.equipment)

            print("OK: onboarding updated (non-interactive)")
            return

        # Interactive
        print("Gym Coach onboarding (interactive) — press Enter to keep defaults")
        prof = conn.execute(
            "SELECT goal, priority, periodization, rest_seconds_compound, rest_seconds_isolation, days_per_week, session_minutes, injuries, experience FROM user_profile WHERE id=1"
        ).fetchone()

        goal = prompt("Goal", prof["goal"] or "strength+hypertrophy")
        priority = prompt("Priority", prof["priority"] or "aesthetics+strength")
        periodization = prompt("Periodization", prof["periodization"] or "alt_week_heavy_light")
        dpw = prompt("Days per week", str(prof["days_per_week"] or "3"))
        sess = prompt("Session minutes", str(prof["session_minutes"] or "60"))
        rest_c = prompt("Rest compound seconds", str(prof["rest_seconds_compound"] or "120"))
        rest_i = prompt("Rest isolation seconds", str(prof["rest_seconds_isolation"] or "90"))
        exp = prompt("Experience", prof["experience"] or "intermediate")
        inj = prompt("Injuries/limitations", prof["injuries"] or "none")
        equip = prompt(
            "Equipment list (comma-separated)",
            "dumbbells, bench, cable machine" if conn.execute("SELECT COUNT(*) c FROM equipment").fetchone()[0] == 0 else "",
        )

        upsert_profile(
            conn,
            {
                "goal": goal,
                "priority": priority,
                "periodization": periodization,
                "days_per_week": int(dpw) if dpw else None,
                "session_minutes": int(sess) if sess else None,
                "rest_seconds_compound": int(rest_c) if rest_c else 120,
                "rest_seconds_isolation": int(rest_i) if rest_i else 90,
                "experience": exp,
                "injuries": inj,
            },
        )
        if equip:
            set_equipment_bulk(conn, equip)

        print("OK: onboarding saved")


if __name__ == "__main__":
    main()
