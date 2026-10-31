import MapKit
import SwiftUI

struct MapScreen: View {
    @Environment(StationStore.self) private var store
    @State private var path: [Station] = []
    @State private var showSettings = false
    @State private var search = LocationSearch()
    @State private var destination: Destination?
    @State private var selectedID: Station.ID?
    @FocusState private var searchFocused: Bool
    @State private var position = Self.camera(at: Site.center, distance: 900)
    @AppStorage("demoMode") private var demoMode = false

    private static func camera(at center: CLLocationCoordinate2D, distance: Double) -> MapCameraPosition {
        .camera(MapCamera(centerCoordinate: center, distance: distance, heading: 0, pitch: 0))
    }

    private var selected: Station? { store.stations.first { $0.id == selectedID } }

    var body: some View {
        NavigationStack(path: $path) {
            // Flat, north-up and pan/zoom only, like a mobility app map.
            Map(position: $position, interactionModes: [.pan, .zoom]) {
                if demoMode, let rider = Backend.rider {
                    Annotation("Your position", coordinate: rider.coordinate, anchor: .center) { RiderDot() }
                        .annotationTitles(.hidden)
                }
                ForEach(store.stations) { station in
                    Annotation(station.name, coordinate: station.coordinate, anchor: .bottom) {
                        Button { select(station) } label: { StationPin(station: station, selected: station.id == selectedID) }
                            .buttonStyle(.plain)
                    }
                    .annotationTitles(.hidden)
                }
                if let destination {
                    Marker(destination.name, systemImage: "building.2.fill", coordinate: destination.coordinate)
                        .tint(Brand.blue)
                }
            }
            .mapStyle(.standard(elevation: .flat, emphasis: .muted, pointsOfInterest: .excludingAll))
            .mapControls {}
            .safeAreaInset(edge: .top) {
                SearchOverlay(search: search, focused: $searchFocused, stations: store.stations,
                              openStation: { station in
                                  searchFocused = false
                                  select(station)
                              },
                              choose: { completion in Task { await go(to: completion) } })
                    .padding(.horizontal, 12)
            }
            .safeAreaInset(edge: .bottom) {
                Group {
                    if let selected {
                        StationCard(station: selected, distance: destination?.distance(to: selected),
                                 dismiss: { selectedID = nil },
                                 open: { path.append(selected) })
                            .transition(.move(edge: .bottom).combined(with: .opacity))
                    } else {
                        StatusBar(destination: destination, clearDestination: clearDestination,
                                  settings: { showSettings = true })
                            .transition(.opacity)
                    }
                }
                .padding(.horizontal, 12)
                .opacity(searchFocused ? 0 : 1)
                .allowsHitTesting(!searchFocused)
                .animation(.easeOut(duration: 0.15), value: searchFocused)
            }
            // The keyboard covers the bottom controls instead of pushing them, and the map, upwards.
            .ignoresSafeArea(.keyboard)
            .navigationDestination(for: Station.self) { StationScreen(station: $0) }
            .toolbar(.hidden, for: .navigationBar)
            .sheet(isPresented: $showSettings) { SettingsSheet() }
        }
        // bikeslot://station/<id> opens a station directly, e.g. from a notification.
        .onOpenURL { url in
            if url.host == "station" { linkedStation = url.lastPathComponent }
        }
        // Launch argument `-openStation <id>` does the same without a confirmation prompt.
        .task { linkedStation = UserDefaults.standard.string(forKey: "openStation") }
        .onChange(of: store.stations) { openLinkedStation() }
        .onChange(of: linkedStation) { openLinkedStation() }
    }

    @State private var linkedStation: String?

    private func select(_ station: Station) {
        withAnimation(.snappy) {
            selectedID = station.id
            // With a rider on the map, show the way: the blue dot and the station together.
            if demoMode, let rider = Backend.rider {
                position = Self.region(around: [rider.coordinate, station.coordinate])
            } else {
                position = Self.camera(at: station.coordinate, distance: 700)
            }
        }
    }

    private func go(to completion: MKLocalSearchCompletion) async {
        searchFocused = false
        guard let place = await search.resolve(completion) else { return }
        search.query = ""
        destination = place
        withAnimation(.snappy) {
            // Suggest the closest station that still has room.
            selectedID = store.stations.filter { $0.free > 0 }.min { place.distance(to: $0) < place.distance(to: $1) }?.id
            position = framing(place)
        }
    }

    /// Shows the destination together with the stations within 3 km of it.
    private func framing(_ place: Destination) -> MapCameraPosition {
        let points = [place.coordinate] + store.stations.filter { place.distance(to: $0) < 3000 }.map(\.coordinate)
        guard points.count > 1 else { return Self.camera(at: place.coordinate, distance: 700) }
        return Self.region(around: points)
    }

