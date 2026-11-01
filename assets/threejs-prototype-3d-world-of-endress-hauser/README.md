# First 3D sketch: Christoph-Merian-Ring in three.js

An early three.js sketch of the ride to a free spot, kept runnable on its own.
It is a low-poly, street-level model of Christoph-Merian-Ring between the two
bicycle stations at Endress+Hauser: you ride down the Ring and see which spots
at each stand are free (green) or taken (red). The app's 3D view and 3D
Navigation are in [`code/ios/BikeSlot/Spot`](../../code/ios/BikeSlot/Spot).

## Run it

Serve the `assets/` folder, because the page also reads the shared
OpenStreetMap extract in `assets/campus-map/`:

```sh
python3 -m http.server 8139 --bind 127.0.0.1 --directory assets
```

Then open
<http://localhost:8139/threejs-prototype-3d-world-of-endress-hauser/index.html>.
three.js r170 loads from jsDelivr, so the page needs internet access.

## Views

- **Ride north → south**: the camera rides the right-hand side of the Ring
  from Bruggrain to the south bend, slowing and turning towards each stand.
- **North stand / South stand**: fixed rider's-eye views of each station,
  with mouse orbit.
- **Free look**: overview with orbit controls.

`window.__ring` exposes `stations` (free and total counts per zone) and
`setMode(view)` for checks.

## Sources

- [`main.js`](main.js) builds everything at load time:
  - [`../campus-map/source.osm`](../campus-map/source.osm) supplies the
    roads, building footprints, the north shelter roof (OSM way 1463536691),
    and mapped trees. © OpenStreetMap contributors, ODbL.
  - [`roof-colors.json`](roof-colors.json) supplies the roof colours.
- Facades are textures drawn on canvases from patterns observed in Google
  Street View (2023-2024), listed in `FACADES`. No imagery is copied.
  Buildings away from the Ring get a generic punched-window facade.
- Cars, trees, shrubs, street lamps, and the bus stop pole are Kenney models
  in [`kenney/`](kenney/), CC0 (each kit has its `License.txt`). Car paint and
  tree crowns are recoloured in code.
- Shelters, racks, bicycles, kerbs, and road markings are generated in code
  from the 29 October 2026 site photos.
- three.js r170 (MIT licence) loads from jsDelivr and is not vendored here.
- Slot states are seeded in the page, 45 slots north and 20 south. The app
  reads them from the backend.
