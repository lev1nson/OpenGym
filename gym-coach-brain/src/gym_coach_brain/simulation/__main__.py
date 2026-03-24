"""Allow running the simulation package directly as a module.

    python -m gym_coach_brain.simulation --months=6 --sessions-per-week=3
    python -m gym_coach_brain.simulation.run --months=6 --sessions-per-week=3
"""
from gym_coach_brain.simulation.run import main

main()