    /// A region showing all the points, with room around them for the pins and the card.
    private static func region(around points: [CLLocationCoordinate2D]) -> MapCameraPosition {
        let lats = points.map(\.latitude), lons = points.map(\.longitude)
        let center = CLLocationCoordinate2D(latitude: (lats.min()! + lats.max()!) / 2,
                                            longitude: (lons.min()! + lons.max()!) / 2)
        let span = MKCoordinateSpan(latitudeDelta: (lats.max()! - lats.min()!) * 1.6 + 0.002,
                                    longitudeDelta: (lons.max()! - lons.min()!) * 1.6 + 0.002)
        return .region(MKCoordinateRegion(center: center, span: span))
    }

    private func clearDestination() {
        withAnimation(.snappy) {
            destination = nil
            position = Self.camera(at: Site.center, distance: 900)
        }
    }

    private func openLinkedStation() {
        guard let id = linkedStation, let station = store.stations.first(where: { $0.id == id }) else { return }
        linkedStation = nil
        path = [station]
    }
}

private struct StationPin: View {
    let station: Station
    let selected: Bool

    var body: some View {
        HStack(spacing: 5) {
            Image(systemName: "bicycle")
                .font(.caption.weight(.bold))
            Text(station.reporting ? "\(station.free)" : "–")
                .font(.subheadline.weight(.bold).monospacedDigit())
                .contentTransition(.numericText())
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .glassBackground(in: Capsule(), tint: station.availability.color, interactive: true)
        .contentShape(Capsule())
        .scaleEffect(selected ? 1.25 : 1, anchor: .bottom)
        .animation(.snappy, value: station.free)
        .animation(.snappy, value: selected)
    }
}

/// Small floating bar shown while no station is selected.
private struct StatusBar: View {
    @Environment(StationStore.self) private var store
    let destination: Destination?
    let clearDestination: () -> Void
    let settings: () -> Void

    var body: some View {
        GlassGroup {
            HStack(spacing: 8) {
                status
                Spacer()
                Button(action: settings) {
                    Image(systemName: "gearshape.fill")
                        .font(.body.weight(.semibold))
                        .foregroundStyle(.secondary)
                        .frame(width: 44, height: 44)
                        .glassBackground(in: Circle(), interactive: true)
                        .contentShape(Circle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Settings")
            }
        }
    }

    private var status: some View {
        HStack(spacing: 8) {
            if let error = store.errorMessage {
                Label(error, systemImage: "wifi.exclamationmark")
                    .foregroundStyle(.orange)
                    .lineLimit(1)
            } else if let destination {
                Label(destination.name, systemImage: "building.2.fill")
                    .foregroundStyle(Brand.blue)
                    .lineLimit(1)
                Button(action: clearDestination) { Image(systemName: "xmark.circle.fill") }
                    .buttonStyle(.plain)
                    .foregroundStyle(.secondary)
                    .accessibilityLabel("Clear destination")
            } else {
                Label("\(store.totalFree) free spots", systemImage: "bicycle")
                    .contentTransition(.numericText())
                    .animation(.snappy, value: store.totalFree)
            }
        }
        .font(.subheadline.weight(.semibold))
        .padding(.horizontal, 14)
        .frame(height: 44)
        .glassBackground(in: Capsule())
    }
}

/// Card for the tapped station. Pulling it down shrinks it; pulling the small card down dismisses it.
private struct StationCard: View {
    let station: Station
    var distance: CLLocationDistance?
    let dismiss: () -> Void
    let open: () -> Void

    @Environment(\.openURL) private var openURL
    @State private var expanded = true
    @State private var drag: CGFloat = 0

    private static let spring = Animation.bouncy(duration: 0.45, extraBounce: 0.12)
    private static let shape = RoundedRectangle(cornerRadius: 34, style: .continuous)

    private var free: String { station.reporting ? "\(station.free)" : "–" }

    var body: some View {
        VStack(spacing: 0) {
            Capsule()
                .fill(.tertiary)
                .frame(width: 36, height: 5)
                .padding(.top, 8)
                .padding(.bottom, expanded ? 12 : 8)
            if expanded {
                details.transition(.opacity)
            } else {
                compact.transition(.opacity)
            }
        }
        .padding(.horizontal, 20)
        .padding(.bottom, expanded ? 20 : 14)
        .frame(maxWidth: .infinity)
        .glassBackground(in: Self.shape)
        .contentShape(Self.shape)
        // Follows the finger downwards and resists being pulled up.
        .offset(y: drag > 0 ? drag : drag / 4)
        .gesture(DragGesture(minimumDistance: 8)
            .onChanged { drag = $0.translation.height }
            .onEnded { value in
                let pull = value.predictedEndTranslation.height
                withAnimation(Self.spring) {
                    drag = 0
                    if pull > 80 {
                        if expanded { expanded = false } else { dismiss() }
                    } else if pull < -60 {
                        expanded = true
                    }
                }
            })
        .onTapGesture {
            if !expanded { withAnimation(Self.spring) { expanded = true } }
        }
        .onChange(of: station.id) { withAnimation(Self.spring) { expanded = true } }
        .sensoryFeedback(.impact(weight: .light), trigger: expanded)
    }

    private var compact: some View {
        HStack(spacing: 12) {
            StationIcon(station: station, size: 40)
            VStack(alignment: .leading, spacing: 1) {
                Text(station.name)
                    .font(.headline)
                    .lineLimit(1)
                Text("\(free) of \(station.capacity) free")
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(.secondary)
                    .contentTransition(.numericText())
            }
            Spacer(minLength: 8)
            Button(action: open) {
                Image(systemName: "location.fill")
                    .font(.body.weight(.semibold))
                    .frame(width: 28, height: 28)
            }
            .prominentGlassButton()
            .buttonBorderShape(.circle)
            .tint(Brand.blue)
            .accessibilityLabel("3D Navigation")
        }
    }

    private var details: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 12) {
                StationIcon(station: station, size: 44)
                Text(station.name)
                    .font(.title3.weight(.bold))
                    .lineLimit(1)
                Spacer(minLength: 0)
            }

            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(free)
                    .font(.system(size: 34, weight: .bold, design: .rounded).monospacedDigit())
                    .foregroundStyle(station.availability.color)
                    .contentTransition(.numericText())
                Text("of \(station.capacity) spots free")
                    .font(.headline)
                    .foregroundStyle(.secondary)
                Spacer(minLength: 0)
                // Only after searching for a place.
                if let distance {
                    Text(Measurement(value: distance, unit: UnitLength.meters)
                        .formatted(.measurement(width: .abbreviated, usage: .road)))
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.secondary)
                }
            }
            .animation(.snappy, value: station.free)

