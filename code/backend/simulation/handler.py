"""Lambda entry point of the Simulation function (handler: simulation.handler.handler).

A schedule starts it every minute. It steps the simulation every few seconds
until shortly before its timeout, so the slots move as often as on a laptop,
and the next run carries on from the slot states in DynamoDB.
"""

import time
from datetime import UTC, datetime

import composition
import logs
from simulation.simulator import STEP

logs.configure()
SPARE_MS = 5000  # stop this long before the timeout, so a step is never cut off


def handler(event: dict, context) -> dict:
    simulator = composition.simulator()
    steps = changed = 0
    while context.get_remaining_time_in_millis() > SPARE_MS + STEP.total_seconds() * 1000:
        changed += simulator.step(datetime.now(UTC))
        steps += 1
        time.sleep(STEP.total_seconds())
    logs.log_event("simulation_run", steps=steps, slots_changed=changed)
    return {"steps": steps, "slots_changed": changed}
