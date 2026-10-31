// One bike station in a 3D model of the Endress+Hauser block. The view starts high above the
// block and flies down, like Google Earth, until you stand right in front of one of its racks:
// a green glowing pad on every free slot, a parked bike on every taken one, and a grey pad on
// every slot no camera has seen recently. Once landed you can look around the rack like in
// Google Maps 3D: drag to orbit and tilt, pinch to zoom, twist to rotate, double-tap to return
// to the front view. The rack stays the focus.
//
// The world comes from site.js (OpenStreetMap buildings, streets and car parks, with street
// trees, bushes, lamps and parked cars; written by code/scene-generator/site_world.py) and
// models.js (Kenney CC0 models from the three.js prototype in assets/, written by
// code/scene-generator/kenney_models.py). The app calls BikeSpot.show({id, slots, racks, rack})
// once, BikeSpot.update(slots) on every change and BikeSpot.focus(rack) to fly to another
// rack, with slots as the Availability API sends them ({number, state, location: {lat, lon}})
// and racks as lists of slot numbers. Every slot stands where the station catalog measured it.
// Opened in a browser on its own
// (spot.html?station=cmr-south-02&slots=10&lat=47.48686&lon=7.59992&heading=0) it runs a demo.

(function () {
  "use strict";

  // Treat colours as sRGB like the rest of the page; r149 defaults to linear, which washes
  // every material out. Must run before the first material is made.
  THREE.ColorManagement.legacyMode = false;

  const GREEN = 0x19c25a; // Brand.free in the app: free
  const RED = 0xd50c2f; // Brand.red: taken
  const MIST = 0xa4b3bc; // Brand.mist: no camera has seen the slot recently
  const HORIZON = 0xe2ebf1; // fog colour, matches the bottom of the CSS sky
  const FLIGHT_SECONDS = 3.6; // from high above the block down to the first rack
  const HOP_SECONDS = 2.2; // over the roofs to another rack of the same station
  const EYE_HEIGHT = 1.7;

  const STEEL = new THREE.MeshStandardMaterial({ color: 0x6f7980, metalness: 0.7, roughness: 0.35 });
  const DARK_STEEL = new THREE.MeshStandardMaterial({ color: 0x4c555c, metalness: 0.6, roughness: 0.5 });
  const GLASS = new THREE.MeshStandardMaterial({ color: 0xcfe3ee, metalness: 0.1, roughness: 0.15,
    transparent: true, opacity: 0.38, side: THREE.DoubleSide, depthWrite: false });
  const CONCRETE = new THREE.MeshStandardMaterial({ color: 0xc9c7c2, roughness: 0.95 });
  const BIKE_COLOURS = [0x24282c, 0x2f3c4f, 0xb3262e, 0x3f4a3c, 0xd9dcdf, 0x1d1f22, 0x7a2f8c, 0x2a5f8f];

  // The shelter at each station, from the site photos: the API has the slots but no shelter
  // type. Any other station gets wheel holders in a painted box.
  const SHELTERS = { "cmr-north-01": "long_shelter", "cmr-south-02": "curved_shelter",
    "cmr-garage-03": "bike_garage", "kaegen-west-04": "curved_shelter" };
  // Per kind of rack: how to build it, and at most how many metres of it to fit on screen.
  // A kind with a `pitch` lays out its slots itself, in rows the catalog numbers in order.
  const KINDS = {
    curved_shelter: { build: curvedShelter },
    open_stand: { build: openStand },
    long_shelter: { build: longShelter, view: 10 },
    bike_garage: { build: bikeGarage, pitch: 0.55 },
  };
  const PITCH = 0.6; // slot spacing of a rack with a single slot, where none can be measured

  let renderer, scene, camera, sun;
  let flight = null; // {start, seconds, eye: [P0..P3], target: [from, to], fade}
  const look = new THREE.Vector3(); // where the camera looks, so a hop can start from there
  // After landing the camera orbits the rack: `goal` follows the fingers, `now` eases after
  // it, `spin` keeps a flick turning for a moment. Angles as in THREE.Spherical.
  const orbit = { active: false, focus: null, home: null, now: null, goal: null, lift: 0,
    spin: { theta: 0, phi: 0 }, pointers: new Map(), lastTap: 0, lastMove: 0 };
  // Turning stays within 100° of the front (behind the rack is the building), and the further
  // out you zoom the more you look down, so the buildings never hide the rack.
  const LIMITS = { minRadius: 4, maxRadius: 70, minPhi: 0.12, maxPhi: 1.5, farPhi: 1.0, turn: 1.75,
    minHeight: 1.2 };
  let racks = []; // {holder, front, distance, eye, target}
  const slots = new Map(); // slot number to {pad, beam, bike, state, shown, phase}
  const FOV = 72; // vertical, close to a phone camera held upright
  const MAX_DISTANCE = 18; // far enough back to see a whole rack on a narrow screen
  const clock = new THREE.Clock();

  // ---- World ---------------------------------------------------------------------------

  function setup() {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.setClearColor(0x000000, 0);
    document.body.appendChild(renderer.domElement);

    scene = new THREE.Scene();
    scene.fog = new THREE.Fog(HORIZON, 420, 1600);
    scene.add(new THREE.HemisphereLight(0xe3f0ff, 0x8f8e86, 0.8));
    sun = new THREE.DirectionalLight(0xfff6e8, 2.0);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.bias = -0.0005;
    sun.shadow.radius = 3;
    Object.assign(sun.shadow.camera, { left: -45, right: 45, top: 45, bottom: -45, near: 1, far: 400 });
    scene.add(sun, sun.target);
    aimSun(new THREE.Vector3());

    camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 3000);
    buildWorld(window.SITE);
    camera.position.set(0, 330, 260);
    camera.lookAt(0, 0, 0);
    window.addEventListener("resize", resize);
    resize();
    renderer.setAnimationLoop(render);
  }

  function resize() {
    const w = window.innerWidth, h = window.innerHeight;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  // Sun low in the south-west, its shadow box following the spot.
  function aimSun(at) {
    sun.target.position.copy(at);
    sun.position.copy(at).add(new THREE.Vector3(-90, 150, 110));
    sun.shadow.camera.updateProjectionMatrix();
  }

  // Local metres (x east, y north) to the scene (x east, z south).
  const toScene = (p, y = 0) => new THREE.Vector3(p[0], y, -p[1]);

  function buildWorld(site) {
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(3000, 3000),
      new THREE.MeshStandardMaterial({ color: 0xc4c9c0, roughness: 1 }));
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    const asphalt = new THREE.MeshStandardMaterial({ color: 0x6b7076, map: grainTexture(), roughness: 0.95 });
    const lot = new THREE.MeshStandardMaterial({ color: 0x8d9296, roughness: 0.95 });
    const path = new THREE.MeshStandardMaterial({ color: 0xc9c4b8, roughness: 1 });
    const paint = new THREE.MeshBasicMaterial({ color: 0xf4f4f0 });

    for (const ring of site.parking) {
      const mesh = new THREE.Mesh(flat(ring), lot);
      mesh.position.y = 0.02;
      mesh.receiveShadow = true;
      scene.add(mesh);
    }
    for (const road of site.roads) {
      const isPath = road.kind === "path";
      const mesh = new THREE.Mesh(ribbon(road.line, road.width), isPath ? path : asphalt);
      mesh.position.y = isPath ? 0.025 : 0.03;
      mesh.receiveShadow = true;
      scene.add(mesh);
      if (!isPath && road.width >= 6) {
        const dashes = new THREE.Mesh(dashLine(road.line), paint);
        dashes.position.y = 0.04;
        scene.add(dashes);
      }
    }

    const looks = {
      endress: [new THREE.MeshStandardMaterial({ map: solarTexture(), roughness: 0.6, metalness: 0.2 }),
        new THREE.MeshStandardMaterial({ map: facadeTexture("#cfd5da", "#3b4b59", 0.42), roughness: 0.55, metalness: 0.25 })],
      office: [new THREE.MeshStandardMaterial({ color: 0xa9aba7, roughness: 0.95 }),
        new THREE.MeshStandardMaterial({ map: facadeTexture("#efede7", "#55646f", 0.36), roughness: 0.85 })],
    };
    for (const building of site.buildings) {
      const shape = new THREE.Shape(building.outline.map((p) => new THREE.Vector2(p[0], p[1])));
      const geometry = new THREE.ExtrudeGeometry(shape, { depth: building.height, bevelEnabled: false });
      geometry.rotateX(-Math.PI / 2);
      const mesh = new THREE.Mesh(geometry, looks[building.style] || looks.office);
      mesh.castShadow = mesh.receiveShadow = true;
      scene.add(mesh);
    }

    // Kenney trees, bushes, lamps and cars, one instanced mesh per model so hundreds stay cheap.
    const turn = (i) => ((i * 2.399) % (2 * Math.PI)); // golden-angle spread of headings
    const facing = (dx, dy) => Math.atan2(dx, -dy); // yaw that turns a model's +z to (dx, dy)
    const trees = ["tree_default_fall", "tree_detailed_fall", "tree_oak_fall", "tree_fat_fall"];
    trees.forEach((name, kind) => instances(name, site.trees.filter((p) => p[2] === kind),
      (p, i) => [p[0], p[1], turn(i), p[3]]));
    ["plant_bushLarge", "plant_bushDetailed"].forEach((name, kind) => instances(name,
      site.bushes.filter((_, i) => i % 2 === kind), (p, i) => [p[0], p[1], turn(i), p[2]]));
    instances("light-curved", site.lamps, (p) => [p[0], p[1], facing(-p[2], -p[3]), 9]);
    ["sedan", "suv", "hatchback-sports", "van"].forEach((name, kind) => instances(name,
      site.cars.filter((p) => p[4] === kind), (p, i) => [p[0], p[1], facing(p[2], p[3]) + ((i % 3) - 1) * 0.04, 1.75]));

    // A patch of lawn under every tree and bush.
    const lawn = merge([...site.trees, ...site.bushes].map((p) => {
      const disc = new THREE.CircleGeometry(p.length > 3 ? 2.4 : 1.3, 12);
      disc.rotateX(-Math.PI / 2);
      disc.translate(p[0], 0, -p[1]);
      return disc;
    }));
    const grass = new THREE.Mesh(lawn, new THREE.MeshStandardMaterial({ color: 0x6f9a4e, roughness: 1 }));
    grass.position.y = 0.035;
    grass.receiveShadow = true;
    scene.add(grass);

  }

  // ---- The spot ------------------------------------------------------------------------

  function show(config) {
    const site = window.SITE;
    const local = (l) => [(l.lon - site.origin[1]) * 111320 * Math.cos(site.origin[0] * Math.PI / 180),
      (l.lat - site.origin[0]) * 111320];
    const spec = KINDS[SHELTERS[config.id]] || KINDS.open_stand;
    const where = new Map(config.slots.map((slot) => [slot.number, local(slot.location)]));
    const across = 2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(FOV / 2)) * camera.aspect);

    racks = config.racks.map((numbers) => {
      // The rack stands at the middle of its slots and runs along their principal axis, which
      // is the row for a single row and the long side for the rows of a garage.
      const points = numbers.map((n) => where.get(n));
      const middle = [0, 1].map((k) => points.reduce((sum, p) => sum + p[k], 0) / points.length);
      let sxx = 0, syy = 0, sxy = 0;
      for (const [x, y] of points) {
        const dx = x - middle[0], dy = y - middle[1];
        sxx += dx * dx;
        syy += dy * dy;
        sxy += dx * dy;
      }
      let heading = 0.5 * Math.atan2(2 * sxy, sxx - syy);
      // Its open front faces the nearer street, where riders come from, so turn it round if
      // that street is on its left.
      const street = (side) => Math.min(...site.roads.filter((r) => r.kind === "road").map((r) => distanceToLine(
        [middle[0] + side * 6 * Math.sin(heading), middle[1] - side * 6 * Math.cos(heading)], r.line)));
      if (street(-1) < street(1)) heading += Math.PI;
      const along = (n) => (where.get(n)[0] - middle[0]) * Math.cos(heading) + (where.get(n)[1] - middle[1]) * Math.sin(heading);
      const order = spec.pitch ? numbers : [...numbers].sort((m, n) => along(m) - along(n));

      const holder = new THREE.Group();
      holder.position.copy(toScene(middle));
      holder.rotation.y = heading;
      scene.add(holder);
      holder.updateMatrixWorld(true); // localToWorld below needs it before the first frame

      const length = along(order[order.length - 1]) - along(order[0]);
      const pitch = spec.pitch || (numbers.length > 1 ? length / (numbers.length - 1) : PITCH);
      const built = spec.build(holder, numbers.length, pitch);
      built.places.forEach((place, i) => slots.set(order[i], makeSlot(place, pitch, order[i])));
      holder.traverse((o) => { if (o.isMesh) o.castShadow = true; });

      // Land straight in front of the rack, at eye height, far enough back to see it whole
      // on this screen. Looking a little below the rack keeps it above the app's card.
      const visible = Math.min(built.width, spec.view || Infinity);
      let distance = Math.min((visible / 2 + 0.8) / Math.tan(across / 2), MAX_DISTANCE);
      // Step closer if that spot would be inside a building.
      const eyeAt = (d) => holder.localToWorld(new THREE.Vector3(0, EYE_HEIGHT, d));
      while (distance > 3 && site.buildings.some((b) => inside([eyeAt(distance).x, -eyeAt(distance).z], b.outline))) {
        distance -= 0.5;
      }
      return { holder, distance, eye: eyeAt(distance),
        target: holder.localToWorld(new THREE.Vector3(0, built.lookHeight ?? 0.35, -0.4)),
        front: holder.localToWorld(new THREE.Vector3(0, 0, 1)).sub(holder.position).normalize() };
    });
    update(config.slots, true);

    // OpenStreetMap places street trees and lamps by rule, not by survey, so clear the ground
    // the station stands on and the view of each rack.
    const sight = racks.map((r) => [[r.eye.x, -r.eye.z], [r.holder.position.x, -r.holder.position.z]]);
    clearProps((p) => [...where.values()].some((q) => Math.hypot(p[0] - q[0], p[1] - q[1]) < 4)
      || sight.some((line) => distanceToLine(p, line) < 3));
    focus(config.rack || 0);
  }

  // Fly to one of the station's racks: on the way in from high above the block, between racks
  // in a short hop over the roofs.
  function focus(index) {
    const rack = racks[THREE.MathUtils.clamp(index, 0, racks.length - 1)];
    if (!rack) return;
    const first = !flight, start = camera.position.clone(), centre = rack.holder.position;
    const away = start.clone().sub(look).setY(0).normalize();
    orbit.active = false;
    aimSun(centre);
    flight = {
      start: clock.elapsedTime,
      seconds: first ? FLIGHT_SECONDS : HOP_SECONDS,
      eye: first
        ? [start, centre.clone().addScaledVector(rack.front, 110).setY(170),
          centre.clone().addScaledVector(rack.front, rack.distance + 22).setY(16), rack.eye]
        : [start, start.clone().addScaledVector(away, 10).setY(start.y + 20),
          rack.eye.clone().addScaledVector(rack.front, 10).setY(rack.eye.y + 20), rack.eye],
      target: [look.clone(), rack.target],
      fade: first, // the pads light up as you arrive, once
    };
  }

  function update(list, instant) {
    for (const slot of list) {
      const s = slots.get(slot.number);
      if (!s) continue;
      s.state = slot.state;
      if (instant) s.shown = slot.state === "taken" ? 1 : 0;
    }
  }

  // A slot: pad on the ground, a light beam while it is free, a bike while it is taken.
  function makeSlot(place, pitch, number) {
    const pad = new THREE.Mesh(roundedRect(pitch * 0.82, 1.5, 0.12),
      new THREE.MeshBasicMaterial({ color: GREEN, transparent: true, opacity: 0.75, depthWrite: false, toneMapped: false }));
    pad.rotation.x = -Math.PI / 2;
    pad.position.set(0, 0.075, 0.35);
    place.add(pad);

    const beam = new THREE.Mesh(new THREE.PlaneGeometry(pitch * 0.7, 1.5),
      new THREE.MeshBasicMaterial({ map: beamTexture(), color: GREEN, transparent: true, opacity: 0.6,
        depthWrite: false, side: THREE.DoubleSide, toneMapped: false }));
    beam.position.set(0, 0.75, 0.35);
    place.add(beam);

    const bike = makeBike(BIKE_COLOURS[(number * 5 + 3) % BIKE_COLOURS.length]);
    bike.position.set(0, 0, 0.2);
    place.add(bike);
    return { pad, beam, bike, state: "unknown", shown: 0, phase: number * 0.7 };
  }

  function render() {
    const dt = Math.min(clock.getDelta(), 0.05);
    const t = clock.elapsedTime;

    let arrived = 1;
    if (flight) {
      const k = Math.min((t - flight.start) / flight.seconds, 1);
      if (orbit.active) {
        stepOrbit(dt);
      } else {
        const e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2; // ease in and out
        camera.position.copy(bezier(flight.eye, e));
        camera.lookAt(look.copy(flight.target[0]).lerp(flight.target[1], Math.min(1, e * 1.25)));
        if (k === 1) startOrbit(flight.eye[3], flight.target[1]);
      }
      if (flight.fade) arrived = THREE.MathUtils.clamp((k - 0.75) / 0.25, 0, 1);
    }

    for (const s of slots.values()) {
      const seen = s.state !== "unknown";
      s.shown += ((s.state === "taken" ? 1 : 0) - s.shown) * Math.min(dt * 6, 1);
      const free = 1 - s.shown;
      s.bike.visible = s.shown > 0.02;
      s.bike.scale.setScalar(0.6 + 0.4 * s.shown);
      s.bike.position.y = (1 - s.shown) * 0.3;
      s.pad.material.color.setHex(!seen ? MIST : s.shown > 0.5 ? RED : GREEN);
      const pulse = 0.5 + 0.5 * Math.sin(t * 2.2 + s.phase);
      s.pad.material.opacity = (s.shown > 0.5 || !seen ? 0.85 : 0.6 + 0.3 * pulse) * (0.35 + 0.65 * arrived);
      s.beam.visible = seen && free > 0.02 && arrived > 0;
      s.beam.material.opacity = free * arrived * (0.45 + 0.2 * Math.sin(t * 2.2 + s.phase));
      const p = s.beam.getWorldPosition(new THREE.Vector3());
      s.beam.lookAt(camera.position.x, p.y, camera.position.z);
    }
    renderer.render(scene, camera);
  }

  // ---- Looking around after landing, like Google Maps in 3D -----------------------------

  function startOrbit(eye, focus) {
    const s = new THREE.Spherical().setFromVector3(eye.clone().sub(focus));
    orbit.focus = focus.clone();
    orbit.home = { radius: s.radius, phi: s.phi, theta: s.theta };
    orbit.now = { ...orbit.home };
    orbit.goal = { ...orbit.home };
    orbit.active = true;
    document.body.classList.add("landed");
  }

  function stepOrbit(dt) {
    const { now, goal, spin } = orbit;
    if (!orbit.pointers.size && (spin.theta || spin.phi)) { // a flick keeps turning, then stops
      goal.theta += spin.theta * dt;
      goal.phi += spin.phi * dt;
      const decay = Math.pow(0.03, dt);
      spin.theta *= decay;
      spin.phi *= decay;
      if (Math.abs(spin.theta) + Math.abs(spin.phi) < 0.02) spin.theta = spin.phi = 0;
    }
    goal.radius = THREE.MathUtils.clamp(goal.radius, LIMITS.minRadius, LIMITS.maxRadius);
    const far = THREE.MathUtils.smoothstep(goal.radius, 15, 60);
    goal.phi = THREE.MathUtils.clamp(goal.phi, LIMITS.minPhi, THREE.MathUtils.lerp(LIMITS.maxPhi, LIMITS.farPhi, far));
    const turned = goal.theta - orbit.home.theta;
    if (Math.abs(turned) > LIMITS.turn) {
      goal.theta = orbit.home.theta + Math.sign(turned) * LIMITS.turn;
      spin.theta = 0;
    }
    const ease = Math.min(dt * 10, 1);
    for (const key of ["radius", "phi", "theta"]) now[key] += (goal[key] - now[key]) * ease;

    const position = new THREE.Vector3()
      .setFromSpherical(new THREE.Spherical(now.radius, now.phi, now.theta)).add(orbit.focus);
    // Behind the rack is the building: rise over its roof instead of ending up inside it.
    let roof = LIMITS.minHeight;
    for (const b of window.SITE.buildings) {
      if (inside([position.x, -position.z], b.outline)) roof = Math.max(roof, b.height + 2);
    }
    orbit.lift += (roof - orbit.lift) * ease;
    position.y = Math.max(position.y, orbit.lift);
    camera.position.copy(position);
    camera.lookAt(look.copy(orbit.focus));
  }

  window.addEventListener("pointerdown", (e) => {
    if (!orbit.active) return;
    orbit.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    orbit.spin.theta = orbit.spin.phi = 0;
    const now = performance.now();
    if (orbit.pointers.size === 1 && now - orbit.lastTap < 300) Object.assign(orbit.goal, orbit.home); // double tap: front view
    orbit.lastTap = orbit.lastMove = now;
  });

  window.addEventListener("pointermove", (e) => {
    const p = orbit.pointers.get(e.pointerId);
    if (!p) return;
    const dx = e.clientX - p.x, dy = e.clientY - p.y;
    const now = performance.now(), seconds = Math.max((now - orbit.lastMove) / 1000, 0.008);
    if (orbit.pointers.size === 1) {
      // One finger: the world follows it, turning around the rack and tilting.
      const turn = -dx * 0.006, tilt = -dy * 0.005;
      orbit.goal.theta += turn;
      orbit.goal.phi += tilt;
      orbit.spin = { theta: turn / seconds, phi: tilt / seconds };
    } else {
      // Two fingers: pinch to zoom, twist to rotate, slide up or down together to tilt.
      const other = [...orbit.pointers.entries()].find(([id]) => id !== e.pointerId)[1];
      const before = [p.x - other.x, p.y - other.y], after = [e.clientX - other.x, e.clientY - other.y];
      orbit.goal.radius *= Math.hypot(...before) / Math.max(Math.hypot(...after), 1);
      orbit.goal.theta += Math.atan2(after[1], after[0]) - Math.atan2(before[1], before[0]);
      orbit.goal.phi -= dy * 0.0025;
    }
    p.x = e.clientX;
    p.y = e.clientY;
    orbit.lastMove = now;
  });

  const release = (e) => {
    orbit.pointers.delete(e.pointerId);
    if (performance.now() - orbit.lastMove > 80) orbit.spin.theta = orbit.spin.phi = 0; // held still: no flick
  };
  window.addEventListener("pointerup", release);
  window.addEventListener("pointercancel", release);
  window.addEventListener("wheel", (e) => {
    if (!orbit.active) return;
    orbit.goal.radius *= Math.exp(e.deltaY * 0.0015);
    e.preventDefault();
  }, { passive: false });


  function inside([x, y], ring) {
    let hit = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > y) !== (yj > y) && x < xi + ((y - yi) * (xj - xi)) / (yj - yi)) hit = !hit;
    }
    return hit;
  }

  // Shortest distance in metres from a point to a polyline, all in local metres.
  function distanceToLine([x, y], line) {
    let best = Infinity;
    for (let i = 1; i < line.length; i++) {
      const [x1, y1] = line[i - 1], [x2, y2] = line[i], dx = x2 - x1, dy = y2 - y1;
      const t = THREE.MathUtils.clamp(((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy || 1), 0, 1);
      best = Math.min(best, Math.hypot(x - x1 - t * dx, y - y1 - t * dy));
    }
    return best;
  }

  function bezier([a, b, c, d], t) {
    const u = 1 - t;
    return a.clone().multiplyScalar(u * u * u).addScaledVector(b, 3 * u * u * t)
      .addScaledVector(c, 3 * u * t * t).addScaledVector(d, t * t * t);
  }

  // One instanced mesh of a Kenney model; `place(item, i)` gives [x, y, yaw, scale].
  const geometries = {};
  const props = []; // {mesh, at: [[x, y], ...]}, so a station can clear the ground it stands on
  const KENNEY = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.8, flatShading: true });
  function instances(name, items, place) {
    if (!items.length) return;
    const mesh = new THREE.InstancedMesh(kenney(name), KENNEY, items.length);
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), up = new THREE.Vector3(0, 1, 0);
    items.forEach((item, i) => {
      const [x, y, yaw, scale] = place(item, i);
      m.compose(new THREE.Vector3(x, 0, -y), q.setFromAxisAngle(up, yaw), new THREE.Vector3(scale, scale, scale));
      mesh.setMatrixAt(i, m);
    });
    mesh.castShadow = mesh.receiveShadow = true;
    scene.add(mesh);
    props.push({ mesh, at: items.map((item, i) => place(item, i).slice(0, 2)) });
  }

  // Hides every tree, bush, lamp and car standing where `blocked([x, y])` is true.
  function clearProps(blocked) {
    const gone = new THREE.Matrix4().makeScale(0, 0, 0);
    for (const { mesh, at } of props) {
      at.forEach((p, i) => { if (blocked(p)) mesh.setMatrixAt(i, gone); });
      mesh.instanceMatrix.needsUpdate = true;
    }
  }

  function kenney(name) {
    if (geometries[name]) return geometries[name];
    const model = window.MODELS[name];
    const bytes = (b64) => Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)).buffer;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(bytes(model.p)), 3));
    geometry.setAttribute("normal", new THREE.BufferAttribute(new Float32Array(bytes(model.n)), 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(new Uint8Array(bytes(model.c)), 3, true));
    geometry.setIndex(new THREE.BufferAttribute(model.wide ? new Uint32Array(bytes(model.i)) : new Uint16Array(bytes(model.i)), 1));
    return (geometries[name] = geometry);
  }

  // ---- Kinds: each builds into `parent` with the open front towards +z -------------------

  // Row of `n` slot anchors along x, centred.
  function row(parent, n, pitch, z = 0) {
    const places = [];
    for (let i = 0; i < n; i++) {
      const place = new THREE.Group();
      place.position.set((i - (n - 1) / 2) * pitch, 0, z);
      parent.add(place);
      places.push(place);
    }
    return places;
  }

  // Paving under a rack, so it reads as its own place on the pavement.
  function paving(parent, width, depth, z) {
    const pad = new THREE.Mesh(new THREE.PlaneGeometry(width, depth),
      new THREE.MeshStandardMaterial({ map: tileTexture(width, depth), roughness: 0.9 }));
    pad.rotation.x = -Math.PI / 2;
    pad.position.set(0, 0.05, z);
    pad.receiveShadow = true;
    parent.add(pad);
  }

  // The galvanised shelters with a curved polycarbonate roof along the silver facade.
  function curvedShelter(parent, n, pitch) {
    const length = n * pitch + 0.7, depth = 2.0, height = 2.2;
    paving(parent, length + 2.4, depth + 4, 0.8);
    const arc = (t) => new THREE.Vector3(0, height * Math.sin(t), depth / 2 - depth * Math.cos(t));
    const profile = [];
    for (let i = 0; i <= 24; i++) profile.push(arc((i / 24) * Math.PI / 2));
    const arches = Math.max(3, Math.round(length / 1.3) + 1);
    for (let i = 0; i < arches; i++) {
      const x = -length / 2 + (length * i) / (arches - 1);
      parent.add(tube(profile.map((p) => p.clone().setX(x)), 0.03, STEEL));
    }
    for (const x of [-length / 2, 0, length / 2]) {
      parent.add(tube([new THREE.Vector3(x, 0, depth / 2), new THREE.Vector3(x, height, depth / 2)], 0.035, STEEL));
    }
    for (const i of [0, 9, 17, 24]) {
      const p = profile[i];
      parent.add(tube([new THREE.Vector3(-length / 2, p.y, p.z), new THREE.Vector3(length / 2, p.y, p.z)], 0.025, STEEL));
    }
    parent.add(new THREE.Mesh(sweep(profile, length), GLASS));
    for (const x of [-length / 2, length / 2]) {
      const shape = new THREE.Shape(profile.map((p) => new THREE.Vector2(p.z, p.y)));
      shape.lineTo(depth / 2, 0.08);
      const panel = new THREE.Mesh(new THREE.ShapeGeometry(shape), GLASS);
      panel.rotation.y = -Math.PI / 2;
      panel.position.x = x;
      parent.add(panel);
    }
    rack(parent, n, pitch, -depth / 2 + 0.3);
    return { places: row(parent, n, pitch, -0.2), width: length };
  }

  // Wheel holders on the asphalt, framed by a yellow marking.
  function openStand(parent, n, pitch) {
    const length = n * pitch + 0.8;
    const yellow = new THREE.MeshBasicMaterial({ color: 0xf2c500 });
    for (const [x, z, sx, sz] of [[0, -0.9, length, 0.08], [0, 1.4, length, 0.08], [-length / 2, 0.25, 0.08, 2.3], [length / 2, 0.25, 0.08, 2.3]]) {
      const line = new THREE.Mesh(new THREE.PlaneGeometry(sx, sz), yellow);
      line.rotation.x = -Math.PI / 2;
      line.position.set(x, 0.055, z);
      parent.add(line);
    }
    rack(parent, n, pitch, -0.6);
    return { places: row(parent, n, pitch, -0.3), width: length, lookHeight: 0.1 };
  }

  // The long flat steel roof by the bus stop, five slots per bay on concrete feet.
  function longShelter(parent, n, pitch) {
    const bays = Math.ceil(n / 5), bay = 5 * pitch, length = bays * bay, depth = 2.5, height = 2.4;
    paving(parent, length + 2, depth + 3.5, 0.6);
    const roof = new THREE.Mesh(new THREE.BoxGeometry(length + 0.4, 0.12, depth + 0.5), DARK_STEEL);
    roof.position.set(0, height, 0);
    parent.add(roof);
    for (let i = 0; i <= bays; i++) {
      const x = -length / 2 + i * bay;
      for (const z of [-depth / 2, depth / 2]) {
        parent.add(tube([new THREE.Vector3(x, 0.25, z), new THREE.Vector3(x, height, z)], 0.045, STEEL));
        const foot = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.25, 0.35), CONCRETE);
        foot.position.set(x, 0.125, z);
        parent.add(foot);
      }
    }
    for (const x of [-length / 2, length / 2]) {
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(depth, height - 0.3),
        new THREE.MeshStandardMaterial({ map: gridTexture(), transparent: true, side: THREE.DoubleSide, depthWrite: false }));
      mesh.rotation.y = Math.PI / 2;
      mesh.position.set(x, 0.3 + (height - 0.3) / 2, 0);
      parent.add(mesh);
    }
    rack(parent, n, pitch, -depth / 2 + 0.35);
    return { places: row(parent, n, pitch, -0.2), width: length };
  }

  // The bike garage: a concrete hall open to the street, with rows of double-sided floor
  // racks. The rack is placed at the middle of its slots, so the hall is built around them.
  function bikeGarage(parent, n, pitch) {
    const rows = 2, perSide = Math.ceil(n / rows / 2), width = perSide * pitch + 2.4, depth = 6.4, height = 3.2;
    const hall = new THREE.Group();
    hall.position.z = 1.7 + 2.9 * (rows - 1) / 2;
    parent.add(hall);
    const walls = new THREE.MeshStandardMaterial({ color: 0xd3d1cc, roughness: 0.95, side: THREE.DoubleSide });
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(width, depth), new THREE.MeshStandardMaterial({ color: 0xe4e6e6, roughness: 0.8 }));
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(0, 0.04, -depth / 2);
    floor.receiveShadow = true;
    hall.add(floor);
    for (const [w, h, x, y, z, ry] of [[width, height, 0, height / 2, -depth, 0], [depth, height, -width / 2, height / 2, -depth / 2, Math.PI / 2],
      [depth, height, width / 2, height / 2, -depth / 2, Math.PI / 2], [width, depth, 0, height, -depth / 2, 0]]) {
      const panel = new THREE.Mesh(new THREE.PlaneGeometry(w, h), walls);
      panel.position.set(x, y, z);
      if (w === width && h === depth) panel.rotation.x = Math.PI / 2; else panel.rotation.y = ry;
      panel.receiveShadow = true;
      hall.add(panel);
    }
    const strip = new THREE.MeshBasicMaterial({ color: 0xfdfdf6 });
    for (let i = 0; i < 3; i++) {
      const light = new THREE.Mesh(new THREE.PlaneGeometry(0.25, depth - 1), strip);
      light.rotation.x = Math.PI / 2;
      light.position.set(-width / 3 + i * width / 3, height - 0.02, -depth / 2);
      hall.add(light);
    }
    const lamp = new THREE.PointLight(0xffffff, 0.8, 18);
    lamp.position.set(0, height - 0.4, -depth / 2);
    hall.add(lamp);
    const places = [];
    for (let r = 0; r < rows; r++) {
      const holder = new THREE.Group();
      holder.position.z = -1.7 - r * 2.9;
      hall.add(holder);
      for (const side of [1, -1]) {
        const half = new THREE.Group();
        half.rotation.y = side === 1 ? 0 : Math.PI;
        holder.add(half);
        rack(half, perSide, pitch, -0.05);
        places.push(...row(half, perSide, pitch, 0.3));
      }
    }
    return { places: places.slice(0, n), width, lookHeight: 0.9 };
  }

  // Front-wheel holders: a vertical loop per slot on a rail along x.
  function rack(parent, n, pitch, z) {
    parent.add(tube([new THREE.Vector3(-(n * pitch) / 2, 0.06, z), new THREE.Vector3((n * pitch) / 2, 0.06, z)], 0.02, STEEL));
    for (let i = 0; i < n; i++) {
      const x = (i - (n - 1) / 2) * pitch;
      const loop = [];
      for (let k = 0; k <= 12; k++) {
        const a = Math.PI * (k / 12);
        loop.push(new THREE.Vector3(x, 0.06 + Math.sin(a) * 0.38, z - Math.cos(a) * 0.18));
      }
      parent.add(tube(loop, 0.012, STEEL));
    }
  }

  // ---- Parts ---------------------------------------------------------------------------

  function makeBike(colour) {
    const bike = new THREE.Group();
    const frame = new THREE.MeshStandardMaterial({ color: colour, metalness: 0.35, roughness: 0.45 });
    const tyre = new THREE.MeshStandardMaterial({ color: 0x18191b, roughness: 0.9 });
    const wheel = new THREE.TorusGeometry(0.33, 0.026, 8, 32);
    for (const z of [-0.52, 0.52]) {
      const w = new THREE.Mesh(wheel, tyre);
      w.rotation.y = Math.PI / 2;
      w.position.set(0, 0.35, z);
      bike.add(w);
    }
    const p = (z, y) => new THREE.Vector3(0, y, z);
    const front = p(-0.52, 0.35), rear = p(0.52, 0.35), crank = p(0.02, 0.3);
    const seat = p(0.22, 0.86), headTop = p(-0.36, 0.9), headLow = p(-0.39, 0.74);
    for (const [a, b] of [[crank, seat], [crank, headLow], [seat, headTop], [crank, rear], [seat, rear], [headLow, front], [headTop, p(-0.34, 1.02)]]) {
      bike.add(rod(a, b, 0.018, frame));
    }
    const bar = rod(new THREE.Vector3(-0.27, 1.02, -0.34), new THREE.Vector3(0.27, 1.02, -0.34), 0.014, tyre);
    const saddle = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.05, 0.26), tyre);
    saddle.position.set(0, 0.92, 0.25);
    bike.add(bar, saddle);
    return bike;
  }

  function tube(points, radius, material) {
    const path = new THREE.CatmullRomCurve3(points, false, "catmullrom", 0);
    return new THREE.Mesh(new THREE.TubeGeometry(path, Math.max(points.length * 3, 8), radius, 8), material);
  }

  function rod(a, b, radius, material) {
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, a.distanceTo(b), 8), material);
    mesh.position.copy(a).add(b).multiplyScalar(0.5);
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
    return mesh;
  }

  // A surface following `profile` (points in y/z) across the full length along x.
  function sweep(profile, length) {
    const positions = [], index = [];
    profile.forEach((p) => positions.push(-length / 2, p.y, p.z, length / 2, p.y, p.z));
    for (let i = 0; i < profile.length - 1; i++) {
      const a = i * 2;
      index.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setIndex(index);
    geometry.computeVertexNormals();
    return geometry;
  }

  // A flat polygon (local metres) lying on the ground.
  function flat(ring) {
    const geometry = new THREE.ShapeGeometry(new THREE.Shape(ring.map((p) => new THREE.Vector2(p[0], p[1]))));
    geometry.rotateX(-Math.PI / 2);
    return geometry;
  }

  // A street `width` wide along `line`: a quad per segment plus a disc at every bend.
  function ribbon(line, width) {
    const parts = [];
    line.forEach((p, i) => {
      if (i > 0) {
        const a = line[i - 1], dx = p[0] - a[0], dy = p[1] - a[1], l = Math.hypot(dx, dy) || 1;
        const nx = (-dy / l) * width / 2, ny = (dx / l) * width / 2;
        parts.push(flat([[a[0] + nx, a[1] + ny], [p[0] + nx, p[1] + ny], [p[0] - nx, p[1] - ny], [a[0] - nx, a[1] - ny]]));
      }
      if (i > 0 && i < line.length - 1) {
        const disc = new THREE.CircleGeometry(width / 2, 16);
        disc.rotateX(-Math.PI / 2);
        disc.translate(p[0], 0, -p[1]);
        parts.push(disc);
      }
    });
    return merge(parts);
  }

  // Centre-line dashes: 3 m painted, 4 m gap.
  function dashLine(line) {
    const parts = [];
    for (let i = 1; i < line.length; i++) {
      const a = line[i - 1], b = line[i], l = Math.hypot(b[0] - a[0], b[1] - a[1]);
      for (let s = 1; s + 3 < l; s += 7) {
        const p = (d) => [a[0] + (b[0] - a[0]) * d / l, a[1] + (b[1] - a[1]) * d / l];
        parts.push(ribbon([p(s), p(s + 3)], 0.15));
      }
    }
    return merge(parts);
  }

  // Joins plain triangle geometries into one, so a street is a single draw call. UVs run in
  // metres across the ground, for the asphalt grain.
  function merge(parts) {
    const positions = [], uvs = [];
    for (const part of parts) {
      const g = part.index ? part.toNonIndexed() : part;
      const p = g.attributes.position.array;
      for (let i = 0; i < p.length; i += 3) {
        positions.push(p[i], p[i + 1], p[i + 2]);
        uvs.push(p[i] / 6, p[i + 2] / 6);
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
    geometry.computeVertexNormals();
    return geometry;
  }

  function roundedRect(w, h, r) {
    const s = new THREE.Shape();
    s.moveTo(-w / 2 + r, -h / 2);
    s.lineTo(w / 2 - r, -h / 2); s.quadraticCurveTo(w / 2, -h / 2, w / 2, -h / 2 + r);
    s.lineTo(w / 2, h / 2 - r); s.quadraticCurveTo(w / 2, h / 2, w / 2 - r, h / 2);
    s.lineTo(-w / 2 + r, h / 2); s.quadraticCurveTo(-w / 2, h / 2, -w / 2, h / 2 - r);
    s.lineTo(-w / 2, -h / 2 + r); s.quadraticCurveTo(-w / 2, -h / 2, -w / 2 + r, -h / 2);
    return new THREE.ShapeGeometry(s);
  }

  // ---- Textures, drawn on canvases so the page needs no image files --------------------

  function canvasTexture(size, draw, repeat) {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = size;
    draw(canvas.getContext("2d"), size);
    const texture = new THREE.CanvasTexture(canvas);
    texture.encoding = THREE.sRGBEncoding;
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    if (repeat) texture.repeat.set(repeat[0], repeat[1]);
    texture.anisotropy = 4;
    return texture;
  }

  // One floor (3.6 m) of facade: wall panels with a band of windows. Extruded walls get
  // UVs in metres, so the texture repeats every 3.6 m.
  function facadeTexture(wall, glass, share) {
    return canvasTexture(256, (g, s) => {
      g.fillStyle = wall; g.fillRect(0, 0, s, s);
      const top = s * (0.62 - share / 2), height = s * share;
      const shine = g.createLinearGradient(0, top, 0, top + height);
      shine.addColorStop(0, glass); shine.addColorStop(1, "#6f8191");
      g.fillStyle = shine; g.fillRect(0, top, s, height);
      g.fillStyle = "rgba(255,255,255,0.35)";
      for (let x = 0; x < s; x += 32) g.fillRect(x, top, 3, height);
      g.fillStyle = "rgba(0,0,0,0.08)";
      g.fillRect(0, s - 4, s, 4);
    }, [1 / 3.6, 1 / 3.6]);
  }

  // Solar panels in rows, like the roofs on the aerial photo of the block.
  function solarTexture() {
    return canvasTexture(256, (g, s) => {
      g.fillStyle = "#c3c6c4"; g.fillRect(0, 0, s, s);
      g.fillStyle = "#2c3d5c";
      for (let y = 8; y < s; y += 64) for (let x = 6; x < s; x += 32) g.fillRect(x, y, 28, 52);
      g.fillStyle = "rgba(255,255,255,0.08)";
      for (let y = 8; y < s; y += 64) g.fillRect(0, y, s, 6);
    }, [1 / 8, 1 / 8]);
  }

  // Asphalt grain: speckles and a few darker patches, no gradients (WebKit dithers those).
  function grainTexture() {
    return canvasTexture(256, (g, s) => {
      g.fillStyle = "#ffffff"; g.fillRect(0, 0, s, s);
      let seed = 3;
      const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
      for (let i = 0; i < 2600; i++) {
        const v = 200 + Math.floor(rand() * 55);
        g.fillStyle = `rgb(${v},${v},${v})`;
        g.fillRect(rand() * s, rand() * s, 1 + rand() * 2, 1 + rand() * 2);
      }
      g.fillStyle = "rgba(0,0,0,0.05)";
      for (let i = 0; i < 6; i++) g.fillRect(rand() * s, rand() * s, 30 + rand() * 60, 20 + rand() * 40);
    });
  }

  function tileTexture(width, depth) {
    return canvasTexture(128, (g, s) => {
      g.fillStyle = "#c8c7c2"; g.fillRect(0, 0, s, s);
      g.strokeStyle = "#a9a8a3"; g.lineWidth = 2;
      for (let i = 0; i <= s; i += 16) {
        g.beginPath(); g.moveTo(i, 0); g.lineTo(i, s); g.stroke();
        g.beginPath(); g.moveTo(0, i); g.lineTo(s, i); g.stroke();
      }
    }, [width / 2.4, depth / 2.4]);
  }

  let beamCache;
  function beamTexture() {
    return beamCache || (beamCache = canvasTexture(128, (g, s) => {
      const up = g.createLinearGradient(0, s, 0, 0);
      up.addColorStop(0, "rgba(255,255,255,0.9)"); up.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = up; g.fillRect(0, 0, s, s);
      g.globalCompositeOperation = "destination-in";
      const sides = g.createLinearGradient(0, 0, s, 0);
      sides.addColorStop(0, "rgba(0,0,0,0)"); sides.addColorStop(0.5, "rgba(0,0,0,1)"); sides.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = sides; g.fillRect(0, 0, s, s);
    }));
  }

  function gridTexture() {
    return canvasTexture(256, (g, s) => {
      g.strokeStyle = "rgba(90,100,108,0.85)"; g.lineWidth = 2;
      for (let i = 0; i <= s; i += 16) {
        g.beginPath(); g.moveTo(i, 0); g.lineTo(i, s); g.stroke();
        g.beginPath(); g.moveTo(0, i); g.lineTo(s, i); g.stroke();
      }
    }, [3, 3]);
  }

  setup();
  window.BikeSpot = { show, focus, update: (list) => update(list, false) };

  // Standalone preview: one straight rack with made-up states that keep changing.
  const params = new URLSearchParams(location.search);
  if (params.has("station")) {
    const count = Number(params.get("slots") || 10);
    const lat = Number(params.get("lat") || 47.48686), lon = Number(params.get("lon") || 7.59992);
    const heading = Number(params.get("heading") || 0) * Math.PI / 180, pitch = 0.5;
    const demo = Array.from({ length: count }, (_, i) => {
      const along = (i - (count - 1) / 2) * pitch;
      return { number: i + 1, state: Math.random() < 0.55 ? "taken" : "free", location: {
        lat: lat + along * Math.sin(heading) / 111320,
        lon: lon + along * Math.cos(heading) / (111320 * Math.cos(lat * Math.PI / 180)) } };
    });
    show({ id: params.get("station"), slots: demo, racks: [demo.map((slot) => slot.number)] });
    setInterval(() => {
      const slot = demo[Math.floor(Math.random() * demo.length)];
      slot.state = slot.state === "taken" ? "free" : "taken";
      update(demo, false);
    }, 2500);
  }
})();
