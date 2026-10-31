#!/bin/sh
# Refreshes the app's built-in demo data with the stations as a running backend reports them.
# Start the backend and the recorded cameras first (code/backend/README.md, code/edge/README.md).
# Run from anywhere:
#   code/ios/refresh-demo.sh [backend url]
set -e
cd "$(dirname "$0")"
URL="${1:-http://localhost:8000}"

python3 - "$URL" BikeSlot/Demo/demo-stations.json <<'PY'
import json, random, sys, urllib.request
url, target = sys.argv[1], sys.argv[2]
get = lambda path: json.load(urllib.request.urlopen(url + path))
details = [get(f"/v1/stations/{station['id']}") for station in get("/v1/stations")["stations"]]
if not any(slot["state"] != "unknown" for detail in details for slot in detail["slots"]):
    sys.exit("No camera has reported yet. Start the recorded cameras, then run this again.")
for detail in details:
    if all(slot["state"] == "unknown" for slot in detail["slots"]):
        # No camera covers this station yet; give the demo a plausible, fixed morning.
        rng = random.Random(detail["id"])
        for slot in detail["slots"]:
            slot["state"] = "taken" if rng.random() < 0.6 else "free"
        for state in ("free", "taken", "unknown"):
            detail[state] = sum(slot["state"] == state for slot in detail["slots"])
json.dump(details, open(target, "w"), indent=2)
print(f"wrote {len(details)} stations to {target}")
PY