            HStack(spacing: 10) {
                Button(action: open) {
                    Label("3D Navigation", systemImage: "location.fill")
                        .lineLimit(1)
                        .minimumScaleFactor(0.8)
                        .frame(maxWidth: .infinity)
                }
                .prominentGlassButton()
                .tint(Brand.blue)
                Button(action: directions) {
                    Label("Directions", systemImage: "bicycle")
                        .frame(maxWidth: .infinity)
                }
                .glassButton()
            }
            .font(.subheadline.weight(.semibold))
            .controlSize(.large)
        }
    }

    /// Cycling directions in Apple Maps.
    private func directions() {
        let c = station.coordinate
        if let url = URL(string: "https://maps.apple.com/directions?destination=\(c.latitude),\(c.longitude)&mode=cycling") {
            openURL(url)
        }
    }
}

private struct StationIcon: View {
    let station: Station
    let size: CGFloat

    var body: some View {
        Image(systemName: "bicycle")
            .font(.system(size: size * 0.42, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(station.availability.color.gradient, in: Circle())
    }
}

/// The rider's position, drawn like the location dot in Apple Maps: a blue dot in a white ring
/// with a breathing halo, and a beam towards where the rider is heading, east down the street.
private struct RiderDot: View {
    @State private var breathing = false

    var body: some View {
        ZStack {
            Circle()
                .fill(Brand.location.opacity(0.18))
                .frame(width: 56, height: 56)
                .scaleEffect(breathing ? 1 : 0.7)
            HeadingBeam()
                .fill(RadialGradient(colors: [Brand.location.opacity(0.55), Brand.location.opacity(0)],
                                     center: .center, startRadius: 6, endRadius: 34))
                .frame(width: 68, height: 68)
                .rotationEffect(.degrees(90))
            Circle()
                .fill(.white)
                .frame(width: 22, height: 22)
                .shadow(color: .black.opacity(0.25), radius: 3, y: 1)
            Circle()
                .fill(Brand.location)
                .frame(width: 15, height: 15)
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) { breathing = true }
        }
        .accessibilityElement()
        .accessibilityLabel("Your position")
    }
}

/// A wedge opening upwards from the centre; rotated, it points the way the rider is heading.
private struct HeadingBeam: Shape {
    func path(in rect: CGRect) -> Path {
        let centre = CGPoint(x: rect.midX, y: rect.midY)
        var path = Path()
        path.move(to: centre)
        path.addArc(center: centre, radius: rect.width / 2, startAngle: .degrees(-118), endAngle: .degrees(-62),
                    clockwise: false)
        path.closeSubpath()
        return path
    }
}

private struct SettingsSheet: View {
    @Environment(\.dismiss) private var dismiss
    @AppStorage("backendURL") private var backendURL = APIClient.defaultURL
    @AppStorage("demoMode") private var demoMode = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Toggle("Demo data", isOn: $demoMode)
                } footer: {
                    Text("Built-in sample stations that change every few seconds. No backend needed.")
                }
                Section {
                    TextField("Backend URL", text: $backendURL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                } footer: {
                    Text("This build uses \(APIClient.defaultURL). A backend on a Mac needs the iPhone on the same Wi-Fi, and Bike Slot needs Local Network access in iOS Settings.")
                }
                .disabled(demoMode)
                // The 3D view is built from OpenStreetMap data, whose licence (ODbL) asks for this credit.
                Section("Credits") {
                    Text("3D map data © OpenStreetMap contributors, under the Open Database License. Trees, cars and lamps by Kenney (CC0), drawn with three.js (MIT).")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    if #available(iOS 26, *) {
                        Button(role: .close) { dismiss() }
                    } else {
                        Button("Done") { dismiss() }
                    }
                }
            }
        }
        .presentationDetents([.medium])
    }
}
