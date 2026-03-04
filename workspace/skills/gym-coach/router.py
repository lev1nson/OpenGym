#!/usr/bin/env python3

"""Natural-language router for gym_coach CLI.

Purpose:
- Accept free-form user text (RU/EN mixed)
- Detect intent and entities
- Dispatch safe structured command to gym_coach.py
- Return short human-friendly response for agent usage
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


BASE_DIR = Path(__file__).resolve().parent
GYM_COACH_PATH = BASE_DIR / "gym_coach.py"
_GYM_COACH_TIMEOUT = 30


DAY_ALIASES: Dict[str, str] = {
    "push": "Push",
    "pull": "Pull",
    "legs": "Legs",
    "ноги": "Legs",
    "жим": "Push",
    "тяга": "Pull",
}


@dataclass
class RouteResult:
    intent: str
    argv: List[str]
    needs_clarification: bool = False
    clarification: Optional[str] = None


RE_WEIGHT_REPS_X = re.compile(r"(?P<w>\d+(?:[\.,]\d+)?)\s*[xх×]\s*(?P<r>\d{1,3})\b", re.IGNORECASE)
RE_WEIGHT_REPS_NA = re.compile(r"(?P<w>\d+(?:[\.,]\d+)?)\s*(?:на|по)\s*(?P<r>\d{1,3})\b", re.IGNORECASE)
RE_RPE = re.compile(r"(?:rpe|@)\s*(?P<rpe>\d+(?:[\.,]\d+)?)", re.IGNORECASE)
RE_RIR = re.compile(r"(?:rir|\bв\s+запасе)\s*(?P<rir>\d+(?:[\.,]\d+)?)|(?P<rir2>\d+(?:[\.,]\d+)?)\s*(?:rir|\bв\s+запасе)", re.IGNORECASE)


def norm_num(raw: str) -> str:
    return raw.replace(",", ".")


def has_any(text: str, words: List[str]) -> bool:
    return any(w in text for w in words)


def extract_day(text: str) -> Optional[str]:
    for key, value in DAY_ALIASES.items():
        if re.search(rf"\b{re.escape(key)}\b", text, flags=re.IGNORECASE):
            return value
    return None


def extract_swap_target(text: str) -> Optional[str]:
    """Extract replacement exercise name from text like 'замени на жим гантелей' or 'replace with push-up'."""
    m = re.search(
        r"(?:заменить?\s+на|замени\s+на|replace\s+with|switch\s+to|заменить?\s+на)\s+(.+)",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip().rstrip(".,!?")
    # Also handle "на X" at the end of text after swap keywords
    m2 = re.search(r"\bна\s+(.+)$", text, re.IGNORECASE)
    if m2:
        candidate = m2.group(1).strip().rstrip(".,!?")
        # Avoid matching day aliases ("на Push" etc.) or short prepositions
        if len(candidate) > 2 and candidate.lower() not in DAY_ALIASES:
            return candidate
    return None


def detect_set_payload(text: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    m = RE_WEIGHT_REPS_X.search(text) or RE_WEIGHT_REPS_NA.search(text)
    if not m:
        return None, None, None, None

    weight = norm_num(m.group("w"))
    reps = m.group("r")

    prefix = text[: m.start()].strip(" :-—")
    exercise = prefix if prefix else None

    # Search for RPE/RIR only in text after the weight×reps match to avoid
    # false positives like the "8" in "70x8 rir 2" being treated as RIR value
    suffix = text[m.end():]

    mrpe = RE_RPE.search(suffix)
    rpe = norm_num(mrpe.group("rpe")) if mrpe else None

    if not rpe:
        mrir = RE_RIR.search(suffix)
        if mrir:
            rir_raw = mrir.group("rir") or mrir.group("rir2")
            if rir_raw:
                rir_val = float(norm_num(rir_raw))
                rpe = str(round(10.0 - rir_val, 1))

    return exercise, weight, reps, rpe


def route_text(raw: str) -> RouteResult:
    text = raw.strip()
    low = text.lower()

    if not text:
        return RouteResult(
            intent="empty",
            argv=[],
            needs_clarification=True,
            clarification="Пустой ввод. Скажи, что сделать: начать тренировку, записать сет, пауза, завершить.",
        )

    # High-priority controls
    if has_any(low, ["статус", "status", "что сейчас", "текущая тренировка"]):
        return RouteResult("workout_status", ["workout", "status"])
    if has_any(low, ["пауза", "pause", "перерыв"]):
        return RouteResult("workout_pause", ["workout", "pause"])
    if has_any(low, ["продолж", "resume", "возобнов"]):
        return RouteResult("workout_resume", ["workout", "resume"])
    if has_any(low, ["отмени последний", "undo", "откат", "удали последний сет"]):
        return RouteResult("workout_undo", ["workout", "undo"])
    if has_any(low, ["прервать", "abort", "отмена тренировки"]):
        return RouteResult("workout_abort", ["workout", "abort"])
    if has_any(low, ["пропускаю", "пропустить", "перенесу", "перенос тренировк", "не тренируюсь", "skip workout", "rest day", "день отдыха", "пропущу"]):
        argv = ["workout", "skip"]
        day = extract_day(low)
        if day:
            argv += ["--day", day]
        reason_m = re.search(r"(?:потому что|because|так как|т\.к\.)\s*(.+)", low)
        if reason_m:
            argv += ["--reason", reason_m.group(1).strip()]
        return RouteResult("workout_skip", argv)
    if has_any(low, ["заверш", "finish", "done", "конец тренировки", "закончил тренировку", "закончил", "всё", "всe", "готово", "потренировался", "end workout"]):
        return RouteResult("workout_done", ["workout", "done"])

    # Program/next
    if has_any(low, ["следующ", "next workout", "что завтра", "какая тренировка"]):
        return RouteResult("next", ["next"])

    # Program generation
    if has_any(low, ["составь программу", "создай программу", "generate program", "новая программа", "придумай программу", "составить программу", "create program"]):
        return RouteResult("program_generate", ["program", "generate"])

    # Program analysis
    if has_any(low, ["анализ программы", "program analyze", "анализ тренировок", "тренировочный отчёт", "тренировочный отчет"]):
        return RouteResult("program_analyze", ["program", "analyze", "--json"])

    # Adapt recommendation
    if has_any(low, ["адапт", "нагрузк", "deload", "прогрессия", "рекомендац"]):
        exercise, _, _, _ = detect_set_payload(low)
        argv = ["adapt", "recommend"]
        if exercise:
            argv += ["--exercise", exercise]
        return RouteResult("adapt_recommend", argv)

    # Readiness intent
    if has_any(low, ["самочув", "readiness", "готовност", "сон", "устал", "стресс", "боль", "настроение"]):
        nums = {k: None for k in ["sleep", "stress", "fatigue", "soreness", "pain", "mood"]}

        m_sleep = re.search(r"(?:сон|sleep)\s*(?P<v>\d+(?:[\.,]\d+)?)", low)
        if m_sleep:
            nums["sleep"] = norm_num(m_sleep.group("v"))

        for key, pattern in [
            ("stress", r"(?:стресс|stress)\s*(?P<v>\d{1,2})"),
            ("fatigue", r"(?:усталость|fatigue)\s*(?P<v>\d{1,2})"),
            ("soreness", r"(?:крепатура|soreness)\s*(?P<v>\d{1,2})"),
            ("pain", r"(?:боль|pain)\s*(?P<v>\d{1,2})"),
            ("mood", r"(?:настроение|mood)\s*(?P<v>\d{1,2})"),
        ]:
            m = re.search(pattern, low)
            if m:
                nums[key] = m.group("v")

        argv = ["readiness", "log"]
        if nums["sleep"]:
            argv += ["--sleep-hours", nums["sleep"]]
        if nums["stress"]:
            argv += ["--stress", nums["stress"]]
        if nums["fatigue"]:
            argv += ["--fatigue", nums["fatigue"]]
        if nums["soreness"]:
            argv += ["--soreness", nums["soreness"]]
        if nums["pain"]:
            argv += ["--pain", nums["pain"]]
        if nums["mood"]:
            argv += ["--mood", nums["mood"]]

        if len(argv) == 2:
            if has_any(low, ["послед", "last", "покажи готовность"]):
                return RouteResult("readiness_last", ["readiness", "last"])
            return RouteResult(
                intent="readiness_ambiguous",
                argv=[],
                needs_clarification=True,
                clarification="Не вижу чисел readiness. Пример: 'сон 7.5 стресс 4 усталость 5 боль 2 настроение 7'.",
            )

        return RouteResult("readiness_log", argv)

    # Exercise substitution (before start to avoid conflict with "замени начало на...")
    if has_any(low, ["замени", "замен", "занят тренажер", "занята машина", "сломан", "нет штанги", "нет гантелей", "нет оборудования", "alternative", "альтернатив", "substitute", "заменить"]):
        target = extract_swap_target(text)
        if not target:
            # Try to find what exercise is being replaced and suggest alternatives
            # Look for exercise keywords like "жим", "тяга", "приседания" etc.
            suggest_argv: List[str] = []
            # Detect source exercise hints from context
            for keyword, ex_name in [
                ("жим лёжа", "Bench Press"), ("жим гантелей", "Dumbbell Press"),
                ("жим стоя", "Overhead Press"), ("жим", "Bench Press"),
                ("тяга штанги", "Barbell Row"), ("тяга", "Barbell Row"),
                ("приседания", "Squat"), ("румынская тяга", "Romanian Deadlift"),
                ("становая тяга", "Deadlift"), ("подтягивания", "Pull-up"),
                ("bench press", "Bench Press"), ("squat", "Squat"),
                ("deadlift", "Deadlift"), ("overhead press", "Overhead Press"),
            ]:
                if keyword in low:
                    suggest_argv = ["workout", "suggest", "--exercise", ex_name]
                    break

            if suggest_argv:
                # Check if equipment exclusion is mentioned
                if has_any(low, ["нет штанги", "без штанги", "no barbell"]):
                    suggest_argv += ["--exclude-equipment", "barbell"]
                elif has_any(low, ["нет гантелей", "без гантелей", "no dumbbells"]):
                    suggest_argv += ["--exclude-equipment", "dumbbell"]
                return RouteResult("exercise_swap_suggest", suggest_argv)

            return RouteResult(
                intent="exercise_swap_ambiguous",
                argv=[],
                needs_clarification=True,
                clarification="Чем заменить упражнение? Например: 'замени на жим гантелей'. Или укажи упражнение: 'чем заменить жим'.",
            )
        argv = ["workout", "swap", "--to", target]
        return RouteResult("exercise_swap", argv)

    # Start workout
    if has_any(low, ["начать тренировку", "старт тренировки", "start workout", "начинаем тренировку", "погнали тренировк", "начнём тренировку", "начнем тренировку"]):
        argv = ["workout", "start"]
        day = extract_day(low)
        if day:
            argv += ["--day", day]
        return RouteResult("workout_start", argv)

    # Extra / unplanned workout
    if has_any(low, ["дополнительн", "внеплановая", "extra workout", "extra session", "сверх плана", "доп тренировк"]):
        argv = ["workout", "start", "--extra"]
        day = extract_day(low)
        if day:
            argv += ["--day", day]
        return RouteResult("workout_extra", argv)

    # Set logging from spoken text
    exercise, weight, reps, rpe = detect_set_payload(text)
    if weight and reps:
        argv = ["workout", "set", "--structured", "--weight", weight, "--reps", reps]
        if exercise:
            argv += ["--exercise", exercise]
        if rpe:
            argv += ["--rpe", rpe]
        return RouteResult("workout_set", argv)

    # Fallback for explicit set intent without parse
    if has_any(low, ["сделал", "запиши сет", "set", "подход"]):
        return RouteResult(
            intent="set_ambiguous",
            argv=[],
            needs_clarification=True,
            clarification="Не распознал вес/повторы. Пример: 'жим 70x6' или 'жим 70 на 6 rpe 8'.",
        )

    return RouteResult(
        intent="unknown",
        argv=[],
        needs_clarification=True,
        clarification="Не понял команду. Доступно: старт/сет/пауза/продолжить/завершить/readiness/адаптация.",
    )


def run_gym_coach(argv: List[str]) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(GYM_COACH_PATH), *argv]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=_GYM_COACH_TIMEOUT)
    except subprocess.TimeoutExpired as e:
        out = e.output or ""
        err = e.stderr or ""
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        if isinstance(err, bytes):
            err = err.decode(errors="replace")
        if not err:
            err = f"gym_coach timed out after {_GYM_COACH_TIMEOUT}s"
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout=out, stderr=err)


def main() -> None:
    p = argparse.ArgumentParser(prog="gym_coach_router")
    p.add_argument("--text", required=True, help="Natural-language user message")
    p.add_argument("--dry-run", action="store_true", help="Only show routing, do not execute")
    p.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    args = p.parse_args()

    route = route_text(args.text)
    payload: Dict[str, object] = {
        "intent": route.intent,
        "needs_clarification": route.needs_clarification,
    }

    if route.needs_clarification:
        payload["clarification"] = route.clarification
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(route.clarification or "Need clarification")
        return

    payload["argv"] = route.argv
    if args.dry_run:
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"Route: {route.intent} -> {' '.join(route.argv)}")
        return

    # program_generate is a signal for the LLM to generate a program — no CLI call
    if route.intent == "program_generate":
        payload["message"] = "LLM should generate program: call profile show, then create JSON program, then program import"
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print("Intent: program_generate — LLM should generate a program based on user profile")
        return

    proc = run_gym_coach(route.argv)
    payload["exit_code"] = proc.returncode
    payload["stdout"] = (proc.stdout or "").strip()
    payload["stderr"] = (proc.stderr or "").strip()

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
        return

    if proc.returncode == 0:
        print(payload["stdout"])
    else:
        err = payload["stderr"] or payload["stdout"] or "Unknown error"
        print(f"Ошибка выполнения: {err}")
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()

