"""Builds data/stations.json from the campus map's slot list.

Run from code/backend:
    .venv/bin/python -m stations.build ../../assets/campus-map/slots.json data/stations.json
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

# Named like bike-sharing stations: the street a rider looks for, with a
# direction because the street has more than one station.
DISPLAY_NAMES = {
    "CMR_NORTH_01": "Christoph-Merian-Ring North",
    "CMR_SOUTH_02": "Christoph-Merian-Ring South",
    "CMR_GARAGE_03": "Christoph-Merian-Ring Bike Garage",
    "KAEGEN_WEST_04": "Kägenstrasse",
}


def station_id(zone_id: str) -> str:
    return zone_id.lower().replace("_", "-")


def build(slots: list[dict]) -> dict:
    zones = defaultdict(list)
    for slot in slots:
        zones[slot["zone_id"]].append(slot)
    unnamed = sorted(set(zones) - set(DISPLAY_NAMES))
    if unnamed:
        raise SystemExit(f"no display name for zone {', '.join(unnamed)}. Add it to DISPLAY_NAMES")

    stations = []
    for zone_id, zone_slots in sorted(zones.items()):
        zone_slots.sort(key=lambda slot: slot["slot"])
        stations.append({
            "id": station_id(zone_id),
            "name": DISPLAY_NAMES[zone_id],
            "location": {
                "lat": round(sum(slot["lat"] for slot in zone_slots) / len(zone_slots), 7),
                "lon": round(sum(slot["lon"] for slot in zone_slots) / len(zone_slots), 7),
            },
            "slots": [
                {"number": slot["slot"], "location": {"lat": slot["lat"], "lon": slot["lon"]}}
                for slot in zone_slots
            ],
        })
    return {"stations": stations}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slots", type=Path, help="assets/campus-map/slots.json")
    parser.add_argument("output", type=Path, help="data/stations.json")
    args = parser.parse_args()
    catalog = build(json.loads(args.slots.read_text())["slots"])
    args.output.write_text(json.dumps(catalog, indent=2) + "\n")
    print(f"wrote {len(catalog['stations'])} stations to {args.output}")


if __name__ == "__main__":
    main()
