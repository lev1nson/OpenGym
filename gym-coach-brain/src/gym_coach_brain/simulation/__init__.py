"""
Simulation package for E2E system validation.

Drives a synthetic 6-month athlete training history through the full production
pipeline (planner → ML worker → adaptation engine) without mocks or parallel
business logic.

Entry point:
    python -m gym_coach_brain.simulation.run --months=6 --sessions-per-week=3
"""
