"""Both APIs and the MCP server on a laptop, sharing one in-memory store.

Run from code/backend:
    .venv/bin/uvicorn local:app --port 8000

With BACKEND_SIMULATION=on, the slots no camera reports fill and empty over a
simulated day, in a background thread of this process.
"""

import composition
import logs

logs.configure()
app = composition.local_app()
if composition.settings().simulation == "on":
    composition.simulator().start()
