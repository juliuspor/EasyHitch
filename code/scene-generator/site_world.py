"""The Endress+Hauser block as a small 3D world for the app's spot view.

Reads the OpenStreetMap extract and writes the buildings, streets, car parks and
street trees, bushes, lamps and parked cars within RADIUS metres of the block as local metres (x east, y north
of ORIGIN) into a script the spot view loads. The view extrudes them in three.js,
flies down from above the block and lands in front of the chosen bike spot.
No Blender needed.

Run: python3 code/scene-generator/site_world.py
"""

import json
import math
import xml.etree.ElementTree as ET
from random import Random
from pathlib import Path

ROOT = Path(__file__).parents[2]
OSM = ROOT / "assets/campus-map/source.osm"
STATIONS = ROOT / "code/backend/data/stations.json"
OUT = ROOT / "code/ios/BikeSlot/Spot/site.js"

ORIGIN = (47.48776, 7.59908)  # middle of the block, same as Site.center in the app
RADIUS = 230
ENDRESS = "238805703"  # the Endress+Hauser block, silver facades and solar roofs
FLOOR = 3.6
ROADS = {"secondary": 7.5, "residential": 6.5, "service": 4.0, "footway": 2.0, "path": 2.0}
TREE_SPACING, TREE_OFFSET = 13.0, 3.5  # metres along and beside the bigger streets
LAMP_SPACING = 34.0
MAX_CARS = 160


def local(lat, lon):
    return (round((lon - ORIGIN[1]) * 111320 * math.cos(math.radians(ORIGIN[0])), 1),
            round((lat - ORIGIN[0]) * 111320, 1))


def inside(point, polygon):
    x, y = point
    hit = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def near_line(point, line, distance):
    px, py = point
    for (x1, y1), (x2, y2) in zip(line, line[1:]):
        dx, dy = x2 - x1, y2 - y1
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy or 1)))
        if math.hypot(px - x1 - t * dx, py - y1 - t * dy) < distance:
            return True
    return False


def main():
    root = ET.parse(OSM).getroot()
    nodes = {n.get("id"): local(float(n.get("lat")), float(n.get("lon"))) for n in root.iter("node")}
    buildings, roads, parking = [], [], []
    for way in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in way.iter("tag")}
        points = [nodes[nd.get("ref")] for nd in way.iter("nd") if nd.get("ref") in nodes]
        if len(points) < 2 or min(math.hypot(*p) for p in points) > RADIUS:
            continue
        ring = points[:-1] if points[0] == points[-1] else points
        if "building" in tags and tags["building"] != "roof":
            levels = int(tags.get("building:levels", 0)) or (4 if way.get("id") == ENDRESS else 3)
            buildings.append({"outline": ring, "height": round(levels * FLOOR, 1),
                              "style": "endress" if way.get("id") == ENDRESS else "office"})
        elif tags.get("highway") in ROADS:
            roads.append({"line": points, "width": ROADS[tags["highway"]],
                          "kind": "path" if tags["highway"] in ("footway", "path") else "road"})
        elif tags.get("amenity") == "parking" and points[0] == points[-1]:
            parking.append(ring)

    spots = [local(s["location"]["lat"], s["location"]["lon"]) for s in json.loads(STATIONS.read_text())["stations"]]
    random = Random(7)  # fixed seed: the same world on every build

    def free(p, clearance, others=(), gap=0):
        """Open ground: not in a building, car park or street, and clear of the racks."""
        return (math.hypot(*p) < RADIUS and not any(inside(p, b["outline"]) for b in buildings)
                and not any(inside(p, lot) for lot in parking)
                and not any(near_line(p, r["line"], r["width"] / 2 + 1.5) for r in roads)
                and all(math.hypot(p[0] - s[0], p[1] - s[1]) > clearance for s in spots)
                and all(math.hypot(p[0] - q[0], p[1] - q[1]) > gap for q in others))

    # Street trees in four kinds with bushes between them, and lamps, along the bigger streets.
    trees, bushes, lamps = [], [], []
    for road in roads:
        if road["width"] < 6:
            continue
        for (x1, y1), (x2, y2) in zip(road["line"], road["line"][1:]):
            length = math.hypot(x2 - x1, y2 - y1)
            nx, ny = -(y2 - y1) / length, (x2 - x1) / length
            at = lambda d, side, offset: (round(x1 + d / length * (x2 - x1) + side * nx * offset, 1),
                                          round(y1 + d / length * (y2 - y1) + side * ny * offset, 1))
            for step in range(int(length // TREE_SPACING)):
                for side in (1, -1):
                    offset = road["width"] / 2 + TREE_OFFSET
                    p = at((step + 0.5) * TREE_SPACING, side, offset)
                    if free(p, 20, [q[:2] for q in trees], 6):
                        trees.append([*p, random.randrange(4), round(random.uniform(3.4, 4.6), 2)])
                    b = at((step + 1) * TREE_SPACING, side, offset)
                    if random.random() < 0.6 and free(b, 20, [q[:2] for q in trees + bushes], 3):
                        bushes.append([*b, round(random.uniform(3.6, 4.8), 2)])
            for step in range(int(length // LAMP_SPACING)):
                side = 1 if step % 2 else -1
                p = at((step + 0.5) * LAMP_SPACING, side, road["width"] / 2 + 1.7)
                if free(p, 12, [q[:2] for q in lamps], 20):
                    lamps.append([*p, round(-side * nx, 3), round(-side * ny, 3)])  # the arm reaches over the street

    # Parked cars in rows across each car park's longest side, about two in three bays taken.
    cars = []
    for lot in parking:
        edges = list(zip(lot, lot[1:] + lot[:1]))
        (ax, ay), (bx, by) = max(edges, key=lambda e: math.hypot(e[1][0] - e[0][0], e[1][1] - e[0][1]))
        length = math.hypot(bx - ax, by - ay)
        dx, dy = (bx - ax) / length, (by - ay) / length
        span = [(x - ax) * -dy + (y - ay) * dx for x, y in lot]
        for depth in range(int(min(span) // 5.6) - 1, int(max(span) // 5.6) + 2):
            for along in range(-60, 60):
                p = (round(ax + along * 2.6 * dx - (depth * 5.6 + 2.8) * dy, 1),
                     round(ay + along * 2.6 * dy + (depth * 5.6 + 2.8) * dx, 1))
                if (inside(p, lot) and random.random() < 0.65
                        and all(math.hypot(p[0] - s[0], p[1] - s[1]) > 25 for s in spots)):
                    cars.append([*p, round(-dy, 3), round(dx, 3), random.randrange(4)])
    cars = random.sample(cars, min(len(cars), MAX_CARS))  # enough to read as car parks, light on a phone

    site = {"origin": ORIGIN, "buildings": buildings, "roads": roads, "parking": parking, "trees": trees,
            "bushes": bushes, "lamps": lamps, "cars": cars}
    OUT.write_text("// Generated by code/scene-generator/site_world.py from OpenStreetMap data\n"
                   "// (© OpenStreetMap contributors, ODbL). Do not edit by hand.\n"
                   f"window.SITE = {json.dumps(site, separators=(',', ':'))};\n")
    print(f"wrote {len(buildings)} buildings, {len(roads)} streets and paths, {len(parking)} car parks, "
          f"{len(trees)} trees, {len(bushes)} bushes, {len(lamps)} lamps, {len(cars)} cars to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
